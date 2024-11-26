import json
import os
import queue
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from . import utils


class BaseDownloader:
    BASE_URL = "https://dl.ash2txt.org/full-scrolls/"

    def __init__(self):
        self.session = utils.create_session()
        self._stop_event = threading.Event()
        self.cleanup_partial_files_on_startup()

    def download(self, **kwargs):
        raise NotImplementedError("Subclasses must implement the download method.")

    @staticmethod
    def start_downloads(tasks):
        total_files = len(tasks)
        files_completed = 0
        total_bytes_downloaded = 0
        max_workers = min(32, os.cpu_count() * 5)
        progress_queue = queue.Queue()

        # Since we don't know the total size, we initialize without total
        pbar = tqdm(total=total_files, desc="Downloading files", unit='file', leave=True)
        pbar.set_description(f"Downloading files (0B)")

        # Signal handling for graceful termination
        def signal_handler(signum, frame):
            print("\nAborting downloads...")
            nonlocal executor
            executor.shutdown(wait=False, cancel_futures=True)
            pbar.close()

        signal.signal(signal.SIGINT, signal_handler)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            global executor_global
            executor_global = executor
            for url, output_file in tasks:
                executor.submit(utils.download_file, url, output_file, progress_queue)

            while files_completed < total_files:
                try:
                    item_type, value = progress_queue.get(timeout=1)
                    if item_type == 'bytes':
                        total_bytes_downloaded += value
                        # pbar.set_postfix({'Bytes Downloaded': utils.format_bytes(total_bytes_downloaded)})
                        pbar.set_description(f"Downloading files ({utils.format_bytes(total_bytes_downloaded)})")
                    elif item_type == 'file':
                        files_completed += value
                        pbar.update(value)
                except queue.Empty:
                    pass  # No progress updates; loop again

        pbar.close()

    @staticmethod
    def load_default_config():
        """Load the default configuration for volumes from a JSON file."""
        config_path = os.path.join(os.path.dirname(__file__), "defaults.json")
        with open(config_path, "r") as file:
            return json.load(file)

    @staticmethod
    def get_volpkg(scroll_default_dict, volpkg_list):
        """Determine the default volpkg if none is provided."""
        default_volpkg = scroll_default_dict.get("default_volpkg", None)

        if default_volpkg and default_volpkg in volpkg_list:
            return default_volpkg
        else:
            # If no default is defined or it is not valid, prompt user
            if len(volpkg_list) == 1:
                print(f"Only one volpkg found: {volpkg_list[0]}. Using it as default.")
                return volpkg_list[0]
            else:
                print("Available volpkgs:")
                for idx, vp in enumerate(volpkg_list, 1):
                    print(f"{idx}. {vp}")
                choice = int(input("Select volpkg by number: "))
                return volpkg_list[choice - 1]

    @staticmethod
    def cleanup_partial_files_on_startup():
        for root, _, files in os.walk("data"):
            # if any file ends with .part
            if any(file.endswith('.part') for file in files):
                print("Cleaning up any partial files...")
            for file in files:
                if file.endswith('.part'):
                    temp_file = os.path.join(root, file)
                    try:
                        os.remove(temp_file)
                        print(f"Deleted partial file: {temp_file}")
                    except PermissionError:
                        print(f"Error deleting partial file {temp_file}: File is being used by another process.")
                    except OSError as e:
                        print(f"Error deleting partial file {temp_file}: {e}")
