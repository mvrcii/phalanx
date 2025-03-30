import os
import time
from urllib.parse import urljoin

from rich import box
from rich.console import Console
from rich.panel import Panel

from . import utils
from .base import BaseDownloader


class VolumeDownloader(BaseDownloader):

    def __init__(self, verbosity="normal"):
        super().__init__(verbosity=verbosity)
        self.session = utils.create_session()
        self.default_config = BaseDownloader.load_default_config()
        self.console = Console()
        self.operation_start_time = time.time()
        self.total_downloaded_bytes = 0

    def get_volume(self, scroll_name, volume_list):
        """Determine the default volume if none is provided."""
        default_volume = self.default_config.get(scroll_name, {}).get("default_volume")

        if default_volume and default_volume in volume_list:
            self.console.print(f"[bold green]Using default volume: {default_volume}[/bold green]")
            return default_volume
        else:
            # If no default is defined or it is not valid, prompt user
            if len(volume_list) == 1:
                self.console.print(
                    f"[bold green]Only one volume found: {volume_list[0]}. Using it as default.[/bold green]")
                return volume_list[0]
            else:
                self.console.print("[bold yellow]Available volumes:[/bold yellow]")
                for idx, vol in enumerate(volume_list, 1):
                    self.console.print(f"{idx}. {vol}")
                choice = int(input("Select volume by number: "))
                return volume_list[choice - 1]

    def download(self, output_path, scroll_name, volpkg_name, volume_id, slices):
        # Reset counters
        self.operation_start_time = time.time()
        self.total_downloaded_bytes = 0

        self.console.print(Panel(
            f"[bold]Target: {scroll_name} | Slices: {slices}[/bold]",
            title="Volume Download Operation",
            subtitle="Phalanx Downloader",
            box=box.ROUNDED
        ))

        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")

        # Fetch available volpkgs
        volpkg_list = utils.fetch_links(scroll_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            self.console.print(f"[bold red]No volpkgs found for scroll {scroll_name}.[/bold red]")
            return

        if not volpkg_name:
            scroll_defaults = self.default_config.get(scroll_name, {})
            volpkg_name = self.get_volpkg(scroll_defaults, volpkg_list)

        if not volpkg_name:
            if len(volpkg_list) == 1:
                volpkg_name = volpkg_list[0]
                self.console.print(f"[bold green]Using volpkg: {volpkg_name}[/bold green]")
            else:
                self.console.print("[bold yellow]Available volpkgs:[/bold yellow]")
                for idx, vp in enumerate(volpkg_list, 1):
                    self.console.print(f"{idx}. {vp}")
                choice = int(input("Select volpkg by number: "))
                volpkg_name = volpkg_list[choice - 1]

        volpkg_url = urljoin(scroll_url, f"{volpkg_name}/")
        volumes_url = urljoin(volpkg_url, "volumes/")

        # Fetch available volumes
        volume_list = utils.fetch_links(volumes_url, self.session, only_dirs=True)
        if not volume_list:
            self.console.print(f"[bold red]No volumes found in volpkg {volpkg_name}.[/bold red]")
            return

        if not volume_id:
            volume_id = self.get_volume(scroll_name, volume_list)

        volume_url = urljoin(volumes_url, f"{volume_id}/")

        # Fetch metadata to get the maximum number of slices
        meta = utils.fetch_meta(volume_url, self.session)
        if not meta:
            self.console.print(f"[bold red]Unable to fetch metadata for volume {volume_id}.[/bold red]")
            return

        max_slices = int(meta.get('slices', 0))
        if max_slices == 0:
            self.console.print(
                f"[bold red]No slices information available in metadata for volume {volume_id}.[/bold red]")
            return

        # Parse slice ranges
        ranges = utils.parse_slice_ranges(slices, max_slices)
        if not ranges:
            self.console.print("[bold red]No valid slice ranges provided.[/bold red]")
            return

        # Prepare download tasks
        output_folder = os.path.join(output_path, scroll_name, volpkg_name, "volumes", volume_id)
        os.makedirs(output_folder, exist_ok=True)

        # Download the meta.json for the volume if not yet existent
        meta_tasks = utils.prepare_file_download_task(volume_url, output_folder, filename=f"meta.json")
        if meta_tasks:
            meta_bytes = self.start_downloads(meta_tasks, file_type='meta.json')
            self.total_downloaded_bytes += meta_bytes
        else:
            if self.verbosity != "quiet":
                self.console.print(f"[dim]Meta.json already exists.[/dim]")

        # Get tasks and count of skipped files
        tasks, skipped_count = utils.prepare_slice_download_tasks(volume_url, ranges, output_folder)
        if tasks:
            slice_bytes = self.start_downloads(tasks)
            self.total_downloaded_bytes += slice_bytes
        else:
            if skipped_count > 0:
                self.console.print(f"[green]All {skipped_count} slice files already exist.[/green]")
            else:
                self.console.print("[green]No new files to download.[/green]")

        # Display operation summary
        self.display_operation_summary(operation_name="Volume Download")
