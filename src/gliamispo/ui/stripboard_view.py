"""
stripboard_view.py — con pannello dettaglio scena + sinossi AI offline
"""
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSplitter, QSpinBox, QMessageBox,
    QFileDialog, QInputDialog, QPlainTextEdit,
)
from PySide6.QtCore import Qt, Signal, QThread, QMimeData, QByteArray, QPoint, QTimer
from PySide6.QtGui import (
    QCursor, QDrag, QPixmap, QPainter,
    QDragEnterEvent, QDragMoveEvent, QDropEvent,
)
from gliamispo.ui import theme
from gliamispo.models.eighths import Eighths
from gliamispo.scheduling.genetic import GeneticScheduler, save_schedule_to_db
from gliamispo.export import export_stripboard, Format
from gliamispo.services.synopsis_generator import (
    generate_synopsis, extract_scene_text,
)


# ---------------------------------------------------------------------------
# SchedulerWorker (invariato)
# ---------------------------------------------------------------------------

class SchedulerWorker(QThread):
    progress = Signal(float, str)
    finished = Signal()
    error    = Signal(str)

    def __init__(self, scenes, constraints, db, project_id):
        super().__init__()
        self._scenes      = scenes
        self._constraints = constraints
        self._db          = db
        self._project_id  = project_id

    def run(self):
        import asyncio
        try:
            scheduler = GeneticScheduler(self._scenes, self._constraints)
            best = asyncio.run(scheduler.optimize(on_progress=self.progress.emit))
            ordered = [self._scenes[i] for i in best]
            max_h = self._constraints.get("max_hours_per_day", 10.0)
            save_schedule_to_db(self._db, self._project_id, ordered, max_h)
            self.explanations = scheduler.explain_schedule(best)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# SynopsisWorker — esegue la summarization in background (100% offline)
# ---------------------------------------------------------------------------

class SynopsisWorker(QThread):
    """
    Esegue la summarization estrattiva TF-IDF in un thread separato
    per non bloccare la UI durante l'elaborazione.
    Nessuna rete, nessuna chiave API.
    """
    done  = Signal(str)   # sinossi generata
    error = Signal(str)   # messaggio di errore

    def __init__(self, raw_blocks: list):
        super().__init__()
        self._raw_blocks = raw_blocks

    def run(self):
        try:
            synopsis = generate_synopsis(self._raw_blocks, max_sentences=2)
            self.done.emit(synopsis)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# SceneStripRow (invariato)
# ---------------------------------------------------------------------------

class SceneStripRow(QFrame):
    clicked = Signal(int, bool)
    duration_edit_requested = Signal(int)

    def __init__(self, scene, compact=False, parent=None):
        super().__init__(parent)
        self._scene_id = scene["id"]
        self._selected = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        h = 26 if compact else 44
        self.setFixedHeight(h)
        ie = scene.get("int_ext", "INT")
        dn = scene.get("day_night", "GIORNO")
        strip_c = theme.strip_color_for(ie, dn)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 8, 0)
        main_layout.setSpacing(0)
        strip = QFrame()
        strip.setFixedWidth(6)
        strip.setStyleSheet(f"background-color: {strip_c.name()};")
        main_layout.addWidget(strip)
        num = scene.get("scene_number", "")
        num_label = QLabel(num)
        font_size = 11 if compact else 12
        num_label.setFont(theme.font_mono(font_size, bold=True))
        num_label.setFixedWidth(40)
        num_label.setStyleSheet(f"color: {theme.TEXT0.name()};")
        main_layout.addWidget(num_label)
        rev_badge = scene.get("revision_badge")
        if rev_badge:
            badge_lbl = QLabel(rev_badge)
            badge_lbl.setFont(theme.font_ui(8, bold=True))
            badge_lbl.setStyleSheet("background:#FFB6C1;color:#000;border-radius:3px;padding:1px 4px;")
            main_layout.addWidget(badge_lbl)
        if not compact:
            div = QFrame()
            div.setFixedWidth(1)
            div.setFixedHeight(32)
            div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
            main_layout.addWidget(div)
        mini = QFrame()
        mini.setFixedWidth(4)
        mini.setStyleSheet(f"background-color: {strip_c.name()}; border-radius: 2px;")
        main_layout.addWidget(mini)
        ie_label = QLabel(ie)
        ie_label.setFont(theme.font_mono(9, bold=True))
        ie_label.setStyleSheet(f"color: white; background-color: {strip_c.name()}; border-radius: 3px; padding: 1px 4px; margin-left: 4px;")
        main_layout.addWidget(ie_label)
        loc = scene.get("location", "")
        loc_label = QLabel(loc)
        loc_label.setFont(theme.font_ui(11))
        loc_label.setStyleSheet(f"color: {theme.TEXT1.name()}; padding-left: 8px;")
        main_layout.addWidget(loc_label, 1)
        dn_label = QLabel(dn)
        dn_label.setFont(theme.font_mono(9))
        dn_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        main_layout.addWidget(dn_label)
        dur = self._format_duration(scene)
        if dur:
            manual = scene.get("manual_shooting_hours", 0.0) or 0.0
            badge_text = f"✏ {dur}" if manual > 0 else dur
            dur_label = QLabel(badge_text)
            dur_label.setFont(theme.font_mono(10, bold=True))
            dur_label.setToolTip(f"Durata manuale: {manual:.1f}h — click per modificare" if manual > 0 else "Click per impostare durata manuale")
            dur_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            dur_label.setStyleSheet(f"color: {theme.TEXT2.name() if not manual else theme.GOLD_DARK.name()}; background-color: {theme.BG0.name()}; border: 1px solid {theme.qss_color(theme.BD1)}; border-radius: 4px; padding: 1px 6px; margin-left: 8px;")
            dur_label.setFixedWidth(65)
            dur_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dur_label.mousePressEvent = lambda e, sid=self._scene_id: self.duration_edit_requested.emit(sid)
            main_layout.addWidget(dur_label)
        if scene.get("requires_intimacy_coordinator"):
            ic_label = QLabel("\u2764")
            ic_label.setFixedWidth(20)
            ic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(ic_label)
        self._update_style()
        self._drag_start_pos = None

    def _format_duration(self, scene):
        w_s = scene.get("page_start_whole", 0) or 0
        e_s = scene.get("page_start_eighths", 0) or 0
        w_e = scene.get("page_end_whole", 0) or 0
        e_e = scene.get("page_end_eighths", 0) or 0
        dur = Eighths(w_e, e_e) - Eighths(w_s, e_s)
        if dur.total_eighths <= 0:
            return None
        return str(dur)

    def set_selected(self, selected):
        self._selected = selected
        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(f"SceneStripRow {{ background-color: {theme.qss_color(theme.GOLD_BG)}; }}")
        else:
            self.setStyleSheet(f"SceneStripRow {{ background-color: {theme.BG1.name()}; }}SceneStripRow:hover {{ background-color: {theme.BG2.name()}; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self.clicked.emit(self._scene_id, ctrl)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start_pos is None:
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < 8:
            return
        self._start_drag()

    def _start_drag(self):
        try:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-gliamispo-scene-id", QByteArray(self._scene_id.to_bytes(4, "big")))
            drag.setMimeData(mime)
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setOpacity(0.75)
            self.render(painter, QPoint(0, 0))
            painter.end()
            drag.setPixmap(pixmap)
            drag.setHotSpot(self._drag_start_pos if self._drag_start_pos else QPoint(0, 0))
            drag.exec(Qt.DropAction.MoveAction)
        except Exception as e:
            import traceback
            QMessageBox.warning(self, "Errore Drag", f"{e}\n\n{traceback.format_exc()}")
        finally:
            self._drag_start_pos = None


# ---------------------------------------------------------------------------
# DayBreakHeader (invariato)
# ---------------------------------------------------------------------------

class DayBreakHeader(QFrame):
    def __init__(self, day, scene_count, pages, hours, locations, n_actors=0, max_hours=10.0, parent=None):
        super().__init__(parent)
        self._day_num = day
        over_budget = hours > max_hours
        self.setFixedHeight(40)
        border_color = theme.STATUS_ERR.name() if over_budget else theme.GOLD.name()
        self.setStyleSheet(f"DayBreakHeader {{ background-color: {theme.BG3.name()}; border-top: 3px solid {border_color}; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)
        day_badge = QLabel(f"  GIORNO {day}  ")
        day_badge.setFont(theme.font_ui(11, bold=True))
        badge_bg = theme.STATUS_ERR.name() if over_budget else theme.GOLD.name()
        day_badge.setStyleSheet(f"color: white; background-color: {badge_bg}; border-radius: 4px; padding: 3px 10px;")
        layout.addWidget(day_badge)
        if locations:
            loc_text = ", ".join(locations[:3])
            if len(locations) > 3:
                loc_text += f" +{len(locations) - 3}"
            loc_label = QLabel(loc_text)
            loc_label.setFont(theme.font_ui(10))
            loc_label.setStyleSheet(f"color: {theme.TEXT2.name()};")
            layout.addWidget(loc_label)
        if n_actors > 0:
            actors_lbl = QLabel(f"{n_actors} attori")
            actors_lbl.setFont(theme.font_ui(10))
            actors_lbl.setStyleSheet(f"color: {theme.TEXT3.name()};")
            layout.addWidget(actors_lbl)
        layout.addStretch()
        hours_color = theme.STATUS_ERR.name() if over_budget else theme.TEXT2.name()
        stats_text = f"{scene_count} sc. | {pages} pag. | {hours:.1f}/{max_hours:.0f}h"
        if over_budget:
            stats_text += " ⚠"
        stats = QLabel(stats_text)
        stats.setFont(theme.font_ui(10, bold=True))
        stats.setStyleSheet(f"color: {hours_color};")
        layout.addWidget(stats)


# ---------------------------------------------------------------------------
# SceneDetailPanel — pannello laterale con sinossi offline
# ---------------------------------------------------------------------------

class SceneDetailPanel(QWidget):
    """
    Pannello informativo laterale.
    La sinossi può essere:
      - già presente nel DB (campo synopsis, scritta dal parser o in precedenza)
      - generata al volo con il pulsante "Genera" (TF-IDF, 100% offline)
      - salvata nel DB dopo la generazione per non ricalcolarla ogni volta
    """
    synopsis_saved = Signal(int, str)   # scene_id, new_synopsis

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(240)
        self.setMaximumWidth(340)
        self.setStyleSheet(f"background-color: {theme.BG2.name()};")

        self._db = None
        self._project_id = None
        self._scene_id = None
        self._raw_blocks: list = []
        self._synopsis_worker = None
        self._original_synopsis = ""  # Per tracciare modifiche

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(f"background-color: {theme.BG3.name()}; border-bottom: 1px solid {theme.qss_color(theme.BD1)};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel("Dettaglio scena")
        lbl.setFont(theme.font_ui(10, bold=True))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()};")
        h_lay.addWidget(lbl)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        outer.addWidget(scroll, 1)

        self._body = QWidget()
        self._body.setStyleSheet(f"background-color: {theme.BG2.name()};")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(14, 14, 14, 14)
        self._body_layout.setSpacing(0)
        scroll.setWidget(self._body)

        self._show_placeholder()

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def clear(self):
        self._db = None
        self._project_id = None
        self._scene_id = None
        self._raw_blocks = []
        self._show_placeholder()

    def load_scene(self, db, scene_id: int, project_id: int):
        self._db = db
        self._project_id = project_id
        self._scene_id = scene_id
        try:
            self._load_impl()
        except Exception as e:
            self._show_error(str(e))

    # ------------------------------------------------------------------
    # Costruzione UI
    # ------------------------------------------------------------------

    def _clear_body(self):
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_placeholder(self):
        self._clear_body()
        lbl = QLabel("Clicca una scena\nper vedere i dettagli")
        lbl.setFont(theme.font_ui(11))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()};")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_layout.addWidget(lbl)
        self._body_layout.addStretch()

    def _show_error(self, msg: str):
        self._clear_body()
        lbl = QLabel(f"Errore: {msg}")
        lbl.setFont(theme.font_ui(10))
        lbl.setStyleSheet(f"color: {theme.STATUS_ERR.name()};")
        lbl.setWordWrap(True)
        self._body_layout.addWidget(lbl)
        self._body_layout.addStretch()

    def _load_impl(self):
        from gliamispo.scheduling.genetic import scene_duration_hours

        db, scene_id, project_id = self._db, self._scene_id, self._project_id

        row = db.execute(
            "SELECT s.scene_number, s.location, s.int_ext, s.day_night, "
            "s.synopsis, s.story_day, s.requires_intimacy_coordinator, "
            "s.page_start_whole, s.page_start_eighths, "
            "s.page_end_whole, s.page_end_eighths, "
            "s.manual_shooting_hours, s.revision_badge, "
            "se.shooting_day, s.raw_blocks "
            "FROM scenes s "
            "LEFT JOIN schedule_entries se ON se.scene_id = s.id AND se.project_id = ? "
            "WHERE s.id = ?",
            (project_id, scene_id)
        ).fetchone()

        if not row:
            self._show_placeholder()
            return

        (scene_number, location, int_ext, day_night, synopsis, story_day,
         requires_intimacy, pw_s, pe_s, pw_e, pe_e,
         manual_hours, revision_badge, shooting_day, raw_blocks_json) = row

        try:
            self._raw_blocks = json.loads(raw_blocks_json) if raw_blocks_json else []
        except Exception:
            self._raw_blocks = []

        has_raw_text = bool(self._raw_blocks) and bool(extract_scene_text(self._raw_blocks).strip())

        elements = db.execute(
            "SELECT category, element_name, quantity FROM scene_elements "
            "WHERE scene_id = ? ORDER BY category, element_name", (scene_id,)
        ).fetchall()

        cast_items   = [(n, q) for c, n, q in elements if c == "Cast"]
        extras_rows  = [(n, q) for c, n, q in elements if c == "Extras"]
        vehicle_rows = [(n, q) for c, n, q in elements if c == "Vehicles"]
        animal_rows  = [(n, q) for c, n, q in elements if c == "Animals"]
        sfx_rows     = [(n, q) for c, n, q in elements if c in ("SFX", "Mechanical FX")]
        vfx_rows     = [(n, q) for c, n, q in elements if c == "VFX"]
        stunt_rows   = [(n, q) for c, n, q in elements if c == "Stunts"]
        prop_rows    = [(n, q) for c, n, q in elements if c == "Props"]

        try:
            shot_count = db.execute("SELECT COUNT(*) FROM shot_list WHERE scene_id = ?", (scene_id,)).fetchone()[0]
        except Exception:
            shot_count = 0

        scene_dict = {
            "manual_shooting_hours": manual_hours or 0.0,
            "page_start_whole": pw_s or 0, "page_start_eighths": pe_s or 0,
            "page_end_whole": pw_e or 0, "page_end_eighths": pe_e or 0,
            "int_ext": int_ext, "day_night": day_night,
            "requires_intimacy_coordinator": requires_intimacy,
            "elements": [(c, n) for c, n, _ in elements],
            "shot_count": shot_count,
        }
        estimated_h = scene_duration_hours(scene_dict)
        dur_eighths = Eighths(pw_e or 0, pe_e or 0) - Eighths(pw_s or 0, pe_s or 0)
        pages_str = str(dur_eighths) if dur_eighths.total_eighths > 0 else "—"

        self._clear_body()
        lay = self._body_layout

        # ── Riga superiore ──
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        sc_lbl = QLabel(f"SC. {scene_number or '?'}")
        sc_lbl.setFont(theme.font_mono(18, bold=True))
        sc_lbl.setStyleSheet(f"color: {theme.TEXT0.name()};")
        top_row.addWidget(sc_lbl)
        if revision_badge:
            rb = QLabel(revision_badge)
            rb.setFont(theme.font_ui(8, bold=True))
            rb.setStyleSheet("background:#FFB6C1;color:#000;border-radius:3px;padding:2px 5px;")
            top_row.addWidget(rb)
        top_row.addStretch()
        strip_c = theme.strip_color_for(int_ext or "INT", day_night or "GIORNO")
        ie_badge = QLabel(int_ext or "INT")
        ie_badge.setFont(theme.font_mono(9, bold=True))
        ie_badge.setStyleSheet(f"color: white; background-color: {strip_c.name()}; border-radius: 3px; padding: 2px 6px;")
        top_row.addWidget(ie_badge)
        dn_badge = QLabel(day_night or "GIORNO")
        dn_badge.setFont(theme.font_mono(9, bold=True))
        dn_badge.setStyleSheet(f"color: {theme.TEXT1.name()}; border: 1px solid {theme.qss_color(theme.BD1)}; border-radius: 3px; padding: 2px 6px;")
        top_row.addWidget(dn_badge)
        top_w = QWidget()
        top_w.setLayout(top_row)
        lay.addWidget(top_w)

        if location:
            loc_lbl = QLabel(location)
            loc_lbl.setFont(theme.font_ui(11, bold=True))
            loc_lbl.setStyleSheet(f"color: {theme.TEXT1.name()}; margin-top: 6px;")
            loc_lbl.setWordWrap(True)
            lay.addWidget(loc_lbl)

        lay.addWidget(self._divider())

        # ── Sezione sinossi ──
        syn_header_row = QHBoxLayout()
        syn_header_row.setSpacing(6)
        syn_title = QLabel("SINOSSI")
        syn_title.setFont(theme.font_ui(9, bold=True))
        syn_title.setStyleSheet(f"color: {theme.TEXT3.name()}; letter-spacing: 1px;")
        syn_header_row.addWidget(syn_title)
        syn_header_row.addStretch()

        # Pulsante "Genera" — offline, nessuna chiave, solo testo locale
        self._gen_btn = QPushButton("↺ Genera")
        self._gen_btn.setFont(theme.font_ui(9, bold=True))
        self._gen_btn.setFixedHeight(22)
        self._gen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._gen_btn.setEnabled(has_raw_text)
        self._gen_btn.setToolTip(
            "Genera sinossi automatica dal testo della scena (offline)"
            if has_raw_text else "Nessun testo di scena disponibile"
        )
        self._gen_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 8px;
            }}
            QPushButton:hover {{ background-color: {theme.qss_color(theme.BD0)}; }}
            QPushButton:disabled {{ color: {theme.TEXT3.name()}; }}
        """)
        self._gen_btn.clicked.connect(self._on_generate)
        syn_header_row.addWidget(self._gen_btn)

        syn_header_w = QWidget()
        syn_header_w.setLayout(syn_header_row)
        lay.addWidget(syn_header_w)

        # Testo sinossi modificabile
        has_synopsis = bool(synopsis and synopsis.strip())
        self._original_synopsis = synopsis.strip() if has_synopsis else ""

        self._synopsis_edit = QPlainTextEdit()
        self._synopsis_edit.setPlainText(self._original_synopsis if has_synopsis else "")
        self._synopsis_edit.setPlaceholderText("Inserisci o modifica la sinossi...")
        self._synopsis_edit.setFont(theme.font_ui(10))
        self._synopsis_edit.setMaximumHeight(80)
        self._synopsis_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                color: {theme.TEXT2.name()};
                background-color: {theme.BG1.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 4px;
            }}
            QPlainTextEdit:focus {{
                border-color: {theme.GOLD.name()};
            }}
        """)
        self._synopsis_edit.textChanged.connect(self._on_synopsis_text_changed)
        lay.addWidget(self._synopsis_edit)

        # Pulsanti salva/annulla sinossi
        syn_actions = QHBoxLayout()
        syn_actions.setContentsMargins(0, 4, 0, 0)
        syn_actions.setSpacing(6)

        self._save_syn_btn = QPushButton("Salva")
        self._save_syn_btn.setFont(theme.font_ui(9))
        self._save_syn_btn.setEnabled(False)
        self._save_syn_btn.setFixedHeight(22)
        self._save_syn_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 8px;
            }}
            QPushButton:hover {{ background-color: {theme.qss_color(theme.BD0)}; }}
            QPushButton:disabled {{ color: {theme.TEXT3.name()}; }}
        """)
        self._save_syn_btn.clicked.connect(self._save_synopsis_edit)
        syn_actions.addWidget(self._save_syn_btn)

        self._revert_syn_btn = QPushButton("Annulla")
        self._revert_syn_btn.setFont(theme.font_ui(9))
        self._revert_syn_btn.setEnabled(False)
        self._revert_syn_btn.setFixedHeight(22)
        self._revert_syn_btn.setStyleSheet(f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 8px;
            }}
            QPushButton:hover {{ background-color: {theme.qss_color(theme.BD0)}; }}
            QPushButton:disabled {{ color: {theme.TEXT3.name()}; }}
        """)
        self._revert_syn_btn.clicked.connect(self._revert_synopsis_edit)
        syn_actions.addWidget(self._revert_syn_btn)
        syn_actions.addStretch()

        syn_actions_w = QWidget()
        syn_actions_w.setLayout(syn_actions)
        lay.addWidget(syn_actions_w)

        lay.addWidget(self._divider())

        # ── Metriche ──
        metrics = QWidget()
        mg = QHBoxLayout(metrics)
        mg.setContentsMargins(0, 0, 0, 0)
        mg.setSpacing(0)
        if shooting_day is not None:
            story_tag = f" gg.{story_day}" if story_day else ""
            mg.addWidget(self._metric_block("GIORNATA", f"#{shooting_day}{story_tag}"))
            mg.addWidget(self._v_divider())
        mg.addWidget(self._metric_block("PAGINE", pages_str))
        mg.addWidget(self._v_divider())
        if manual_hours and manual_hours > 0:
            h_val, h_sub = f"{manual_hours:.1f}h ✏", "manuale"
        else:
            mins = int(estimated_h * 60)
            h_val = f"{estimated_h:.1f}h" if mins >= 60 else f"{mins}min"
            h_sub = "stimato"
        mg.addWidget(self._metric_block("TEMPO", h_val, subtitle=h_sub))
        lay.addWidget(metrics)
        lay.addWidget(self._divider())

        # ── Moltiplicatori ──
        if not (manual_hours and manual_hours > 0):
            mults = self._describe_multipliers(scene_dict, elements)
            if mults:
                m_lbl = QLabel(mults)
                m_lbl.setFont(theme.font_ui(9))
                m_lbl.setStyleSheet(f"color: {theme.TEXT3.name()}; margin-bottom: 4px;")
                m_lbl.setWordWrap(True)
                lay.addWidget(m_lbl)
                lay.addWidget(self._divider())

        # ── Cast ──
        if cast_items:
            lay.addWidget(self._section_header(f"CAST  ({len(cast_items)})"))
            for name, qty in cast_items:
                lay.addWidget(self._element_row("•", name, qty if qty and qty > 1 else None))
            lay.addSpacing(6)

        # ── Figurazioni ──
        total_extras = sum((q or 1) for _, q in extras_rows)
        if total_extras > 0:
            lay.addWidget(self._section_header("FIGURAZIONI"))
            lay.addWidget(self._kv_row("Totale", str(total_extras)))
            lay.addSpacing(6)

        # ── Tecnici ──
        has_tech = vehicle_rows or animal_rows or sfx_rows or vfx_rows or stunt_rows
        if has_tech or requires_intimacy:
            lay.addWidget(self._section_header("ELEMENTI TECNICI"))
            for name, _ in vehicle_rows:
                lay.addWidget(self._kv_row("Veicolo", name))
            for name, _ in animal_rows:
                lay.addWidget(self._kv_row("Animale", name))
            for name, _ in sfx_rows:
                lay.addWidget(self._kv_row("SFX", name))
            for name, _ in vfx_rows:
                lay.addWidget(self._kv_row("VFX", name))
            for name, _ in stunt_rows:
                lay.addWidget(self._kv_row("Stunt", name))
            if requires_intimacy:
                lay.addWidget(self._kv_row("Intimacy", "Coordinator richiesto"))
            lay.addSpacing(6)

        # ── Props ──
        if prop_rows:
            lay.addWidget(self._section_header(f"PROPS  ({len(prop_rows)})"))
            for name, qty in prop_rows[:5]:
                lay.addWidget(self._element_row("·", name, qty if qty and qty > 1 else None))
            if len(prop_rows) > 5:
                more = QLabel(f"  + altri {len(prop_rows) - 5}")
                more.setFont(theme.font_ui(9))
                more.setStyleSheet(f"color: {theme.TEXT3.name()};")
                lay.addWidget(more)

        lay.addStretch()

    # ------------------------------------------------------------------
    # Generazione sinossi offline
    # ------------------------------------------------------------------

    def _on_generate(self):
        """Avvia il SynopsisWorker (thread) — nessuna rete, nessuna chiave."""
        if not self._raw_blocks:
            return

        # Chiedi conferma se ci sono modifiche non salvate
        current = self._synopsis_edit.toPlainText()
        if current != self._original_synopsis:
            reply = QMessageBox.question(
                self,
                "Rigenerare sinossi?",
                "Ci sono modifiche non salvate. Rigenerare sovrascriverà il testo.\n\nContinuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._gen_btn.setEnabled(False)
        self._gen_btn.setText("⏳")
        self._synopsis_edit.setPlainText("Elaborazione…")
        self._synopsis_edit.setEnabled(False)

        self._synopsis_worker = SynopsisWorker(self._raw_blocks)
        self._synopsis_worker.done.connect(self._on_synopsis_done)
        self._synopsis_worker.error.connect(self._on_synopsis_error)
        self._synopsis_worker.start()

    def _on_synopsis_done(self, synopsis: str):
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("↺ Genera")
        self._synopsis_edit.setEnabled(True)

        if not synopsis:
            self._synopsis_edit.setPlainText("")
            self._synopsis_edit.setPlaceholderText("Testo troppo breve per generare una sinossi.")
            self._original_synopsis = ""
            self._save_syn_btn.setEnabled(False)
            self._revert_syn_btn.setEnabled(False)
            return

        # Salva nel DB
        try:
            self._db.execute("UPDATE scenes SET synopsis = ? WHERE id = ?", (synopsis, self._scene_id))
            self._db.commit()
        except Exception as e:
            QMessageBox.warning(self, "Errore salvataggio", f"Impossibile salvare la sinossi:\n{e}")

        self._synopsis_edit.setPlainText(synopsis)
        self._original_synopsis = synopsis
        self._save_syn_btn.setEnabled(False)
        self._revert_syn_btn.setEnabled(False)
        self.synopsis_saved.emit(self._scene_id, synopsis)

    def _on_synopsis_error(self, msg: str):
        self._gen_btn.setEnabled(True)
        self._gen_btn.setText("↺ Genera")
        self._synopsis_edit.setEnabled(True)
        self._synopsis_edit.setPlainText(self._original_synopsis)
        self._save_syn_btn.setEnabled(False)
        self._revert_syn_btn.setEnabled(False)
        QMessageBox.warning(self, "Errore generazione sinossi", msg)

    def _on_synopsis_text_changed(self):
        """Attiva pulsanti quando la sinossi viene modificata manualmente."""
        current = self._synopsis_edit.toPlainText()
        has_changes = current != self._original_synopsis
        self._save_syn_btn.setEnabled(has_changes)
        self._revert_syn_btn.setEnabled(has_changes)

    def _save_synopsis_edit(self):
        """Salva la sinossi modificata manualmente nel database."""
        if self._scene_id is None or self._db is None:
            return

        new_synopsis = self._synopsis_edit.toPlainText().strip()

        try:
            self._db.execute(
                "UPDATE scenes SET synopsis = ? WHERE id = ?",
                (new_synopsis, self._scene_id)
            )
            self._db.commit()

            self._original_synopsis = new_synopsis
            self._save_syn_btn.setEnabled(False)
            self._revert_syn_btn.setEnabled(False)

            self.synopsis_saved.emit(self._scene_id, new_synopsis)

        except Exception as e:
            QMessageBox.warning(
                self,
                "Errore",
                f"Impossibile salvare la sinossi:\n{e}"
            )

    def _revert_synopsis_edit(self):
        """Annulla le modifiche e ripristina la sinossi originale."""
        self._synopsis_edit.setPlainText(self._original_synopsis)
        self._save_syn_btn.setEnabled(False)
        self._revert_syn_btn.setEnabled(False)

    # ------------------------------------------------------------------
    # Helper UI
    # ------------------------------------------------------------------

    def _divider(self):
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background-color: {theme.qss_color(theme.BD0)}; margin: 8px 0;")
        return d

    def _v_divider(self):
        d = QFrame()
        d.setFixedWidth(1)
        d.setFixedHeight(36)
        d.setStyleSheet(f"background-color: {theme.qss_color(theme.BD0)};")
        return d

    def _section_header(self, text):
        lbl = QLabel(text)
        lbl.setFont(theme.font_ui(9, bold=True))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()}; letter-spacing: 1px; margin-top: 4px; margin-bottom: 2px;")
        return lbl

    def _kv_row(self, key, value):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(6)
        k = QLabel(key)
        k.setFont(theme.font_ui(10))
        k.setStyleSheet(f"color: {theme.TEXT3.name()};")
        lay.addWidget(k)
        lay.addStretch()
        v = QLabel(value)
        v.setFont(theme.font_ui(10, bold=True))
        v.setStyleSheet(f"color: {theme.TEXT1.name()};")
        lay.addWidget(v)
        return w

    def _element_row(self, bullet, name, qty=None):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(2, 1, 0, 1)
        lay.setSpacing(4)
        b = QLabel(bullet)
        b.setFont(theme.font_ui(10))
        b.setStyleSheet(f"color: {theme.TEXT3.name()};")
        b.setFixedWidth(10)
        lay.addWidget(b)
        n = QLabel(name)
        n.setFont(theme.font_ui(10))
        n.setStyleSheet(f"color: {theme.TEXT1.name()};")
        lay.addWidget(n, 1)
        if qty:
            q = QLabel(f"×{qty}")
            q.setFont(theme.font_mono(9))
            q.setStyleSheet(f"color: {theme.TEXT3.name()};")
            lay.addWidget(q)
        return w

    def _metric_block(self, label, value, subtitle=""):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(label)
        lbl.setFont(theme.font_ui(8, bold=True))
        lbl.setStyleSheet(f"color: {theme.TEXT3.name()}; letter-spacing: 1px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl)
        val = QLabel(value)
        val.setFont(theme.font_mono(13, bold=True))
        val.setStyleSheet(f"color: {theme.TEXT0.name()};")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(val)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setFont(theme.font_ui(8))
            sub.setStyleSheet(f"color: {theme.TEXT3.name()};")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(sub)
        return w

    def _describe_multipliers(self, scene_dict, elements):
        parts = []
        cats = {c for c, _, _ in elements}
        cast_count = sum(1 for c, _, _ in elements if c == "Cast")
        if "Stunts" in cats:
            parts.append("Stunt ×3.0")
        if "Intimacy" in cats or scene_dict.get("requires_intimacy_coordinator"):
            parts.append("Intimacy ×1.8")
        if "VFX" in cats or "Mechanical FX" in cats:
            parts.append("VFX ×2.0")
        if cast_count > 2:
            parts.append(f"Cast({cast_count}) ×{1.0 + (cast_count - 2) * 0.15:.2f}")
        if scene_dict.get("int_ext") == "INT":
            parts.append("INT ×1.2")
        dn = scene_dict.get("day_night", "")
        if dn == "NOTTE":
            parts.append("Notte ×1.5")
        elif dn in ("ALBA", "TRAMONTO"):
            parts.append(f"{dn} ×1.3")
        sc = scene_dict.get("shot_count", 0)
        if sc > 5:
            parts.append(f"{sc} inquadr. ×{1.0 + ((sc - 5) / 5) * 0.25:.2f}")
        base_eighths = (
            (scene_dict.get("page_end_whole", 0) * 8 + scene_dict.get("page_end_eighths", 0))
            - (scene_dict.get("page_start_whole", 0) * 8 + scene_dict.get("page_start_eighths", 0))
        )
        base_h = max(base_eighths / 8.0 * 1.5, 0.25)
        if not parts:
            return f"Base: {base_h:.2f}h (1 pag = 1.5h)"
        return "Moltiplicatori: " + " · ".join(parts)


# ---------------------------------------------------------------------------
# StripboardView (identica alla versione precedente)
# ---------------------------------------------------------------------------

class StripboardView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._compact = False
        self._selected_ids: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {theme.BG2.name()};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(16, 8, 16, 8)
        tb_layout.setSpacing(8)
        regen_btn = QPushButton("Rigenera")
        regen_btn.setFont(theme.font_ui(11))
        regen_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        regen_btn.setStyleSheet(self._ghost_btn_style())
        regen_btn.clicked.connect(self._start_regen)
        tb_layout.addWidget(regen_btn)
        self._worker = None
        self._compact_btn = QPushButton("Compatta")
        self._compact_btn.setFont(theme.font_ui(11))
        self._compact_btn.setCheckable(True)
        self._compact_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._compact_btn.setStyleSheet(self._ghost_btn_style())
        self._compact_btn.clicked.connect(self._toggle_compact)
        tb_layout.addWidget(self._compact_btn)
        legend_btn = QPushButton("Legenda")
        legend_btn.setFont(theme.font_ui(11))
        legend_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        legend_btn.setStyleSheet(self._ghost_btn_style())
        tb_layout.addWidget(legend_btn)
        add_day_btn = QPushButton("+ Giornata")
        add_day_btn.setFont(theme.font_ui(11))
        add_day_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_day_btn.setStyleSheet(self._ghost_btn_style())
        add_day_btn.clicked.connect(self._add_shooting_day)
        tb_layout.addWidget(add_day_btn)
        tb_layout.addStretch()
        self._days_label = QLabel("")
        self._days_label.setFont(theme.font_ui(10))
        self._days_label.setStyleSheet(f"color: {theme.TEXT3.name()}; padding-right: 8px;")
        tb_layout.addWidget(self._days_label)
        export_excel_btn = QPushButton("Esporta XLS")
        export_excel_btn.setFont(theme.font_ui(11))
        export_excel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_excel_btn.setStyleSheet(self._ghost_btn_style())
        export_excel_btn.clicked.connect(self._on_export_excel)
        tb_layout.addWidget(export_excel_btn)
        export_pdf_btn = QPushButton("Esporta PDF")
        export_pdf_btn.setFont(theme.font_ui(11))
        export_pdf_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_pdf_btn.setStyleSheet(self._ghost_btn_style())
        export_pdf_btn.clicked.connect(self._on_export_pdf)
        tb_layout.addWidget(export_pdf_btn)
        layout.addWidget(toolbar)

        self._batch_bar = QWidget()
        self._batch_bar.setVisible(False)
        self._batch_bar.setStyleSheet(f"background-color: {theme.qss_color(theme.GOLD_BG)}; border-bottom: 1px solid {theme.qss_color(theme.GOLD_BD)};")
        bb_layout = QHBoxLayout(self._batch_bar)
        bb_layout.setContentsMargins(16, 6, 16, 6)
        bb_layout.setSpacing(10)
        self._batch_label = QLabel("0 scene selezionate")
        self._batch_label.setFont(theme.font_ui(11, bold=True))
        self._batch_label.setStyleSheet(f"color: {theme.GOLD_DARK.name()};")
        bb_layout.addWidget(self._batch_label)
        bb_layout.addWidget(QLabel("→"))
        self._move_to_day_spin = QSpinBox()
        self._move_to_day_spin.setPrefix("Giorno ")
        self._move_to_day_spin.setMinimum(1)
        self._move_to_day_spin.setMaximum(999)
        self._move_to_day_spin.setFont(theme.font_ui(11))
        self._move_to_day_spin.setFixedWidth(110)
        bb_layout.addWidget(self._move_to_day_spin)
        move_btn = QPushButton("Sposta")
        move_btn.setFont(theme.font_ui(11))
        move_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        move_btn.clicked.connect(self._on_batch_move)
        bb_layout.addWidget(move_btn)
        desel_btn = QPushButton("✕ Deseleziona")
        desel_btn.setFont(theme.font_ui(11))
        desel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        desel_btn.setStyleSheet(self._ghost_btn_style())
        desel_btn.clicked.connect(self._deselect_all)
        bb_layout.addWidget(desel_btn)
        bb_layout.addStretch()
        layout.addWidget(self._batch_bar)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {theme.qss_color(theme.BD1)}; }}")
        strips_container = QWidget()
        strips_container.setStyleSheet(f"background-color: {theme.BG1.name()};")
        strips_v = QVBoxLayout(strips_container)
        strips_v.setContentsMargins(0, 0, 0, 0)
        strips_v.setSpacing(0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {theme.BG1.name()}; }}")
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)
        strips_v.addWidget(self._scroll, 1)
        self._detail_panel = SceneDetailPanel()
        self._splitter.addWidget(strips_container)
        self._splitter.addWidget(self._detail_panel)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([700, 0])
        self._detail_visible = False
        layout.addWidget(self._splitter, 1)

        self._strip_widgets = []
        self._drop_indicator = QFrame(self._content)
        self._drop_indicator.setFixedHeight(3)
        self._drop_indicator.setStyleSheet("background-color: #c8940a;")
        self._drop_indicator.setVisible(False)
        self._content.setAcceptDrops(True)
        self._content.dragEnterEvent = self._drag_enter_event
        self._content.dragMoveEvent = self._drag_move_event
        self._content.dropEvent = self._drop_event
        self._drag_insert_index = -1
        self._phantom_days: set[int] = set()

    def _ghost_btn_style(self):
        return f"QPushButton {{ color: {theme.TEXT2.name()}; background: transparent; border: 1.5px solid {theme.qss_color(theme.BD1)}; border-radius: 6px; padding: 5px 14px; }}QPushButton:hover {{ background-color: {theme.qss_color(theme.BD0)}; }}QPushButton:checked {{ color: {theme.GOLD.name()}; border-color: {theme.qss_color(theme.GOLD_BD)}; background-color: {theme.qss_color(theme.GOLD_BG)}; }}"

    def _toggle_compact(self):
        self._compact = self._compact_btn.isChecked()
        if self._project_id:
            self.load_project(self._project_id)

    def _add_shooting_day(self):
        if not self._project_id:
            return
        db = self._container.database
        row = db.execute("SELECT MAX(shooting_day) FROM schedule_entries WHERE project_id = ?", (self._project_id,)).fetchone()
        next_day = (row[0] or 0) + 1
        if self._phantom_days:
            next_day = max(next_day, max(self._phantom_days) + 1)
        self._phantom_days.add(next_day)
        self.load_project(self._project_id)

    def _estimate_days_needed(self) -> int:
        if not self._project_id:
            return 1
        from gliamispo.scheduling.genetic import scene_duration_hours
        db = self._container.database
        proj = db.execute("SELECT hours_per_shooting_day FROM projects WHERE id = ?", (self._project_id,)).fetchone()
        max_h = float(proj[0]) if proj and proj[0] else 10.0
        rows = db.execute(
            "SELECT s.manual_shooting_hours, s.page_start_whole, s.page_start_eighths, s.page_end_whole, s.page_end_eighths, s.int_ext, s.day_night, s.requires_intimacy_coordinator, GROUP_CONCAT(DISTINCT se.category || ':' || se.element_name) as elems FROM scenes s LEFT JOIN scene_elements se ON se.scene_id = s.id WHERE s.project_id = ? GROUP BY s.id",
            (self._project_id,)
        ).fetchall()
        total_h = 0.0
        for r in rows:
            elements = []
            if r[8]:
                for item in r[8].split(','):
                    if ':' in item:
                        cat, name = item.split(':', 1)
                        elements.append((cat.strip(), name.strip()))
            total_h += scene_duration_hours({'manual_shooting_hours': r[0] or 0.0, 'page_start_whole': r[1], 'page_start_eighths': r[2], 'page_end_whole': r[3], 'page_end_eighths': r[4], 'int_ext': r[5], 'day_night': r[6], 'requires_intimacy_coordinator': r[7], 'elements': elements})
        import math
        return max(1, math.ceil(total_h / max_h))

    def load_project(self, project_id):
        import traceback
        try:
            self._load_project_impl(project_id)
        except Exception as e:
            QMessageBox.critical(self, "Errore Load Project", f"Errore:\n{e}\n\n{traceback.format_exc()}")

    def _load_project_impl(self, project_id):
        self._project_id = project_id
        self._selected_ids.clear()
        self._batch_bar.setVisible(False)
        self._detail_panel.clear()
        self._splitter.setSizes([700, 0])
        self._detail_visible = False
        widgets_to_delete = self._strip_widgets[:]
        self._strip_widgets.clear()
        for w in widgets_to_delete:
            try:
                self._content_layout.removeWidget(w)
                w.deleteLater()
            except RuntimeError:
                pass
        db = self._container.database
        try:
            entries = db.execute(
                "SELECT se.shooting_day, se.scene_id, s.scene_number, s.location, s.int_ext, s.day_night, s.is_locked, s.requires_intimacy_coordinator, s.page_start_whole, s.page_start_eighths, s.page_end_whole, s.page_end_eighths, s.revision_badge, s.manual_shooting_hours FROM schedule_entries se JOIN scenes s ON se.scene_id = s.id WHERE se.project_id = ? ORDER BY se.shooting_day, se.position",
                (project_id,)
            ).fetchall()
        except Exception:
            entries = []
        if not entries:
            scenes = db.execute("SELECT id, scene_number, location, int_ext, day_night, is_locked, requires_intimacy_coordinator, page_start_whole, page_start_eighths, page_end_whole, page_end_eighths, revision_badge, manual_shooting_hours FROM scenes WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()
            for s in scenes:
                scene = {"id": s[0], "scene_number": s[1], "location": s[2], "int_ext": s[3], "day_night": s[4], "is_locked": s[5], "requires_intimacy_coordinator": s[6], "page_start_whole": s[7], "page_start_eighths": s[8], "page_end_whole": s[9], "page_end_eighths": s[10], "revision_badge": s[11] if len(s) > 11 else None, "manual_shooting_hours": s[12] if len(s) > 12 else None}
                row = SceneStripRow(scene, self._compact)
                row.clicked.connect(self._on_strip_clicked)
                row.duration_edit_requested.connect(self._on_duration_edit)
                self._content_layout.insertWidget(self._content_layout.count() - 1, row)
                self._strip_widgets.append(row)
            return
        days = {}
        for e in entries:
            scene = {"id": e[1], "scene_number": e[2], "location": e[3], "int_ext": e[4], "day_night": e[5], "is_locked": e[6], "requires_intimacy_coordinator": e[7], "page_start_whole": e[8], "page_start_eighths": e[9], "page_end_whole": e[10], "page_end_eighths": e[11], "revision_badge": e[12] if len(e) > 12 else None, "manual_shooting_hours": e[13] if len(e) > 13 else None}
            days.setdefault(e[0], []).append(scene)
        for pd in sorted(self._phantom_days):
            if pd not in days:
                days[pd] = []
        sorted_days = sorted(days.keys())
        for idx, day_num in enumerate(sorted_days):
            scenes_in_day = days[day_num]
            total_eighths = 0
            locations = []
            for sc in scenes_in_day:
                dur = Eighths(sc.get("page_end_whole", 0) or 0, sc.get("page_end_eighths", 0) or 0) - Eighths(sc.get("page_start_whole", 0) or 0, sc.get("page_start_eighths", 0) or 0)
                total_eighths += dur.total_eighths
                loc = sc.get("location", "")
                if loc and loc not in locations:
                    locations.append(loc)
            pages_str = str(Eighths(total_eighths // 8, total_eighths % 8))
            n_actors_row = db.execute("SELECT COUNT(DISTINCT se.element_name) FROM schedule_entries ent JOIN scene_elements se ON se.scene_id = ent.scene_id WHERE ent.project_id = ? AND ent.shooting_day = ? AND se.category = 'Cast'", (project_id, day_num)).fetchone()
            n_actors = n_actors_row[0] if n_actors_row else 0
            from gliamispo.scheduling.genetic import scene_duration_hours
            try:
                proj_h_row = db.execute("SELECT hours_per_shooting_day FROM projects WHERE id = ?", (project_id,)).fetchone()
                max_h_day = float(proj_h_row[0]) if proj_h_row and proj_h_row[0] else 10.0
            except Exception:
                max_h_day = 10.0
            day_used_hours = 0.0
            for sc in scenes_in_day:
                elems_rows = db.execute("SELECT category, element_name FROM scene_elements WHERE scene_id = ?", (sc["id"],)).fetchall()
                sc_full = dict(sc)
                sc_full["elements"] = list(elems_rows)
                sc_full["shot_count"] = db.execute("SELECT COUNT(*) FROM shot_list WHERE scene_id = ?", (sc["id"],)).fetchone()[0]
                day_used_hours += scene_duration_hours(sc_full)
            if idx > 0:
                day_divider = QFrame()
                day_divider.setFixedHeight(12)
                day_divider.setStyleSheet(f"background-color: {theme.BG0.name()};")
                self._content_layout.insertWidget(self._content_layout.count() - 1, day_divider)
                self._strip_widgets.append(day_divider)
            header = DayBreakHeader(day_num, len(scenes_in_day), pages_str, day_used_hours, locations, n_actors, max_h_day)
            self._content_layout.insertWidget(self._content_layout.count() - 1, header)
            self._strip_widgets.append(header)
            for sc in scenes_in_day:
                row = SceneStripRow(sc, self._compact)
                row.clicked.connect(self._on_strip_clicked)
                row.duration_edit_requested.connect(self._on_duration_edit)
                self._content_layout.insertWidget(self._content_layout.count() - 1, row)
                self._strip_widgets.append(row)
        try:
            actual = len(days)
            estimated = self._estimate_days_needed()
            if actual < estimated:
                self._days_label.setText(f"⚠ {actual}/{estimated} gg stimati")
                self._days_label.setStyleSheet(f"color: {theme.STATUS_WARN.name()}; padding-right: 8px; font-weight: bold;")
            else:
                self._days_label.setText(f"{actual} giorni")
                self._days_label.setStyleSheet(f"color: {theme.TEXT3.name()}; padding-right: 8px;")
        except Exception:
            pass

    def _on_strip_clicked(self, scene_id: int, ctrl: bool):
        if ctrl:
            if scene_id in self._selected_ids:
                self._selected_ids.discard(scene_id)
            else:
                self._selected_ids.add(scene_id)
        else:
            self._selected_ids = {scene_id}
            self._show_scene_detail(scene_id)
        self._update_selection_visual()
        self._update_batch_toolbar()

    def _show_scene_detail(self, scene_id: int):
        if not self._detail_visible:
            total = self._splitter.width()
            self._splitter.setSizes([int(total * 0.68), int(total * 0.32)])
            self._detail_visible = True
        self._detail_panel.load_scene(self._container.database, scene_id, self._project_id)

    def _update_selection_visual(self):
        for w in self._strip_widgets:
            if isinstance(w, SceneStripRow):
                w.set_selected(w._scene_id in self._selected_ids)

    def _update_batch_toolbar(self):
        n = len(self._selected_ids)
        self._batch_bar.setVisible(n > 0)
        self._batch_label.setText("1 scena selezionata" if n == 1 else f"{n} scene selezionate")

    def _deselect_all(self):
        self._selected_ids.clear()
        self._update_selection_visual()
        self._update_batch_toolbar()

    def _on_batch_move(self):
        if not self._selected_ids:
            return
        target_day = self._move_to_day_spin.value()
        all_warnings = []
        for scene_id in self._selected_ids:
            all_warnings.extend(self._check_drop_constraints(scene_id, target_day))
        if all_warnings:
            reply = QMessageBox.question(self, "Conflitti cast rilevati", "\n".join(all_warnings) + "\n\nProcedere comunque?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        db = self._container.database
        try:
            for scene_id in self._selected_ids:
                db.execute("UPDATE schedule_entries SET shooting_day = ? WHERE project_id = ? AND scene_id = ?", (target_day, self._project_id, scene_id))
            db.commit()
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile spostare le scene: {exc}")
            return
        self._selected_ids.clear()
        self.load_project(self._project_id)

    def _check_drop_constraints(self, scene_id: int, target_day: int) -> list[str]:
        warnings = []
        db = self._container.database
        cast = db.execute("SELECT se.element_name FROM scene_elements se WHERE se.scene_id = ? AND se.category = 'Cast'", (scene_id,)).fetchall()
        for actor in cast:
            conflict = db.execute("SELECT s.scene_number FROM schedule_entries ent JOIN scenes s ON s.id = ent.scene_id JOIN scene_elements el ON el.scene_id = ent.scene_id WHERE ent.project_id = ? AND ent.shooting_day = ? AND el.element_name = ? AND ent.scene_id != ?", (self._project_id, target_day, actor[0], scene_id)).fetchone()
            if conflict:
                warnings.append(f"⚠️  {actor[0]} è già in scena {conflict[0]} nel giorno {target_day}")
        return warnings

    def _drag_enter_event(self, event: QDragEnterEvent):
        try:
            if event.mimeData().hasFormat("application/x-gliamispo-scene-id"):
                event.acceptProposedAction()
            else:
                event.ignore()
        except Exception:
            event.ignore()

    def _drag_move_event(self, event: QDragMoveEvent):
        try:
            if not event.mimeData().hasFormat("application/x-gliamispo-scene-id"):
                event.ignore()
                return
            event.acceptProposedAction()
            y = event.position().toPoint().y()
            insert_idx = self._find_insert_index(y)
            self._drag_insert_index = insert_idx
            self._update_drop_indicator(insert_idx)
            scroll_bar = self._scroll.verticalScrollBar()
            viewport_y = self._scroll.mapFromGlobal(self._content.mapToGlobal(event.position().toPoint())).y()
            viewport_h = self._scroll.viewport().height()
            if viewport_y < 40:
                scroll_bar.setValue(scroll_bar.value() - 10)
            elif viewport_y > viewport_h - 40:
                scroll_bar.setValue(scroll_bar.value() + 10)
        except Exception:
            event.ignore()

    def _drop_event(self, event: QDropEvent):
        try:
            if not event.mimeData().hasFormat("application/x-gliamispo-scene-id"):
                event.ignore()
                return
            raw = event.mimeData().data("application/x-gliamispo-scene-id")
            scene_id = int.from_bytes(bytes(raw), "big")
            self._drop_indicator.setVisible(False)
            event.acceptProposedAction()
            insert_idx = self._drag_insert_index
            self._drag_insert_index = -1
            if insert_idx < 0:
                return
            self._apply_drop(scene_id, insert_idx)
        except Exception as e:
            import traceback
            self._drop_indicator.setVisible(False)
            self._drag_insert_index = -1
            event.ignore()
            QMessageBox.warning(self, "Errore Drop", f"{e}\n\n{traceback.format_exc()}")

    def _find_insert_index(self, y: int) -> int:
        try:
            scene_strips = [(i, w) for i, w in enumerate(self._strip_widgets) if isinstance(w, SceneStripRow) and w is not None]
            if not scene_strips:
                return 0
            for i, w in scene_strips:
                if y < w.geometry().top() + w.height() // 2:
                    return i
            return scene_strips[-1][0] + 1
        except Exception:
            return 0

    def _update_drop_indicator(self, insert_idx: int):
        try:
            strips = [(i, w) for i, w in enumerate(self._strip_widgets) if isinstance(w, SceneStripRow) and w is not None]
            if not strips:
                self._drop_indicator.setVisible(False)
                return
            content_w = self._content.width()
            scene_idxs = [i for i, _ in strips]
            if insert_idx <= scene_idxs[0]:
                y = strips[0][1].geometry().top()
            elif insert_idx > scene_idxs[-1]:
                y = strips[-1][1].geometry().bottom()
            else:
                for i, w in strips:
                    if i >= insert_idx:
                        y = w.geometry().top()
                        break
                else:
                    y = strips[-1][1].geometry().bottom()
            self._drop_indicator.setGeometry(0, y - 1, content_w, 3)
        except Exception:
            self._drop_indicator.setVisible(False)
            return
        self._drop_indicator.raise_()
        self._drop_indicator.setVisible(True)

    def _apply_drop(self, scene_id: int, insert_before_idx: int):
        import traceback
        try:
            if self._project_id is None:
                return
            db = self._container.database
            target_day = self._resolve_target_day(insert_before_idx)
            if target_day is None:
                return
            try:
                origin_row = db.execute("SELECT shooting_day FROM schedule_entries WHERE project_id = ? AND scene_id = ?", (self._project_id, scene_id)).fetchone()
                origin_day = origin_row[0] if origin_row else None
            except Exception:
                origin_day = None
            try:
                warnings = self._check_drop_constraints(scene_id, target_day)
            except Exception:
                warnings = []
            if warnings:
                reply = QMessageBox.question(self, "Conflitti cast rilevati", "\n".join(warnings) + "\n\nProcedere comunque?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No:
                    return
            target_position = self._resolve_target_position(insert_before_idx, target_day)
            try:
                db.execute("UPDATE schedule_entries SET shooting_day = ?, position = ? WHERE project_id = ? AND scene_id = ?", (target_day, target_position, self._project_id, scene_id))
                self._repack_positions(db, target_day)
                if origin_day is not None and origin_day != target_day:
                    self._repack_positions(db, origin_day)
                db.commit()
            except Exception as exc:
                QMessageBox.critical(self, "Errore DB", f"{exc}\n\n{traceback.format_exc()}")
                return
            project_id = self._project_id
            QTimer.singleShot(0, lambda: self._safe_reload(project_id))
        except Exception as e:
            QMessageBox.critical(self, "Errore Apply Drop", f"{e}\n\n{traceback.format_exc()}")

    def _safe_reload(self, project_id: int):
        import traceback
        try:
            if self._project_id == project_id:
                self.load_project(project_id)
        except Exception as e:
            QMessageBox.critical(self, "Errore Reload", f"{e}\n\n{traceback.format_exc()}")

    def _resolve_target_day(self, insert_before_idx: int) -> int:
        if not self._strip_widgets:
            return 1
        current_day = None
        for i, w in enumerate(self._strip_widgets):
            if i >= insert_before_idx:
                break
            if isinstance(w, DayBreakHeader):
                current_day = w._day_num
        if current_day is None:
            for w in self._strip_widgets:
                if isinstance(w, DayBreakHeader):
                    return w._day_num
            return 1
        if insert_before_idx >= len(self._strip_widgets):
            return current_day + 1
        return current_day

    def _resolve_target_position(self, insert_before_idx: int, target_day: int) -> int:
        count = 0
        for i, w in enumerate(self._strip_widgets):
            if i >= insert_before_idx:
                break
            if isinstance(w, SceneStripRow):
                count += 1
        return count

    def _repack_positions(self, db, shooting_day: int):
        entries = db.execute("SELECT scene_id FROM schedule_entries WHERE project_id = ? AND shooting_day = ? ORDER BY position", (self._project_id, shooting_day)).fetchall()
        for pos, (sid,) in enumerate(entries):
            db.execute("UPDATE schedule_entries SET position = ? WHERE project_id = ? AND scene_id = ?", (pos, self._project_id, sid))

    def _start_regen(self):
        if self._project_id is None:
            return
        db = self._container.database
        rows = db.execute('SELECT s.id, s.location, s.int_ext, s.day_night, s.page_start_whole, s.page_start_eighths, s.page_end_whole, s.page_end_eighths, s.manual_shooting_hours, s.is_locked, s.requires_intimacy_coordinator, GROUP_CONCAT(DISTINCT se.category || ":" || se.element_name) as elements_str FROM scenes s LEFT JOIN scene_elements se ON se.scene_id = s.id WHERE s.project_id = ? GROUP BY s.id ORDER BY s.id', (self._project_id,)).fetchall()
        if not rows:
            return
        shot_counts = {r[0]: r[1] for r in db.execute('SELECT scene_id, COUNT(*) FROM shot_list WHERE scene_id IN (SELECT id FROM scenes WHERE project_id = ?) GROUP BY scene_id', (self._project_id,)).fetchall()}
        scenes = []
        for r in rows:
            elements = []
            if r[11]:
                for item in r[11].split(','):
                    if ':' in item:
                        cat, name = item.split(':', 1)
                        elements.append((cat.strip(), name.strip()))
            scenes.append({'id': r[0], 'location': r[1], 'int_ext': r[2], 'day_night': r[3], 'page_start_whole': r[4], 'page_start_eighths': r[5], 'page_end_whole': r[6], 'page_end_eighths': r[7], 'manual_shooting_hours': r[8] or 0.0, 'is_locked': r[9], 'requires_intimacy_coordinator': r[10], 'elements': elements, 'cast': [n for c, n in elements if c == 'Cast'], 'shot_count': shot_counts.get(r[0], 0), 'page_duration': ((r[6]*8+r[7]) - (r[4]*8+r[5])) / 8.0})
        proj_row = db.execute('SELECT hours_per_shooting_day FROM projects WHERE id = ?', (self._project_id,)).fetchone()
        max_hours = float(proj_row[0]) if proj_row and proj_row[0] else 10.0
        self._worker = SchedulerWorker(scenes, {'max_hours_per_day': max_hours}, db, self._project_id)
        self._worker.finished.connect(self._on_regen_done)
        self._worker.error.connect(self._on_regen_error)
        self._worker.start()

    def _on_export_excel(self):
        if self._project_id is None:
            return
        data = export_stripboard(self._container.database, self._project_id, fmt=Format.EXCEL)
        path, _ = QFileDialog.getSaveFileName(self, "Esporta Stripboard", "stripboard.xlsx", "Excel (*.xlsx)")
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _on_export_pdf(self):
        if self._project_id is None:
            return
        data = export_stripboard(self._container.database, self._project_id, fmt=Format.PDF)
        if not data:
            QMessageBox.warning(self, "Export", "Installa fpdf2: pip install fpdf2")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Esporta Stripboard", "stripboard.pdf", "PDF (*.pdf)")
        if path:
            with open(path, "wb") as f:
                f.write(data)

    def _on_regen_done(self):
        if self._project_id:
            self.load_project(self._project_id)
        if self._worker and hasattr(self._worker, 'explanations') and self._worker.explanations:
            QMessageBox.information(self, 'Ottimizzazione completata', '\n'.join(self._worker.explanations))

    def _on_regen_error(self, msg):
        QMessageBox.warning(self, 'Errore scheduling', msg)

    def _on_duration_edit(self, scene_id: int):
        db = self._container.database
        current = db.execute("SELECT manual_shooting_hours FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        current_val = float(current[0]) if current and current[0] else 0.0
        val, ok = QInputDialog.getDouble(self, "Durata scena", "Ore di ripresa stimate (0 = calcolo automatico):", value=current_val, min=0.0, max=24.0, decimals=1)
        if ok:
            db.execute("UPDATE scenes SET manual_shooting_hours = ? WHERE id = ?", (val, scene_id))
            db.commit()
            self.load_project(self._project_id)

    def clear(self):
        self._project_id = None
        self._selected_ids.clear()
        self._batch_bar.setVisible(False)
        self._phantom_days.clear()
        self._detail_panel.clear()
        self._splitter.setSizes([700, 0])
        self._detail_visible = False
        for w in self._strip_widgets:
            self._content_layout.removeWidget(w)
            w.deleteLater()
        self._strip_widgets.clear()