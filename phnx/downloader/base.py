import json
import os
import queue
import signal
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from rich import box
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
from rich.table import Table

from . import utils


class BaseDownloader:
    BASE_URL = "https://dl.ash2txt.org/full-scrolls/"
    console = Console()

    def __init__(self, verbosity="normal"):
        self.session = utils.create_session()
        self._stop_event = threading.Event()
        self.verbosity = verbosity
        self.cleanup_partial_files_on_startup()
        self.operation_start_time = time.time()
        self.total_downloaded_bytes = 0
        self.fragments_processed = 0
        self.fragments_successful = 0

    def download(self, **kwargs):
        raise NotImplementedError("Subclasses must implement the download method.")

    @staticmethod
    def start_downloads(tasks, file_type="slices", register_signals=True):
        """Download files with progress tracking"""
        total_files = len(tasks)
        files_completed = 0
        total_bytes_downloaded = 0
        max_workers = min(32, os.cpu_count() * 5)
        progress_queue = queue.Queue()

        if total_files == 0:
            return 0  # Return zero bytes if no tasks

        console = Console()

        # Rich's Progress bar with file units
        with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                "•",
                TextColumn("{task.completed}/{task.total} files"),
                "•",
                TimeRemainingColumn(),
                console=console,
                expand=True
        ) as progress:
            task_id = progress.add_task(f"Downloading {file_type}", total=total_files)

            # Signal handling for graceful termination
            global executor_global
            executor_global = None

            if register_signals:
                def signal_handler(signum, frame):
                    console.print("[bold red]\nAborting downloads...[/bold red]")
                    if executor_global:
                        executor_global.shutdown(wait=False, cancel_futures=True)

                signal.signal(signal.SIGINT, signal_handler)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                if register_signals:
                    executor_global = executor

                for url, output_file in tasks:
                    executor.submit(utils.download_file, url, output_file, progress_queue)

                while files_completed < total_files:
                    try:
                        item_type, value = progress_queue.get(timeout=1)
                        if item_type == 'bytes':
                            total_bytes_downloaded += value
                            progress.update(task_id,
                                            description=f"Downloading {file_type} ({utils.format_bytes(total_bytes_downloaded)})")
                        elif item_type == 'file':
                            files_completed += value
                            progress.update(task_id, advance=value)
                    except queue.Empty:
                        pass

        return total_bytes_downloaded

    @staticmethod
    def load_default_config():
        """Load the default configuration for volumes from a JSON file."""
        config_path = os.path.join(os.path.dirname(__file__), "defaults.json")
        with open(config_path, "r") as file:
            return json.load(file)

    @staticmethod
    def get_volpkg(scroll_default_dict, volpkg_list):
        """Determine the default volpkg if none is provided."""
        console = Console()
        default_volpkg = scroll_default_dict.get("default_volpkg", None)

        if default_volpkg and default_volpkg in volpkg_list:
            return default_volpkg
        else:
            # If no default is defined or it is not valid, prompt user
            if len(volpkg_list) == 1:
                console.print(f"[bold green]Only one volpkg found: {volpkg_list[0]}. Using it as default.[/bold green]")
                return volpkg_list[0]
            else:
                console.print("[bold yellow]Available volpkgs:[/bold yellow]")
                for idx, vp in enumerate(volpkg_list, 1):
                    console.print(f"{idx}. {vp}")
                choice = int(input("Select volpkg by number: "))
                return volpkg_list[choice - 1]

    @staticmethod
    def cleanup_partial_files_on_startup():
        console = Console()
        fragment_counts = defaultdict(int)
        total_files = 0

        for root, _, files in os.walk("data"):
            partial_files = [f for f in files if f.endswith('.part')]
            if not partial_files:
                continue

            for file in partial_files:
                temp_file = os.path.join(root, file)
                try:
                    os.remove(temp_file)
                    # Extract fragment ID from path
                    path_parts = root.split(os.sep)
                    for i, part in enumerate(path_parts):
                        if part == "fragments" and i + 1 < len(path_parts):
                            fragment_id = path_parts[i + 1]
                            fragment_counts[fragment_id] += 1
                            break
                    total_files += 1
                except (PermissionError, OSError) as e:
                    console.print(f"[bold red]Error deleting partial file {temp_file}: {e}[/bold red]")

        if total_files > 0:
            console.print(
                f"[yellow]Cleanup: Removed {total_files} partial files across {len(fragment_counts)} fragments[/yellow]")

    def display_operation_summary(self, operation_name="Download Operation"):
        """Display a summary of the download operation with consolidated statistics."""
        duration = time.time() - self.operation_start_time

        table = Table(title="Operation Summary", show_header=False, box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Fragments Processed",
                      f"{self.fragments_successful}/{self.fragments_processed} completed successfully")
        table.add_row("Total Downloaded", f"{utils.format_bytes(self.total_downloaded_bytes)}")
        table.add_row("Total Time", f"{duration:.1f} seconds")

        self.console.print()
        self.console.print(table)
