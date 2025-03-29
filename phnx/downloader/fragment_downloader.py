import os
from urllib.parse import urljoin

from . import utils
from .base import BaseDownloader


class FragmentDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()
        self.session = utils.create_session()
        self.default_config = BaseDownloader.load_default_config()

    def download(self, output_dir, scroll_name, volpkg_name, fragment_id, slices, mask):
        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")
        volpkg_list = utils.fetch_links(scroll_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            print(f"No volpkgs found for scroll {scroll_name}.")
            return

        if not volpkg_name:
            scroll_defaults = self.default_config.get(scroll_name, {})
            volpkg_name = self.get_volpkg(scroll_defaults, volpkg_list)

        volpkg_url = urljoin(scroll_url, f"{volpkg_name}/")
        paths_url = urljoin(volpkg_url, "paths/")
        fragment_list = utils.fetch_links(paths_url, self.session, only_dirs=True)
        if not fragment_list:
            print(f"No fragments found in volpkg {volpkg_name}.")
            return

        if fragment_id not in fragment_list:
            print(f"Fragment {fragment_id} not found in volpkg {volpkg_name}.")
            print("Available fragments:")
            for frag in fragment_list:
                print(f"- {frag}")
            return

        fragment_url = urljoin(paths_url, f"{fragment_id}/")
        layers_url = urljoin(fragment_url, "layers/")
        slice_files = utils.fetch_links(layers_url, self.session, keyword=['.tif', '.jpg'])
        if not slice_files:
            print(f"Unable to fetch slices for fragment {fragment_id}.")
            return

        max_slices = int(len(slice_files))
        if max_slices == 0:
            print(f"No slices information available for fragment {fragment_id}.")
            return

        ranges = utils.parse_slice_ranges(slices, max_slices)
        if not ranges:
            print("No valid slice ranges provided.")
            return

        fragment_dir = os.path.join(output_dir, scroll_name.lower(), "fragments", fragment_id)
        os.makedirs(fragment_dir, exist_ok=True)
        output_folder = os.path.join(fragment_dir, "layers")

        ext = '.tif'
        if slice_files[0].lower().endswith('.jpg'):
            ext = '.jpg'
        filename_format = "{:02d}" + ext

        slice_tasks = utils.prepare_slice_download_tasks(layers_url, ranges, output_folder, filename_format)
        if slice_tasks:
            self.start_downloads(slice_tasks)
        else:
            print(f"All slices downloaded for {scroll_name} and fragment id '{fragment_id}'.")

        if mask:
            mask_files = utils.fetch_links(fragment_url, self.session, keyword='mask')
            if not mask_files:
                print(f"No mask file found for fragment {fragment_id}. Skipping mask download.")
            else:
                selected_mask = None
                for mf in mask_files:
                    if mf.endswith('_mask.png'):
                        selected_mask = mf
                        break
                if not selected_mask:
                    for mf in mask_files:
                        if mf.endswith('_flat_mask.png'):
                            selected_mask = mf
                            break
                if not selected_mask:
                    selected_mask = mask_files[0]
                mask_tasks = utils.prepare_file_download_task(fragment_url, fragment_dir, filename=selected_mask)
                if mask_tasks:
                    print(f"Downloading mask file: {selected_mask}")
                    self.start_downloads(mask_tasks, file_type='mask')
                else:
                    print(f"Mask file {selected_mask} already exists for '{scroll_name}' and '{fragment_id}'.")
