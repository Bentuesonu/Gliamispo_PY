import time


MIGRATIONS = {}


def _register(version):
    def decorator(fn):
        MIGRATIONS[version] = fn
        return fn
    return decorator


def column_missing(conn, table, column):
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return column not in [c[1] for c in cols]


def table_exists(conn, table):
    r = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return r is not None


def run_migrations(conn):
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in sorted(MIGRATIONS.keys()):
        if current < version:
            MIGRATIONS[version](conn)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()


# ---- V2 ----
@_register(2)
def _v2(conn):
    if column_missing(conn, "scenes", "requires_intimacy_coordinator"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN "
            "requires_intimacy_coordinator INTEGER DEFAULT 0"
        )


# ---- V3 ----
@_register(3)
def _v3(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS shooting_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            schedule_name TEXT NOT NULL DEFAULT 'Piano di Lavorazione',
            total_days INTEGER, start_date TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            last_modified INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS shooting_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            day_number INTEGER NOT NULL, shoot_date TEXT,
            call_time TEXT DEFAULT '07:00', wrap_time TEXT DEFAULT '19:00',
            location_primary TEXT, notes TEXT,
            FOREIGN KEY (schedule_id)
                REFERENCES shooting_schedules(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS shooting_day_scenes (
            shooting_day_id INTEGER NOT NULL,
            scene_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            estimated_duration_minutes INTEGER,
            PRIMARY KEY (shooting_day_id, scene_id),
            FOREIGN KEY (shooting_day_id)
                REFERENCES shooting_days(id) ON DELETE CASCADE,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );
    """)
    if column_missing(conn, "scenes", "estimated_crew_size"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN estimated_crew_size INTEGER"
        )
    if column_missing(conn, "scenes", "special_requirements"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN special_requirements TEXT"
        )


# ---- V4 ----
@_register(4)
def _v4(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS intimacy_protocols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            coordinator_name TEXT, coordinator_contact TEXT,
            consent_form_signed INTEGER DEFAULT 0,
            closed_set_required INTEGER DEFAULT 1,
            rehearsal_scheduled TEXT, rehearsal_completed INTEGER DEFAULT 0,
            specific_notes TEXT, contact_boundaries TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS budget_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT DEFAULT 'Cortometraggio',
            language TEXT DEFAULT 'it', currency TEXT DEFAULT 'EUR',
            description TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS budget_template_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            parent_id INTEGER, account_code TEXT,
            account_name TEXT NOT NULL,
            level INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0,
            default_rate REAL, default_unit_type TEXT,
            default_fringes_percent REAL DEFAULT 0,
            FOREIGN KEY (template_id)
                REFERENCES budget_templates(id) ON DELETE CASCADE
        );
    """)
    if column_missing(conn, "projects", "total_budget"):
        conn.execute("ALTER TABLE projects ADD COLUMN total_budget REAL")
    if column_missing(conn, "projects", "contingency_percent"):
        conn.execute(
            "ALTER TABLE projects ADD COLUMN "
            "contingency_percent REAL DEFAULT 10.0"
        )


# ---- V5 ----
@_register(5)
def _v5(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS call_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shooting_day_id INTEGER NOT NULL,
            generated_at INTEGER DEFAULT (strftime('%s','now')),
            pdf_path TEXT, crew_call TEXT DEFAULT '07:00',
            general_notes TEXT, weather_forecast TEXT,
            FOREIGN KEY (shooting_day_id)
                REFERENCES shooting_days(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS call_sheet_cast (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sheet_id INTEGER NOT NULL,
            actor_name TEXT NOT NULL, character_name TEXT,
            call_time TEXT NOT NULL, pickup_location TEXT,
            notes TEXT, makeup_call TEXT, wardrobe_call TEXT,
            FOREIGN KEY (call_sheet_id)
                REFERENCES call_sheets(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS call_sheet_crew (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sheet_id INTEGER NOT NULL,
            crew_member_name TEXT NOT NULL, department TEXT,
            call_time TEXT NOT NULL, contact TEXT,
            FOREIGN KEY (call_sheet_id)
                REFERENCES call_sheets(id) ON DELETE CASCADE
        );
    """)


# ---- V6 (12 step) ----
@_register(6)
def _v6(conn):
    # Step 1-2: colonne ML a projects e scene_elements
    if column_missing(conn, "projects", "ml_enabled"):
        conn.execute(
            "ALTER TABLE projects ADD COLUMN ml_enabled INTEGER DEFAULT 1"
        )
    if column_missing(conn, "projects", "ml_min_confidence"):
        conn.execute(
            "ALTER TABLE projects ADD COLUMN "
            "ml_min_confidence REAL DEFAULT 0.60"
        )
    se_cols = [
        ("ai_model_version", "TEXT DEFAULT 'v0.0.0'"),
        ("detection_method", "TEXT DEFAULT 'vocabulary'"),
        ("user_modified", "INTEGER DEFAULT 0"),
        ("original_category", "TEXT"),
        ("modified_at", "INTEGER"),
        ("created_at", "INTEGER DEFAULT (strftime('%s','now'))"),
    ]
    for col, typedef in se_cols:
        if column_missing(conn, "scene_elements", col):
            conn.execute(
                f"ALTER TABLE scene_elements ADD COLUMN {col} {typedef}"
            )

    # Step 3: colonne parser a scenes
    for col, typedef in [
        ("parser_used", "TEXT"),
        ("parser_confidence", "REAL"),
        ("parsed_at", "INTEGER"),
    ]:
        if column_missing(conn, "scenes", col):
            conn.execute(
                f"ALTER TABLE scenes ADD COLUMN {col} {typedef}"
            )

    # Step 4: tabelle ML
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ml_model_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL, version TEXT NOT NULL,
            model_path TEXT NOT NULL, trained_on INTEGER NOT NULL,
            training_dataset_size INTEGER, training_duration_seconds REAL,
            accuracy REAL, precision REAL, recall REAL, f1_score REAL,
            category_metrics TEXT, confusion_matrix TEXT,
            is_active INTEGER DEFAULT 0, is_baseline INTEGER DEFAULT 0,
            training_notes TEXT,
            UNIQUE(model_name, version)
        );
        CREATE TABLE IF NOT EXISTS training_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER,
            scene_text TEXT, scene_context TEXT,
            detected_elements TEXT, user_corrections TEXT,
            correction_type TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            user_id TEXT,
            used_for_training INTEGER DEFAULT 0,
            used_in_model_version TEXT,
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS user_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element_id INTEGER, scene_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_category TEXT, after_category TEXT,
            before_name TEXT, after_name TEXT,
            before_quantity INTEGER, after_quantity INTEGER,
            original_confidence REAL, original_model_version TEXT,
            corrected_at INTEGER DEFAULT (strftime('%s','now')),
            session_id TEXT, trained_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS vocabulary_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL UNIQUE, canonical_form TEXT NOT NULL,
            category TEXT NOT NULL,
            source TEXT NOT NULL
                CHECK(source IN ('BUILTIN', 'USER_ADDED', 'ML_LEARNED')),
            learned_from_corrections INTEGER DEFAULT 0,
            base_confidence REAL DEFAULT 0.70,
            added_at INTEGER DEFAULT (strftime('%s','now')),
            last_used INTEGER, usage_count INTEGER DEFAULT 0,
            language TEXT DEFAULT 'it'
        );
        CREATE TABLE IF NOT EXISTS element_confidence_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element_id INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            detection_method TEXT,
            recorded_at INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (element_id)
                REFERENCES scene_elements(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS multiword_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_text TEXT NOT NULL, category TEXT NOT NULL,
            co_occurrence_score REAL, frequency INTEGER DEFAULT 1,
            source TEXT CHECK(source IN ('BUILTIN', 'LEARNED')),
            learned_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(entity_text, category)
        );
        CREATE TABLE IF NOT EXISTS ml_performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version_id INTEGER NOT NULL,
            period_start INTEGER NOT NULL, period_end INTEGER NOT NULL,
            total_predictions INTEGER DEFAULT 0,
            correct_predictions INTEGER DEFAULT 0,
            false_positives INTEGER DEFAULT 0,
            false_negatives INTEGER DEFAULT 0,
            category_stats TEXT,
            accuracy REAL GENERATED ALWAYS AS (
                CASE WHEN total_predictions > 0
                THEN CAST(correct_predictions AS REAL) / total_predictions
                ELSE 0.0 END
            ) STORED,
            FOREIGN KEY (model_version_id)
                REFERENCES ml_model_versions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ai_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            context_type TEXT, context_value TEXT,
            suggested_element TEXT, frequency INTEGER DEFAULT 1,
            last_used INTEGER,
            UNIQUE(context_type, context_value, suggested_element)
        );
    """)

    # Step 5: migrazione eighths
    old_count = conn.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
    if old_count > 0:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes_backup_v5 AS
            SELECT * FROM scenes
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenes_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            scene_number TEXT, location TEXT,
            int_ext TEXT NOT NULL CHECK(int_ext IN ('INT','EXT','INT/EXT')),
            day_night TEXT NOT NULL
                CHECK(day_night IN
                    ('GIORNO','NOTTE','ALBA','TRAMONTO','CONTINUO')),
            page_start_whole INTEGER NOT NULL DEFAULT 1,
            page_start_eighths INTEGER NOT NULL DEFAULT 0
                CHECK(page_start_eighths >= 0 AND page_start_eighths < 8),
            page_end_whole INTEGER NOT NULL DEFAULT 1,
            page_end_eighths INTEGER NOT NULL DEFAULT 0
                CHECK(page_end_eighths >= 0 AND page_end_eighths < 8),
            page_start_decimal REAL GENERATED ALWAYS AS
                (page_start_whole + page_start_eighths / 8.0) STORED,
            page_end_decimal REAL GENERATED ALWAYS AS
                (page_end_whole + page_end_eighths / 8.0) STORED,
            synopsis TEXT, story_day INTEGER DEFAULT 1,
            requires_intimacy_coordinator INTEGER DEFAULT 0,
            estimated_crew_size INTEGER,
            special_requirements TEXT,
            parser_used TEXT, parser_confidence REAL, parsed_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            CHECK((page_end_whole > page_start_whole) OR
                  (page_end_whole = page_start_whole
                   AND page_end_eighths >= page_start_eighths)),
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    if old_count > 0:
        conn.execute("""
            INSERT INTO scenes_new (
                id, project_id, scene_number, location,
                int_ext, day_night,
                page_start_whole, page_start_eighths,
                page_end_whole, page_end_eighths,
                synopsis, story_day,
                requires_intimacy_coordinator,
                estimated_crew_size, special_requirements,
                parser_used, parser_confidence, parsed_at,
                created_at
            )
            SELECT
                id, project_id, scene_number, location,
                int_ext, day_night,
                CAST(page_start AS INTEGER),
                MIN(7, CAST(((page_start - CAST(page_start AS INTEGER))
                    * 8) + 0.5 AS INTEGER)),
                CAST(page_end AS INTEGER),
                MIN(7, CAST(((page_end - CAST(page_end AS INTEGER))
                    * 8) + 0.5 AS INTEGER)),
                synopsis, story_day,
                COALESCE(requires_intimacy_coordinator, 0),
                estimated_crew_size, special_requirements,
                parser_used, parser_confidence, parsed_at,
                created_at
            FROM scenes
        """)
        new_count = conn.execute(
            "SELECT COUNT(*) FROM scenes_new"
        ).fetchone()[0]
        if old_count != new_count:
            conn.execute("DROP TABLE scenes_new")
            raise RuntimeError(
                f"V6 step 5: conteggio non corrispondente "
                f"({old_count} vs {new_count})"
            )

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TRIGGER IF EXISTS update_project_stats_insert")
    conn.execute("DROP TRIGGER IF EXISTS update_project_stats_verify")
    conn.execute("DROP TABLE IF EXISTS scenes")
    conn.execute("ALTER TABLE scenes_new RENAME TO scenes")
    conn.execute("PRAGMA foreign_keys = ON")

    # Step 6: indici ML
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_elements_scene
            ON scene_elements(scene_id);
        CREATE INDEX IF NOT EXISTS idx_elements_category
            ON scene_elements(category);
        CREATE INDEX IF NOT EXISTS idx_elements_confidence
            ON scene_elements(ai_confidence);
        CREATE INDEX IF NOT EXISTS idx_confidence_history_element
            ON element_confidence_history(element_id);
        CREATE INDEX IF NOT EXISTS idx_training_data_scene
            ON training_data(scene_id);
        CREATE INDEX IF NOT EXISTS idx_vocabulary_category
            ON vocabulary_terms(category);
        CREATE INDEX IF NOT EXISTS idx_vocabulary_term
            ON vocabulary_terms(term);
        CREATE INDEX IF NOT EXISTS idx_multiword_category
            ON multiword_entities(category);
    """)

    # Step 7: popolaBaselineTrainingData
    conn.execute("""
        INSERT INTO training_data (scene_id, scene_text, created_at)
        SELECT id, synopsis, strftime('%s','now')
        FROM scenes
        WHERE synopsis IS NOT NULL AND synopsis != ''
        AND NOT EXISTS (
            SELECT 1 FROM training_data td WHERE td.scene_id = scenes.id
        )
    """)

    # Step 8: creaBaselineMLModel
    now = int(time.time())
    conn.execute("""
        INSERT OR IGNORE INTO ml_model_versions
            (model_name, version, model_path, trained_on,
             is_active, is_baseline)
        VALUES ('baseline', 'v1.0.0', 'builtin', ?, 1, 1)
    """, (now,))

    # Step 9: project_stats con trigger gruppo B
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_stats (
            project_id INTEGER PRIMARY KEY,
            total_scenes INTEGER DEFAULT 0,
            total_elements INTEGER DEFAULT 0,
            ml_detected_elements INTEGER DEFAULT 0,
            user_verified_elements INTEGER DEFAULT 0,
            avg_confidence REAL DEFAULT 0.0,
            last_updated INTEGER,
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS update_project_stats_insert
        AFTER INSERT ON scene_elements
        BEGIN
            INSERT INTO project_stats (project_id, total_elements,
                ml_detected_elements, last_updated)
            SELECT s.project_id, 1,
                CASE WHEN NEW.ai_suggested = 1 THEN 1 ELSE 0 END,
                strftime('%s','now')
            FROM scenes s WHERE s.id = NEW.scene_id
            ON CONFLICT(project_id) DO UPDATE SET
                total_elements = total_elements + 1,
                ml_detected_elements = ml_detected_elements +
                    (CASE WHEN NEW.ai_suggested = 1 THEN 1 ELSE 0 END),
                last_updated = strftime('%s','now');
        END;

        CREATE TRIGGER IF NOT EXISTS update_project_stats_verify
        AFTER UPDATE OF user_verified ON scene_elements
        WHEN NEW.user_verified = 1 AND OLD.user_verified = 0
        BEGIN
            UPDATE project_stats SET
                user_verified_elements = user_verified_elements + 1,
                last_updated = strftime('%s','now')
            WHERE project_id = (
                SELECT project_id FROM scenes WHERE id = NEW.scene_id
            );
        END;
    """)

    # Step 10: enhanceSceneElementsConstraints
    old_elem_count = conn.execute(
        "SELECT COUNT(*) FROM scene_elements"
    ).fetchone()[0]

    conn.execute("""
        CREATE TABLE scene_elements_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            category TEXT NOT NULL CHECK(category IN (
                'Cast','Extras','Stunts','Intimacy','Vehicles','Props',
                'Special FX','Wardrobe','Makeup','Livestock',
                'Animal Handlers','Music','Sound','Set Dressing',
                'Greenery','Special Equipment','Security',
                'Additional Labor','VFX','Mechanical FX','Notes'
            )),
            element_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1 CHECK(quantity > 0),
            notes TEXT,
            ai_suggested INTEGER DEFAULT 0,
            ai_confidence REAL CHECK(ai_confidence IS NULL OR
                (ai_confidence >= 0.0 AND ai_confidence <= 1.0)),
            ai_model_version TEXT DEFAULT 'v0.0.0',
            detection_method TEXT DEFAULT 'vocabulary',
            user_verified INTEGER DEFAULT 0,
            user_modified INTEGER DEFAULT 0,
            original_category TEXT,
            modified_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(scene_id, category, element_name),
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        INSERT INTO scene_elements_new (
            id, scene_id, category, element_name, quantity, notes,
            ai_suggested, ai_confidence, ai_model_version,
            detection_method, user_verified, user_modified,
            original_category, modified_at, created_at
        )
        SELECT
            id, scene_id, category, element_name, quantity, notes,
            COALESCE(ai_suggested, 0),
            ai_confidence,
            COALESCE(ai_model_version, 'v0.0.0'),
            COALESCE(detection_method, 'vocabulary'),
            COALESCE(user_verified, 0),
            COALESCE(user_modified, 0),
            original_category, modified_at, created_at
        FROM scene_elements
    """)

    new_elem_count = conn.execute(
        "SELECT COUNT(*) FROM scene_elements_new"
    ).fetchone()[0]
    if old_elem_count != new_elem_count:
        conn.execute("DROP TABLE scene_elements_new")
        raise RuntimeError(
            f"V6 step 10: conteggio non corrispondente "
            f"({old_elem_count} vs {new_elem_count})"
        )

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE scene_elements")
    conn.execute(
        "ALTER TABLE scene_elements_new RENAME TO scene_elements"
    )
    conn.execute("PRAGMA foreign_keys = ON")

    # Ricrea indici su scene_elements dopo RENAME
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_elements_scene
            ON scene_elements(scene_id);
        CREATE INDEX IF NOT EXISTS idx_elements_category
            ON scene_elements(category);
        CREATE INDEX IF NOT EXISTS idx_elements_confidence
            ON scene_elements(ai_confidence);
    """)

    # Step 11: trigger gruppo C
    conn.executescript("""
        DROP TRIGGER IF EXISTS track_confidence_on_insert;
        CREATE TRIGGER track_confidence_on_insert
        AFTER INSERT ON scene_elements
        WHEN NEW.ai_confidence IS NOT NULL
        BEGIN
            INSERT INTO element_confidence_history
                (element_id, model_version, confidence_score,
                 detection_method)
            VALUES (
                NEW.id,
                COALESCE(NEW.ai_model_version, 'unknown'),
                NEW.ai_confidence,
                COALESCE(NEW.detection_method, 'NER')
            );
        END;

        DROP TRIGGER IF EXISTS track_confidence_on_update;
        CREATE TRIGGER track_confidence_on_update
        AFTER UPDATE OF ai_confidence ON scene_elements
        WHEN NEW.ai_confidence != OLD.ai_confidence
            AND NEW.ai_confidence IS NOT NULL
        BEGIN
            INSERT INTO element_confidence_history
                (element_id, model_version, confidence_score,
                 detection_method)
            VALUES (
                NEW.id,
                COALESCE(NEW.ai_model_version, 'unknown'),
                NEW.ai_confidence,
                COALESCE(NEW.detection_method, 'Updated')
            );
        END;
    """)


# ---- V7 ----
@_register(7)
def _v7(conn):
    v7_cols = [
        ("ai_model_version", "TEXT DEFAULT 'v0.0.0'"),
        ("detection_method", "TEXT DEFAULT 'vocabulary'"),
        ("user_modified", "INTEGER DEFAULT 0"),
        ("original_category", "TEXT"),
        ("modified_at", "INTEGER"),
        ("created_at", "INTEGER DEFAULT (strftime('%s','now'))"),
    ]
    for col, typedef in v7_cols:
        if column_missing(conn, "scene_elements", col):
            conn.execute(
                f"ALTER TABLE scene_elements ADD COLUMN {col} {typedef}"
            )
    conn.execute("""
        UPDATE scene_elements SET
            ai_model_version = COALESCE(ai_model_version, 'v0.0.0'),
            detection_method = COALESCE(detection_method, 'vocabulary'),
            user_modified = COALESCE(user_modified, 0)
        WHERE ai_model_version IS NULL
           OR detection_method IS NULL
           OR user_modified IS NULL
    """)


# ---- V8 ----
@_register(8)
def _v8(conn):
    if column_missing(conn, "scenes", "manual_shooting_hours"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN "
            "manual_shooting_hours REAL DEFAULT 0.0"
        )


# ---- V9 ----
@_register(9)
def _v9(conn):
    if column_missing(conn, "projects", "hours_per_shooting_day"):
        conn.execute(
            "ALTER TABLE projects ADD COLUMN "
            "hours_per_shooting_day REAL DEFAULT 10.0"
        )
    if column_missing(conn, "scenes", "is_locked"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN is_locked INTEGER DEFAULT 0"
        )


# ---- V10 ----
@_register(10)
def _v10(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_corrections_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element_id INTEGER,
            scene_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            before_category TEXT, after_category TEXT,
            before_name TEXT, after_name TEXT,
            before_quantity INTEGER, after_quantity INTEGER,
            original_confidence REAL, original_model_version TEXT,
            corrected_at INTEGER DEFAULT (strftime('%s','now')),
            session_id TEXT, trained_at INTEGER
        )
    """)
    if table_exists(conn, "user_corrections"):
        conn.execute("""
            INSERT INTO user_corrections_new
            SELECT * FROM user_corrections
        """)
        conn.execute("DROP TABLE user_corrections")
    conn.execute(
        "ALTER TABLE user_corrections_new "
        "RENAME TO user_corrections"
    )
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_corrections_timeline
            ON user_corrections(corrected_at);
        CREATE INDEX IF NOT EXISTS idx_corrections_action
            ON user_corrections(action);
        CREATE INDEX IF NOT EXISTS idx_corrections_scene
            ON user_corrections(scene_id);
        CREATE INDEX IF NOT EXISTS idx_corrections_model
            ON user_corrections(original_model_version);
    """)


# ---- V11 : seeding vocabolario italiano predefinito ----

@_register(11)
def _v11(conn):
    VOCAB = [
        # Props
        ('pistola','pistola','Props'),('fucile','fucile','Props'),
        ('coltello','coltello','Props'),('spada','spada','Props'),
        ('borsa','borsa','Props'),('valigia','valigia','Props'),
        ('telefono','telefono','Props'),('cellulare','cellulare','Props'),
        ('libro','libro','Props'),('giornale','giornale','Props'),
        ('bicchiere','bicchiere','Props'),('bottiglia','bottiglia','Props'),
        ('chiave','chiave','Props'),('documento','documento','Props'),
        ('fotografia','fotografia','Props'),('mappa','mappa','Props'),
        ('lettera','lettera','Props'),('busta','busta','Props'),
        ('orologio','orologio','Props'),('anello','anello','Props'),
        ('sigaretta','sigaretta','Props'),('accendino','accendino','Props'),
        ('valigetta','valigetta','Props'),('zaino','zaino','Props'),
        ('portafoglio','portafoglio','Props'),
        # Vehicles
        ('auto','automobile','Vehicles'),('automobile','automobile','Vehicles'),
        ('macchina','automobile','Vehicles'),('camion','camion','Vehicles'),
        ('moto','motocicletta','Vehicles'),('motocicletta','motocicletta','Vehicles'),
        ('furgone','furgone','Vehicles'),('ambulanza','ambulanza','Vehicles'),
        ('taxi','taxi','Vehicles'),('autobus','autobus','Vehicles'),
        ('treno','treno','Vehicles'),('barca','barca','Vehicles'),
        ('elicottero','elicottero','Vehicles'),('aereo','aereo','Vehicles'),
        # Special FX
        ('esplosione','esplosione','Special FX'),('fuoco','fuoco','Special FX'),
        ('fiamme','fiamme','Special FX'),('sangue','sangue','Special FX'),
        ('pioggia artificiale','pioggia','Special FX'),
        ('fumo','fumo','Special FX'),('nebbia','nebbia','Special FX'),
        ('neve artificiale','neve','Special FX'),
        # Wardrobe
        ('costume','costume','Wardrobe'),('uniforme','uniforme','Wardrobe'),
        ('abito','abito','Wardrobe'),('vestito','vestito','Wardrobe'),
        ('giacca','giacca','Wardrobe'),('impermeabile','impermeabile','Wardrobe'),
        # Makeup
        ('trucco','trucco','Makeup'),('parrucca','parrucca','Makeup'),
        ('protesi','protesi','Makeup'),('maschera','maschera','Makeup'),
        ('cicatrice','cicatrice','Makeup'),('ferita','ferita','Makeup'),
        # Set Dressing
        ('tavolo','tavolo','Set Dressing'),('sedia','sedia','Set Dressing'),
        ('letto','letto','Set Dressing'),('divano','divano','Set Dressing'),
        ('lampada','lampada','Set Dressing'),('specchio','specchio','Set Dressing'),
        ('quadro','quadro','Set Dressing'),('tenda','tenda','Set Dressing'),
        # Animals
        ('cavallo','cavallo','Livestock'),('cane','cane','Livestock'),
        ('gatto','gatto','Livestock'),('uccello','uccello','Livestock'),
        # Stunts
        ('rissa','rissa','Stunts'),('combattimento','combattimento','Stunts'),
        ('caduta','caduta','Stunts'),('inseguimento','inseguimento','Stunts'),
        ('sparatoria','sparatoria','Stunts'),
        # Music / Sound
        ('musica','musica','Music'),('chitarra','chitarra','Music'),
        ('pianoforte','pianoforte','Music'),('violino','violino','Music'),
        ('microfono','microfono','Sound'),
        # VFX
        ('CGI','CGI','VFX'),('effetto visivo','effetto visivo','VFX'),
        ('green screen','green screen','VFX'),
        # Special Equipment
        ('gru','gru','Special Equipment'),('steadicam','steadicam','Special Equipment'),
        ('drone','drone','Special Equipment'),('jib','jib','Special Equipment'),
    ]
    for term, canonical, category in VOCAB:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO vocabulary_terms'
                ' (term, canonical_form, category, source)'
                ' VALUES (?, ?, ?, ?)',
                (term, canonical, category, 'BUILTIN')
            )
        except Exception:
            pass


# ---- V12 : schedule_entries (tabella leggera per lo stripboard) ----

@_register(12)
def _v12(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS schedule_entries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id   INTEGER NOT NULL,
            scene_id     INTEGER NOT NULL,
            shooting_day INTEGER NOT NULL,
            position     INTEGER NOT NULL DEFAULT 0,
            UNIQUE(project_id, scene_id),
            FOREIGN KEY (project_id)
                REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (scene_id)
                REFERENCES scenes(id)   ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_schedule_project_day
            ON schedule_entries(project_id, shooting_day);
    ''')


# ---- V14 : raw_blocks (testo strutturato Fountain per scena) ----

@_register(14)
def _v14(conn):
    if column_missing(conn, "scenes", "raw_blocks"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN raw_blocks TEXT"
        )


# ---- V15 : scene_notes — note libere per scena ----
@_register(15)
def _v15(conn):
    if column_missing(conn, "scenes", "scene_notes"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN scene_notes TEXT"
        )


# ---- V13 : rejected_elements (blacklist per elementi eliminati) ----

@_register(13)
def _v13(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS rejected_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            element_name TEXT NOT NULL,
            category TEXT,
            scene_id INTEGER,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_rejected_name
            ON rejected_elements(element_name);
    ''')
