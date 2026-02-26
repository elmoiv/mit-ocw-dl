import os

from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from downloader import DownloadTask
from models import CourseData
from ui.download_panel import DownloadPanel
from ui.file_tree import FileTreeWidget
from ui.workers import DownloadWorker, ScrapeWorker
from utils import bytes_to_human, clean_name


# ── Helpers ──────────────────────────────────────────────────────────────── #
DARK_BG = '#0d1117'
CARD_BG = '#161b22'
ACCENT = '#4fc3f7'
BTN_PRIMARY = '#1565c0'
BTN_DANGER = '#c62828'
BTN_SUCCESS = '#2e7d32'
TEXT_MAIN = '#e6edf3'
TEXT_DIM = '#8b949e'
BORDER = '#30363d'


def _make_btn(text: str, color: str, min_w: int = 120) -> QPushButton:
    btn = QPushButton(text)
    btn.setMinimumWidth(min_w)
    btn.setFixedHeight(34)
    btn.setStyleSheet(
        f'QPushButton {{'
        f'  background: {color}; color: white; border: none;'
        f'  border-radius: 5px; font-size: 13px; font-weight: bold; padding: 0 14px;'
        f'}}'
        f'QPushButton:hover {{ background: {color}dd; }}'
        f'QPushButton:pressed {{ background: {color}aa; }}'
        f'QPushButton:disabled {{ background: #333; color: #666; }}'
    )
    return btn


def _make_line_edit(placeholder: str = '') -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setFixedHeight(34)
    le.setStyleSheet(
        f'QLineEdit {{'
        f'  background: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid {BORDER};'
        f'  border-radius: 5px; padding: 0 10px; font-size: 13px;'
        f'}}'
        f'QLineEdit:focus {{ border: 1px solid {ACCENT}; }}'
    )
    return le


def _card(parent=None) -> QFrame:
    frame = QFrame(parent)
    frame.setStyleSheet(
        f'QFrame {{ background: {CARD_BG}; border: 1px solid {BORDER};'
        f' border-radius: 8px; }}'
    )
    return frame


# ── Main Window ──────────────────────────────────────────────────────────── #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('MIT OCW Downloader')
        self.resize(960, 780)
        self.setMinimumSize(780, 560)

        self._course_data: CourseData | None = None
        self._scrape_worker: ScrapeWorker | None = None
        self._dl_worker: DownloadWorker | None = None
        self._downloading = False

        self._apply_dark_theme()
        self._build_ui()

        self._settings = QSettings('MITOCWDownloader', 'App')
        saved_dir = self._settings.value('last_download_dir', os.path.expanduser('~/Downloads'))
        self._dir_input.setText(saved_dir)

    # ------------------------------------------------------------------ #
    # Theme
    # ------------------------------------------------------------------ #
    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(DARK_BG))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_MAIN))
        palette.setColor(QPalette.ColorRole.Base, QColor(CARD_BG))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor('#1c2128'))
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_MAIN))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_MAIN))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor('#000'))
        self.setPalette(palette)
        self.setStyleSheet(
            f'QMainWindow {{ background: {DARK_BG}; }}'
            f'QTreeWidget {{ background: {CARD_BG}; color: {TEXT_MAIN}; '
            f'  border: 1px solid {BORDER}; border-radius: 6px; '
            f'  alternate-background-color: #1c2128; outline: 0; }}'
            f'QTreeWidget::item {{ padding: 3px 4px; }}'
            f'QTreeWidget::item:hover {{ background: #21262d; }}'
            f'QTreeWidget::item:selected {{ background: #1f3a5f; }}'
            f'QHeaderView::section {{ background: #21262d; color: {TEXT_DIM};'
            f'  border: none; border-bottom: 1px solid {BORDER}; padding: 5px; }}'
            f'QScrollBar:vertical {{ background: {CARD_BG}; width: 8px; }}'
            f'QScrollBar::handle:vertical {{ background: #333; border-radius: 4px; min-height: 20px; }}'
            f'QLabel {{ color: {TEXT_MAIN}; }}'
            f'QStatusBar {{ background: #0d1117; color: {TEXT_DIM}; border-top: 1px solid {BORDER}; }}'
            f'QSpinBox {{ background: {CARD_BG}; color: {TEXT_MAIN}; border: 1px solid {BORDER};'
            f'  border-radius: 4px; padding: 3px 6px; }}'
            f'QCheckBox {{ color: {TEXT_DIM}; spacing: 6px; }}'
            f'QCheckBox::indicator {{ width: 16px; height: 16px; }}'
        )

    # ------------------------------------------------------------------ #
    # UI Construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        # ── Header ──
        root.addWidget(self._build_header())

        # ── Input card ──
        root.addWidget(self._build_input_card())

        # ── Status log label ──
        self._lbl_log = QLabel('Enter a course URL and click Scrape.')
        self._lbl_log.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')
        root.addWidget(self._lbl_log)

        # ── Selection toolbar ──
        self._sel_bar = self._build_selection_bar()
        self._sel_bar.setVisible(False)
        root.addWidget(self._sel_bar)

        # ── File tree ──
        self._tree = FileTreeWidget()
        self._tree.setVisible(False)
        self._tree.selection_changed.connect(self._on_selection_changed)
        root.addWidget(self._tree, 1)

        # ── Download panel ──
        self._dl_panel = DownloadPanel()
        self._dl_panel.setVisible(False)
        root.addWidget(self._dl_panel)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage('Ready')

    def _build_header(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)

        title = QLabel('🎓  MIT OCW Downloader')
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet(f'color: {ACCENT};')

        sub = QLabel('Download course materials from MIT OpenCourseWare')
        sub.setStyleSheet(f'color: {TEXT_DIM}; font-size: 11px;')

        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(title)
        col.addWidget(sub)

        h.addLayout(col)
        h.addStretch()
        return w

    def _build_input_card(self) -> QFrame:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Row 1 – URL input
        row1 = QHBoxLayout()
        lbl = QLabel('Course URL:')
        lbl.setFixedWidth(90)
        lbl.setStyleSheet(f'color: {TEXT_DIM};')
        self._url_input = _make_line_edit(
            'e.g. https://ocw.mit.edu/courses/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX/'
        )
        self._btn_scrape = _make_btn('🔍  Scrape', BTN_PRIMARY, 120)
        self._btn_scrape.clicked.connect(self._on_scrape)

        row1.addWidget(lbl)
        row1.addWidget(self._url_input, 1)
        row1.addWidget(self._btn_scrape)
        layout.addLayout(row1)

        # Row 2 – Output dir + workers
        row2 = QHBoxLayout()
        lbl2 = QLabel('Save to:')
        lbl2.setFixedWidth(90)
        lbl2.setStyleSheet(f'color: {TEXT_DIM};')
        self._dir_input = _make_line_edit('Select output directory…')
        self._dir_input.setText(os.path.expanduser('~/Downloads'))
        btn_dir = _make_btn('📂  Browse', '#37474f', 110)
        btn_dir.clicked.connect(self._browse_dir)

        lbl3 = QLabel('Workers:')
        lbl3.setStyleSheet(f'color: {TEXT_DIM};')
        self._spin_workers = QSpinBox()
        self._spin_workers.setRange(1, 8)
        self._spin_workers.setValue(3)
        self._spin_workers.setFixedWidth(58)
        self._spin_workers.setToolTip('Parallel download threads')

        row2.addWidget(lbl2)
        row2.addWidget(self._dir_input, 1)
        row2.addWidget(btn_dir)
        row2.addSpacing(14)
        row2.addWidget(lbl3)
        row2.addWidget(self._spin_workers)
        layout.addLayout(row2)

        # Row 3 – Download button + stop
        row3 = QHBoxLayout()
        self._lbl_sel_summary = QLabel('No files selected')
        self._lbl_sel_summary.setStyleSheet(f'color: {TEXT_DIM}; font-size: 12px;')

        self._btn_download = _make_btn('⬇  Download Selected', BTN_SUCCESS, 180)
        self._btn_download.setEnabled(False)
        self._btn_download.clicked.connect(self._on_download)

        self._btn_stop = _make_btn('⬛  Stop', BTN_DANGER, 100)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        row3.addWidget(self._lbl_sel_summary, 1)
        row3.addWidget(self._btn_download)
        row3.addWidget(self._btn_stop)
        layout.addLayout(row3)

        return card

    def _build_selection_bar(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        lbl = QLabel('Quick Select:')
        lbl.setStyleSheet(f'color: {TEXT_DIM};')
        h.addWidget(lbl)

        btn_all = QPushButton('✔  Select All')
        btn_none = QPushButton('☐  Deselect All')
        for b in (btn_all, btn_none):
            b.setFixedHeight(28)
            b.setStyleSheet(
                f'QPushButton {{ background: #21262d; color: {TEXT_MAIN};'
                f' border: 1px solid {BORDER}; border-radius: 4px; padding: 0 10px; font-size: 12px; }}'
                f'QPushButton:hover {{ background: #30363d; }}'
            )
        btn_all.clicked.connect(lambda: self._tree.select_all(True))
        btn_none.clicked.connect(lambda: self._tree.select_all(False))

        h.addWidget(btn_all)
        h.addWidget(btn_none)
        h.addStretch()
        return w

    # ------------------------------------------------------------------ #
    # Slots – Scraping
    # ------------------------------------------------------------------ #
    def _on_scrape(self):
        url = self._url_input.text().strip()
        if not url:
            QMessageBox.warning(self, 'No URL', 'Please enter a course URL.')
            return
        if not url.startswith('http'):
            url = 'https://' + url
            self._url_input.setText(url)

        self._btn_scrape.setEnabled(False)
        self._btn_scrape.setText('Scraping…')
        self._tree.setVisible(False)
        self._sel_bar.setVisible(False)
        self._dl_panel.setVisible(False)
        self._btn_download.setEnabled(False)
        self._lbl_log.setStyleSheet(f'color: {ACCENT}; font-size: 11px;')
        self._lbl_log.setText('🔄  Connecting…')

        self._scrape_worker = ScrapeWorker(url)
        self._scrape_worker.progress.connect(self._on_scrape_progress)
        self._scrape_worker.finished.connect(self._on_scrape_done)
        self._scrape_worker.error.connect(self._on_scrape_error)
        self._scrape_worker.start()

    def _on_scrape_progress(self, msg: str):
        self._lbl_log.setText(f'🔄  {msg}')

    def _on_scrape_done(self, course: CourseData):
        self._course_data = course
        self._btn_scrape.setEnabled(True)
        self._btn_scrape.setText('🔍  Scrape')
        self._lbl_log.setStyleSheet(f'color: #66bb6a; font-size: 11px;')
        total = sum(len(s.items) for s in course.sections)
        self._lbl_log.setText(
            f'✔  {course.title}  —  {len(course.sections)} sections, {total} files'
        )

        self._tree.load_course(course)
        self._tree.setVisible(True)
        self._sel_bar.setVisible(True)
        self._status_bar.showMessage(f'Loaded: {course.title}')

    def _on_scrape_error(self, msg: str):
        self._btn_scrape.setEnabled(True)
        self._btn_scrape.setText('🔍  Scrape')
        self._lbl_log.setStyleSheet('color: #ef5350; font-size: 11px;')
        self._lbl_log.setText(f'✖  Error: {msg}')
        QMessageBox.critical(self, 'Scrape Failed', msg)

    # ------------------------------------------------------------------ #
    # Slots – Selection
    # ------------------------------------------------------------------ #
    def _on_selection_changed(self, count: int, total_bytes: int):
        if count == 0:
            self._lbl_sel_summary.setText('No files selected')
            self._btn_download.setEnabled(False)
        else:
            print(count, total_bytes)
            self._lbl_sel_summary.setText(
                f'{count} file{"s" if count != 1 else ""} selected  •  '
                f'{bytes_to_human(total_bytes)} total'
            )
            self._btn_download.setEnabled(not self._downloading)

    # ------------------------------------------------------------------ #
    # Slots – Download
    # ------------------------------------------------------------------ #
    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, 'Select Output Directory', self._dir_input.text()
        )
        if d:
            self._dir_input.setText(d)
            self._settings.setValue('last_download_dir', d)

    def _on_download(self):
        if not self._course_data:
            return
        out_root = self._dir_input.text().strip()
        self._settings.setValue('last_download_dir', out_root)
        if not out_root:
            QMessageBox.warning(self, 'No Directory', 'Please select an output directory.')
            return

        selected = self._tree.get_selected_items()
        if not selected:
            QMessageBox.warning(self, 'Nothing Selected', 'Select at least one file.')
            return

        # Build tasks
        course_folder = os.path.join(out_root, self._course_data.folder_name)
        tasks = []
        for res, section_name in selected:
            sec_folder = os.path.join(course_folder, clean_name(section_name))
            task = DownloadTask(item=res, dest_folder=sec_folder)
            tasks.append(task)

        # Reset panel
        self._dl_panel.reset()
        for t in tasks:
            self._dl_panel.add_task(t)
        self._dl_panel.setVisible(True)

        self._downloading = True
        self._btn_download.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._btn_scrape.setEnabled(False)

        workers = self._spin_workers.value()
        self._dl_worker = DownloadWorker(tasks, course_folder, max_workers=workers)
        self._dl_worker.task_update.connect(self._on_task_update)
        self._dl_worker.overall_update.connect(self._on_overall_update)
        self._dl_worker.finished.connect(self._on_download_finished)
        self._dl_worker.start()

        self._status_bar.showMessage(
            f'Downloading {len(tasks)} files → {course_folder}'
        )

    def _on_task_update(self, task: DownloadTask):
        self._dl_panel.update_task(task)

    def _on_overall_update(
        self, current: int, total: int, speed: float, elapsed: float, remaining: float
    ):
        self._dl_panel.update_overall(current, total, speed, elapsed, remaining)

    def _on_download_finished(self):
        self._downloading = False
        self._btn_download.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_scrape.setEnabled(True)
        self._dl_panel.set_finished()
        self._status_bar.showMessage('Download complete ✔')
        if self._dl_worker:
            self._dl_worker.quit()
            self._dl_worker = None

    def _on_stop(self):
        if self._dl_worker:
            self._dl_worker.stop_downloads()
            self._dl_worker = None
        self._downloading = False
        self._btn_stop.setEnabled(False)
        self._btn_download.setEnabled(True)
        self._btn_scrape.setEnabled(True)
        self._dl_panel.set_finished()
        self._status_bar.showMessage('Download stopped.')

    # ------------------------------------------------------------------ #
    def closeEvent(self, event):
        if self._dl_worker:
            self._dl_worker.stop_downloads()
        event.accept()
