# Guida Tecnica di Migrazione — Gliamispo: Swift → Python 3.11+ / PyQt6

---

## 1. Executive Summary

Gliamispo è un'applicazione macOS per il breakdown cinematografico, composta da circa 32.000 righe di codice Swift con architettura a layer: modelli di dominio, database SQLite con migrazioni incrementali V2–V10, pipeline NLP multi-componente (NER, pattern matching, context engine, normalizzazione terminologica), inferenza ML on-device via CoreML, scheduling genetico, parsing di script Fountain e PDF, UI SwiftUI a tre colonne, e un sistema di dependency injection tramite ServiceContainer con lazy loading. Il progetto gestisce 25+ tabelle SQLite, 9 trigger di produzione, colonne GENERATED ALWAYS, e un sistema di feedback loop per il retraining incrementale dei modelli.

La migrazione verso Python 3.11+ con PyQt6 presenta una complessità medio-alta, stimata in 16 settimane per un team di 2 sviluppatori. Le tecnologie target sono Python 3.11+ (per TaskGroup e ExceptionGroup nativi), PyQt6 per l'interfaccia grafica, SQLite tramite il modulo standard `sqlite3`, asyncio per la pipeline NLP, threading e concurrent.futures per lo scheduling genetico, e scikit-learn come sostituto primario di CoreML con supporto ONNX opzionale per modelli esistenti convertiti. I rischi principali sono: la perdita di dati durante la migrazione dello schema scenes in V6 (bug Swift confermato su estimated_crew_size e special_requirements), l'assenza di CoreML su piattaforme non-Apple che richiede un'architettura ML completamente diversa, la complessità dell'aritmetica eighths (ottavi di pagina) con trappole sottili nell'arrotondamento, e l'interazione tra asyncio e il thread principale di PyQt6 che non consente una traduzione 1:1 dell'actor pattern Swift.

L'approccio raccomandato è ibrido: strangler fig per i layer database e modelli (portabili indipendentemente dalla UI), big bang per la UI dato che SwiftUI e PyQt6 non condividono alcun substrato. La migrazione procede dal basso verso l'alto: prima lo schema e il DatabaseManager con i test di regressione, poi i modelli e la logica NLP/ML, infine la UI. Questo permette di validare la correttezza dello schema e delle migrazioni prima di affrontare i componenti più rischiosi.

---

## 2. Mappa Architetturale Swift → Python

| Componente Swift | Ruolo | Equivalente Python | Note |
|---|---|---|---|
| SceneElement + BreakdownCategory | Modello elemento + enum 21 valori | dataclass + enum.Enum | rawValue stringa con spazi |
| Scene (struct) | Modello scena con eighths | dataclass Scene | Campi GENERATED ALWAYS calcolati in Python |
| Project (struct) | Modello progetto | dataclass Project | |
| SQLiteManager | CRUD + schema + migrazioni | DatabaseManager (sqlite3) | threading.Lock equivale a NSLock+dbLock |
| SQLiteManager.eseguiMigrazioni() | Migrazioni V2–V10 | MigrationManager | PRAGMA user_version per versioning |
| MigrationManager.swift | Codice morto, non eseguito | Non migrare | Solo documentazione d'intento |
| ServiceContainer | DI container con lazy var | ServiceContainer con cached_property | Fallback a 3 livelli per ML |
| NLPPipelineCoordinator (actor) | Orchestrazione NLP a 5 componenti | Classe con asyncio | async let → asyncio.gather |
| NERExtractor | Estrazione entità NER | Classe Python con spaCy/regex | |
| VocabularyManager | Matching su vocabulary_terms | Classe Python con lookup DB | |
| DynamicPatternMatcher | Pattern regex dinamici | Classe Python con re | |
| ContextEngine | Arricchimento contestuale | Classe Python | |
| TermNormalizer | Normalizzazione termini | Classe Python con threading.Lock | MainActor → Lock esplicito |
| GeneticScheduler | Ottimizzazione schedule genetica | concurrent.futures.ProcessPoolExecutor | yield ogni 10 generazioni |
| FountainParser | Parsing script .fountain e PDF | Classe Python | FOUNTAIN_LINES_PER_PAGE = 56 |
| EighthsCalculator | Conversione righe→eighths | Classe Eighths Python | EIGHTHS_CALC_LINES_PER_PAGE = 55 |
| BreakdownOrchestrator | Pipeline breakdown 6 step | Classe Python asincrona | 5 dipendenze iniettate |
| FeedbackLoopService (actor) | Feedback loop ML + retraining | Classe Python con Lock | Bug flush() da correggere |
| OnDeviceInference | Inferenza CoreML (NLModel) | scikit-learn SGDClassifier+TF-IDF | ONNX opzionale, regole fallback |
| DummyInference | Fallback ML (array vuoto) | Funzione/classe che ritorna [] | |
| SceneRepository | Repository scene con cache | Classe Python | |
| CallSheet | Generazione fogli di lavorazione | Classe Python | |
| IntimacyProtocol | Protocolli intimità | Classe Python | |
| SmartElementExtractor | Estrazione elementi smart | Classe Python | |
| NLPProcessorV2 | Processore NLP avanzato | Classe Python | |
| SynonymExpander | Espansione sinonimi | Classe Python | |
| AIAssistant | Assistente AI (usa ai_patterns) | Classe Python | ai_patterns mancante in DDL Swift |
| MLScheduler | Scheduling operazioni ML | Classe Python con timer | |
| MLAnalyticsService | Analytics ML | Classe Python | |
| ScriptImportService | Import script completo | Classe Python | |
| SwiftUI Views | UI a tre colonne | PyQt6 QSplitter + QWidget | Signal/slot sostituisce @Published |
| Combine / @Published | Reactive bindings | PyQt6 Signal/Slot | |
| UserDefaults | Preferenze utente | QSettings o configparser | |
| NSLock | Mutex per SQLite | threading.Lock | Pattern identico lock/defer → with |
| NotificationCenter | Pub/sub tra componenti | QObject signals o blinker | Soglia 50 correzioni → retraining |

---

## 3. Schema Dati e Layer Database

### 3.1 Modelli Python (dataclasses)

```python
from dataclasses import dataclass, field
from enum import Enum
import time


class BreakdownCategory(Enum):
    CAST = "Cast"
    EXTRAS = "Extras"
    STUNTS = "Stunts"
    INTIMACY = "Intimacy"
    VEHICLES = "Vehicles"
    PROPS = "Props"
    SPECIAL_FX = "Special FX"
    WARDROBE = "Wardrobe"
    MAKEUP = "Makeup"
    LIVESTOCK = "Livestock"
    ANIMAL_HANDLERS = "Animal Handlers"
    MUSIC = "Music"
    SOUND = "Sound"
    SET_DRESSING = "Set Dressing"
    GREENERY = "Greenery"
    SPECIAL_EQUIPMENT = "Special Equipment"
    SECURITY = "Security"
    ADDITIONAL_LABOR = "Additional Labor"
    VFX = "VFX"
    MECHANICAL_FX = "Mechanical FX"
    NOTES = "Notes"


VALID_CATEGORIES_SQL = ", ".join(f"'{c.value}'" for c in BreakdownCategory)


@dataclass
class SceneElement:
    id: int = 0
    scene_id: int = 0
    category: str = ""
    element_name: str = ""
    quantity: int = 1
    notes: str = ""
    ai_suggested: int = 0
    ai_confidence: float = None
    ai_model_version: str = "v0.0.0"
    detection_method: str = "vocabulary"
    user_verified: int = 0
    user_modified: int = 0
    original_category: str = None
    modified_at: int = None
    created_at: int = field(default_factory=lambda: int(time.time()))


class Eighths:
    __slots__ = ("whole", "eighths")

    def __init__(self, whole=0, eighths=0):
        self.whole = whole + eighths // 8
        self.eighths = eighths % 8

    @classmethod
    def from_decimal(cls, value):
        w = int(value)
        remainder = value - w
        e = min(7, round(remainder * 8))
        return cls(w, e)

    @classmethod
    def from_string(cls, s):
        s = s.strip()
        parts = s.split()
        if len(parts) == 2 and "/" in parts[1]:
            w = int(parts[0])
            num, den = parts[1].split("/")
            e = int(num) * 8 // int(den)
            return cls(w, min(7, e))
        if "/" in s:
            num, den = s.split("/")
            return cls(0, int(num) * 8 // int(den))
        return cls(int(s), 0)

    @property
    def total_eighths(self):
        return self.whole * 8 + self.eighths

    def __sub__(self, other):
        diff = self.total_eighths - other.total_eighths
        return Eighths(diff // 8, diff % 8)

    def __repr__(self):
        if self.eighths == 0:
            return str(self.whole)
        return f"{self.whole} {self.eighths}/8"


@dataclass
class Scene:
    id: int = 0
    project_id: int = 0
    scene_number: str = ""
    location: str = ""
    int_ext: str = "INT"
    day_night: str = "GIORNO"
    page_start_whole: int = 1
    page_start_eighths: int = 0
    page_end_whole: int = 1
    page_end_eighths: int = 0
    synopsis: str = None
    story_day: int = 1
    requires_intimacy_coordinator: int = 0
    estimated_crew_size: int = None
    special_requirements: str = None
    parser_used: str = None
    parser_confidence: float = None
    parsed_at: int = None
    manual_shooting_hours: float = 0.0
    is_locked: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def page_start_decimal(self):
        return self.page_start_whole + self.page_start_eighths / 8.0

    @property
    def page_end_decimal(self):
        return self.page_end_whole + self.page_end_eighths / 8.0

    @property
    def duration_eighths(self):
        end = Eighths(self.page_end_whole, self.page_end_eighths)
        start = Eighths(self.page_start_whole, self.page_start_eighths)
        return end - start


@dataclass
class Project:
    id: int = 0
    title: str = ""
    director: str = None
    production_company: str = None
    created_date: int = field(default_factory=lambda: int(time.time()))
    last_modified: int = field(default_factory=lambda: int(time.time()))
    language: str = None
    currency: str = None
    ml_enabled: int = 1
    ml_min_confidence: float = 0.60
    total_budget: float = None
    contingency_percent: float = 10.0
    hours_per_shooting_day: float = 10.0
```

### 3.2 DatabaseManager Python

In Swift, SQLiteManager usa `NSLock` con il pattern `dbLock.lock(); defer { dbLock.unlock() }` in circa 44 metodi. L'equivalente Python è `threading.Lock` usato come context manager.

Confronto Swift → Python:

```swift
// Swift — pattern lock/defer in SQLiteManager
func leggiProgetti() -> [Project] {
    dbLock.lock()
    defer { dbLock.unlock() }
    // ... query SQL ...
}
```

```python
# Python — equivalente con threading.Lock e context manager
import sqlite3
import threading
from contextlib import contextmanager


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

    def execute_script(self, sql):
        with self._lock:
            self._conn.executescript(sql)

    def leggi_progetti(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM projects").fetchall()
            return [Project(**dict(r)) for r in rows]

    @property
    def user_version(self):
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    @user_version.setter
    def user_version(self, v):
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

    def close(self):
        self._conn.close()
```

Il pattern `check_same_thread=False` è necessario perché in Python il modulo `sqlite3` di default vieta l'uso di una connessione da un thread diverso da quello che l'ha creata. Con una singola connessione protetta da Lock, questo è sicuro. Con connessioni multiple il Lock non basta — serve un approccio diverso (trattato nella sezione 6).

### 3.3 Schema DDL Completo

```sql
-- ============================================================
-- Schema DDL completo — Gliamispo Python
-- Basato su SQLiteManager.creaTabelle() + migrazioni V2–V10
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
    CHECK((page_end_whole > page_start_whole) OR
          (page_end_whole = page_start_whole AND
           page_end_eighths >= page_start_eighths)),
    synopsis TEXT,
    story_day INTEGER DEFAULT 1,
    requires_intimacy_coordinator INTEGER DEFAULT 0,
    estimated_crew_size INTEGER,
    special_requirements TEXT,
    parser_used TEXT,
    parser_confidence REAL,
    parsed_at INTEGER,
    manual_shooting_hours REAL DEFAULT 0.0,
    is_locked INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (strftime('%s','now')),
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

-- ------- ai_patterns (⚠️ mancante nel DDL Swift — bug latente) -------
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

-- ------- budget_accounts -------
CREATE TABLE IF NOT EXISTS budget_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    parent_id INTEGER,
    account_code TEXT,
    account_name TEXT NOT NULL,
    level INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
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

-- ------- dood_entries (⚠️ CREATE TABLE mancante nel codebase Swift — bug) -------
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
    SELECT RAISE(ABORT, 'Invalid category: ' || NEW.category);
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
    SELECT RAISE(ABORT, 'Invalid category: ' || NEW.category);
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
```

### 3.4 MigrationManager Python

```python
import sqlite3
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

    # Step 5: migrazione eighths (correzione bug Swift:
    # include estimated_crew_size e special_requirements)
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
            CHECK((page_end_whole > page_start_whole) OR
                  (page_end_whole = page_start_whole
                   AND page_end_eighths >= page_start_eighths)),
            synopsis TEXT, story_day INTEGER DEFAULT 1,
            requires_intimacy_coordinator INTEGER DEFAULT 0,
            estimated_crew_size INTEGER,
            special_requirements TEXT,
            parser_used TEXT, parser_confidence REAL, parsed_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s','now')),
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

    # Step 12 è gestito dal run_migrations (PRAGMA user_version = 6)


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
    # Backfill valori NULL/empty
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
```

---

## 4. Logica Core — Componenti Non Banali

### 4.1 Eighths (aritmetica MOD 8)

In Swift, **Eighths** è una struct definita in `Double+Eighths.swift` che rappresenta la durata di una scena in ottavi di pagina, formato industry-standard cinematografico (es. "1 3/8"). Supporta inizializzazione da intero, decimale e stringa, e la sottrazione tra struct per calcolare la durata.

```python
class Eighths:
    __slots__ = ("whole", "eighths")

    def __init__(self, whole=0, eighths=0):
        self.whole = whole + eighths // 8
        self.eighths = eighths % 8

    @classmethod
    def from_decimal(cls, value):
        w = int(value)
        remainder = value - w
        e = min(7, round(remainder * 8))
        return cls(w, e)

    @classmethod
    def from_string(cls, s):
        s = s.strip()
        parts = s.split()
        if len(parts) == 2 and "/" in parts[1]:
            w = int(parts[0])
            num, den = parts[1].split("/")
            e = int(num) * 8 // int(den)
            return cls(w, min(7, e))
        if "/" in s:
            num, den = s.split("/")
            return cls(0, int(num) * 8 // int(den))
        return cls(int(s), 0)

    @property
    def total_eighths(self):
        return self.whole * 8 + self.eighths

    def __sub__(self, other):
        diff = self.total_eighths - other.total_eighths
        return Eighths(diff // 8, diff % 8)

    def __eq__(self, other):
        return self.total_eighths == other.total_eighths

    def __repr__(self):
        if self.eighths == 0:
            return str(self.whole)
        return f"{self.whole} {self.eighths}/8"


def scene_duration(page_start, page_end):
    start = Eighths.from_decimal(page_start)
    end = Eighths.from_decimal(page_end)
    return end - start
```

⚠️ La trappola principale è calcolare `round((page_end - page_start) * 8)` direttamente sulla differenza decimale: per valori come 1.375 - 1.0 il risultato è corretto (3/8), ma per combinazioni come 2.875 - 1.125 la differenza floating-point può produrre arrotondamenti errati. Costruire sempre i due Eighths separatamente e poi sottrarre `total_eighths`.

### 4.2 NLPPipelineCoordinator → asyncio

In Swift, **NLPPipelineCoordinator** è un actor con 5 dipendenze iniettate (NERExtractor, VocabularyManager, DynamicPatternMatcher, ContextEngine, TermNormalizer). Il metodo `processScene()` esegue 3 estrazioni in parallelo con `async let`, poi normalizzazione serializzata via `MainActor`, conflict resolution sincrona, context enhancement asincrona, deduplicazione e sort per confidence.

```python
import asyncio


class NLPPipelineCoordinator:
    def __init__(self, ner, vocabulary, pattern_matcher,
                 context_engine, normalizer):
        self._ner = ner
        self._vocab = vocabulary
        self._patterns = pattern_matcher
        self._context = context_engine
        self._normalizer = normalizer
        self._norm_lock = asyncio.Lock()

    async def process_scene(self, scene_text, scene_context):
        # Step 1: 3 estrazioni in parallelo (equivale a async let triplo)
        ner_task = asyncio.create_task(
            self._ner.extract(scene_text)
        )
        vocab_task = asyncio.create_task(
            self._vocab.match(scene_text)
        )
        pattern_task = asyncio.create_task(
            self._patterns.find(scene_text)
        )
        ner_results, vocab_results, pattern_results = await asyncio.gather(
            ner_task, vocab_task, pattern_task
        )

        # Step 2: normalizzazione serializzata (MainActor → Lock)
        merged = ner_results + vocab_results + pattern_results
        async with self._norm_lock:
            normalized = [
                self._normalizer.normalize(e) for e in merged
            ]

        # Step 3: conflict resolution sincrono
        resolved = self._resolve_conflicts(normalized)

        # Step 4: context enhancement
        enhanced = await self._context.enhance(resolved, scene_context)

        # Step 5: dedup + sort by confidence
        seen = set()
        deduped = []
        for e in enhanced:
            key = (e.category, e.element_name)
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        deduped.sort(key=lambda e: e.ai_confidence or 0, reverse=True)
        return deduped

    def _resolve_conflicts(self, elements):
        by_name = {}
        for e in elements:
            if e.element_name not in by_name:
                by_name[e.element_name] = e
            elif (e.ai_confidence or 0) > (by_name[e.element_name].ai_confidence or 0):
                by_name[e.element_name] = e
        return list(by_name.values())
```

⚠️ In PyQt6, asyncio non gira sul thread principale della GUI. Usare `QThread` o `QRunnable` con `QThreadPool` per lanciare il loop asyncio da un worker thread, comunicando i risultati via signal/slot. Non è possibile tradurre il pattern Swift actor 1:1: l'actor Swift serializza automaticamente gli accessi, mentre in Python serve gestire esplicitamente la concorrenza tra il loop asyncio e il thread Qt.

### 4.3 GeneticScheduler → concurrent.futures

In Swift, **GeneticScheduler** ottimizza il piano di lavorazione con un algoritmo genetico (populationSize=100, generations=500, mutationRate=0.10, eliteSize=10, tournamentSize=5, convergenceThreshold=0.001). Il metodo `optimize()` è async e yielda ogni 10 generazioni per non bloccare la UI.

```python
import random
import asyncio


class GeneticScheduler:
    POP_SIZE = 100
    GENERATIONS = 500
    MUTATION_RATE = 0.10
    ELITE_SIZE = 10
    TOURNAMENT_SIZE = 5
    CONVERGENCE_THRESHOLD = 0.001

    def __init__(self, scenes, constraints):
        self.scenes = scenes
        self.constraints = constraints

    async def optimize(self, on_progress=None):
        if not self.scenes:
            return []

        population = [self._random_schedule() for _ in range(self.POP_SIZE)]
        best_fitness = None

        for gen in range(self.GENERATIONS):
            scored = [(ind, self._fitness(ind)) for ind in population]
            scored.sort(key=lambda x: x[1], reverse=True)

            current_best = scored[0][1]
            if best_fitness is not None:
                if abs(current_best - best_fitness) < self.CONVERGENCE_THRESHOLD:
                    break
            best_fitness = current_best

            # Yield ogni 10 generazioni per non bloccare la UI
            if gen % 10 == 0:
                if on_progress:
                    on_progress(gen / self.GENERATIONS, f"Gen {gen}")
                await asyncio.sleep(0)

            elite = [s[0] for s in scored[:self.ELITE_SIZE]]
            children = list(elite)
            while len(children) < self.POP_SIZE:
                p1 = self._tournament(scored)
                p2 = self._tournament(scored)
                child = self._crossover(p1, p2)
                if random.random() < self.MUTATION_RATE:
                    child = self._mutate(child)
                children.append(child)
            population = children

        scored = [(ind, self._fitness(ind)) for ind in population]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _tournament(self, scored):
        contestants = random.sample(scored, self.TOURNAMENT_SIZE)
        return max(contestants, key=lambda x: x[1])[0]

    def _random_schedule(self):
        schedule = list(range(len(self.scenes)))
        random.shuffle(schedule)
        return schedule

    def _fitness(self, individual):
        # Implementazione specifica del dominio
        return 0.0

    def _crossover(self, p1, p2):
        size = len(p1)
        start, end = sorted(random.sample(range(size), 2))
        child = [None] * size
        child[start:end] = p1[start:end]
        fill = [g for g in p2 if g not in child[start:end]]
        idx = 0
        for i in range(size):
            if child[i] is None:
                child[i] = fill[idx]
                idx += 1
        return child

    def _mutate(self, individual):
        a, b = random.sample(range(len(individual)), 2)
        individual[a], individual[b] = individual[b], individual[a]
        return individual
```

⚠️ Per computazioni CPU-intensive su dataset grandi, sostituire `await asyncio.sleep(0)` con `concurrent.futures.ProcessPoolExecutor` per la funzione fitness, mantenendo il loop generazionale nel thread principale. Con 100 individui e 500 generazioni, la fitness è il collo di bottiglia.

### 4.4 FountainParser

In Swift, **FountainParser** parsa script in formato Fountain (formato testo standard per sceneggiature) e righe da PDF con euristica per PDFKit. Usa `FOUNTAIN_LINES_PER_PAGE = 56` (Courier 12pt US Letter). Il risultato è un array di `ParsedScene` con sceneNumber, location, intExt, dayNight, pageStart, pageEnd, synopsis, characters, props, vehicles, specialEffects.

```python
import re

FOUNTAIN_LINES_PER_PAGE = 56


class ParsedScene:
    def __init__(self):
        self.scene_number = ""
        self.location = ""
        self.int_ext = "INT"
        self.day_night = "GIORNO"
        self.page_start = 0.0
        self.page_end = 0.0
        self.synopsis = ""
        self.characters = []
        self.props = []
        self.vehicles = []
        self.special_effects = []


SCENE_HEADING_RE = re.compile(
    r"^(\.)?(?P<ie>INT|EXT|INT/EXT)[.\s]+(?P<loc>.+?)"
    r"\s*[-–—]\s*(?P<dn>GIORNO|NOTTE|ALBA|TRAMONTO|CONTINUO|DAY|NIGHT|DAWN|DUSK)",
    re.IGNORECASE
)

CHARACTER_RE = re.compile(r"^[A-Z][A-Z\s.'-]{1,40}$")


class FountainParser:
    def parse(self, text):
        lines = text.splitlines()
        scenes = []
        current = None
        line_num = 0

        for line in lines:
            line_num += 1
            stripped = line.strip()
            m = SCENE_HEADING_RE.match(stripped)
            if m:
                if current:
                    current.page_end = line_num / FOUNTAIN_LINES_PER_PAGE
                    scenes.append(current)
                current = ParsedScene()
                current.int_ext = m.group("ie").upper()
                current.location = m.group("loc").strip()
                current.day_night = self._normalize_daynight(
                    m.group("dn")
                )
                current.scene_number = str(len(scenes) + 1)
                current.page_start = line_num / FOUNTAIN_LINES_PER_PAGE
                continue

            if current and stripped and CHARACTER_RE.match(stripped):
                name = stripped.split("(")[0].strip()
                if name and name not in current.characters:
                    current.characters.append(name)

            if current:
                current.synopsis += stripped + " "

        if current:
            current.page_end = line_num / FOUNTAIN_LINES_PER_PAGE
            scenes.append(current)

        for s in scenes:
            s.synopsis = s.synopsis.strip()

        return scenes

    def _normalize_daynight(self, value):
        mapping = {
            "DAY": "GIORNO", "NIGHT": "NOTTE",
            "DAWN": "ALBA", "DUSK": "TRAMONTO",
        }
        v = value.upper()
        return mapping.get(v, v)
```

⚠️ La costante `EIGHTHS_CALC_LINES_PER_PAGE = 55` va usata separatamente nel calcolatore da posizione PDF raw (EighthsCalculator), non nel FountainParser. Confondere le due costanti produce derive sistematiche nel conteggio pagine.

### 4.5 BreakdownOrchestrator

In Swift, **BreakdownOrchestrator** ha 5 dipendenze (parser, nlpPipeline, database, feedbackLoop, mlInference) e una pipeline a 6 step: parse → NLP extraction per scena → insert DB (scena + personaggi + elementi NLP con soglie confidence da UserDefaults) → feedback loop trackImport → aggiornamento frontmatter → completamento. Il progresso è comunicato via closure `(Double, String)`.

```python
class BreakdownOrchestrator:
    def __init__(self, parser, nlp_pipeline, database,
                 feedback_loop, ml_inference):
        self._parser = parser
        self._nlp = nlp_pipeline
        self._db = database
        self._feedback = feedback_loop
        self._ml = ml_inference

    async def run_breakdown(self, file_path, project_id,
                            min_confidence=0.60, on_progress=None):
        # Step 1: parse
        if on_progress:
            on_progress(0.0, "Parsing script...")
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        parsed_scenes = self._parser.parse(text)
        total = len(parsed_scenes)
        if total == 0:
            return

        for i, ps in enumerate(parsed_scenes):
            pct = (i + 1) / total

            # Step 2: NLP extraction
            if on_progress:
                on_progress(pct * 0.6, f"NLP scena {i+1}/{total}")
            elements = await self._nlp.process_scene(
                ps.synopsis, ps.location
            )

            # Inferenza ML opzionale
            ml_elements = self._ml.predict(
                f"{ps.int_ext} {ps.location} "
                f"{ps.day_night}: {ps.synopsis}"
            )
            elements = self._merge_ml(elements, ml_elements)

            # Step 3: insert DB
            start_e = Eighths.from_decimal(ps.page_start)
            end_e = Eighths.from_decimal(ps.page_end)

            scene_id = self._db.execute(
                "INSERT INTO scenes (project_id, scene_number, location, "
                "int_ext, day_night, page_start_whole, page_start_eighths, "
                "page_end_whole, page_end_eighths, synopsis) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (project_id, ps.scene_number, ps.location,
                 ps.int_ext, ps.day_night,
                 start_e.whole, start_e.eighths,
                 end_e.whole, end_e.eighths, ps.synopsis)
            ).lastrowid

            for char in ps.characters:
                self._db.execute(
                    "INSERT OR IGNORE INTO scene_elements "
                    "(scene_id, category, element_name) VALUES (?,?,?)",
                    (scene_id, "Cast", char)
                )

            for elem in elements:
                if (elem.ai_confidence or 0) >= min_confidence:
                    self._db.execute(
                        "INSERT OR IGNORE INTO scene_elements "
                        "(scene_id, category, element_name, "
                        "ai_suggested, ai_confidence) "
                        "VALUES (?,?,?,1,?)",
                        (scene_id, elem.category, elem.element_name,
                         elem.ai_confidence)
                    )

            # Step 4: feedback
            self._feedback.track_import(scene_id, len(elements))

            if on_progress:
                on_progress(0.6 + pct * 0.3, f"Inserita scena {i+1}")

        # Step 5-6: frontmatter e completamento
        if on_progress:
            on_progress(1.0, "Breakdown completato")

    def _merge_ml(self, nlp_elements, ml_elements):
        existing = {(e.category, e.element_name) for e in nlp_elements}
        for ml_e in ml_elements:
            if (ml_e.category, ml_e.element_name) not in existing:
                nlp_elements.append(ml_e)
        return nlp_elements
```

⚠️ La soglia `min_confidence` in Swift viene letta da UserDefaults, in Python può essere configurata in `QSettings` o passata come parametro. I personaggi estratti dal parser vengono inseriti senza filtro confidence (sono deterministici), mentre gli elementi NLP/ML passano per la soglia.

### 4.6 ServiceContainer → contenitore DI Python

In Swift, **ServiceContainer** usa `lazy var` con dependency injection esplicita e un fallback a 3 livelli per ML: modello utente in Application Support → modello bundle → DummyInference.

```python
import functools
import os


class ServiceContainer:
    def __init__(self, db_path):
        self._db_path = db_path

    @functools.cached_property
    def database(self):
        return DatabaseManager(self._db_path)

    @functools.cached_property
    def term_normalizer(self):
        return TermNormalizer()

    @functools.cached_property
    def vocabulary_manager(self):
        return VocabularyManager(self.database)

    @functools.cached_property
    def nlp_pipeline(self):
        return NLPPipelineCoordinator(
            ner=NERExtractor(),
            vocabulary=self.vocabulary_manager,
            pattern_matcher=DynamicPatternMatcher(),
            context_engine=ContextEngine(),
            normalizer=self.term_normalizer,
        )

    @functools.cached_property
    def ml_inference(self):
        # Fallback a 3 livelli come in Swift
        user_model = os.path.expanduser(
            "~/Library/Application Support/Gliamispo/model.onnx"
        )
        if os.path.exists(user_model):
            return OnnxInference(user_model)
        bundle_model = os.path.join(
            os.path.dirname(__file__), "resources", "model.pkl"
        )
        if os.path.exists(bundle_model):
            return SklearnInference(bundle_model)
        return DummyInference()

    @functools.cached_property
    def feedback_loop(self):
        return FeedbackLoopService(self.database)

    @functools.cached_property
    def breakdown_orchestrator(self):
        return BreakdownOrchestrator(
            parser=FountainParser(),
            nlp_pipeline=self.nlp_pipeline,
            database=self.database,
            feedback_loop=self.feedback_loop,
            ml_inference=self.ml_inference,
        )

    @functools.cached_property
    def scene_repository(self):
        return SceneRepository(self.database)
```

⚠️ `functools.cached_property` è thread-safe per design in Python 3.12+. Su Python 3.11, le prime chiamate concorrenti possono creare istanze duplicate — se serve garanzia, usare un `threading.Lock` nel `__init__` e controllare manualmente. Per questo progetto, dato che il ServiceContainer viene inizializzato nel thread principale prima che i worker partano, il rischio è minimo.

### 4.7 FeedbackLoopService e ciclo ML

In Swift, **FeedbackLoopService** è un actor con una `feedbackQueue` interna usata solo da `trackImport()`. I metodi `recordCategoryChange()`, `trackVerification()` e `trackUserCorrection()` scrivono direttamente nel DB. Bug confermato: `flush()` svuota la queue in memoria ma non persiste nulla nel database. La soglia di 50 correzioni non ancora usate per training triggera il retraining.

```python
import threading


class FeedbackLoopService:
    FLUSH_THRESHOLD = 10
    RETRAIN_THRESHOLD = 50

    def __init__(self, database):
        self._db = database
        self._queue = []
        self._lock = threading.Lock()
        self._on_retrain_needed = None  # callback o signal PyQt6

    def track_import(self, scene_id, element_count):
        with self._lock:
            self._queue.append({
                "scene_id": scene_id,
                "element_count": element_count,
            })
            if len(self._queue) >= self.FLUSH_THRESHOLD:
                self._flush()

    def _flush(self):
        # CORREZIONE BUG SWIFT: persiste prima di svuotare
        for entry in self._queue:
            self._db.execute(
                "INSERT INTO training_data (scene_id, scene_text, "
                "created_at) "
                "SELECT id, synopsis, strftime('%s','now') "
                "FROM scenes WHERE id = ? AND NOT EXISTS ("
                "  SELECT 1 FROM training_data td "
                "  WHERE td.scene_id = scenes.id"
                ")",
                (entry["scene_id"],)
            )
        self._queue.clear()

    def record_category_change(self, element_id, scene_id,
                               before_cat, after_cat, confidence):
        self._db.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action, before_category, "
            "after_category, original_confidence) "
            "VALUES (?,?,'MODIFY_CATEGORY',?,?,?)",
            (element_id, scene_id, before_cat, after_cat, confidence)
        )
        self._check_retrain()

    def track_verification(self, element_id, scene_id, accepted):
        action = "VERIFY" if accepted else "REJECT"
        self._db.execute(
            "INSERT INTO user_corrections "
            "(element_id, scene_id, action) VALUES (?,?,?)",
            (element_id, scene_id, action)
        )
        self._check_retrain()

    def _check_retrain(self):
        row = self._db.execute(
            "SELECT COUNT(*) FROM user_corrections "
            "WHERE trained_at IS NULL"
        ).fetchone()
        if row and row[0] >= self.RETRAIN_THRESHOLD:
            if self._on_retrain_needed:
                self._on_retrain_needed()
```

⚠️ In Swift, la soglia retraining viene comunicata via `NotificationCenter.default.post`. In PyQt6, l'equivalente è un `pyqtSignal` su un `QObject`, oppure un callback diretto. Il campo `_on_retrain_needed` va collegato al segnale appropriato durante l'inizializzazione nel ServiceContainer.

### 4.8 OnDeviceInference → scikit-learn / ONNX / regole pure

In Swift, **OnDeviceInference** wrappa `NLModel` (CoreML) per classificazione testuale. Arricchisce l'input con prefisso contesto scena ("INT CUCINA GIORNO: ..."), chiama `predictedLabelHypotheses(for:maximumCount:5)` e filtra ipotesi con confidence >= 0.30. **DummyInference** è il fallback (array vuoto). `NLModel` non è thread-safe.

```python
import pickle
import os


class SklearnInference:
    def __init__(self, model_path):
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        self._vectorizer = bundle["vectorizer"]
        self._clf = bundle["classifier"]
        self._lock = __import__("threading").Lock()

    def predict(self, text, max_results=5, min_confidence=0.30):
        with self._lock:
            X = self._vectorizer.transform([text])
            if hasattr(self._clf, "decision_function"):
                scores = self._clf.decision_function(X)[0]
            else:
                scores = self._clf.predict_proba(X)[0]
            classes = self._clf.classes_

        pairs = sorted(
            zip(classes, scores), key=lambda x: x[1], reverse=True
        )
        results = []
        for cat, score in pairs[:max_results]:
            conf = max(0, min(1, score))
            if conf >= min_confidence:
                results.append(SceneElement(
                    category=cat,
                    element_name=cat,
                    ai_suggested=1,
                    ai_confidence=conf,
                    detection_method="sklearn",
                ))
        return results


class OnnxInference:
    def __init__(self, model_path):
        import onnxruntime as ort
        self._session = ort.InferenceSession(model_path)
        self._lock = __import__("threading").Lock()

    def predict(self, text, max_results=5, min_confidence=0.30):
        with self._lock:
            inputs = {self._session.get_inputs()[0].name: [[text]]}
            outputs = self._session.run(None, inputs)
        # Parsing output dipende dal formato del modello convertito
        return []


class DummyInference:
    def predict(self, text, max_results=5, min_confidence=0.30):
        return []
```

⚠️ scikit-learn è la scelta primaria per nuovi training (SGDClassifier + TF-IDF consente training incrementale). ONNX Runtime è opzionale, utile solo se si convertono modelli .mlmodel esistenti tramite `coremltools` + `onnxmltools`. Il fallback minimo è `DummyInference` (array vuoto) oppure regole pure basate su `vocabulary_terms` dal database, che non richiedono alcun modello ma offrono recall limitata.

---

## 5. Layer UI — Swift/SwiftUI → PyQt6

| Componente SwiftUI | Widget PyQt6 | Note |
|---|---|---|
| NavigationSplitView | QSplitter (3 pane) | Orientamento orizzontale |
| List + ForEach | QListWidget / QTreeView + QStandardItemModel | |
| @State / @Binding | Signal/Slot tra widget | |
| @Published + ObservableObject | pyqtSignal su QObject | Sostituisce Combine |
| @StateObject | Istanza persistente nel parent widget | |
| @EnvironmentObject | Passaggio esplicito o singleton | |
| Sheet / .sheet() | QDialog | Modal con exec() |
| Alert / .alert() | QMessageBox | |
| TabView | QTabWidget | |
| Table (SwiftUI) | QTableView + QStandardItemModel | |
| TextField | QLineEdit | |
| TextEditor | QTextEdit | |
| Toggle | QCheckBox | |
| Picker | QComboBox | |
| Slider | QSlider | |
| ProgressView | QProgressBar | |
| Button | QPushButton | |
| Menu / ContextMenu | QMenu | |
| Toolbar | QToolBar | |
| FileImporter | QFileDialog.getOpenFileName | |

Snippet PyQt6 per la finestra principale a tre colonne:

```python
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QListWidget, QWidget,
    QVBoxLayout, QLabel, QTableView, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject


class ProjectSignals(QObject):
    project_selected = pyqtSignal(int)
    scene_selected = pyqtSignal(int)
    breakdown_progress = pyqtSignal(float, str)


class MainWindow(QMainWindow):
    def __init__(self, container):
        super().__init__()
        self._container = container
        self._signals = ProjectSignals()
        self.setWindowTitle("Gliamispo")
        self.resize(1400, 800)
        self._project_ids = []
        self._scene_ids = []

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Colonna 1: lista progetti
        self._project_list = QListWidget()
        self._project_list.currentRowChanged.connect(
            self._on_project_selected
        )
        splitter.addWidget(self._project_list)

        # Colonna 2: lista scene
        self._scene_list = QListWidget()
        self._scene_list.currentRowChanged.connect(
            self._on_scene_selected
        )
        splitter.addWidget(self._scene_list)

        # Colonna 3: dettaglio scena + elementi
        detail = QWidget()
        layout = QVBoxLayout(detail)
        self._scene_label = QLabel("Seleziona una scena")
        self._elements_table = QTableView()
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._scene_label)
        layout.addWidget(self._elements_table)
        layout.addWidget(self._progress)
        splitter.addWidget(detail)

        splitter.setSizes([250, 300, 850])
        self.setCentralWidget(splitter)

        self._signals.breakdown_progress.connect(self._update_progress)

    def _on_project_selected(self, row):
        if row >= 0:
            project_id = self._project_ids[row]
            self._signals.project_selected.emit(project_id)
            self._load_scenes(project_id)

    def _on_scene_selected(self, row):
        if row >= 0:
            scene_id = self._scene_ids[row]
            self._signals.scene_selected.emit(scene_id)

    def _load_scenes(self, project_id):
        rows = self._container.database.execute(
            "SELECT id, scene_number, location FROM scenes "
            "WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        self._scene_list.clear()
        self._scene_ids = []
        for r in rows:
            self._scene_list.addItem(f"{r[1]} — {r[2]}")
            self._scene_ids.append(r[0])

    def _update_progress(self, value, message):
        self._progress.setVisible(value < 1.0)
        self._progress.setValue(int(value * 100))
        self.statusBar().showMessage(message)
```

Il pattern `pyqtSignal` su `ProjectSignals` sostituisce sia `@Published` che `Combine.PassthroughSubject` dello SwiftUI originale. Ogni componente che in Swift era un `@Published var` diventa un signal emesso quando il valore cambia, con slot che aggiornano i widget dipendenti.

---

## 6. Trappole Comuni e Anti-Pattern

L'aritmetica Eighths è la trappola più insidiosa nella migrazione. In Swift, la struct Eighths costruisce separatamente i due valori (inizio e fine pagina) dal decimale, poi sottrae i `totalEighths`. La tentazione in Python è semplificare con `round((page_end - page_start) * 8)`, che funziona nella maggior parte dei casi ma produce risultati errati quando le posizioni decimali provengono da divisioni di riga per pagina (tipicamente riga/56 nel FountainParser). Esempio concreto: una scena dalla riga 17 alla riga 89, con FOUNTAIN_LINES_PER_PAGE=56 — `page_start = 17/56 ≈ 0.3036`, `page_end = 89/56 ≈ 1.5893`. Il metodo diretto calcola `round((1.5893 - 0.3036) * 8) = round(10.286) = 10` eighths. Il metodo struct calcola `Eighths.from_decimal(0.3036)` → `round(0.3036 * 8) = round(2.429) = 2` → `Eighths(0,2)`, poi `Eighths.from_decimal(1.5893)` → `round(0.5893 * 8) = round(4.714) = 5` → `Eighths(1,5)`, differenza `13 - 2 = 11` eighths. Il risultato diverge: 10 vs 11, un'intera ottava di pagina persa. Questo accade perché la quantizzazione ai bordi è non-lineare: arrotondare la differenza grezza non equivale a sottrarre differenze già arrotondate. Il pattern sicuro è sempre: costruire i due Eighths da decimale, poi sottrarre.

La thread-safety SQLite richiede attenzione specifica. In Swift, SQLiteManager usa un singolo `NSLock` (`dbLock`) con lock/defer in 44 metodi, proteggendo una singola connessione `OpaquePointer`. In Python, `threading.Lock` sulla singola connessione con `check_same_thread=False` replica questo pattern. Tuttavia, se si decide di usare connessioni multiple (per esempio una per thread, come suggeriscono alcuni pattern Python), il Lock non basta: ogni connessione SQLite acquisisce lock a livello di file, e scritture concorrenti in WAL mode possono comunque produrre `SQLITE_BUSY`. La soluzione corretta con connessione singola + Lock è sufficiente e fedele all'architettura Swift originale.

La tabella `ai_patterns` è usata attivamente da **AIAssistant.swift** (INSERT, SELECT, UPDATE) ma non ha un `CREATE TABLE IF NOT EXISTS` nel codebase Swift — è un bug latente che si manifesta solo quando AIAssistant viene invocato prima che qualche altro path crei la tabella accidentalmente. In Python va creata esplicitamente nello schema DDL iniziale, altrimenti ogni operazione di AIAssistant fallirà con "no such table".

La traduzione di NLPPipelineCoordinator da actor Swift ad asyncio Python non è 1:1. L'actor Swift serializza automaticamente tutti gli accessi ai suoi metodi e proprietà, garantendo thread-safety implicita. In Python, `asyncio` è single-threaded per design nel suo event loop, ma in PyQt6 il loop asyncio non può girare sul thread principale (occupato dall'event loop Qt). La soluzione è un `QThread` dedicato con il proprio `asyncio.run()`, comunicando con la GUI via signal/slot. L'alternativa è `QThreadPool` con `QRunnable`, ma perde i benefici di `asyncio.gather` per le estrazioni parallele. Il `QThread` dedicato è il compromesso migliore.

CoreML (`NLModel`) non è disponibile fuori da macOS, rendendo impossibile usare direttamente i modelli .mlmodelc esistenti. scikit-learn con `SGDClassifier` + `TfidfVectorizer` è la scelta primaria per nuovi training perché supporta training incrementale (`partial_fit`), è leggero, e si integra nativamente in Python. Per riusare modelli CoreML esistenti, la catena di conversione è `coremltools` → `onnxmltools` → `.onnx`, caricabile con `onnxruntime`; questo path è opzionale e richiede che la conversione avvenga su macOS. Il fallback minimo è `DummyInference` (ritorna array vuoto) o regole pure che matchano `vocabulary_terms` dal database senza alcun modello ML.

La discrepanza `linesPerPage` tra FountainParser (56) e EighthsCalculator (55) è intenzionale nel codebase Swift e va mantenuta in Python. Confondere le due costanti produce una deriva sistematica: usare 56 nel calcolatore da posizione PDF raw sovrastima la pagina di circa 1.8%, accumulando errori su script lunghi. Definire `FOUNTAIN_LINES_PER_PAGE = 56` nel modulo parser e `EIGHTHS_CALC_LINES_PER_PAGE = 55` nel modulo calcolatore, senza mai condividerle.

**TermNormalizer** in Swift viene eseguito dentro un `withTaskGroup` nel NLPPipelineCoordinator tramite `await MainActor.run { ... }`, il che lo serializza sul thread principale. Questo implica che TermNormalizer non è thread-safe internamente e dipende dalla serializzazione esterna. In Python, il `_norm_lock` (asyncio.Lock) nel NLPPipelineCoordinator replica questa garanzia, ma solo se tutte le chiamate a `normalize()` passano per il coordinatore. Se TermNormalizer viene usato direttamente da altri componenti, va protetto con un `threading.Lock` proprio.

Il bug `flush()` nel **FeedbackLoopService** Swift è un no-op silenzioso: svuota la `feedbackQueue` in memoria senza persistere nulla nel database. Se replicato in Python, le entry di training accumulate da `trackImport()` vengono perse ogni 10 chiamate. La correzione nel codice Python sopra inserisce le entry in `training_data` prima di chiamare `self._queue.clear()`, assicurando che nessun dato di feedback vada perso.

Il bug V6 scenes_new in Swift non include `estimated_crew_size` né `special_requirements` nella definizione della tabella `scenes_new` e nel `INSERT FROM scenes`. Queste colonne erano state aggiunte a `scenes` dalla migrazione V3, ma V6 step 5 le perde durante il rename. Su database Swift importati in Python che hanno già subito V6, queste colonne sono irrimediabilmente perse. La migrazione Python V6 corregge il bug includendo entrambe le colonne, ma per database Swift già migrati a V6 è necessario un recovery manuale da `scenes_backup_v5` (che V6 crea preventivamente e lascia nel DB).

Il vincolo `UNIQUE(scene_id, category, element_name)` introdotto da V6 step 10 impatta il metodo `inserisciElemento()`: un INSERT con combinazione duplicata ora fallisce con `UNIQUE constraint failed`. Lo schema Python iniziale include questo vincolo fin dall'inizio, quindi anche installazioni fresche ne sono affette. Per gestire import di database Swift pre-V6 che potrebbero contenere duplicati, è necessario un passo di de-duplicazione preventiva prima dell'import: raggruppare per `(scene_id, category, element_name)`, mantenere la riga con `id` più alto, e eliminare le altre. Nel codice applicativo, usare `INSERT OR IGNORE` oppure `INSERT OR REPLACE` a seconda della semantica desiderata.

---

## 7. Piano di Migrazione a Fasi

### Fase 1 — Fondamenta (settimane 1-2)

Obiettivo: struttura progetto Python, ambiente di sviluppo, CI base. Creare la struttura di directory, configurare `pyproject.toml` con tutte le dipendenze, impostare pytest e linting, creare lo script di bootstrap del database.

Componenti: `pyproject.toml`, struttura directory, `conftest.py`, `bootstrap_db.py`.

Il rischio tecnico è basso; l'unico punto d'attenzione è assicurarsi che la versione di SQLite bundlata con Python 3.11+ supporti `GENERATED ALWAYS AS ... STORED` (richiede SQLite ≥ 3.31.0, incluso in Python 3.11+).

Criterio di completamento:

```bash
pytest tests/test_bootstrap.py -v
```

### Fase 2 — Database e Modelli (settimane 3-4)

Obiettivo: DatabaseManager completo, schema DDL, tutte le migrazioni V2–V10, modelli dataclass, test di regressione su ogni migrazione.

Componenti: `database/manager.py`, `database/schema.sql`, `database/migrations.py`, `models/project.py`, `models/scene.py`, `models/scene_element.py`, `models/eighths.py`.

Il rischio tecnico è medio-alto per le migrazioni V6 (12 step) e V10. I test devono verificare che ogni migrazione sia idempotente, che i conteggi pre/post rename corrispondano, e che i trigger funzionino correttamente.

Criterio di completamento:

```bash
pytest tests/database/test_schema.py tests/database/test_migrations.py tests/models/test_eighths.py -v
```

### Fase 3 — NLP e Parsing (settimane 5-7)

Obiettivo: FountainParser, NLPPipelineCoordinator con le 5 dipendenze, TermNormalizer con serializzazione corretta, VocabularyManager.

Componenti: `parsing/fountain_parser.py`, `nlp/pipeline.py`, `nlp/ner_extractor.py`, `nlp/vocabulary_manager.py`, `nlp/pattern_matcher.py`, `nlp/context_engine.py`, `nlp/term_normalizer.py`.

Il rischio tecnico è medio. La pipeline NLP è il componente con più interdipendenze e il test end-to-end richiede uno script Fountain di riferimento con risultati attesi noti.

Criterio di completamento:

```bash
pytest tests/parsing/test_fountain.py tests/nlp/test_pipeline.py -v
```

### Fase 4 — Scheduling e ML (settimane 8-10)

Obiettivo: GeneticScheduler, OnDeviceInference (scikit-learn), FeedbackLoopService (con bug flush corretto), BreakdownOrchestrator completo, MLScheduler.

Componenti: `scheduling/genetic.py`, `ml/inference.py`, `ml/feedback_loop.py`, `breakdown/orchestrator.py`, `ml/scheduler.py`, `ml/analytics.py`.

Il rischio tecnico è alto per l'integrazione ML: il training iniziale del modello scikit-learn richiede dati di training dal database, e il GeneticScheduler deve produrre risultati deterministici con seed fisso per i test.

Criterio di completamento:

```bash
pytest tests/scheduling/test_genetic.py tests/ml/test_inference.py tests/breakdown/test_orchestrator.py -v
```

### Fase 5 — UI PyQt6 (settimane 11-14)

Obiettivo: finestra principale a tre colonne, dialoghi CRUD per progetti/scene/elementi, integrazione signal/slot con i componenti di backend, progress bar per breakdown, import/export.

Componenti: `ui/main_window.py`, `ui/project_dialog.py`, `ui/scene_detail.py`, `ui/breakdown_progress.py`, `ui/call_sheet_view.py`, `ui/schedule_view.py`.

Il rischio tecnico è medio. Il punto critico è l'integrazione asyncio/Qt: il breakdown orchestrator è asincrono e deve comunicare progresso alla UI senza bloccarla. Testare con `pytest-qt`.

Criterio di completamento:

```bash
pytest tests/ui/test_main_window.py -v
```

### Fase 6 — Export, Test, Hardening (settimane 15-16)

Obiettivo: export PDF call sheets, import di database Swift esistenti (con de-duplicazione e validazione), test di integrazione completi, gestione errori robusta, packaging.

Componenti: `export/call_sheet_pdf.py`, `import/swift_db_importer.py`, `tests/integration/`, script di packaging.

Il rischio tecnico è medio. L'import di DB Swift pre-V6 richiede validazione dei CHECK constraint e de-duplicazione degli elementi. Il packaging cross-platform (PyInstaller o cx_Freeze) può presentare problemi con le dipendenze native di PyQt6.

Criterio di completamento:

```bash
pytest tests/ -v --tb=short
```

---

## 8. Configurazione Ambiente e Bootstrap

### pyproject.toml

```toml
[project]
name = "gliamispo"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "PyQt6>=6.5",
    "scikit-learn>=1.3",
]

[project.optional-dependencies]
onnx = ["onnxruntime>=1.16"]
dev = [
    "pytest>=7.4",
    "pytest-qt>=4.2",
    "pytest-asyncio>=0.21",
    "ruff>=0.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 88
```

### Script di bootstrap del DB

```python
#!/usr/bin/env python3
# bootstrap_db.py
import sqlite3
import os
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
DB_DIR = os.path.expanduser("~/Library/Application Support/Gliamispo")
DB_PATH = os.path.join(DB_DIR, "gliamispo.sqlite")


def bootstrap(db_path=None):
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    # Importa ed esegui migrazioni
    from database.migrations import run_migrations
    run_migrations(conn)

    conn.close()
    return path


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else None
    result = bootstrap(p)
    print(f"Database inizializzato: {result}")
```

### Struttura directory del progetto

```
gliamispo-python/
├── pyproject.toml
├── bootstrap_db.py
├── src/
│   └── gliamispo/
│       ├── __init__.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── project.py
│       │   ├── scene.py
│       │   ├── scene_element.py
│       │   └── eighths.py
│       ├── database/
│       │   ├── __init__.py
│       │   ├── manager.py
│       │   ├── migrations.py
│       │   └── schema.sql
│       ├── nlp/
│       │   ├── __init__.py
│       │   ├── pipeline.py
│       │   ├── ner_extractor.py
│       │   ├── vocabulary_manager.py
│       │   ├── pattern_matcher.py
│       │   ├── context_engine.py
│       │   └── term_normalizer.py
│       ├── parsing/
│       │   ├── __init__.py
│       │   └── fountain_parser.py
│       ├── scheduling/
│       │   ├── __init__.py
│       │   └── genetic.py
│       ├── ml/
│       │   ├── __init__.py
│       │   ├── inference.py
│       │   ├── feedback_loop.py
│       │   ├── scheduler.py
│       │   └── analytics.py
│       ├── breakdown/
│       │   ├── __init__.py
│       │   └── orchestrator.py
│       ├── export/
│       │   ├── __init__.py
│       │   └── call_sheet_pdf.py
│       ├── import_/
│       │   ├── __init__.py
│       │   └── swift_db_importer.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── main_window.py
│       │   ├── project_dialog.py
│       │   ├── scene_detail.py
│       │   ├── breakdown_progress.py
│       │   ├── call_sheet_view.py
│       │   └── schedule_view.py
│       ├── services/
│       │   ├── __init__.py
│       │   └── container.py
│       └── resources/
│           └── model.pkl
└── tests/
    ├── conftest.py
    ├── test_bootstrap.py
    ├── database/
    │   ├── test_schema.py
    │   └── test_migrations.py
    ├── models/
    │   └── test_eighths.py
    ├── parsing/
    │   └── test_fountain.py
    ├── nlp/
    │   └── test_pipeline.py
    ├── scheduling/
    │   └── test_genetic.py
    ├── ml/
    │   └── test_inference.py
    ├── breakdown/
    │   └── test_orchestrator.py
    ├── ui/
    │   └── test_main_window.py
    └── integration/
        └── test_full_pipeline.py
```

### Comando di verifica ambiente

```bash
python -c "
import sys, sqlite3
assert sys.version_info >= (3, 11), f'Python 3.11+ richiesto, trovato {sys.version}'
v = sqlite3.sqlite_version_info
assert v >= (3, 31, 0), f'SQLite 3.31+ richiesto per GENERATED ALWAYS, trovato {sqlite3.sqlite_version}'
from PyQt6.QtWidgets import QApplication
import sklearn
print(f'OK: Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}, '
      f'scikit-learn {sklearn.__version__}')
"
```
