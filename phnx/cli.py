import click

from phnx.downloader.fragment_downloader import FragmentDownloader
from phnx.downloader.volume_downloader import VolumeDownloader


@click.group()
def cli():
    """phalanx: A versatile downloader for scrolls and fragments."""
    pass


@cli.command(name='download-volume')
@click.argument('scroll-id', required=True, type=int)
@click.option('--volpkg-name', default=None, help='Name of the volpkg (if multiple are available).')
@click.option('--output-path', required=True, help='The output path (the path of the full_scrolls directory).')
@click.option('--volume-id', default=None, help='Volume identifier.')
@click.option('--slices', default='all', help='Slice ranges to download (e.g., "1-5,10,15-20").')
def download_volume(scroll_id, volpkg_name, output_path, volume_id, slices):
    """
    Download slices from a volume.

    Mandatory arguments:
      scroll-id: Numeric scroll ID (e.g., 5). This value will be prepended with "Scroll" (e.g., Scroll5).
    """
    downloader = VolumeDownloader()
    downloader.download(
        output_path=output_path,
        scroll_name=f"Scroll{scroll_id}",
        volpkg_name=volpkg_name,
        volume_id=volume_id,
        slices=slices
    )


@cli.command(name='download-fragment')
@click.argument('scroll-id', required=True, type=int)
@click.argument('frag-ids', required=True, type=str)
@click.option('--output-dir', default='data', help='Output data root directory.')
@click.option('--volpkg-name', default=None, help='Name of the volpkg (if multiple are available).')
@click.option('--slices', default='all', help='Slice ranges to download (e.g., "0-10,15,20-25").')
@click.option('--mask/--no-mask', default=True, help='Attempt to download the mask for the fragment (default: true).')
@click.option('--parallel/--sequential', default=True,
              help='Download fragments in parallel or sequentially (default: parallel).')
def download_fragment(scroll_id, frag_ids, volpkg_name, output_dir, slices, mask, parallel):
    """
    Download slices from one or multiple fragments.

    Mandatory arguments:
      scroll-id: Numeric scroll ID (e.g., 5). This value will be prepended with "Scroll" (e.g., Scroll5).
      frag-ids: Fragment ID or comma-separated list of fragment IDs (e.g., "20241024131838" or "20241024131838,20241024131839").
    """
    downloader = FragmentDownloader()

    # Parse fragment IDs
    fragment_ids = [fid.strip() for fid in frag_ids.split(',')]

    if len(fragment_ids) == 1:
        # Single fragment, use the original download method
        downloader.download(
            output_dir=output_dir,
            scroll_name=f"Scroll{scroll_id}",
            volpkg_name=volpkg_name,
            fragment_id=fragment_ids[0],
            slices=slices,
            mask=mask
        )
    else:
        # Multiple fragments, use the new download_multiple method
        downloader.download_multiple(
            output_dir=output_dir,
            scroll_name=f"Scroll{scroll_id}",
            volpkg_name=volpkg_name,
            fragment_ids=fragment_ids,
            slices=slices,
            mask=mask,
            parallel=parallel
        )


if __name__ == '__main__':
    cli()