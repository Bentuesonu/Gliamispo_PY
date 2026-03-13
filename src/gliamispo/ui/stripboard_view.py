from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QCursor
from gliamispo.ui import theme
from gliamispo.models.eighths import Eighths
from gliamispo.scheduling.genetic import GeneticScheduler, save_schedule_to_db


class SchedulerWorker(QThread):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

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
            best = asyncio.run(
                scheduler.optimize(on_progress=self.progress.emit)
            )
            ordered = [self._scenes[i] for i in best]
            save_schedule_to_db(self._db, self._project_id, ordered)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class SceneStripRow(QFrame):
    clicked = pyqtSignal(int)

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

        # Color strip
        strip = QFrame()
        strip.setFixedWidth(6)
        strip.setStyleSheet(f"background-color: {strip_c.name()};")
        main_layout.addWidget(strip)

        # Lock icon
        locked = scene.get("is_locked", 0)
        lock_label = QLabel("\U0001F512" if locked else "\U0001F513")
        lock_label.setFont(theme.font_ui(10))
        lock_label.setFixedWidth(24)
        lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        main_layout.addWidget(lock_label)

        # Scene number
        num = scene.get("scene_number", "")
        num_label = QLabel(num)
        font_size = 11 if compact else 12
        num_label.setFont(theme.font_mono(font_size, bold=True))
        num_label.setFixedWidth(40)
        num_label.setStyleSheet(f"color: {theme.TEXT0.name()};")
        main_layout.addWidget(num_label)

        if not compact:
            # Divider
            div = QFrame()
            div.setFixedWidth(1)
            div.setFixedHeight(32)
            div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
            main_layout.addWidget(div)

        # Color indicator mini strip
        mini = QFrame()
        mini.setFixedWidth(4)
        mini.setStyleSheet(f"background-color: {strip_c.name()}; border-radius: 2px;")
        main_layout.addWidget(mini)

        # INT/EXT badge
        ie_label = QLabel(ie)
        ie_label.setFont(theme.font_mono(9, bold=True))
        ie_label.setStyleSheet(f"""
            color: white;
            background-color: {strip_c.name()};
            border-radius: 3px;
            padding: 1px 4px;
            margin-left: 4px;
        """)
        main_layout.addWidget(ie_label)

        # Location
        loc = scene.get("location", "")
        loc_label = QLabel(loc)
        loc_label.setFont(theme.font_ui(11))
        loc_label.setStyleSheet(f"color: {theme.TEXT1.name()}; padding-left: 8px;")
        main_layout.addWidget(loc_label, 1)

        # Day/Night
        dn_label = QLabel(dn)
        dn_label.setFont(theme.font_mono(9))
        dn_label.setStyleSheet(f"color: {theme.TEXT3.name()};")
        main_layout.addWidget(dn_label)

        # Duration badge
        dur = self._format_duration(scene)
        if dur:
            dur_label = QLabel(dur)
            dur_label.setFont(theme.font_mono(10, bold=True))
            dur_label.setStyleSheet(f"""
                color: {theme.TEXT2.name()};
                background-color: {theme.BG0.name()};
                border: 1px solid {theme.qss_color(theme.BD1)};
                border-radius: 4px;
                padding: 1px 6px;
                margin-left: 8px;
            """)
            dur_label.setFixedWidth(60)
            dur_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(dur_label)

        # Intimacy warning
        if scene.get("requires_intimacy_coordinator"):
            ic_label = QLabel("\u2764")
            ic_label.setFixedWidth(20)
            ic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(ic_label)

        self._update_style()

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
            self.setStyleSheet(
                f"SceneStripRow {{ background-color: {theme.qss_color(theme.GOLD_BG)}; }}"
            )
        else:
            self.setStyleSheet(
                f"SceneStripRow {{ background-color: {theme.BG1.name()}; }}"
                f"SceneStripRow:hover {{ background-color: {theme.BG2.name()}; }}"
            )

    def mousePressEvent(self, event):
        self.clicked.emit(self._scene_id)


class DayBreakHeader(QFrame):
    def __init__(self, day, scene_count, pages, hours, locations, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet(f"background-color: {theme.BG3.name()};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(12)

        day_badge = QLabel(f"  GIORNO {day}  ")
        day_badge.setFont(theme.font_ui(10, bold=True))
        day_badge.setStyleSheet(f"""
            color: white;
            background-color: {theme.GOLD.name()};
            border-radius: 4px;
            padding: 2px 8px;
        """)
        layout.addWidget(day_badge)

        if locations:
            loc_text = ", ".join(locations[:3])
            if len(locations) > 3:
                loc_text += f" +{len(locations) - 3}"
            loc_label = QLabel(loc_text)
            loc_label.setFont(theme.font_ui(10))
            loc_label.setStyleSheet(f"color: {theme.TEXT2.name()};")
            layout.addWidget(loc_label)

        layout.addStretch()

        stats = QLabel(f"{scene_count} sc. \u00b7 {pages} pag. \u00b7 ~{hours:.1f} h")
        stats.setFont(theme.font_ui(10))
        stats.setStyleSheet(f"color: {theme.TEXT3.name()};")
        layout.addWidget(stats)


class StripboardView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._project_id = None
        self._compact = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
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

        tb_layout.addStretch()
        layout.addWidget(toolbar)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {theme.qss_color(theme.BD1)};")
        layout.addWidget(div)

        # Content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {theme.BG1.name()}; }}")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        self._strip_widgets = []

    def _ghost_btn_style(self):
        return f"""
            QPushButton {{
                color: {theme.TEXT2.name()};
                background: transparent;
                border: 1.5px solid {theme.qss_color(theme.BD1)};
                border-radius: 6px;
                padding: 5px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme.qss_color(theme.BD0)};
            }}
            QPushButton:checked {{
                color: {theme.GOLD.name()};
                border-color: {theme.qss_color(theme.GOLD_BD)};
                background-color: {theme.qss_color(theme.GOLD_BG)};
            }}
        """

    def _toggle_compact(self):
        self._compact = self._compact_btn.isChecked()
        if self._project_id:
            self.load_project(self._project_id)

    def load_project(self, project_id):
        self._project_id = project_id

        for w in self._strip_widgets:
            self._content_layout.removeWidget(w)
            w.deleteLater()
        self._strip_widgets.clear()

        db = self._container.database

        try:
            entries = db.execute(
                "SELECT se.shooting_day, se.scene_id, s.scene_number, s.location, "
                "s.int_ext, s.day_night, s.is_locked, s.requires_intimacy_coordinator, "
                "s.page_start_whole, s.page_start_eighths, s.page_end_whole, s.page_end_eighths "
                "FROM schedule_entries se "
                "JOIN scenes s ON se.scene_id = s.id "
                "WHERE se.project_id = ? "
                "ORDER BY se.shooting_day, se.position",
                (project_id,)
            ).fetchall()
        except Exception:
            entries = []

        if not entries:
            # Show scenes without schedule
            scenes = db.execute(
                "SELECT id, scene_number, location, int_ext, day_night, is_locked, "
                "requires_intimacy_coordinator, "
                "page_start_whole, page_start_eighths, page_end_whole, page_end_eighths "
                "FROM scenes WHERE project_id = ? ORDER BY id", (project_id,)
            ).fetchall()
            for s in scenes:
                scene = {
                    "id": s[0], "scene_number": s[1], "location": s[2],
                    "int_ext": s[3], "day_night": s[4], "is_locked": s[5],
                    "requires_intimacy_coordinator": s[6],
                    "page_start_whole": s[7], "page_start_eighths": s[8],
                    "page_end_whole": s[9], "page_end_eighths": s[10],
                }
                row = SceneStripRow(scene, self._compact)
                self._content_layout.insertWidget(
                    self._content_layout.count() - 1, row
                )
                self._strip_widgets.append(row)
            return

        # Group by shooting day
        days = {}
        for e in entries:
            day = e[0]
            scene = {
                "id": e[1], "scene_number": e[2], "location": e[3],
                "int_ext": e[4], "day_night": e[5], "is_locked": e[6],
                "requires_intimacy_coordinator": e[7],
                "page_start_whole": e[8], "page_start_eighths": e[9],
                "page_end_whole": e[10], "page_end_eighths": e[11],
            }
            days.setdefault(day, []).append(scene)

        for day_num in sorted(days.keys()):
            scenes_in_day = days[day_num]
            total_eighths = 0
            locations = []
            for sc in scenes_in_day:
                dur = Eighths(
                    sc.get("page_end_whole", 0) or 0,
                    sc.get("page_end_eighths", 0) or 0
                ) - Eighths(
                    sc.get("page_start_whole", 0) or 0,
                    sc.get("page_start_eighths", 0) or 0
                )
                total_eighths += dur.total_eighths
                loc = sc.get("location", "")
                if loc and loc not in locations:
                    locations.append(loc)

            pages_str = str(Eighths(total_eighths // 8, total_eighths % 8))
            hours = total_eighths / 8.0 * 1.5

            header = DayBreakHeader(
                day_num, len(scenes_in_day), pages_str, hours, locations
            )
            self._content_layout.insertWidget(
                self._content_layout.count() - 1, header
            )
            self._strip_widgets.append(header)

            for sc in scenes_in_day:
                row = SceneStripRow(sc, self._compact)
                self._content_layout.insertWidget(
                    self._content_layout.count() - 1, row
                )
                self._strip_widgets.append(row)

    def _start_regen(self):
        if self._project_id is None:
            return
        db = self._container.database
        rows = db.execute(
            'SELECT id, location, int_ext, day_night,'
            ' page_start_whole, page_start_eighths,'
            ' page_end_whole, page_end_eighths'
            ' FROM scenes WHERE project_id = ? ORDER BY id',
            (self._project_id,)
        ).fetchall()
        if not rows:
            return
        scenes = [
            {'id': r[0], 'location': r[1], 'int_ext': r[2],
             'day_night': r[3],
             'page_start_whole': r[4], 'page_start_eighths': r[5],
             'page_end_whole': r[6], 'page_end_eighths': r[7]}
            for r in rows
        ]
        proj_row = db.execute(
            'SELECT hours_per_shooting_day FROM projects WHERE id = ?',
            (self._project_id,)
        ).fetchone()
        max_hours = float(proj_row[0]) if proj_row and proj_row[0] else 10.0

        self._worker = SchedulerWorker(
            scenes, {'max_hours_per_day': max_hours},
            db, self._project_id
        )
        self._worker.finished.connect(self._on_regen_done)
        self._worker.error.connect(self._on_regen_error)
        self._worker.start()

    def _on_regen_done(self):
        if self._project_id:
            self.load_project(self._project_id)

    def _on_regen_error(self, msg):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, 'Errore scheduling', msg)

    def clear(self):
        self._project_id = None
        for w in self._strip_widgets:
            self._content_layout.removeWidget(w)
            w.deleteLater()
        self._strip_widgets.clear()
