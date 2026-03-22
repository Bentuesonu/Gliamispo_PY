import sqlite3
import threading
from contextlib import contextmanager
from gliamispo.models.project import Project


class DatabaseManager:
    def __init__(self, db_path):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row

    @contextmanager
    def _transaction(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def execute(self, sql, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def commit(self):
        with self._lock:
            self._conn.commit()

    def execute_script(self, sql):
        with self._lock:
            self._conn.executescript(sql)

    def leggi_progetti(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects").fetchall()
            return [Project(**dict(r)) for r in rows]

    @property
    def user_version(self):
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @user_version.setter
    def user_version(self, v):
        # FIX: il setter originale non acquisiva il lock
        with self._lock:
            self._conn.execute(f"PRAGMA user_version = {int(v)}")
            self._conn.commit()

    def column_missing(self, table, column):
        with self._lock:
            cols = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            return column not in [c["name"] for c in cols]

    def table_exists(self, table):
        with self._lock:
            r = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            return r is not None

    def get_low_confidence_elements(
        self, project_id: int, threshold: float = 0.60
    ) -> list:
        """
        Restituisce gli elementi AI con confidenza sotto soglia
        non ancora verificati dall'utente.

        Usato dalla UI per evidenziare elementi che necessitano revisione
        e dall'MLAnalyticsService per misurare la qualità del modello.

        Args:
            project_id: ID del progetto corrente.
            threshold:  Soglia di confidenza (default 0.60, come ml_min_confidence).

        Returns:
            Lista di sqlite3.Row con campi:
            id, element_name, category, ai_confidence, scene_id, scene_number
        """
        with self._lock:
            return self._conn.execute(
                """
                SELECT
                    se.id,
                    se.element_name,
                    se.category,
                    se.ai_confidence,
                    se.scene_id,
                    s.scene_number
                FROM scene_elements se
                JOIN scenes s ON s.id = se.scene_id
                WHERE s.project_id    = ?
                  AND se.ai_confidence < ?
                  AND se.user_verified  = 0
                  AND se.ai_suggested   = 1
                ORDER BY se.ai_confidence ASC
                """,
                (project_id, threshold),
            ).fetchall()

    def _get_setting(self, key: str):
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def get_setting(self, key: str):
        """Public wrapper for _get_setting (used by EmailDistributor)."""
        return self._get_setting(key)

    def populate_weather_forecast(self, call_sheet_id: int,
                                  lat: float, lon: float) -> bool:
        import urllib.request, json
        api_key = self._get_setting("openweather_api_key")
        if not api_key:
            return False
        url = (f"https://api.openweathermap.org/data/2.5/weather"
               f"?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=it")
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
                forecast = {
                    "temp":        data["main"]["temp"],
                    "description": data["weather"][0]["description"],
                    "icon":        data["weather"][0]["icon"],
                }
            with self._lock:
                self._conn.execute(
                    "UPDATE call_sheets SET weather_forecast=? WHERE id=?",
                    (json.dumps(forecast), call_sheet_id)
                )
                self._conn.commit()
            return True
        except Exception as e:
            print(f"[Weather] {e}")
            return False

    def get_cast_names_for_project(self, project_id: int) -> list[str]:
        with self._lock:
            rows = self._conn.execute('''
                SELECT DISTINCT se.element_name
                FROM scene_elements se JOIN scenes s ON s.id = se.scene_id
                WHERE s.project_id = ? AND se.category = 'Cast'
                ORDER BY se.element_name
            ''', (project_id,)).fetchall()
            return [r[0] for r in rows]

    def get_contact_availability_conflicts(
        self, project_id: int, shooting_day_date: int
    ) -> list:
        day_end = shooting_day_date + 86400
        with self._lock:
            return self._conn.execute('''
                SELECT c.full_name FROM contact_availability ca
                JOIN contacts c ON c.id = ca.contact_id
                WHERE c.project_id = ? AND ca.date_blocked BETWEEN ? AND ?
            ''', (project_id, shooting_day_date, day_end)).fetchall()

    def import_locations_from_scenes(self, project_id: int) -> int:
        with self._lock:
            names = self._conn.execute('''
                SELECT DISTINCT location FROM scenes
                WHERE project_id = ? AND location IS NOT NULL
            ''', (project_id,)).fetchall()
        count = 0
        for (name,) in names:
            if not self.execute(
                'SELECT id FROM locations WHERE project_id=? AND name=?',
                (project_id, name)
            ).fetchone():
                self.execute(
                    'INSERT INTO locations (project_id, name) VALUES (?,?)',
                    (project_id, name)
                )
                count += 1
        if count:
            with self._lock:
                self._conn.commit()
        return count

    def estimate_scene_cost(self, scene_id: int) -> float:
        with self._lock:
            cast_cost = self._conn.execute('''
                SELECT COALESCE(SUM(c.daily_rate), 0)
                FROM scene_elements se
                LEFT JOIN contacts c
                    ON c.full_name = se.element_name
                    AND c.project_id = (SELECT project_id FROM scenes WHERE id = ?)
                WHERE se.scene_id = ? AND se.category = 'Cast'
            ''', (scene_id, scene_id)).fetchone()[0]
            props_cost = self._conn.execute('''
                SELECT COALESCE(SUM(prop_cost), 0)
                FROM scene_elements
                WHERE scene_id = ? AND prop_cost IS NOT NULL
            ''', (scene_id,)).fetchone()[0]
        total = (cast_cost or 0) + (props_cost or 0)
        with self._lock:
            self._conn.execute(
                'UPDATE scenes SET estimated_cost=? WHERE id=?', (total, scene_id))
            self._conn.commit()
        return total

    def get_budget_templates(self) -> list:
        """Restituisce tutti i template di budget disponibili."""
        with self._lock:
            return self._conn.execute(
                "SELECT id, template_name, template_type, description "
                "FROM budget_templates ORDER BY id"
            ).fetchall()

    def generate_budget_from_template(
        self, project_id: int, template_id: int
    ) -> dict:
        """
        Genera il budget completo combinando template e elementi del breakdown.

        1. Crea i conti base dal template selezionato
        2. Copia le voci predefinite del template
        3. Aggiunge automaticamente le voci dagli elementi del breakdown

        Args:
            project_id: ID del progetto
            template_id: ID del template da usare

        Returns:
            dict con 'accounts', 'details', 'from_breakdown'
        """
        with self._lock:
            # Elimina budget esistente
            self._conn.execute(
                "DELETE FROM budget_accounts WHERE project_id = ?",
                (project_id,)
            )

            template_details_count = 0
            breakdown_details_count = 0

            # --- FASE 1: Conti e voci dal template ---
            template_accounts = self._conn.execute("""
                SELECT id, account_code, account_name, level, sort_order
                FROM budget_template_accounts
                WHERE template_id = ?
                ORDER BY sort_order
            """, (template_id,)).fetchall()

            # Mappa code -> account_id per associare elementi breakdown
            code_to_account = {}
            max_sort_order = 0

            for ta in template_accounts:
                ta_id, code, name, level, sort_order = ta
                cursor = self._conn.execute("""
                    INSERT INTO budget_accounts
                        (project_id, parent_id, account_code, account_name,
                         level, sort_order, subtotal)
                    VALUES (?, NULL, ?, ?, ?, ?, 0)
                """, (project_id, code, name, level, sort_order))
                acc_id = cursor.lastrowid
                code_to_account[code] = acc_id
                max_sort_order = max(max_sort_order, sort_order)

                # Copia voci predefinite dal template
                details = self._conn.execute("""
                    SELECT description, units, unit_type, rate, fringes_percent
                    FROM budget_template_details
                    WHERE template_account_id = ?
                    ORDER BY sort_order
                """, (ta_id,)).fetchall()

                for desc, units, unit_type, rate, fringes in details:
                    self._conn.execute("""
                        INSERT INTO budget_details
                            (account_id, description, units, unit_type,
                             rate, fringes_percent, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'Estimated')
                    """, (acc_id, desc, units, unit_type, rate, fringes))
                    template_details_count += 1

            # --- FASE 2: Elementi dal breakdown ---
            # Ottieni rate per categoria breakdown
            rates = {}
            rate_rows = self._conn.execute(
                "SELECT breakdown_category, budget_account_code, budget_account_name, "
                "default_rate, default_unit_type, default_fringes_percent "
                "FROM budget_category_rates"
            ).fetchall()
            for r in rate_rows:
                rates[r[0]] = {
                    'code': r[1], 'name': r[2],
                    'rate': r[3], 'unit_type': r[4], 'fringes': r[5]
                }

            # Ottieni elementi del breakdown raggruppati
            elements = self._conn.execute("""
                SELECT
                    se.category,
                    se.element_name,
                    SUM(se.quantity) as total_qty,
                    COUNT(DISTINCT se.scene_id) as scene_count
                FROM scene_elements se
                JOIN scenes s ON se.scene_id = s.id
                WHERE s.project_id = ?
                GROUP BY se.category, se.element_name
                ORDER BY se.category, se.element_name
            """, (project_id,)).fetchall()

            # Raggruppa per categoria
            from collections import defaultdict
            by_category = defaultdict(list)
            for cat, name, qty, scenes in elements:
                by_category[cat].append({
                    'name': name,
                    'quantity': qty or 1,
                    'scenes': scenes
                })

            # Aggiungi voci dal breakdown
            for category, items in by_category.items():
                rate_info = rates.get(category, {
                    'code': '999', 'name': category,
                    'rate': 100, 'unit_type': 'flat', 'fringes': 0
                })

                # Cerca conto esistente o creane uno nuovo
                acc_id = code_to_account.get(rate_info['code'])
                if not acc_id:
                    max_sort_order += 1
                    cursor = self._conn.execute("""
                        INSERT INTO budget_accounts
                            (project_id, account_code, account_name,
                             level, sort_order, subtotal)
                        VALUES (?, ?, ?, 1, ?, 0)
                    """, (project_id, rate_info['code'], rate_info['name'],
                          max_sort_order))
                    acc_id = cursor.lastrowid
                    code_to_account[rate_info['code']] = acc_id

                # Aggiungi voci per ogni elemento
                for item in items:
                    units = item['scenes']
                    rate = rate_info['rate']
                    fringes = rate_info['fringes']
                    unit_type = rate_info['unit_type']

                    # Per elementi con quantità > 1, moltiplica
                    if item['quantity'] > 1:
                        units = units * item['quantity']

                    self._conn.execute("""
                        INSERT INTO budget_details
                            (account_id, description, units, unit_type,
                             rate, fringes_percent, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, 'Estimated', 'Da breakdown')
                    """, (acc_id, item['name'], units, unit_type, rate, fringes))
                    breakdown_details_count += 1

            # --- FASE 3: Ricalcola subtotal per tutti i conti ---
            for acc_id in code_to_account.values():
                self._conn.execute("""
                    UPDATE budget_accounts SET subtotal = (
                        SELECT COALESCE(SUM(rate * units * (1 + fringes_percent/100.0)), 0)
                        FROM budget_details WHERE account_id = ?
                    ) WHERE id = ?
                """, (acc_id, acc_id))

            self._conn.commit()
            return {
                'accounts': len(code_to_account),
                'details': template_details_count + breakdown_details_count,
                'from_breakdown': breakdown_details_count
            }

    def get_budget_category_rates(self):
        """Restituisce i costi predefiniti per categoria."""
        with self._lock:
            return self._conn.execute(
                "SELECT breakdown_category, budget_account_code, budget_account_name, "
                "default_rate, default_unit_type, default_fringes_percent "
                "FROM budget_category_rates ORDER BY budget_account_code"
            ).fetchall()

    def update_budget_category_rate(
        self, category: str, rate: float, unit_type: str = None
    ):
        """Aggiorna il costo predefinito per una categoria."""
        with self._lock:
            if unit_type:
                self._conn.execute(
                    "UPDATE budget_category_rates SET default_rate = ?, "
                    "default_unit_type = ? WHERE breakdown_category = ?",
                    (rate, unit_type, category)
                )
            else:
                self._conn.execute(
                    "UPDATE budget_category_rates SET default_rate = ? "
                    "WHERE breakdown_category = ?",
                    (rate, category)
                )
            self._conn.commit()

    def close(self):
        self._conn.close()