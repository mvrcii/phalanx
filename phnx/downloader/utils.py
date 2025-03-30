import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from rich.console import Console
from urllib3.util.retry import Retry

console = Console()


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
    """
    Fetches and returns a sorted list of links from a given URL that contain the specified keyword(s).

    Parameters:
        url (str): The URL to fetch links from.
        session (requests.Session): The session to use for the HTTP request.
        keyword (str or list of str, optional): A keyword or list of keywords that must appear in the link.
        only_dirs (bool): If True, return only directory links (those ending with '/').

    Returns:
        list: A sorted list of filtered link names.
    """
    # Normalize keyword input: convert single string to a list, or leave as-is if already a list.
    keywords = [keyword] if isinstance(keyword, str) else keyword if keyword else None

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if href in ('../',):
                continue  # Skip parent directory link
            if keywords:
                # Only include the link if at least one keyword is found in the href (case insensitive)
                if not any(kw.lower() in href.lower() for kw in keywords):
                    continue
            is_dir = href.endswith('/')
            if only_dirs and not is_dir:
                continue
            if not only_dirs and is_dir:
                continue
            links.append(href.strip('/'))
        return sorted(links)
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching links from {url}: {e}[/bold red]")
        return []


def fetch_meta(folder_url, session):
    """Fetches and returns the JSON metadata from a meta.json file in the specified folder URL."""
    try:
        meta_url = urljoin(folder_url, "meta.json")
        response = session.get(meta_url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        console.print(f"[bold red]Failed to fetch meta.json from {folder_url}: {e}[/bold red]")
        return None


def parse_slice_ranges(slice_ranges, max_slices):
    """
    Parses slice ranges from a user input format like "1-10,15,20-25".

    Args:
        slice_ranges (str): Input string defining slice ranges (e.g., "1-10,15,20-25").
        max_slices (int): Maximum number of slices to consider.

    Returns:
        list of tuples: List of ranges as (start, end, step).
    """
    if slice_ranges.strip().lower() == 'all':
        return [(0, max_slices - 1, 1)]

    pattern = re.compile(r'^(\d+)(?:-(\d+))?(?::(\d+))?$')
    ranges = []
    for part in slice_ranges.split(','):
        part = part.strip()
        match = pattern.match(part)
        if not match:
            console.print(f"[bold red]Invalid range format: '{part}'[/bold red]")
            continue
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        step = int(match.group(3)) if match.group(3) else 1
        if start > end:
            start, end = end, start
        if start < 0 or end >= max_slices:
            console.print(f"[bold red]Range {start}-{end} is out of bounds (0-{max_slices - 1}).[/bold red]")
            continue
        ranges.append((start, end, step))
    return ranges


def prepare_slice_download_tasks(base_url, ranges, output_folder, filename_format="{:05d}.tif"):
    """
    Prepares a list of download tasks based on the provided ranges.

    Args:
        base_url (str): The base URL for downloading files.
        ranges (list of tuples): List of (start, end, step) tuples for range generation.
        output_folder (str): Path to the folder where the files will be downloaded.
        filename_format (str): Format string for file naming. Default is "{:05d}.tif".

    Returns:
        tuple: (tasks, skipped_count) - List of download tasks and count of skipped files
    """
    tasks = []
    skipped_count = 0
    os.makedirs(output_folder, exist_ok=True)

    for start, end, step in ranges:
        for i in range(start, end + 1, step):
            filename = filename_format.format(i)
            url = urljoin(base_url, filename)
            output_file = os.path.join(output_folder, filename)
            tmp_output_file = output_file + '.part'

            # Remove temporary files if they exist
            if os.path.exists(tmp_output_file):
                os.remove(tmp_output_file)

            # Skip files that are already downloaded and meet the size requirement
            if os.path.exists(output_file):
                skipped_count += 1
                continue

            tasks.append((url, output_file))

    return tasks, skipped_count


def prepare_file_download_task(base_url, output_folder, filename):
    """
    Prepares a download task based on the provided base URL.

    Args:
        base_url (str): The base URL for downloading files.
        output_folder (str): Path to the folder where the files will be downloaded to.
        filename (str): Name of the file to download.

    Returns:
        list: List of download tasks as tuples (url, output_file).
    """
    mask_url = urljoin(base_url, filename)
    output_file = os.path.join(output_folder, filename)
    tmp_output_file = output_file + '.part'

    # Remove temporary files if they exist
    if os.path.exists(tmp_output_file):
        os.remove(tmp_output_file)

    # Skip files that are already downloaded
    if os.path.exists(output_file):
        return []

    return [(mask_url, output_file)]


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
    console = Console()
    temp_file = output_file + '.part'
    total_bytes = 0

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
                            chunk_size = len(chunk)
                            total_bytes += chunk_size
                            # Report bytes downloaded
                            progress_queue.put(('bytes', chunk_size))
                os.rename(temp_file, output_file)
                # Report file completion
                progress_queue.put(('file', 1))
                return total_bytes
        except requests.RequestException as e:
            console.print(f"[yellow]Error downloading {url}: {e}. Retrying ({attempt + 1}/{retries})...[/yellow]")
            time.sleep(2 ** attempt)
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}[/bold red]")
            time.sleep(2 ** attempt)

    console.print(f"[bold red]Failed to download {url} after {retries} attempts.[/bold red]")
    progress_queue.put(('file', 1))  # Ensure progress bar completes even on failure
    return 0
