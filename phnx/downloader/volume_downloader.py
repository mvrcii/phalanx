# phnx/downloader/volpkg_downloader.py
import os
from urllib.parse import urljoin

from tqdm import tqdm

from . import utils
from .base import BaseDownloader


class VolpkgDownloader(BaseDownloader):
    BASE_URL = "https://dl.ash2txt.org/full-scrolls/"

    def __init__(self):
        super().__init__()
        self.session = utils.create_session()

    def download(self, scroll_name, volpkg_name, volume_id, slices):
        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")
        volpkg_url = scroll_url  # Adjusted: volpkgs are directly under scroll directory
        # Fetch available volpkgs
        volpkg_list = utils.fetch_links(volpkg_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            print(f"No volpkgs found for scroll {scroll_name}.")
            return

        if not volpkg_name:
            if len(volpkg_list) == 1:
                volpkg_name = volpkg_list[0]
                print(f"Using volpkg: {volpkg_name}")
            else:
                print("Available volpkgs:")
                for idx, vp in enumerate(volpkg_list, 1):
                    print(f"{idx}. {vp}")
                choice = int(input("Select volpkg by number: "))
                volpkg_name = volpkg_list[choice - 1]

        volpkg_url = urljoin(volpkg_url, f"{volpkg_name}/")
        volumes_url = urljoin(volpkg_url, "volumes/")
        # Fetch available volumes
        volume_list = utils.fetch_links(volumes_url, self.session, only_dirs=True)
        if not volume_list:
            print(f"No volumes found in volpkg {volpkg_name}.")
            return

        if not volume_id:
            print("Available volumes:")
            for idx, vol in enumerate(volume_list, 1):
                print(f"{idx}. {vol}")
            choice = int(input("Select volume by number: "))
            volume_id = volume_list[choice - 1]

        volume_url = urljoin(volumes_url, f"{volume_id}/")
        layers_url = volume_url
        # Fetch metadata to get the maximum number of slices
        meta = utils.fetch_meta(volume_url, self.session)
        if not meta:
            print(f"Unable to fetch metadata for volume {volume_id}.")
            return

        max_slices = int(meta.get('slices', 0))
        if max_slices == 0:
            print(f"No slices information available in metadata for volume {volume_id}.")
            return

        # Parse slice ranges
        ranges = utils.parse_slice_ranges(slices, max_slices)
        if not ranges:
            print("No valid slice ranges provided.")
            return

        # Prepare download tasks
        output_folder = os.path.join("data", scroll_name.lower(), "volumes", volume_id, "layers")
        os.makedirs(output_folder, exist_ok=True)
        tasks = utils.prepare_download_tasks(layers_url, ranges, output_folder, filename_format="{:05d}.tif")
        if not tasks:
            print("All files are already downloaded.")
            return

        # Start downloading
        self.start_downloads(tasks)

    def start_downloads(self, tasks):
        total_files = len(tasks)
        with tqdm(total=total_files, desc="Downloading slices") as pbar:
            for url, output_file in tasks:
                utils.download_file(self.session, url, output_file)
                pbar.update(1)
