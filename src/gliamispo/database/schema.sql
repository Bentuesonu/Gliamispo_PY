-- ============================================================
-- Schema DDL completo — Gliamispo Python
-- Basato su SQLiteManager.creaTabelle() + migrazioni V2–V17
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ------- projects -------
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    director TEXT,
    production_company TEXT,
    created_date INTEGER DEFAULT (strftime('%s','now')),
    last_modified INTEGER DEFAULT (strftime('%s','now')),
    language TEXT,
    currency TEXT,
    ml_enabled INTEGER DEFAULT 1,
    ml_min_confidence REAL DEFAULT 0.60,
    total_budget REAL,
    contingency_percent REAL DEFAULT 10.0,
    hours_per_shooting_day REAL DEFAULT 10.0
);

-- ------- scenes (schema post-V6 con eighths e GENERATED ALWAYS) -------
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    scene_number TEXT,
    location TEXT,
    int_ext TEXT NOT NULL CHECK(int_ext IN ('INT', 'EXT', 'INT/EXT')),
    day_night TEXT NOT NULL CHECK(day_night IN ('GIORNO', 'NOTTE', 'ALBA', 'TRAMONTO', 'CONTINUO')),
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
    synopsis TEXT,
    raw_blocks TEXT,   -- JSON list di {type, text}
    story_day INTEGER DEFAULT 1,
    requires_intimacy_coordinator INTEGER DEFAULT 0,
    estimated_crew_size INTEGER,
    special_requirements TEXT,
    parser_used TEXT,
    parser_confidence REAL,
    parsed_at INTEGER,
    manual_shooting_hours REAL DEFAULT 0.0,
    is_locked INTEGER DEFAULT 0,
    scene_notes TEXT,
    location_id INTEGER,
    revision_id INTEGER,       -- FK a script_revisions (V17)
    revision_badge TEXT,       -- etichetta colore revisione (V17)
    estimated_cost REAL DEFAULT 0.0,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    CHECK((page_end_whole > page_start_whole) OR
          (page_end_whole = page_start_whole AND
           page_end_eighths >= page_start_eighths)),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ------- scene_elements (schema post-V6 step 10 con CHECK e UNIQUE) -------
CREATE TABLE IF NOT EXISTS scene_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    category TEXT NOT NULL CHECK(category IN (
        'Cast','Extras','Stunts','Intimacy','Vehicles','Props',
        'Special FX','Wardrobe','Makeup','Livestock','Animal Handlers',
        'Music','Sound','Set Dressing','Greenery','Special Equipment',
        'Security','Additional Labor','VFX','Mechanical FX','Notes'
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
);

-- ------- user_corrections (post-V10, senza CHECK su action) -------
CREATE TABLE IF NOT EXISTS user_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element_id INTEGER,
    scene_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    before_category TEXT,
    after_category TEXT,
    before_name TEXT,
    after_name TEXT,
    before_quantity INTEGER,
    after_quantity INTEGER,
    original_confidence REAL,
    original_model_version TEXT,
    corrected_at INTEGER DEFAULT (strftime('%s','now')),
    session_id TEXT,
    trained_at INTEGER
);

-- ------- rejected_elements (blacklist per elementi eliminati dall'utente) -------
CREATE TABLE IF NOT EXISTS rejected_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element_name TEXT NOT NULL,
    category TEXT,
    scene_id INTEGER,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_rejected_name
    ON rejected_elements(element_name);

-- ------- training_data -------
CREATE TABLE IF NOT EXISTS training_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER,
    scene_text TEXT,
    scene_context TEXT,
    detected_elements TEXT,
    user_corrections TEXT,
    correction_type TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    user_id TEXT,
    used_for_training INTEGER DEFAULT 0,
    used_in_model_version TEXT,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- ------- vocabulary_terms -------
CREATE TABLE IF NOT EXISTS vocabulary_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL UNIQUE,
    canonical_form TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('BUILTIN', 'USER_ADDED', 'ML_LEARNED')),
    learned_from_corrections INTEGER DEFAULT 0,
    base_confidence REAL DEFAULT 0.70,
    added_at INTEGER DEFAULT (strftime('%s','now')),
    last_used INTEGER,
    usage_count INTEGER DEFAULT 0,
    language TEXT DEFAULT 'it'
);

-- ------- ml_model_versions -------
CREATE TABLE IF NOT EXISTS ml_model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    model_path TEXT NOT NULL,
    trained_on INTEGER NOT NULL,
    training_dataset_size INTEGER,
    training_duration_seconds REAL,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    category_metrics TEXT,
    confusion_matrix TEXT,
    is_active INTEGER DEFAULT 0,
    is_baseline INTEGER DEFAULT 0,
    training_notes TEXT,
    UNIQUE(model_name, version)
);

-- ------- element_confidence_history -------
CREATE TABLE IF NOT EXISTS element_confidence_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    element_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    detection_method TEXT,
    recorded_at INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (element_id) REFERENCES scene_elements(id) ON DELETE CASCADE
);

-- ------- multiword_entities -------
CREATE TABLE IF NOT EXISTS multiword_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_text TEXT NOT NULL,
    category TEXT NOT NULL,
    co_occurrence_score REAL,
    frequency INTEGER DEFAULT 1,
    source TEXT CHECK(source IN ('BUILTIN', 'LEARNED')),
    learned_at INTEGER DEFAULT (strftime('%s','now')),
    UNIQUE(entity_text, category)
);

-- ------- ml_performance_metrics (con GENERATED ALWAYS) -------
CREATE TABLE IF NOT EXISTS ml_performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version_id INTEGER NOT NULL,
    period_start INTEGER NOT NULL,
    period_end INTEGER NOT NULL,
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
    FOREIGN KEY (model_version_id) REFERENCES ml_model_versions(id) ON DELETE CASCADE
);

-- ------- ai_patterns -------
CREATE TABLE IF NOT EXISTS ai_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context_type TEXT,
    context_value TEXT,
    suggested_element TEXT,
    frequency INTEGER DEFAULT 1,
    last_used INTEGER,
    UNIQUE(context_type, context_value, suggested_element)
);

-- ------- shooting_schedules -------
CREATE TABLE IF NOT EXISTS shooting_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    schedule_name TEXT NOT NULL DEFAULT 'Piano di Lavorazione',
    total_days INTEGER,
    start_date TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    last_modified INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ------- shooting_days -------
CREATE TABLE IF NOT EXISTS shooting_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    shoot_date TEXT,
    call_time TEXT DEFAULT '07:00',
    wrap_time TEXT DEFAULT '19:00',
    location_primary TEXT,
    notes TEXT,
    FOREIGN KEY (schedule_id) REFERENCES shooting_schedules(id) ON DELETE CASCADE
);

-- ------- shooting_day_scenes -------
CREATE TABLE IF NOT EXISTS shooting_day_scenes (
    shooting_day_id INTEGER NOT NULL,
    scene_id INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
    estimated_duration_minutes INTEGER,
    PRIMARY KEY (shooting_day_id, scene_id),
    FOREIGN KEY (shooting_day_id) REFERENCES shooting_days(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- ------- schedule_entries (tabella leggera per stripboard) -------
CREATE TABLE IF NOT EXISTS schedule_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL,
    scene_id     INTEGER NOT NULL,
    shooting_day INTEGER NOT NULL,
    position     INTEGER NOT NULL DEFAULT 0,
    UNIQUE(project_id, scene_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_schedule_project_day
    ON schedule_entries(project_id, shooting_day);

-- ------- intimacy_protocols -------
CREATE TABLE IF NOT EXISTS intimacy_protocols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    coordinator_name TEXT,
    coordinator_contact TEXT,
    consent_form_signed INTEGER DEFAULT 0,
    closed_set_required INTEGER DEFAULT 1,
    rehearsal_scheduled TEXT,
    rehearsal_completed INTEGER DEFAULT 0,
    specific_notes TEXT,
    contact_boundaries TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now')),
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE
);

-- ------- budget_templates -------
CREATE TABLE IF NOT EXISTS budget_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    template_type TEXT DEFAULT 'Cortometraggio',
    language TEXT DEFAULT 'it',
    currency TEXT DEFAULT 'EUR',
    description TEXT,
    created_at INTEGER DEFAULT (strftime('%s','now'))
);

-- ------- budget_template_accounts -------
CREATE TABLE IF NOT EXISTS budget_template_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    parent_id INTEGER,
    account_code TEXT,
    account_name TEXT NOT NULL,
    level INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    default_rate REAL,
    default_unit_type TEXT,
    default_fringes_percent REAL DEFAULT 0,
    FOREIGN KEY (template_id) REFERENCES budget_templates(id) ON DELETE CASCADE
);

-- ------- budget_template_details -------
CREATE TABLE IF NOT EXISTS budget_template_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_account_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    units REAL DEFAULT 1,
    unit_type TEXT DEFAULT 'flat',
    rate REAL DEFAULT 0,
    fringes_percent REAL DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    FOREIGN KEY (template_account_id) REFERENCES budget_template_accounts(id) ON DELETE CASCADE
);

-- ------- budget_category_rates -------
-- Mapping categorie breakdown -> budget con costi predefiniti
CREATE TABLE IF NOT EXISTS budget_category_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    breakdown_category TEXT NOT NULL UNIQUE,
    budget_account_code TEXT NOT NULL,
    budget_account_name TEXT NOT NULL,
    default_rate REAL DEFAULT 0,
    default_unit_type TEXT DEFAULT 'giorni',
    default_fringes_percent REAL DEFAULT 0,
    notes TEXT
);

-- ------- budget_accounts -------
CREATE TABLE IF NOT EXISTS budget_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    parent_id INTEGER,
    account_code TEXT,
    account_name TEXT NOT NULL,
    level INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
    subtotal REAL DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ------- budget_details -------
CREATE TABLE IF NOT EXISTS budget_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    units REAL DEFAULT 0,
    unit_type TEXT,
    rate REAL DEFAULT 0,
    fringes_percent REAL DEFAULT 0,
    status TEXT DEFAULT 'Estimated',
    actual_cost REAL,
    notes TEXT,
    FOREIGN KEY (account_id) REFERENCES budget_accounts(id) ON DELETE CASCADE
);

-- ------- call_sheets -------
CREATE TABLE IF NOT EXISTS call_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shooting_day_id INTEGER NOT NULL,
    generated_at INTEGER DEFAULT (strftime('%s','now')),
    pdf_path TEXT,
    crew_call TEXT DEFAULT '07:00',
    general_notes TEXT,
    weather_forecast TEXT,
    production_logo_path TEXT,
    director_signature_path TEXT,
    next_day_preview TEXT,      -- JSON scene giorno dopo
    distribution_log TEXT,      -- JSON log invii email
    FOREIGN KEY (shooting_day_id) REFERENCES shooting_days(id) ON DELETE CASCADE
);

-- ------- call_sheet_cast -------
CREATE TABLE IF NOT EXISTS call_sheet_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL,
    actor_name TEXT NOT NULL,
    character_name TEXT,
    call_time TEXT NOT NULL,
    pickup_location TEXT,
    notes TEXT,
    makeup_call TEXT,
    wardrobe_call TEXT,
    contact_id INTEGER,
    FOREIGN KEY (call_sheet_id) REFERENCES call_sheets(id) ON DELETE CASCADE
);

-- ------- call_sheet_crew -------
CREATE TABLE IF NOT EXISTS call_sheet_crew (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL,
    crew_member_name TEXT NOT NULL,
    department TEXT,
    call_time TEXT NOT NULL,
    contact TEXT,
    FOREIGN KEY (call_sheet_id) REFERENCES call_sheets(id) ON DELETE CASCADE
);

-- ------- dood_entries -------
CREATE TABLE IF NOT EXISTS dood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    actor_name TEXT NOT NULL,
    shoot_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'W',
    UNIQUE(project_id, actor_name, shoot_day),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ------- project_stats -------
CREATE TABLE IF NOT EXISTS project_stats (
    project_id INTEGER PRIMARY KEY,
    total_scenes INTEGER DEFAULT 0,
    total_elements INTEGER DEFAULT 0,
    ml_detected_elements INTEGER DEFAULT 0,
    user_verified_elements INTEGER DEFAULT 0,
    avg_confidence REAL DEFAULT 0.0,
    last_updated INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- ------- shot_list (V19) -------
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
);
CREATE INDEX IF NOT EXISTS idx_shot_scene ON shot_list(scene_id, position);

-- ------- contacts (V20) -------
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
);

-- ------- contact_availability (V20) -------
CREATE TABLE IF NOT EXISTS contact_availability (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id   INTEGER NOT NULL,
    date_blocked INTEGER NOT NULL,
    reason       TEXT,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

-- ------- locations (V21) -------
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
);

-- ------- script_revisions (V17) -------
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
);

-- ------- revision_scene_changes (V17) -------
CREATE TABLE IF NOT EXISTS revision_scene_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    revision_id INTEGER NOT NULL,
    scene_number TEXT NOT NULL,
    change_type TEXT NOT NULL,   -- added/modified/deleted
    diff_summary TEXT,
    FOREIGN KEY (revision_id) REFERENCES script_revisions(id) ON DELETE CASCADE
);

-- ------- distribution_log (V24) -------
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
);

-- ------- settings (chiave/valore globali, necessario a _get_setting) -------
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
 
 
-- ------- search_index (FTS5, V18) -------
-- Tabella virtuale per ricerca full-text su scene ed elementi.
-- Colonne indicizzate: content_type, content_id, text
-- Colonna NON indicizzata: project_id  (usata solo come filtro WHERE)
CREATE VIRTUAL TABLE IF NOT EXISTS search_index
USING fts5(
    content_type,
    content_id,
    project_id UNINDEXED,
    text,
    tokenize = "unicode61"
);
 
 
-- ------- Trigger FTS5 — sincronizzazione automatica -------
 
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

-- ============================================================
-- TRIGGER — Gruppo A (creaTriggers, inizializzazione)
-- ============================================================

CREATE TRIGGER IF NOT EXISTS update_project_timestamp
AFTER UPDATE ON projects
BEGIN
    UPDATE projects SET last_modified = strftime('%s','now')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS validate_confidence
BEFORE INSERT ON scene_elements
WHEN NEW.ai_confidence IS NOT NULL
    AND (NEW.ai_confidence < 0.0 OR NEW.ai_confidence > 1.0)
BEGIN
    SELECT RAISE(ABORT, 'Confidence must be between 0.0 and 1.0');
END;

CREATE TRIGGER IF NOT EXISTS validate_category_insert
BEFORE INSERT ON scene_elements FOR EACH ROW
WHEN NEW.category NOT IN (
    'Cast','Extras','Stunts','Intimacy','Vehicles','Props',
    'Special FX','Wardrobe','Makeup','Livestock','Animal Handlers',
    'Music','Sound','Set Dressing','Greenery','Special Equipment',
    'Security','Additional Labor','VFX','Mechanical FX','Notes'
)
BEGIN
    SELECT RAISE(ABORT, 'Invalid category');
END;

CREATE TRIGGER IF NOT EXISTS validate_category_update
BEFORE UPDATE OF category ON scene_elements FOR EACH ROW
WHEN NEW.category NOT IN (
    'Cast','Extras','Stunts','Intimacy','Vehicles','Props',
    'Special FX','Wardrobe','Makeup','Livestock','Animal Handlers',
    'Music','Sound','Set Dressing','Greenery','Special Equipment',
    'Security','Additional Labor','VFX','Mechanical FX','Notes'
)
BEGIN
    SELECT RAISE(ABORT, 'Invalid category');
END;

CREATE TRIGGER IF NOT EXISTS validate_page_range
BEFORE INSERT ON scenes
WHEN (NEW.page_end_whole < NEW.page_start_whole) OR
     (NEW.page_end_whole = NEW.page_start_whole
      AND NEW.page_end_eighths < NEW.page_start_eighths)
BEGIN
    SELECT RAISE(ABORT, 'Page end must be >= page start');
END;


-- ============================================================
-- TRIGGER — Gruppo B (creaProjectStats, V6 step 9)
-- ============================================================

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


-- ============================================================
-- TRIGGER — Gruppo C (creaTriggersConfidenceHistory, V6 step 11)
-- ============================================================

DROP TRIGGER IF EXISTS track_confidence_on_insert;
CREATE TRIGGER track_confidence_on_insert
AFTER INSERT ON scene_elements
WHEN NEW.ai_confidence IS NOT NULL
BEGIN
    INSERT INTO element_confidence_history
        (element_id, model_version, confidence_score, detection_method)
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
        (element_id, model_version, confidence_score, detection_method)
    VALUES (
        NEW.id,
        COALESCE(NEW.ai_model_version, 'unknown'),
        NEW.ai_confidence,
        COALESCE(NEW.detection_method, 'Updated')
    );
END;