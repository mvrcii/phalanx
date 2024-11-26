import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session():
    """Creates a requests session with retries and custom headers."""
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({'User-Agent': 'phalanx Downloader/1.0'})
    return session


def fetch_links(url, session, keyword=None, only_dirs=False):
    """Fetches and returns a sorted list of links from a given URL that contain the specified keyword."""
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if href in ('../',):
                continue  # Skip parent directory link
            if keyword and keyword not in href.lower():
                continue
            is_dir = href.endswith('/')
            if only_dirs and not is_dir:
                continue
            if not only_dirs and is_dir:
                continue
            links.append(href.strip('/'))
        return sorted(links)
    except requests.RequestException as e:
        print(f"Error fetching links from {url}: {e}")
        return []


def fetch_meta(folder_url, session):
    """Fetches and returns the JSON metadata from a meta.json file in the specified folder URL."""
    try:
        meta_url = urljoin(folder_url, "meta.json")
        response = session.get(meta_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch meta.json from {folder_url}: {e}")
        return None


def parse_slice_ranges(slice_ranges, max_slice):
    """Parses a string of slice ranges and returns a list of ranges."""
    if slice_ranges.strip().lower() == 'all':
        return [(0, max_slice - 1, 1)]

    pattern = re.compile(r'^(\d+)(?:-(\d+))?(?::(\d+))?$')
    ranges = []
    for part in slice_ranges.split(','):
        part = part.strip()
        match = pattern.match(part)
        if not match:
            print(f"Invalid range format: '{part}'")
            continue
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        step = int(match.group(3)) if match.group(3) else 1
        if start > end:
            start, end = end, start
        if start < 0 or end >= max_slice:
            print(f"Range {start}-{end} is out of bounds (0-{max_slice - 1}).")
            continue
        ranges.append((start, end, step))
    return ranges


def prepare_download_tasks(base_url, ranges, output_folder, filename_format="{:05d}.tif"):
    """Prepares a list of download tasks based on the provided ranges."""
    tasks = []
    for start, end, step in ranges:
        for i in range(start, end + 1, step):
            filename = filename_format.format(i)
            url = urljoin(base_url, filename)
            output_file = os.path.join(output_folder, filename)
            tmp_output_file = output_file + '.part'

            if os.path.exists(tmp_output_file):
                os.remove(tmp_output_file)

            if os.path.exists(output_file) and os.path.getsize(output_file) >= 10 * 1024 * 1024:
                continue
            tasks.append((url, output_file))
    return tasks


def format_bytes(size):
    """Converts bytes to a human-readable format."""
    power = 2 ** 10
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"


def download_file(url, output_file, progress_queue, retries=3):
    """Downloads a file with retries, reports progress via progress_queue."""
    temp_file = output_file + '.part'
    for attempt in range(retries):
        try:
            session = create_session()  # Create a session per thread
            with session.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                os.makedirs(os.path.dirname(output_file), exist_ok=True)

                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                        if chunk:
                            f.write(chunk)
                            # Report bytes downloaded
                            progress_queue.put(('bytes', len(chunk)))
                os.rename(temp_file, output_file)
                # Report file completion
                progress_queue.put(('file', 1))
                return
        except requests.RequestException as e:
            print(f"Error downloading {url}: {e}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(2 ** attempt)
    print(f"Failed to download {url} after {retries} attempts.")
    progress_queue.put(('file', 1))  # To ensure progress bar completes even if download fails
