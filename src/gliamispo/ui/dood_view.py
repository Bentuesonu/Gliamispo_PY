from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QFrame, QHeaderView, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor
from gliamispo.ui import theme


DOOD_STATES = ['', 'W', 'T', 'H', 'F']

STATUS_COLORS = {
    'W': ('#1E8449', '#FFFFFF'),   # verde / testo bianco
    'T': ('#B7950B', '#FFFFFF'),   # giallo scuro / testo bianco
    'H': ('#707B7C', '#FFFFFF'),   # grigio / testo bianco
    'F': ('#922B21', '#FFFFFF'),   # rosso / testo bianco
    '':  (None,      None),
}


class DayOutOfDaysView(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container  = container
        self._project_id = None
        self._cast_names = []
        self._day_nums   = []
        self._matrix     = {}   # {actor: {day: status}}

        self.setStyleSheet(f'background-color: {theme.BG1.name()};')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f'background-color: {theme.BG2.name()};')
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 10, 16, 10)
        title = QLabel('DAY OUT OF DAYS')
        title.setFont(theme.font_ui(12, bold=True))
        title.setStyleSheet(f'color: {theme.TEXT0.name()};')
        h_layout.addWidget(title)
        h_layout.addStretch()
        self._info = QLabel('')
        self._info.setFont(theme.font_ui(11))
        self._info.setStyleSheet(f'color: {theme.TEXT3.name()};')
        h_layout.addWidget(self._info)

        export_btn = QPushButton('Esporta PDF')
        export_btn.setFont(theme.font_ui(11))
        export_btn.setStyleSheet(f'''
            QPushButton {{
                color: {theme.GOLD.name()};
                background-color: {theme.qss_color(theme.GOLD_BG)};
                border: 1.5px solid {theme.qss_color(theme.GOLD_BD)};
                border-radius: 6px; padding: 5px 14px;
            }}
        ''')
        export_btn.clicked.connect(self._export_pdf)
        h_layout.addWidget(export_btn)

        layout.addWidget(header)

        # Legenda
        legend = QWidget()
        legend.setStyleSheet(f'background-color: {theme.BG3.name()};')
        leg_layout = QHBoxLayout(legend)
        leg_layout.setContentsMargins(16, 6, 16, 6)
        leg_layout.setSpacing(16)
        for code, label, color in [
            ('W', 'Working', '#1E8449'),
            ('T', 'Travel',  '#B7950B'),
            ('H', 'Hold',    '#707B7C'),
            ('F', 'Finished','#922B21'),
        ]:
            lbl = QLabel(f'{code} – {label}')
            lbl.setFont(theme.font_ui(10))
            lbl.setStyleSheet(
                f'color: white; background-color: {color};'
                f' border-radius: 3px; padding: 2px 8px;'
            )
            leg_layout.addWidget(lbl)
        leg_layout.addStretch()
        hint = QLabel('Clicca una cella per cambiare stato')
        hint.setFont(theme.font_ui(10))
        hint.setStyleSheet(f'color: {theme.TEXT4.name()};')
        leg_layout.addWidget(hint)
        layout.addWidget(legend)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f'background-color: {theme.qss_color(theme.BD1)};')
        layout.addWidget(div)

        # Tabella
        self._table = QTableWidget()
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(f'''
            QTableWidget {{
                background-color: {theme.BG1.name()};
                border: none;
                gridline-color: {theme.qss_color(theme.BD0)};
            }}
            QHeaderView::section {{
                background-color: {theme.BG3.name()};
                color: {theme.TEXT2.name()};
                border: none;
                border-bottom: 1px solid {theme.qss_color(theme.BD1)};
                padding: 6px 4px;
                font-size: 10px; font-weight: 600;
            }}
            QTableWidget::item {{ text-align: center; padding: 2px; }}
        ''')
        self._table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self._table, 1)

    # ── Caricamento ──────────────────────────────────────────────────
    def load_project(self, project_id):
        self._project_id = project_id
        db = self._container.database

        # 1. Leggi gli attori
        cast = db.execute(
            'SELECT DISTINCT element_name FROM scene_elements'
            " WHERE category = 'Cast' AND scene_id IN"
            ' (SELECT id FROM scenes WHERE project_id = ?)'
            ' ORDER BY element_name',
            (project_id,)
        ).fetchall()
        self._cast_names = [c[0] for c in cast]

        # 2. Leggi i giorni di ripresa
        try:
            days = db.execute(
                'SELECT DISTINCT shooting_day FROM schedule_entries'
                ' WHERE project_id = ? ORDER BY shooting_day',
                (project_id,)
            ).fetchall()
            self._day_nums = [d[0] for d in days]
        except Exception:
            self._day_nums = []

        if not self._day_nums:
            n = db.execute(
                'SELECT COUNT(*) FROM scenes WHERE project_id = ?',
                (project_id,)
            ).fetchone()[0]
            self._day_nums = list(range(1, n + 1))

        # 3. Mappa scena → giorni
        scene_days = {}
        try:
            entries = db.execute(
                'SELECT scene_id, shooting_day FROM schedule_entries'
                ' WHERE project_id = ?',
                (project_id,)
            ).fetchall()
            for e in entries:
                scene_days.setdefault(e[0], []).append(e[1])
        except Exception:
            pass
        if not scene_days:
            scenes = db.execute(
                'SELECT id FROM scenes WHERE project_id = ? ORDER BY id',
                (project_id,)
            ).fetchall()
            for idx, s in enumerate(scenes):
                scene_days[s[0]] = [idx + 1]

        # 4. Calcola matrice automatica (Working + Hold)
        actor_work_days = {}
        for actor in self._cast_names:
            sc_rows = db.execute(
                'SELECT scene_id FROM scene_elements'
                " WHERE element_name = ? AND category = 'Cast'"
                ' AND scene_id IN'
                ' (SELECT id FROM scenes WHERE project_id = ?)',
                (actor, project_id),
            ).fetchall()
            work = set()
            for sf in sc_rows:
                for d in scene_days.get(sf[0], []):
                    work.add(d)
            actor_work_days[actor] = work

        # Costruisci matrice con Hold automatico
        self._matrix = {}
        for actor, work_set in actor_work_days.items():
            if not work_set:
                continue
            first = min(work_set)
            last  = max(work_set)
            row   = {}
            for day in self._day_nums:
                if day < first or day > last:
                    row[day] = ''
                elif day in work_set:
                    row[day] = 'W'
                else:
                    row[day] = 'H'
            self._matrix[actor] = row

        # 5. Sovrascrivi con modifiche manuali salvate
        try:
            manual = db.execute(
                'SELECT actor_name, shoot_day, status'
                ' FROM dood_entries WHERE project_id = ?',
                (project_id,)
            ).fetchall()
            for m in manual:
                self._matrix.setdefault(m[0], {})[m[1]] = m[2]
        except Exception:
            pass

        self._rebuild_table()

    # ── Ricostruzione tabella ─────────────────────────────────────────
    def _rebuild_table(self):
        actors = [a for a in self._cast_names if a in self._matrix]
        headers = ['Attore'] + [f'G{d}' for d in self._day_nums] + ['Tot']
        self._table.blockSignals(True)
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(actors))

        for i, actor in enumerate(actors):
            # Colonna 0: nome attore
            name_item = QTableWidgetItem(actor)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            name_item.setFont(theme.font_ui(11, bold=True))
            self._table.setItem(i, 0, name_item)

            total = 0
            for j, day in enumerate(self._day_nums):
                status = self._matrix.get(actor, {}).get(day, '')
                item   = self._make_cell(status)
                if status == 'W':
                    total += 1
                self._table.setItem(i, j + 1, item)

            tot_item = QTableWidgetItem(str(total))
            tot_item.setFlags(tot_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tot_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tot_item.setFont(theme.font_ui(11, bold=True))
            self._table.setItem(i, len(headers) - 1, tot_item)

        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.blockSignals(False)
        self._info.setText(
            f'{len(actors)} attori · {len(self._day_nums)} giorni'
        )

    def _make_cell(self, status):
        item = QTableWidgetItem(status)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        bg, fg = STATUS_COLORS.get(status, (None, None))
        if bg:
            item.setBackground(QColor(bg))
            item.setForeground(QColor(fg))
        return item

    # ── Click su cella ───────────────────────────────────────────────
    def _on_cell_clicked(self, row, col):
        # Ignora colonna 0 (nome) e ultima (totale)
        if col == 0 or col == self._table.columnCount() - 1:
            return
        actors = [a for a in self._cast_names if a in self._matrix]
        if row >= len(actors):
            return
        actor = actors[row]
        day   = self._day_nums[col - 1]

        current = self._matrix.get(actor, {}).get(day, '')
        idx     = DOOD_STATES.index(current) if current in DOOD_STATES else 0
        nxt     = DOOD_STATES[(idx + 1) % len(DOOD_STATES)]

        self._matrix.setdefault(actor, {})[day] = nxt
        self._persist(actor, day, nxt)

        # Aggiorna solo la cella cliccata + totale
        self._table.setItem(row, col, self._make_cell(nxt))
        total = sum(
            1 for d in self._day_nums
            if self._matrix.get(actor, {}).get(d, '') == 'W'
        )
        tot_item = QTableWidgetItem(str(total))
        tot_item.setFlags(tot_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tot_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tot_item.setFont(theme.font_ui(11, bold=True))
        self._table.setItem(row, self._table.columnCount() - 1, tot_item)

    def _persist(self, actor, day, status):
        if self._project_id is None:
            return
        try:
            self._container.database.execute(
                'INSERT INTO dood_entries'
                ' (project_id, actor_name, shoot_day, status)'
                ' VALUES (?, ?, ?, ?)'
                ' ON CONFLICT(project_id, actor_name, shoot_day)'
                ' DO UPDATE SET status = excluded.status',
                (self._project_id, actor, day, status),
            )
            self._container.database.commit()
        except Exception:
            pass

    def _export_pdf(self):
        from PyQt6.QtWidgets import QFileDialog
        from gliamispo.export.pdf_exporter import DayOutOfDaysExporter

        if not self._cast_names:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Salva DOOD PDF', '', 'PDF (*.pdf)'
        )
        if not path:
            return

        actors = [a for a in self._cast_names if a in self._matrix]
        db_row = self._container.database.execute(
            'SELECT title FROM projects WHERE id = ?',
            (self._project_id,)
        ).fetchone()
        title = db_row[0] if db_row else ''

        data = DayOutOfDaysExporter(title).export(
            actors, self._day_nums, self._matrix
        )
        if data:
            with open(path, 'wb') as f:
                f.write(data)

    def clear(self):
        self._project_id = None
        self._cast_names = []
        self._day_nums   = []
        self._matrix     = {}
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._info.setText('')
