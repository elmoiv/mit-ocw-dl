from PyQt6.QtCore import QThread, pyqtSignal

from downloader import DownloadManager, DownloadTask
from models import CourseData
from scraper import scrape_course


class ScrapeWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # CourseData
    error = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            data = scrape_course(self.url, progress_cb=self.progress.emit)
            self.finished.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))


class DownloadWorker(QThread):
    task_update = pyqtSignal(object)          # DownloadTask
    overall_update = pyqtSignal('long long', 'long long', float, float, float)  # current, total, speed, elapsed, remaining
    finished = pyqtSignal()

    def __init__(
        self,
        tasks: list,
        dest_root: str,
        max_workers: int = 3,
        parent=None,
    ):
        super().__init__(parent)
        self.tasks = tasks
        self.dest_root = dest_root
        self.max_workers = max_workers
        self._manager: DownloadManager | None = None

    def run(self):
        self._manager = DownloadManager(
            tasks=self.tasks,
            dest_root=self.dest_root,
            max_workers=self.max_workers,
            on_task_update=self.task_update.emit,
            on_overall_update=self.overall_update.emit,
            on_finished=self.finished.emit,
        )
        self._manager.start()
        # Block until manager signals finished via on_finished
        # (manager runs its own daemon threads; we just wait here)
        self.exec()  # Qt event loop keeps thread alive

    def stop_downloads(self):
        if self._manager:
            self._manager.stop()
