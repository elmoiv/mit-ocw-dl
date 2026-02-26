# MIT OCW Downloader

A clean, fast, dark-themed desktop app to browse and batch-download course materials from [MIT OpenCourseWare](https://ocw.mit.edu) — built with PyQt6, requests, and BeautifulSoup4.

---

<img width="1920" height="1016" alt="image" src="https://github.com/user-attachments/assets/0e4c2b40-e1c3-4db4-afdb-31cf58ce60ef" />


---

## Features

| | |
|---|---|
| 🔍 **Smart scraping** | Parses the course `/download/` page and groups all files by section automatically |
| ☑️ **Granular selection** | Check/uncheck entire sections or individual files; parent checkboxes go tristate |
| 📊 **Live size summary** | Per-file size, per-section total, and selected total all update as you click |
| ⬇️ **Parallel downloads** | Configurable 1–8 worker threads; runs concurrently for maximum speed |
| ⏱️ **Rich progress UI** | Per-file progress bars with speed, overall bar, elapsed time, and ETA |
| ♻️ **Resume support** | Interrupted files pick back up via HTTP `Range` headers — no re-downloading |
| 📁 **Clean folder layout** | Output is organized as `<dir>/<course-slug>/<Section Name>/filename.ext` |
| 🌙 **Dark theme** | Fully styled with a professional dark palette — easy on the eyes |

---

## Requirements

- **Python 3.10+**
- PyQt6
- requests
- beautifulsoup4

---

## Installation

```bash
git clone https://github.com/elmoiv/mit-ocw-dl.git
cd mit-ocw-dl
pip install -r requirements.txt
```

Or install dependencies manually:

```bash
pip install PyQt6 requests beautifulsoup4
```

---

## Running

```bash
python main.py
```

---

## How to Use

### 1. Enter a course URL

Paste any MIT OCW course URL into the top bar. The app accepts the standard course page format:

```
https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020
```

You don't need to append `/download/` — the app handles that automatically.

### 2. Scrape

Click **🔍 Scrape**. The app fetches the download page, parses all sections (Lecture Videos, Problem Sets, Exams, etc.) and lists every file with its type and size. This runs in a background thread so the UI stays responsive.

### 3. Select what you want

- **Check/uncheck a section header** to toggle all files in that section at once.
- **Check/uncheck individual files** — the section header updates to reflect partial selection (tristate).
- Use **Select All** / **Deselect All** buttons for quick full toggles.
- The bottom bar shows a live count and total size of your current selection.

### 4. Choose output directory and workers

- Click **📂 Browse** to pick where files will be saved.
- Adjust **Workers** (default: 3) to control how many files download simultaneously. Higher values are faster on a good connection; lower values are gentler on the server.

### 5. Download

Click **⬇ Download Selected**. The progress panel expands at the bottom showing:

- A row per file with its own progress bar, downloaded/total size, and live speed
- An overall progress bar across all files
- Global speed, elapsed time, and estimated time remaining

### 6. Stop / Resume

Click **⬛ Stop** at any time. Partial files are kept on disk. When you click Download again on the same selection, each file resumes from where it left off — no bytes are wasted.

---

## Output Folder Structure

```
~/Downloads/
└── 6-006-introduction-to-algorithms-spring-2020/
    ├── Lecture Videos/
    │   ├── Lecture 1- Algorithms and Computation.mp4
    │   ├── Lecture 2- Data Structures and Dynamic Arrays.mp4
    │   └── ...
    ├── Problem Sets/
    │   ├── Problem Set 1.pdf
    │   └── ...
    ├── Exams/
    │   └── ...
    └── Lecture Notes/
        └── ...
```

Folder names are sanitized automatically (illegal characters removed/replaced).

---

## Project Structure

```
mit_ocw_downloader/
├── main.py                 # Entry point — creates QApplication and MainWindow
├── models.py               # Dataclasses: CourseData, Section, ResourceItem
├── scraper.py              # Fetches /download/ page, parses sections and files
├── downloader.py           # Thread-pool DownloadManager with resume support
├── utils.py                # Size parsing, bytes→human, seconds→human, name sanitizing
├── requirements.txt
└── ui/
    ├── main_window.py      # Top-level window; wires all components together
    ├── file_tree.py        # QTreeWidget with tristate checkboxes and live size signals
    ├── download_panel.py   # Per-task rows + overall stats bar
    └── workers.py          # QThread subclasses: ScrapeWorker, DownloadWorker
```

---

## Known Limitations

- Only works with courses that have a `/download/` page on OCW (most do, but some older ones don't).
- File sizes shown in the tree come from the HTML listing and may occasionally differ slightly from the actual download size.
- The app does not log in or bypass any access controls — it can only download publicly available materials.

---

## Dependencies

| Package | Purpose |
|---|---|
| `PyQt6` | GUI framework — windows, widgets, threading signals |
| `requests` | HTTP downloads with streaming and resume support |
| `beautifulsoup4` | HTML parsing of the OCW download page |

No other third-party libraries are used.

---

## License

MIT License. This tool is for personal educational use. Please respect MIT OCW's [Terms of Use](https://ocw.mit.edu/pages/privacy-and-terms-of-use/).
