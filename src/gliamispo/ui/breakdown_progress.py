from PySide6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel
from PySide6.QtCore import Signal


class BreakdownProgress(QWidget):
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._status_label = QLabel("In attesa...")

        layout = QVBoxLayout(self)
        layout.addWidget(self._status_label)
        layout.addWidget(self._progress_bar)

        self.setVisible(False)

    def update_progress(self, value, message):
        self._progress_bar.setValue(int(value * 100))
        self._status_label.setText(message)
        self.setVisible(value < 1.0)

    def reset(self):
        self._progress_bar.setValue(0)
        self._status_label.setText("In attesa...")
        self.setVisible(False)
