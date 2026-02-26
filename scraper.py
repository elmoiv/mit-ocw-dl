from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup

from models import CourseData, ResourceItem, Section
from utils import clean_name, course_url_to_folder_name, parse_size_to_bytes

BASE_OCW = 'https://ocw.mit.edu'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/121.0.0.0 Safari/537.36'
    )
}


def normalize_course_url(url: str) -> str:
    url = url.strip().rstrip('/')
    for suffix in ('/download', '/pages/syllabus', '/pages'):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def get_course_title(soup: BeautifulSoup) -> str:
    for selector in ['h1.course-title', 'h1', 'title']:
        tag = soup.select_one(selector)
        if tag:
            text = tag.get_text(strip=True).split('|')[0].strip()
            if text:
                return text
    return 'Unknown Course'


def _fetch_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def _parse_resource_items(soup: BeautifulSoup, section_name: str) -> list[ResourceItem]:
    """Extract all ResourceItem entries from any page containing resource-item divs."""
    items = []
    for item_div in soup.find_all('div', class_='resource-item'):
        thumb = item_div.find('a', class_='resource-thumbnail')
        if not thumb:
            continue
        dl_url = (thumb.get('href') or '').strip()
        if not dl_url:
            continue

        # Resource type
        type_div = thumb.find('div', class_='resource-type-thumbnail')
        res_type = type_div.get_text(strip=True) if type_div else 'file'

        # File size
        size_div = item_div.find('div', class_='resource-list-file-size')
        size_str = size_div.get_text(strip=True) if size_div else '0 B'
        size_bytes = parse_size_to_bytes(size_str)

        # Title
        title_a = item_div.find('a', class_='resource-list-title')
        item_title = (
            title_a.get_text(strip=True)
            if title_a
            else dl_url.split('/')[-1]
        )

        items.append(
            ResourceItem(
                title=item_title,
                url=dl_url,
                file_size_str=size_str or '? B',
                file_size_bytes=size_bytes,
                resource_type=res_type,
                section_name=section_name,
            )
        )
    return items


def _get_see_all_url(resource_list_div) -> Optional[str]:
    """Return the absolute URL of the 'See all' link if present, else None."""
    see_all = resource_list_div.find('a', class_='text-decoration-none')
    if not see_all:
        # Fallback: any anchor whose text contains 'See all'
        see_all = resource_list_div.find(
            lambda tag: tag.name == 'a' and 'See all' in tag.get_text()
        )
    if not see_all:
        return None
    href = (see_all.get('href') or '').strip()
    if not href:
        return None
    if href.startswith('http'):
        return href
    return BASE_OCW + href


def scrape_course(
    url: str, progress_cb: Optional[Callable[[str], None]] = None
) -> CourseData:
    base_url = normalize_course_url(url)
    download_url = base_url + '/download/'

    if progress_cb:
        progress_cb(f'Fetching: {download_url}')

    try:
        soup = _fetch_soup(download_url)
    except requests.RequestException as exc:
        raise RuntimeError(f'Failed to fetch download page: {exc}') from exc

    title = get_course_title(soup)
    folder_name = course_url_to_folder_name(base_url)
    course = CourseData(title=title, url=base_url, folder_name=folder_name)

    resource_lists = soup.find_all('div', class_='resource-list')
    if not resource_lists:
        raise RuntimeError(
            'No resource sections found. '
            'Please verify the course URL is correct and the course has a download page.'
        )

    for rl in resource_lists:
        h4 = rl.find('h4')
        if not h4:
            continue
        section_name = h4.get_text(strip=True)
        section = Section(name=section_name)

        if progress_cb:
            progress_cb(f'Parsing section: {section_name}')

        # Check for "See all" — means this section is truncated on the download page
        see_all_url = _get_see_all_url(rl)
        if see_all_url:
            if progress_cb:
                progress_cb(f'  → Fetching full list: {see_all_url}')
            try:
                full_soup = _fetch_soup(see_all_url)
                items = _parse_resource_items(full_soup, section_name)
            except requests.RequestException as exc:
                if progress_cb:
                    progress_cb(f'  ⚠ Could not fetch full list ({exc}), using truncated.')
                items = _parse_resource_items(rl, section_name)
        else:
            items = _parse_resource_items(rl, section_name)

        section.items.extend(items)

        if section.items:
            course.sections.append(section)

    if progress_cb:
        total_items = sum(len(s.items) for s in course.sections)
        progress_cb(
            f'Done. Found {len(course.sections)} sections, {total_items} files.'
        )

    return course