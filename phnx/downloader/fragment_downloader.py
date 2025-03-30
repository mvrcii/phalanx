import concurrent.futures
import os
import queue
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn
from rich.table import Table

from . import utils
from .base import BaseDownloader


class FragmentDownloader(BaseDownloader):
    def __init__(self, verbosity="normal"):
        super().__init__(verbosity=verbosity)
        self.session = utils.create_session()
        self.default_config = BaseDownloader.load_default_config()
        self.console = Console()
        self.operation_start_time = time.time()
        self.total_downloaded_bytes = 0
        self.fragments_processed = 0
        self.fragments_successful = 0

    def download_multiple(self, output_dir, scroll_name, volpkg_name, fragment_ids, slices, mask, parallel=True):
        """
        Download multiple fragments.

        Args:
            output_dir: Output directory for downloaded files
            scroll_name: Scroll name
            volpkg_name: Volume package name or None
            fragment_ids: List of fragment IDs to download
            slices: Slice ranges to download
            mask: Whether to download the mask
            parallel: Whether to download fragments in parallel or sequentially
        """
        # Reset operation counters
        self.fragments_processed = len(fragment_ids)
        self.fragments_successful = 0
        self.total_downloaded_bytes = 0
        self.operation_start_time = time.time()

        # Show initial operation panel with fewer details
        self.console.print(Panel(
            f"[bold]Scroll: {scroll_name} | Mode: {'Parallel' if parallel else 'Sequential'} | Fragments: {len(fragment_ids)} | Slices: {slices}[/bold]",
            title="phalanx - Fragment Downloader",
            subtitle="",
            box=box.ROUNDED
        ))

        if parallel:
            self.console.print(f"[cyan]Using parallel download mode[/cyan]")
            # Handle parallel downloads with a consolidated progress display
            self._download_parallel(output_dir, scroll_name, volpkg_name, fragment_ids, slices, mask)
        else:
            self.console.print(f"[cyan]Using sequential download mode[/cyan]")
            # Download fragments sequentially
            for i, fragment_id in enumerate(fragment_ids):
                try:
                    bytes_downloaded = self.download(
                        output_dir,
                        scroll_name,
                        volpkg_name,
                        fragment_id,
                        slices,
                        mask,
                        fragment_index=i + 1,
                        total_fragments=len(fragment_ids)
                    )
                    self.total_downloaded_bytes += bytes_downloaded
                    self.fragments_successful += 1
                except Exception as e:
                    self.console.print(f"[bold red]Error downloading fragment {fragment_id}: {str(e)}[/bold red]")
                    continue

        # Display operation summary at the end
        self.display_operation_summary()

    def _download_parallel(self, output_dir, scroll_name, volpkg_name, fragment_ids, slices, mask):
        """Handle parallel downloads with a consolidated progress display"""
        # First, announce all fragments being processed
        for i, fragment_id in enumerate(fragment_ids):
            self.console.print(f"Processing fragment: {fragment_id} ({i + 1}/{len(fragment_ids)})")

        # Set up shared progress tracking
        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            TextColumn("{task.completed}/{task.total} files"),
            "•",
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
            refresh_per_second=5  # Reduce refresh rate to avoid excessive updates
        )

        # Create a progress table that will hold all our tasks
        overall_progress = Table.grid()
        overall_progress.add_row(progress)

        # Create a task for each fragment (slices)
        fragment_tasks = {}
        mask_tasks = {}

        # Function to download a fragment and update the appropriate task
        def download_fragment_with_progress(fragment_id, fragment_index):
            try:
                # Pre-setup slice tasks
                slice_task_id = fragment_tasks[fragment_id]
                mask_task_id = mask_tasks.get(fragment_id) if mask else None

                # Perform the actual download, passing the progress and task IDs
                return self._download_with_progress(
                    output_dir=output_dir,
                    scroll_name=scroll_name,
                    volpkg_name=volpkg_name,
                    fragment_id=fragment_id,
                    slices=slices,
                    mask=mask,
                    progress=progress,
                    slice_task_id=slice_task_id,
                    mask_task_id=mask_task_id,
                    fragment_index=fragment_index,
                    total_fragments=len(fragment_ids)
                )
            except Exception as e:
                self.console.print(f"[bold red]Error downloading fragment {fragment_id}: {str(e)}[/bold red]")
                return 0

        # Start the live display with our consolidated progress
        with Live(overall_progress, refresh_per_second=5):
            # Create all tasks first
            for i, fragment_id in enumerate(fragment_ids):
                task_desc = f"Fragment {fragment_id} slices"
                # Initialize task without total until we know how many slices
                fragment_tasks[fragment_id] = progress.add_task(task_desc, total=None)
                if mask:
                    # For mask, we know it's always 1 file - initialize correctly
                    mask_tasks[fragment_id] = progress.add_task(f"Fragment {fragment_id} mask", total=1)

            # Then run the downloads in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_frag = {
                    executor.submit(
                        download_fragment_with_progress,
                        fragment_id,
                        i + 1
                    ): fragment_id for i, fragment_id in enumerate(fragment_ids)
                }

                # Process completed futures
                for future in concurrent.futures.as_completed(future_to_frag):
                    fragment_id = future_to_frag[future]
                    try:
                        bytes_downloaded = future.result()
                        self.total_downloaded_bytes += bytes_downloaded
                        self.fragments_successful += 1
                    except Exception as e:
                        self.console.print(f"[bold red]Error downloading fragment {fragment_id}: {str(e)}[/bold red]")

    def _download_with_progress(self, output_dir, scroll_name, volpkg_name, fragment_id, slices, mask,
                                progress, slice_task_id, mask_task_id, fragment_index, total_fragments):
        """Download a fragment with progress tracking through the provided progress object"""
        total_bytes = 0

        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")
        volpkg_list = utils.fetch_links(scroll_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - No volpkgs found")
            return 0

        if not volpkg_name:
            scroll_defaults = self.default_config.get(scroll_name, {})
            volpkg_name = self.get_volpkg(scroll_defaults, volpkg_list)

        volpkg_url = urljoin(scroll_url, f"{volpkg_name}/")
        paths_url = urljoin(volpkg_url, "paths/")
        fragment_list = utils.fetch_links(paths_url, self.session, only_dirs=True)
        if not fragment_list:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - No fragments found")
            return 0

        if fragment_id not in fragment_list:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - Not found in volpkg")
            return 0

        fragment_url = urljoin(paths_url, f"{fragment_id}/")
        layers_url = urljoin(fragment_url, "layers/")
        slice_files = utils.fetch_links(layers_url, self.session, keyword=['.tif', '.jpg'])
        if not slice_files:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - No slices found")
            return 0

        max_slices = int(len(slice_files))
        if max_slices == 0:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - Empty slices")
            return 0

        ranges = utils.parse_slice_ranges(slices, max_slices)
        if not ranges:
            progress.update(slice_task_id, description=f"[red]Fragment {fragment_id} - Invalid slice ranges")
            return 0

        fragment_dir = os.path.join(output_dir, scroll_name.lower(), "fragments", fragment_id)
        os.makedirs(fragment_dir, exist_ok=True)
        output_folder = os.path.join(fragment_dir, "layers")

        ext = '.tif'
        if slice_files[0].lower().endswith('.jpg'):
            ext = '.jpg'
        filename_format = "{:02d}" + ext

        # Get tasks and count of skipped files
        slice_tasks, skipped_count = utils.prepare_slice_download_tasks(layers_url, ranges, output_folder,
                                                                        filename_format)

        # Update progress task with total files
        total_slice_files = len(slice_tasks)
        if total_slice_files > 0:
            progress.update(slice_task_id, total=total_slice_files, completed=0)

            # Setup a custom download tracking queue
            download_queue = self._create_tracking_queue(progress, slice_task_id)

            # Download slices
            bytes_downloaded = self._download_files(slice_tasks, download_queue)
            total_bytes += bytes_downloaded

            progress.update(slice_task_id,
                            description=f"Fragment {fragment_id} slices - {utils.format_bytes(bytes_downloaded)}")
        else:
            if skipped_count > 0:
                progress.update(slice_task_id, description=f"Fragment {fragment_id} slices - Already exist")
                progress.update(slice_task_id, total=1, completed=1)  # Mark as complete
            else:
                progress.update(slice_task_id, description=f"Fragment {fragment_id} - No slices to download")
                progress.update(slice_task_id, total=1, completed=1)  # Mark as complete

        # Handle mask download if requested
        if mask:
            mask_files = utils.fetch_links(fragment_url, self.session, keyword='mask')
            if not mask_files:
                if mask_task_id:
                    progress.update(mask_task_id, description=f"Fragment {fragment_id} - No mask available")
                    progress.update(mask_task_id, total=1, completed=1)  # Mark as complete
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

                progress.update(mask_task_id, description=f"Fragment {fragment_id} mask - {selected_mask}")

                mask_tasks = utils.prepare_file_download_task(fragment_url, fragment_dir, filename=selected_mask)
                if mask_tasks:
                    progress.update(mask_task_id, total=1, completed=0)

                    # Setup a custom download tracking queue for mask
                    mask_queue = self._create_tracking_queue(progress, mask_task_id)

                    # Download mask
                    mask_bytes = self._download_files(mask_tasks, mask_queue)
                    total_bytes += mask_bytes

                    progress.update(mask_task_id,
                                    description=f"Fragment {fragment_id} mask - {utils.format_bytes(mask_bytes)}")
                else:
                    progress.update(mask_task_id, description=f"Fragment {fragment_id} mask - Already exists")
                    progress.update(mask_task_id, total=1, completed=1)  # Mark as complete

        return total_bytes

    def _create_tracking_queue(self, progress, task_id):
        """Create a queue that updates a specific progress task"""
        import queue

        q = queue.Queue()

        # Start a background thread to process the queue
        def queue_processor():
            files_completed = 0
            bytes_downloaded = 0

            while True:
                try:
                    item_type, value = q.get()
                    if item_type == 'bytes':
                        bytes_downloaded += value
                        progress.update(task_id,
                                        description=f"{progress.tasks[task_id].description.split(' - ')[0]} - {utils.format_bytes(bytes_downloaded)}")
                    elif item_type == 'file':
                        files_completed += value
                        # Update progress
                        progress.update(task_id, advance=value)
                    elif item_type == 'done':
                        # Final byte count update when done
                        final_bytes = value if isinstance(value, (int, float)) else bytes_downloaded
                        progress.update(task_id,
                                        description=f"{progress.tasks[task_id].description.split(' - ')[0]} - {utils.format_bytes(final_bytes)}")
                        break
                except Exception:
                    pass

                q.task_done()

        processor = threading.Thread(target=queue_processor, daemon=True)
        processor.start()

        return q

    def _download_files(self, tasks, progress_queue):
        """Download files with custom progress tracking"""
        if not tasks:
            return 0

        total_bytes_downloaded = 0
        max_workers = min(4, len(tasks))  # Limit workers per fragment to avoid excessive concurrency

        # Create a queue to track bytes downloaded
        bytes_queue = queue.Queue()

        # Wrapper function to track bytes
        def download_and_track(url, output_file, progress_queue):
            try:
                bytes_downloaded = utils.download_file(url, output_file, progress_queue)
                bytes_queue.put(bytes_downloaded)
                return bytes_downloaded
            except Exception as e:
                self.console.print(f"[bold red]Error in download: {str(e)}[/bold red]")
                return 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for url, output_file in tasks:
                futures.append(executor.submit(download_and_track, url, output_file, progress_queue))

            # Wait for all downloads to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Ensure any exceptions are raised
                except Exception as e:
                    self.console.print(f"[bold red]Error in download: {str(e)}[/bold red]")

        # Collect total bytes downloaded
        while not bytes_queue.empty():
            total_bytes_downloaded += bytes_queue.get()

        # Signal the queue processor to exit with the correct byte count
        progress_queue.put(('done', total_bytes_downloaded))

        return total_bytes_downloaded

    def start_downloads_with_unit(self, tasks, file_type="slices", register_signals=True, unit="file"):
        """Enhanced version of start_downloads that uses the correct unit"""
        total_files = len(tasks)
        files_completed = 0
        total_bytes_downloaded = 0
        max_workers = min(32, os.cpu_count() * 5)
        progress_queue = queue.Queue()

        if total_files == 0:
            return 0  # Return zero bytes if no tasks

        console = Console()

        # Create a progress bar with the correct unit
        with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                "•",
                TextColumn(f"{{task.completed}}/{{task.total}} {unit}s"),
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

    def download(self, output_dir, scroll_name, volpkg_name, fragment_id, slices, mask,
                 register_signals=True, fragment_index=None, total_fragments=None):
        """Download a single fragment and return the bytes downloaded."""
        fragment_context = ""
        if fragment_index is not None and total_fragments is not None:
            fragment_context = f" ({fragment_index}/{total_fragments})"

        self.console.print(f"[bold]Processing fragment: {fragment_id}{fragment_context}[/bold]")

        scroll_url = urljoin(self.BASE_URL, f"{scroll_name}/")
        volpkg_list = utils.fetch_links(scroll_url, self.session, keyword='.volpkg', only_dirs=True)
        if not volpkg_list:
            self.console.print(f"[bold red]No volpkgs found for scroll {scroll_name}.[/bold red]")
            return 0

        if not volpkg_name:
            scroll_defaults = self.default_config.get(scroll_name, {})
            volpkg_name = self.get_volpkg(scroll_defaults, volpkg_list)

        volpkg_url = urljoin(scroll_url, f"{volpkg_name}/")
        paths_url = urljoin(volpkg_url, "paths/")
        fragment_list = utils.fetch_links(paths_url, self.session, only_dirs=True)
        if not fragment_list:
            self.console.print(f"[bold red]No fragments found in volpkg {volpkg_name}.[/bold red]")
            return 0

        if fragment_id not in fragment_list:
            self.console.print(f"[bold red]Fragment {fragment_id} not found in volpkg {volpkg_name}.[/bold red]")
            if self.verbosity != "quiet":
                self.console.print("[yellow]Available fragments:[/yellow]")
                for i, frag in enumerate(fragment_list[:5]):  # Show only first 5 fragments
                    self.console.print(f"- {frag}")
                if len(fragment_list) > 5:
                    self.console.print(f"  ...and {len(fragment_list) - 5} more")
            return 0

        fragment_url = urljoin(paths_url, f"{fragment_id}/")
        layers_url = urljoin(fragment_url, "layers/")
        slice_files = utils.fetch_links(layers_url, self.session, keyword=['.tif', '.jpg'])
        if not slice_files:
            self.console.print(f"[bold red]Unable to fetch slices for fragment {fragment_id}.[/bold red]")
            return 0

        max_slices = int(len(slice_files))
        if max_slices == 0:
            self.console.print(f"[bold red]No slices information available for fragment {fragment_id}.[/bold red]")
            return 0

        ranges = utils.parse_slice_ranges(slices, max_slices)
        if not ranges:
            self.console.print("[bold red]No valid slice ranges provided.[/bold red]")
            return 0

        fragment_dir = os.path.join(output_dir, scroll_name.lower(), "fragments", fragment_id)
        os.makedirs(fragment_dir, exist_ok=True)
        output_folder = os.path.join(fragment_dir, "layers")

        ext = '.tif'
        if slice_files[0].lower().endswith('.jpg'):
            ext = '.jpg'
        filename_format = "{:02d}" + ext

        # Get tasks and count of skipped files
        slice_tasks, skipped_count = utils.prepare_slice_download_tasks(layers_url, ranges, output_folder,
                                                                        filename_format)

        bytes_downloaded = 0
        if slice_tasks:
            # Use our enhanced method with correct unit
            bytes_downloaded += self.start_downloads_with_unit(slice_tasks, register_signals=register_signals,
                                                               unit="file")
        else:
            if skipped_count > 0:
                self.console.print(
                    f"[green]All {skipped_count} slices already exist for fragment '{fragment_id}'.[/green]")
            else:
                self.console.print(f"[green]No slices to download for fragment '{fragment_id}'.[/green]")

        mask_bytes_downloaded = 0
        if mask:
            mask_files = utils.fetch_links(fragment_url, self.session, keyword='mask')
            if not mask_files:
                self.console.print(
                    f"[yellow]No mask file found for fragment {fragment_id}. Skipping mask download.[/yellow]")
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
                    # Use our enhanced method with correct unit for mask download
                    mask_bytes_downloaded = self.start_downloads_with_unit(
                        mask_tasks,
                        file_type=f"mask ({selected_mask})",
                        register_signals=register_signals,
                        unit="file"
                    )
                    bytes_downloaded += mask_bytes_downloaded
                else:
                    if self.verbosity != "quiet":
                        self.console.print(f"[dim]Mask file already exists.[/dim]")

        return bytes_downloaded
