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


# ---- V16 : campi per ODG professionale ----

@_register(16)
def _v16(conn):
    """Aggiunge campi per ODG professionale."""
    cols = [
        ("production_logo_path",   "TEXT"),
        ("director_signature_path", "TEXT"),
        ("next_day_preview",        "TEXT"),  # JSON scene giorno dopo
        ("distribution_log",        "TEXT"),  # JSON log invii email
    ]
    for col, typedef in cols:
        if column_missing(conn, "call_sheets", col):
            conn.execute(
                f"ALTER TABLE call_sheets ADD COLUMN {col} {typedef}"
            )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cs_cast_pickup"
        " ON call_sheet_cast(call_sheet_id)"
    )


# ---- V17 : script revisions (Hollywood color system) ----

@_register(17)
def _v17(conn):
    """Sistema revisioni sceneggiatura standard Hollywood."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS script_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            revision_number INTEGER NOT NULL DEFAULT 1,
            revision_color TEXT NOT NULL DEFAULT 'white',
            imported_at INTEGER DEFAULT (strftime('%s','now')),
            notes TEXT,
            file_path TEXT,
            is_current INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS revision_scene_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER NOT NULL,
            scene_number TEXT NOT NULL,
            change_type TEXT NOT NULL,
            diff_summary TEXT,
            FOREIGN KEY (revision_id) REFERENCES script_revisions(id) ON DELETE CASCADE
        )
    """)
    if column_missing(conn, "scenes", "revision_id"):
        conn.execute("ALTER TABLE scenes ADD COLUMN revision_id INTEGER")
    if column_missing(conn, "scenes", "revision_badge"):
        conn.execute("ALTER TABLE scenes ADD COLUMN revision_badge TEXT")
        
# ---- V18 : FTS5 full-text search (Feature 1.5) ----
 
@_register(18)
def _v18(conn):
    """
    Indice FTS5 per ricerca full-text su scene ed elementi.
 
    Crea:
      - Tabella virtuale  search_index (FTS5, tokenizer unicode61)
      - Trigger           fts_scene_insert  — dopo INSERT su scenes
      - Trigger           fts_scene_update  — dopo UPDATE su scenes
      - Trigger           fts_scene_delete  — dopo DELETE su scenes
      - Trigger           fts_element_insert — dopo INSERT su scene_elements
      - Tabella           settings  (key/value, necessaria a _get_setting)
 
    Popola l'indice con i dati già presenti nel DB.
    """
 
    # 1. Tabella settings (serve a populate_weather_forecast e ad altre
    #    funzionalità future; non esisteva in nessuna migrazione precedente)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
 
    # 2. Tabella virtuale FTS5
    #    Nota: content_type, content_id e text sono indicizzati;
    #          project_id è UNINDEXED (usato solo come filtro WHERE).
    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index
        USING fts5(
            content_type,
            content_id,
            project_id UNINDEXED,
            text,
            tokenize = "unicode61"
        );
    """)
 
    # 3. Trigger su scenes
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS fts_scene_insert
        AFTER INSERT ON scenes
        BEGIN
            INSERT INTO search_index(content_type, content_id, project_id, text)
            VALUES(
                'scene',
                NEW.id,
                NEW.project_id,
                COALESCE(NEW.scene_number, '')
                || ' ' || COALESCE(NEW.location, '')
                || ' ' || COALESCE(NEW.synopsis,  '')
            );
        END;
 
        CREATE TRIGGER IF NOT EXISTS fts_scene_update
        AFTER UPDATE ON scenes
        BEGIN
            DELETE FROM search_index
            WHERE content_type = 'scene' AND content_id = OLD.id;
 
            INSERT INTO search_index(content_type, content_id, project_id, text)
            VALUES(
                'scene',
                NEW.id,
                NEW.project_id,
                COALESCE(NEW.scene_number, '')
                || ' ' || COALESCE(NEW.location, '')
                || ' ' || COALESCE(NEW.synopsis,  '')
            );
        END;
 
        CREATE TRIGGER IF NOT EXISTS fts_scene_delete
        AFTER DELETE ON scenes
        BEGIN
            DELETE FROM search_index
            WHERE content_type = 'scene' AND content_id = OLD.id;
        END;
    """)
 
    # 4. Trigger su scene_elements
    conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS fts_element_insert
        AFTER INSERT ON scene_elements
        BEGIN
            INSERT INTO search_index(content_type, content_id, project_id, text)
            SELECT
                'element',
                NEW.id,
                s.project_id,
                COALESCE(NEW.element_name, '') || ' ' || COALESCE(NEW.category, '')
            FROM scenes s
            WHERE s.id = NEW.scene_id;
        END;
 
        CREATE TRIGGER IF NOT EXISTS fts_element_delete
        AFTER DELETE ON scene_elements
        BEGIN
            DELETE FROM search_index
            WHERE content_type = 'element' AND content_id = OLD.id;
        END;
    """)
 
    # 5. Popola l'indice con i dati già esistenti nel DB
    #    Usiamo INSERT OR IGNORE per essere idempotenti in caso di retry.
    conn.executescript("""
        INSERT OR IGNORE INTO search_index(content_type, content_id, project_id, text)
        SELECT
            'scene',
            id,
            project_id,
            COALESCE(scene_number, '')
            || ' ' || COALESCE(location, '')
            || ' ' || COALESCE(synopsis,  '')
        FROM scenes;
 
        INSERT OR IGNORE INTO search_index(content_type, content_id, project_id, text)
        SELECT
            'element',
            se.id,
            s.project_id,
            COALESCE(se.element_name, '') || ' ' || COALESCE(se.category, '')
        FROM scene_elements se
        JOIN scenes s ON s.id = se.scene_id;
    """)
 
    # 6. Rebuild dell'indice FTS5 per garantire la coerenza
    #    (necessario dopo un bulk-insert tramite executescript)
    conn.execute("INSERT INTO search_index(search_index) VALUES('rebuild')")


# ---- V19 : shot_list (Feature 2.1) ----

@_register(19)
def _v19(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shot_list (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id        INTEGER NOT NULL,
            shot_number     TEXT    NOT NULL,
            shot_type       TEXT    NOT NULL
                CHECK(shot_type IN
                    ('MASTER','MCU','CU','ECU','OTS',
                     'INSERT','WIDE','TWO_SHOT','POV','CUTAWAY')),
            lens_mm         INTEGER,
            camera_movement TEXT
                CHECK(camera_movement IN
                    ('STATICO','DOLLY','STEADICAM','DRONE',
                     'HANDHELD','CRANE','ZOOM')),
            description     TEXT,
            setup_notes     TEXT,
            is_completed    INTEGER DEFAULT 0,
            position        INTEGER DEFAULT 0,
            created_at      INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_shot_scene'
        ' ON shot_list(scene_id, position)')


# ---- V20 : contacts & contact_availability ----

@_register(20)
def _v20(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            full_name   TEXT NOT NULL,
            role        TEXT,
            department  TEXT,
            agent_name  TEXT,
            phone       TEXT,
            email       TEXT,
            daily_rate  REAL,
            currency    TEXT DEFAULT 'EUR',
            notes       TEXT,
            photo_path  TEXT,
            created_at  INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contact_availability (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id   INTEGER NOT NULL,
            date_blocked INTEGER NOT NULL,
            reason       TEXT,
            FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
        )
    """)
    if column_missing(conn, "call_sheet_cast", "contact_id"):
        conn.execute("ALTER TABLE call_sheet_cast ADD COLUMN contact_id INTEGER")


# ---- V21 : locations & location_id su scenes ----

@_register(21)
def _v21(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id         INTEGER NOT NULL,
            name               TEXT NOT NULL,
            address            TEXT,
            latitude           REAL,
            longitude          REAL,
            contact_name       TEXT,
            contact_phone      TEXT,
            permit_notes       TEXT,
            availability_notes TEXT,
            photos_dir         TEXT,
            created_at         INTEGER DEFAULT (strftime('%s','now')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    if column_missing(conn, "scenes", "location_id"):
        conn.execute("ALTER TABLE scenes ADD COLUMN location_id INTEGER")


# ---- V22 : prop tracking su scene_elements ----

@_register(22)
def _v22(conn):
    for col, typedef in [
        ("prop_status",      "TEXT DEFAULT 'da_trovare'"),
        ("prop_responsible", "TEXT"),
        ("prop_due_date",    "INTEGER"),
        ("prop_cost",        "REAL"),
    ]:
        if column_missing(conn, "scene_elements", col):
            conn.execute(f"ALTER TABLE scene_elements ADD COLUMN {col} {typedef}")


# ---- V23 : estimated_cost su scenes (Feature 3.2) ----

@_register(23)
def _v23(conn):
    if column_missing(conn, "scenes", "estimated_cost"):
        conn.execute(
            "ALTER TABLE scenes ADD COLUMN estimated_cost REAL DEFAULT 0.0"
        )


# ---- V24 : distribution_log (Feature 4.1 — Email Distribution) ----

@_register(24)
def _v24(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS distribution_log (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            call_sheet_id    INTEGER NOT NULL,
            recipient_name   TEXT NOT NULL,
            recipient_email  TEXT NOT NULL,
            sent_at          INTEGER DEFAULT (strftime('%s','now')),
            status           TEXT DEFAULT 'sent',
            pdf_hash         TEXT,
            FOREIGN KEY (call_sheet_id)
                REFERENCES call_sheets(id) ON DELETE CASCADE
        )
    """)


# ---- V25 : Performance indexes (Feature 5.3) ----

@_register(25)
def _v25(conn):
    """Indici strategici per performance."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_scenes_project"
        " ON scenes(project_id, scene_number)",
        "CREATE INDEX IF NOT EXISTS idx_elements_scene"
        " ON scene_elements(scene_id, category)",
        "CREATE INDEX IF NOT EXISTS idx_elements_ai"
        " ON scene_elements(category) WHERE ai_suggested=1",
        "CREATE INDEX IF NOT EXISTS idx_dood_project"
        " ON dood_entries(project_id, actor_name)",
        "CREATE INDEX IF NOT EXISTS idx_budget_project"
        " ON budget_accounts(project_id, code)",
    ]
    for sql in indexes:
        try:
            conn.execute(sql)
        except Exception:
            pass  # Index might already exist or table might not exist yet
    conn.execute("ANALYZE")


# ---- V26 : Budget templates predefiniti ----

@_register(26)
def _v26(conn):
    """Popola budget_templates con template standard italiani."""
    # Aggiungi colonna subtotal a budget_accounts se mancante
    if table_exists(conn, "budget_accounts") and column_missing(conn, "budget_accounts", "subtotal"):
        conn.execute(
            "ALTER TABLE budget_accounts ADD COLUMN subtotal REAL DEFAULT 0"
        )

    # Se le tabelle budget non esistono, esci (V4 non è stata ancora applicata)
    if not table_exists(conn, "budget_templates"):
        return

    # Template Cortometraggio
    conn.execute("""
        INSERT OR IGNORE INTO budget_templates
            (id, template_name, template_type, language, currency, description)
        VALUES
            (1, 'Cortometraggio Standard', 'Cortometraggio', 'it', 'EUR',
             'Template base per cortometraggi fino a 30 minuti'),
            (2, 'Lungometraggio Low Budget', 'Lungometraggio', 'it', 'EUR',
             'Template per lungometraggi con budget contenuto'),
            (3, 'Spot Pubblicitario', 'Commerciale', 'it', 'EUR',
             'Template per spot e video pubblicitari')
    """)

    # Conti per Cortometraggio Standard (id=1)
    SHORT_ACCOUNTS = [
        ('100', 'Sviluppo e Pre-produzione', 1, 1),
        ('200', 'Cast Artistico', 1, 2),
        ('300', 'Troupe Tecnica', 1, 3),
        ('400', 'Scenografia e Costumi', 1, 4),
        ('500', 'Attrezzature e Noleggi', 1, 5),
        ('600', 'Location e Trasporti', 1, 6),
        ('700', 'Post-produzione', 1, 7),
        ('800', 'Assicurazioni e Legale', 1, 8),
        ('900', 'Spese Generali', 1, 9),
    ]
    for code, name, level, sort_order in SHORT_ACCOUNTS:
        conn.execute(
            'INSERT OR IGNORE INTO budget_template_accounts'
            ' (template_id, account_code, account_name, level, sort_order)'
            ' VALUES (1, ?, ?, ?, ?)',
            (code, name, level, sort_order)
        )

    # Conti per Lungometraggio (id=2)
    FEATURE_ACCOUNTS = [
        ('100', 'Sviluppo', 1, 1),
        ('200', 'Sceneggiatura', 1, 2),
        ('300', 'Produzione Esecutiva', 1, 3),
        ('400', 'Regia', 1, 4),
        ('500', 'Cast Principale', 1, 5),
        ('600', 'Cast Secondario e Comparse', 1, 6),
        ('700', 'Troupe Tecnica', 1, 7),
        ('800', 'Scenografia', 1, 8),
        ('900', 'Costumi e Trucco', 1, 9),
        ('1000', 'Attrezzature', 1, 10),
        ('1100', 'Location', 1, 11),
        ('1200', 'Trasporti e Catering', 1, 12),
        ('1300', 'Post-produzione', 1, 13),
        ('1400', 'Musica e Diritti', 1, 14),
        ('1500', 'Assicurazioni', 1, 15),
        ('1600', 'Spese Generali e Contingency', 1, 16),
    ]
    for code, name, level, sort_order in FEATURE_ACCOUNTS:
        conn.execute(
            'INSERT OR IGNORE INTO budget_template_accounts'
            ' (template_id, account_code, account_name, level, sort_order)'
            ' VALUES (2, ?, ?, ?, ?)',
            (code, name, level, sort_order)
        )

    # Conti per Spot Pubblicitario (id=3)
    COMMERCIAL_ACCOUNTS = [
        ('100', 'Agenzia e Concept', 1, 1),
        ('200', 'Regia e Produzione', 1, 2),
        ('300', 'Talent e Modelli', 1, 3),
        ('400', 'Troupe', 1, 4),
        ('500', 'Set e Props', 1, 5),
        ('600', 'Location e Permessi', 1, 6),
        ('700', 'Attrezzature Speciali', 1, 7),
        ('800', 'Post-produzione e VFX', 1, 8),
        ('900', 'Musica e Sound Design', 1, 9),
        ('1000', 'Diritti e Buyout', 1, 10),
    ]
    for code, name, level, sort_order in COMMERCIAL_ACCOUNTS:
        conn.execute(
            'INSERT OR IGNORE INTO budget_template_accounts'
            ' (template_id, account_code, account_name, level, sort_order)'
            ' VALUES (3, ?, ?, ?, ?)',
            (code, name, level, sort_order)
        )


# ---- V27 ----
@_register(27)
def _v27(conn):
    """Aggiunge budget_template_details e popola voci di esempio."""
    # Crea la tabella per i dettagli dei template
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget_template_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_account_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            units REAL DEFAULT 1,
            unit_type TEXT DEFAULT 'flat',
            rate REAL DEFAULT 0,
            fringes_percent REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (template_account_id)
                REFERENCES budget_template_accounts(id) ON DELETE CASCADE
        )
    """)

    # Funzione helper per inserire voci
    def insert_details(account_code, template_id, details):
        row = conn.execute(
            "SELECT id FROM budget_template_accounts "
            "WHERE template_id = ? AND account_code = ?",
            (template_id, account_code)
        ).fetchone()
        if not row:
            return
        acc_id = row[0]
        for i, (desc, units, unit_type, rate, fringes) in enumerate(details):
            conn.execute(
                "INSERT INTO budget_template_details "
                "(template_account_id, description, units, unit_type, rate, "
                "fringes_percent, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (acc_id, desc, units, unit_type, rate, fringes, i + 1)
            )

    # ---- Voci per Cortometraggio Standard (template_id=1) ----
    # 100 - Sviluppo e Pre-produzione
    insert_details('100', 1, [
        ('Sceneggiatura', 1, 'flat', 500, 0),
        ('Casting', 1, 'flat', 300, 0),
        ('Sopralluoghi', 2, 'giorni', 100, 0),
        ('Storyboard', 1, 'flat', 400, 0),
    ])
    # 200 - Cast Artistico
    insert_details('200', 1, [
        ('Protagonista', 3, 'giorni', 200, 0),
        ('Co-protagonista', 3, 'giorni', 150, 0),
        ('Attori secondari', 6, 'giorni', 80, 0),
        ('Comparse', 10, 'giorni', 50, 0),
    ])
    # 300 - Troupe Tecnica
    insert_details('300', 1, [
        ('Direttore fotografia', 4, 'giorni', 300, 0),
        ('Operatore camera', 4, 'giorni', 200, 0),
        ('Fonico', 4, 'giorni', 180, 0),
        ('Assistente regia', 5, 'giorni', 120, 0),
        ('Segretaria edizione', 4, 'giorni', 150, 0),
    ])
    # 400 - Scenografia e Costumi
    insert_details('400', 1, [
        ('Scenografo', 5, 'giorni', 180, 0),
        ('Costumista', 3, 'giorni', 150, 0),
        ('Materiali scenografia', 1, 'flat', 800, 0),
        ('Noleggio costumi', 1, 'flat', 400, 0),
    ])
    # 500 - Attrezzature e Noleggi
    insert_details('500', 1, [
        ('Camera e ottiche', 4, 'giorni', 250, 0),
        ('Luci e grip', 4, 'giorni', 150, 0),
        ('Audio kit', 4, 'giorni', 80, 0),
        ('Carrello/Dolly', 2, 'giorni', 120, 0),
    ])
    # 600 - Location e Trasporti
    insert_details('600', 1, [
        ('Affitto location principale', 3, 'giorni', 300, 0),
        ('Location secondarie', 2, 'giorni', 150, 0),
        ('Trasporti troupe', 4, 'giorni', 100, 0),
        ('Parcheggi e permessi', 1, 'flat', 200, 0),
    ])
    # 700 - Post-produzione
    insert_details('700', 1, [
        ('Montaggio', 10, 'giorni', 150, 0),
        ('Color grading', 3, 'giorni', 200, 0),
        ('Sound design', 5, 'giorni', 150, 0),
        ('Mix audio', 2, 'giorni', 250, 0),
        ('Musiche', 1, 'flat', 500, 0),
    ])
    # 800 - Assicurazioni e Legale
    insert_details('800', 1, [
        ('Assicurazione produzione', 1, 'flat', 400, 0),
        ('Consulenza legale', 1, 'flat', 300, 0),
        ('SIAE/diritti', 1, 'flat', 200, 0),
    ])
    # 900 - Spese Generali
    insert_details('900', 1, [
        ('Catering', 4, 'giorni', 150, 0),
        ('Spese ufficio', 1, 'flat', 200, 0),
        ('Imprevisti', 1, 'flat', 500, 0),
    ])

    # ---- Voci per Lungometraggio Low Budget (template_id=2) ----
    # 100 - Sviluppo
    insert_details('100', 2, [
        ('Ricerca e sviluppo concept', 1, 'flat', 1000, 0),
        ('Opzione diritti', 1, 'flat', 2000, 0),
    ])
    # 200 - Sceneggiatura
    insert_details('200', 2, [
        ('Sceneggiatore', 1, 'flat', 5000, 0),
        ('Revisioni', 1, 'flat', 1500, 0),
        ('Script doctor', 1, 'flat', 1000, 0),
    ])
    # 300 - Produzione Esecutiva
    insert_details('300', 2, [
        ('Produttore esecutivo', 20, 'settimane', 500, 0),
        ('Line producer', 12, 'settimane', 400, 0),
        ('Coordinatore produzione', 10, 'settimane', 300, 0),
    ])
    # 400 - Regia
    insert_details('400', 2, [
        ('Regista', 1, 'flat', 8000, 0),
        ('Aiuto regista', 6, 'settimane', 350, 0),
    ])
    # 500 - Cast Principale
    insert_details('500', 2, [
        ('Protagonista', 5, 'settimane', 1500, 0),
        ('Co-protagonista', 4, 'settimane', 1000, 0),
    ])
    # 600 - Cast Secondario e Comparse
    insert_details('600', 2, [
        ('Attori secondari', 20, 'giorni', 200, 0),
        ('Comparse', 50, 'giorni', 60, 0),
        ('Figurazioni speciali', 10, 'giorni', 100, 0),
    ])
    # 700 - Troupe Tecnica
    insert_details('700', 2, [
        ('DOP', 5, 'settimane', 800, 0),
        ('Camera operators', 5, 'settimane', 500, 0),
        ('Gaffer', 5, 'settimane', 450, 0),
        ('Sound mixer', 5, 'settimane', 500, 0),
        ('Grip team', 5, 'settimane', 600, 0),
    ])
    # 800 - Scenografia
    insert_details('800', 2, [
        ('Scenografo', 8, 'settimane', 400, 0),
        ('Costruzioni', 1, 'flat', 5000, 0),
        ('Arredamento set', 1, 'flat', 3000, 0),
    ])
    # 900 - Costumi e Trucco
    insert_details('900', 2, [
        ('Costumista', 6, 'settimane', 350, 0),
        ('Acquisto/noleggio costumi', 1, 'flat', 3000, 0),
        ('Makeup artist', 5, 'settimane', 350, 0),
        ('Materiali trucco', 1, 'flat', 800, 0),
    ])
    # 1000 - Attrezzature
    insert_details('1000', 2, [
        ('Camera package', 5, 'settimane', 1500, 0),
        ('Lighting package', 5, 'settimane', 800, 0),
        ('Grip equipment', 5, 'settimane', 500, 0),
        ('Audio equipment', 5, 'settimane', 400, 0),
    ])
    # 1100 - Location
    insert_details('1100', 2, [
        ('Location principale', 5, 'settimane', 2000, 0),
        ('Location secondarie', 1, 'flat', 5000, 0),
        ('Permessi', 1, 'flat', 1500, 0),
    ])
    # 1200 - Trasporti e Catering
    insert_details('1200', 2, [
        ('Trasporti produzione', 5, 'settimane', 600, 0),
        ('Catering', 25, 'giorni', 300, 0),
        ('Craft services', 25, 'giorni', 100, 0),
    ])
    # 1300 - Post-produzione
    insert_details('1300', 2, [
        ('Editor', 12, 'settimane', 500, 0),
        ('Color grading', 1, 'flat', 3000, 0),
        ('Sound design', 4, 'settimane', 500, 0),
        ('Mix Dolby', 1, 'flat', 4000, 0),
        ('VFX base', 1, 'flat', 5000, 0),
    ])
    # 1400 - Musica e Diritti
    insert_details('1400', 2, [
        ('Compositore', 1, 'flat', 5000, 0),
        ('Licenze musica', 1, 'flat', 2000, 0),
        ('Diritti archivio', 1, 'flat', 1500, 0),
    ])
    # 1500 - Assicurazioni
    insert_details('1500', 2, [
        ('Assicurazione produzione', 1, 'flat', 3000, 0),
        ('Assicurazione E&O', 1, 'flat', 2000, 0),
        ('Workers comp', 1, 'flat', 1500, 0),
    ])
    # 1600 - Spese Generali e Contingency
    insert_details('1600', 2, [
        ('Ufficio produzione', 1, 'flat', 2000, 0),
        ('Spese legali', 1, 'flat', 3000, 0),
        ('Contingency (10%)', 1, 'flat', 10000, 0),
    ])

    # ---- Voci per Spot Pubblicitario (template_id=3) ----
    # 100 - Agenzia e Concept
    insert_details('100', 3, [
        ('Fee agenzia', 1, 'flat', 5000, 0),
        ('Sviluppo concept', 1, 'flat', 2000, 0),
    ])
    # 200 - Regia e Produzione
    insert_details('200', 3, [
        ('Regista', 2, 'giorni', 2000, 0),
        ('Producer', 5, 'giorni', 500, 0),
        ('PM', 5, 'giorni', 350, 0),
    ])
    # 300 - Talent e Modelli
    insert_details('300', 3, [
        ('Talent principale', 2, 'giorni', 1500, 0),
        ('Modelli secondari', 4, 'giorni', 500, 0),
        ('Buyout talent', 1, 'flat', 3000, 0),
    ])
    # 400 - Troupe
    insert_details('400', 3, [
        ('DOP', 2, 'giorni', 1000, 0),
        ('Gaffer', 2, 'giorni', 500, 0),
        ('Grip team', 2, 'giorni', 800, 0),
        ('Sound', 2, 'giorni', 400, 0),
        ('Stylist', 2, 'giorni', 600, 0),
        ('MUA', 2, 'giorni', 500, 0),
    ])
    # 500 - Set e Props
    insert_details('500', 3, [
        ('Set design', 1, 'flat', 3000, 0),
        ('Props', 1, 'flat', 1500, 0),
        ('Styling prodotto', 1, 'flat', 1000, 0),
    ])
    # 600 - Location e Permessi
    insert_details('600', 3, [
        ('Studio', 2, 'giorni', 2000, 0),
        ('Permessi', 1, 'flat', 500, 0),
    ])
    # 700 - Attrezzature Speciali
    insert_details('700', 3, [
        ('Camera RED/Alexa', 2, 'giorni', 1000, 0),
        ('Ottiche speciali', 2, 'giorni', 500, 0),
        ('Motion control', 1, 'giorni', 2000, 0),
        ('Drone', 1, 'giorni', 800, 0),
    ])
    # 800 - Post-produzione e VFX
    insert_details('800', 3, [
        ('Editing', 5, 'giorni', 400, 0),
        ('Color grading', 2, 'giorni', 500, 0),
        ('VFX/CGI', 1, 'flat', 5000, 0),
        ('Motion graphics', 1, 'flat', 2000, 0),
    ])
    # 900 - Musica e Sound Design
    insert_details('900', 3, [
        ('Sound design', 3, 'giorni', 400, 0),
        ('Mix audio', 1, 'giorni', 600, 0),
        ('Licenza musica', 1, 'flat', 2000, 0),
    ])
    # 1000 - Diritti e Buyout
    insert_details('1000', 3, [
        ('Buyout media', 1, 'flat', 5000, 0),
        ('Diritti immagine', 1, 'flat', 2000, 0),
        ('Assicurazione', 1, 'flat', 1000, 0),
    ])


# ---- V28 ----
@_register(28)
def _v28(conn):
    """Crea budget_category_rates per mapping breakdown -> budget."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget_category_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            breakdown_category TEXT NOT NULL UNIQUE,
            budget_account_code TEXT NOT NULL,
            budget_account_name TEXT NOT NULL,
            default_rate REAL DEFAULT 0,
            default_unit_type TEXT DEFAULT 'giorni',
            default_fringes_percent REAL DEFAULT 0,
            notes TEXT
        )
    """)

    # Mapping categorie breakdown -> conti budget con costi predefiniti
    CATEGORY_RATES = [
        # breakdown_category, account_code, account_name, rate, unit_type, fringes
        ('Cast', '200', 'Cast Artistico', 200, 'giorni', 0),
        ('Extras', '210', 'Comparse e Figurazioni', 60, 'giorni', 0),
        ('Stunts', '220', 'Stunt e Controfigure', 400, 'giorni', 0),
        ('Intimacy', '225', 'Coordinatore Intimità', 350, 'giorni', 0),
        ('Vehicles', '600', 'Veicoli e Trasporti', 150, 'giorni', 0),
        ('Props', '410', 'Oggetti di Scena', 50, 'flat', 0),
        ('Special FX', '510', 'Effetti Speciali Pratici', 500, 'giorni', 0),
        ('Wardrobe', '420', 'Costumi', 80, 'flat', 0),
        ('Makeup', '430', 'Trucco e Parrucco', 150, 'giorni', 0),
        ('Livestock', '240', 'Animali', 200, 'giorni', 0),
        ('Animal Handlers', '245', 'Addestratori Animali', 250, 'giorni', 0),
        ('Music', '710', 'Musica e Composizione', 300, 'flat', 0),
        ('Sound', '720', 'Sound Design', 200, 'giorni', 0),
        ('Set Dressing', '400', 'Scenografia e Arredamento', 100, 'flat', 0),
        ('Greenery', '405', 'Verde e Piante', 50, 'flat', 0),
        ('Special Equipment', '500', 'Attrezzature Speciali', 300, 'giorni', 0),
        ('Security', '810', 'Sicurezza', 150, 'giorni', 0),
        ('Additional Labor', '300', 'Personale Aggiuntivo', 120, 'giorni', 0),
        ('VFX', '700', 'Effetti Visivi (VFX)', 500, 'flat', 0),
        ('Mechanical FX', '520', 'Effetti Meccanici', 400, 'giorni', 0),
        ('Notes', '900', 'Varie e Imprevisti', 0, 'flat', 0),
    ]

    for cat, code, name, rate, unit_type, fringes in CATEGORY_RATES:
        conn.execute(
            "INSERT OR IGNORE INTO budget_category_rates "
            "(breakdown_category, budget_account_code, budget_account_name, "
            "default_rate, default_unit_type, default_fringes_percent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cat, code, name, rate, unit_type, fringes)
        )


# ---- V29 : schedule_entries (fix per database che non hanno la tabella) ----
@_register(29)
def _v29(conn):
    """Crea schedule_entries se non esiste (fix per database esistenti)."""
    if not table_exists(conn, "schedule_entries"):
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