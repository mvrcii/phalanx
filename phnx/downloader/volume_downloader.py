import os
from urllib.parse import urljoin

from . import utils
from .base import BaseDownloader


class VolumeDownloader(BaseDownloader):

    def __init__(self):
        super().__init__()
        self.session = utils.create_session()
        self.default_config = BaseDownloader.load_default_config()

    def get_volume(self, scroll_name, volume_list):
        """Determine the default volume if none is provided."""
        default_volume = self.default_config.get(scroll_name, {}).get("default_volume")

        if default_volume and default_volume in volume_list:
            print(f"Using default volume: {default_volume}")
            return default_volume
        else:
            # If no default is defined or it is not valid, prompt user
            if len(volume_list) == 1:
                print(f"Only one volume found: {volume_list[0]}. Using it as default.")
                return volume_list[0]
            else:
                print("Available volumes:")
                for idx, vol in enumerate(volume_list, 1):
                    print(f"{idx}. {vol}")
                choice = int(input("Select volume by number: "))
                return volume_list[choice - 1]

    def download(self, output_path, scroll_name, volpkg_name, volume_id, slices):
        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")

        # Fetch available volpkgs
        volpkg_list = utils.fetch_links(scroll_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            print(f"No volpkgs found for scroll {scroll_name}.")
            return

        if not volpkg_name:
            scroll_defaults = self.default_config.get(scroll_name, {})
            volpkg_name = self.get_volpkg(scroll_defaults, volpkg_list)

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

        volpkg_url = urljoin(scroll_url, f"{volpkg_name}/")
        volumes_url = urljoin(volpkg_url, "volumes/")

        # Fetch available volumes
        volume_list = utils.fetch_links(volumes_url, self.session, only_dirs=True)
        if not volume_list:
            print(f"No volumes found in volpkg {volpkg_name}.")
            return

        if not volume_id:
            volume_id = self.get_volume(scroll_name, volume_list)

        volume_url = urljoin(volumes_url, f"{volume_id}/")

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
        output_folder = os.path.join(output_path, scroll_name, "volumes", volume_id, "layers")
        os.makedirs(output_folder, exist_ok=True)
        tasks = utils.prepare_slice_download_tasks(volume_url, ranges, output_folder)
        if not tasks:
            print("All files are already downloaded.")
            return

        # Start downloading
        self.start_downloads(tasks)
