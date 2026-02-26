from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from downloader import DownloadTask, TaskStatus
from utils import bytes_to_human, seconds_to_human


# ── Single task row ──────────────────────────────────────────────────────── #
class TaskRow(QWidget):
    def __init__(self, task: DownloadTask, parent=None):
        super().__init__(parent)
        self.task = task

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self._lbl_name = QLabel(task.filename)
        self._lbl_name.setMaximumWidth(340)
        self._lbl_name.setToolTip(task.item.url)
        f = QFont()
        f.setPointSize(9)
        self._lbl_name.setFont(f)

        self._lbl_status = QLabel('Pending')
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._lbl_status.setFont(f)
        top.addWidget(self._lbl_name, 1)
        top.addWidget(self._lbl_status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(12)
        self._bar.setTextVisible(False)

        layout.addLayout(top)
        layout.addWidget(self._bar)

        self.setStyleSheet(
            'TaskRow { border-bottom: 1px solid #2a2a2a; }'
        )

    def refresh(self):
        task = self.task
        status_colors = {
            TaskStatus.PENDING: '#888888',
            TaskStatus.DOWNLOADING: '#4fc3f7',
            TaskStatus.DONE: '#66bb6a',
            TaskStatus.ERROR: '#ef5350',
            TaskStatus.SKIPPED: '#ffa726',
        }
        color = status_colors.get(task.status, '#aaaaaa')

        if task.status == TaskStatus.DOWNLOADING:
            pct = task.progress_pct
            down = bytes_to_human(task.downloaded_bytes)
            total = bytes_to_human(task.total_bytes)
            spd = bytes_to_human(int(task.speed)) + '/s'
            self._lbl_status.setText(f'{down} / {total}  •  {spd}')
            self._bar.setValue(int(pct))
        elif task.status == TaskStatus.DONE:
            self._lbl_status.setText(f'✔  {bytes_to_human(task.downloaded_bytes)}')
            self._bar.setValue(100)
        elif task.status == TaskStatus.ERROR:
            self._lbl_status.setText(f'✖  {task.error_msg[:60]}')
        else:
            self._lbl_status.setText(task.status.name.capitalize())

        self._lbl_status.setStyleSheet(f'color: {color};')
        bar_style = (
            f'QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}'
            'QProgressBar { background: #2a2a2a; border-radius: 2px; }'
        )
        self._bar.setStyleSheet(bar_style)


# ── Main panel ───────────────────────────────────────────────────────────── #
class DownloadPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            'DownloadPanel { background: #1a1a2e; border-top: 2px solid #4fc3f7; }'
        )
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Header stats row
        stats_row = QHBoxLayout()
        label_style = 'color: #ccddff; font-size: 11px;'

        self._lbl_overall = QLabel('Overall Progress')
        self._lbl_overall.setStyleSheet('color: #4fc3f7; font-weight: bold; font-size: 12px;')

        self._lbl_speed = QLabel('Speed: --')
        self._lbl_speed.setStyleSheet(label_style)
        self._lbl_elapsed = QLabel('Elapsed: 00:00')
        self._lbl_elapsed.setStyleSheet(label_style)
        self._lbl_remaining = QLabel('Remaining: --:--')
        self._lbl_remaining.setStyleSheet(label_style)
        self._lbl_size = QLabel('0 B / 0 B')
        self._lbl_size.setStyleSheet(label_style)

        stats_row.addWidget(self._lbl_overall)
        stats_row.addStretch()
        stats_row.addWidget(self._lbl_size)
        stats_row.addWidget(QLabel('|'))
        stats_row.addWidget(self._lbl_speed)
        stats_row.addWidget(QLabel('|'))
        stats_row.addWidget(self._lbl_elapsed)
        stats_row.addWidget(QLabel('|'))
        stats_row.addWidget(self._lbl_remaining)
        root.addLayout(stats_row)

        # Overall bar
        self._overall_bar = QProgressBar()
        self._overall_bar.setRange(0, 1000)
        self._overall_bar.setValue(0)
        self._overall_bar.setFixedHeight(16)
        self._overall_bar.setFormat('%v‰')
        self._overall_bar.setTextVisible(False)
        self._overall_bar.setStyleSheet(
            'QProgressBar { background: #2a2a2a; border-radius: 3px; }'
            'QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 #1565c0, stop:1 #4fc3f7); border-radius: 3px; }'
        )
        root.addWidget(self._overall_bar)

        # Scroll area for task rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; }')

        self._task_container = QWidget()
        self._task_container.setStyleSheet('background: transparent;')
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 0, 0, 0)
        self._task_layout.setSpacing(0)
        self._task_layout.addStretch()

        scroll.setWidget(self._task_container)
        root.addWidget(scroll)

        self._rows: dict[int, TaskRow] = {}  # task id -> row

    # ------------------------------------------------------------------ #
    def reset(self):
        self._rows.clear()
        while self._task_layout.count() > 1:
            item = self._task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._overall_bar.setValue(0)
        self._lbl_size.setText('0 B / 0 B')
        self._lbl_speed.setText('Speed: --')
        self._lbl_elapsed.setText('Elapsed: 00:00')
        self._lbl_remaining.setText('Remaining: --:--')

    def add_task(self, task: DownloadTask):
        row = TaskRow(task)
        self._rows[id(task)] = row
        self._task_layout.insertWidget(self._task_layout.count() - 1, row)

    def update_task(self, task: DownloadTask):
        row = self._rows.get(id(task))
        if row:
            row.refresh()

    def update_overall(
        self, current: int, total: int, speed: float, elapsed: float, remaining_bytes: float
    ):
        if total > 0:
            pct = int(current / total * 1000)
            self._overall_bar.setValue(pct)
        self._lbl_size.setText(f'{bytes_to_human(current)} / {bytes_to_human(total)}')
        self._lbl_speed.setText(f'Speed: {bytes_to_human(int(speed))}/s')
        self._lbl_elapsed.setText(f'Elapsed: {seconds_to_human(elapsed)}')
        eta = (remaining_bytes / speed) if speed > 0 else float('inf')
        self._lbl_remaining.setText(f'ETA: {seconds_to_human(eta)}')

    def set_finished(self):
        self._lbl_remaining.setText('ETA: Done ✔')
        self._overall_bar.setValue(1000)
