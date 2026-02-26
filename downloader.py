import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional

import requests

from models import ResourceItem
from utils import clean_name

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    )
}
CHUNK_SIZE = 1024 * 64  # 64 KB


class TaskStatus(Enum):
    PENDING = auto()
    DOWNLOADING = auto()
    DONE = auto()
    ERROR = auto()
    SKIPPED = auto()


@dataclass
class DownloadTask:
    item: ResourceItem
    dest_folder: str
    status: TaskStatus = TaskStatus.PENDING
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error_msg: str = ''
    filename: str = ''
    speed: float = 0.0  # bytes/sec instant

    def __post_init__(self):
        self.total_bytes = self.item.file_size_bytes
        url = self.item.url
        raw = url.split('/')[-1].split('?')[0]
        extension = os.path.splitext(raw)[1] or self.item.resource_type
        self.filename = '{}{}'.format(clean_name(self.item.title), extension) if self.item.title else clean_name(raw)

    @property
    def progress_pct(self) -> float:
        if self.total_bytes > 0:
            return min(100.0, self.downloaded_bytes / self.total_bytes * 100)
        return 0.0


class DownloadManager:
    """Thread-pool based download manager."""

    def __init__(
        self,
        tasks: List[DownloadTask],
        dest_root: str,
        max_workers: int = 3,
        on_task_update: Optional[Callable[[DownloadTask], None]] = None,
        on_overall_update: Optional[Callable[[int, int, float, float, float], None]] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ):
        self.tasks = tasks
        self.dest_root = dest_root
        self.max_workers = max_workers
        self.on_task_update = on_task_update
        self.on_overall_update = on_overall_update
        self.on_finished = on_finished

        self._lock = threading.Lock()
        self._queue: List[DownloadTask] = list(tasks)
        self._active_count = 0
        self._stopped = False

        self._start_time: float = 0
        self._total_bytes = sum(t.total_bytes for t in tasks)
        self._completed_bytes = 0  # bytes from completed tasks
        # Track per-task partial bytes for in-flight reporting
        self._in_flight: dict = {}  # task_id -> bytes downloaded so far

    # ------------------------------------------------------------------ #
    def start(self):
        self._start_time = time.monotonic()
        self._stopped = False
        self._spawn_workers()

    def stop(self):
        self._stopped = True

    # ------------------------------------------------------------------ #
    def _spawn_workers(self):
        with self._lock:
            while self._active_count < self.max_workers and self._queue:
                task = self._queue.pop(0)
                self._active_count += 1
                t = threading.Thread(
                    target=self._run_task, args=(task,), daemon=True
                )
                t.start()

    def _on_task_finish(self, task: DownloadTask):
        """Called when a task completes/errors (inside thread)."""
        with self._lock:
            # Move in-flight bytes to completed
            in_flight = self._in_flight.pop(id(task), 0)
            if task.status == TaskStatus.DONE:
                self._completed_bytes += task.downloaded_bytes
            self._active_count -= 1
            spawn = not self._stopped

        if self.on_task_update:
            self.on_task_update(task)
        self._emit_overall()

        if spawn:
            self._spawn_workers()

        with self._lock:
            all_done = self._active_count == 0 and not self._queue
        if all_done and self.on_finished:
            self.on_finished()

    def _emit_overall(self):
        if not self.on_overall_update:
            return
        with self._lock:
            in_flight_bytes = sum(self._in_flight.values())
            current_bytes = self._completed_bytes + in_flight_bytes
            elapsed = time.monotonic() - self._start_time
        speed = current_bytes / elapsed if elapsed > 0 else 0.0
        remaining_bytes = max(0, self._total_bytes - current_bytes)
        self.on_overall_update(current_bytes, self._total_bytes, speed, elapsed, remaining_bytes)

    def _run_task(self, task: DownloadTask):
        with self._lock:
            self._in_flight[id(task)] = 0

        try:
            os.makedirs(task.dest_folder, exist_ok=True)
            filepath = os.path.join(task.dest_folder, task.filename)

            # Resume support
            resume_bytes = 0
            extra_headers = {}
            if os.path.exists(filepath):
                resume_bytes = os.path.getsize(filepath)
                extra_headers['Range'] = f'bytes={resume_bytes}-'

            task.status = TaskStatus.DOWNLOADING
            if self.on_task_update:
                self.on_task_update(task)

            resp = requests.get(
                task.item.url,
                headers={**HEADERS, **extra_headers},
                stream=True,
                timeout=60,
            )

            if resp.status_code == 416:
                # Already fully downloaded
                task.status = TaskStatus.DONE
                task.downloaded_bytes = task.total_bytes
                self._on_task_finish(task)
                return

            resp.raise_for_status()

            # Update actual total size
            content_length = resp.headers.get('Content-Length')
            if content_length:
                cl = int(content_length)
                task.total_bytes = (resume_bytes + cl) if resp.status_code == 206 else cl

            write_mode = 'ab' if resp.status_code == 206 else 'wb'
            task.downloaded_bytes = resume_bytes

            speed_window: list = []  # (time, bytes) pairs for rolling speed
            last_speed_time = time.monotonic()
            last_speed_bytes = 0

            with open(filepath, write_mode) as fh:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if self._stopped:
                        task.status = TaskStatus.PENDING
                        self._on_task_finish(task)
                        return
                    if not chunk:
                        continue

                    fh.write(chunk)
                    n = len(chunk)
                    task.downloaded_bytes += n

                    with self._lock:
                        self._in_flight[id(task)] = task.downloaded_bytes

                    # Rolling speed (1 s window)
                    now = time.monotonic()
                    if now - last_speed_time >= 0.5:
                        delta_t = now - last_speed_time
                        delta_b = task.downloaded_bytes - last_speed_bytes
                        task.speed = delta_b / delta_t if delta_t > 0 else 0
                        last_speed_time = now
                        last_speed_bytes = task.downloaded_bytes

                    if self.on_task_update:
                        self.on_task_update(task)
                    self._emit_overall()

            task.status = TaskStatus.DONE
        except Exception as exc:
            task.status = TaskStatus.ERROR
            task.error_msg = str(exc)

        self._on_task_finish(task)
