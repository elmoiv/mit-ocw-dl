import re


UNIT_MAP = {
    'B': 1,
    'KB': 1024,
    'MB': 1024 ** 2,
    'GB': 1024 ** 3,
    'TB': 1024 ** 4,
}


def parse_size_to_bytes(size_str: str) -> int:
    size_str = size_str.strip()
    match = re.match(r'([\d.]+)\s*(\w+)', size_str, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).upper()
        return int(value * UNIT_MAP.get(unit, 1))
    return 0


def bytes_to_human(size_bytes: int) -> str:
    if size_bytes < 0:
        size_bytes = 0
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def seconds_to_human(seconds: float) -> str:
    if seconds < 0 or seconds == float('inf'):
        return '--:--'
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'[\s_]+', ' ', name).strip()
    return name or 'unnamed'


def course_url_to_folder_name(url: str) -> str:
    url = url.rstrip('/')
    parts = url.split('/')
    for i, part in enumerate(parts):
        if part == 'courses' and i + 1 < len(parts):
            return clean_name(parts[i + 1])
    return clean_name(parts[-1])
