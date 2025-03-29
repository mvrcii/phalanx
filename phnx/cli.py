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
@click.argument('frag-id', required=True, type=str)
@click.option('--output-dir', default='data', help='Output data root directory.')
@click.option('--volpkg-name', default=None, help='Name of the volpkg (if multiple are available).')
@click.option('--slices', default='all', help='Slice ranges to download (e.g., "0-10,15,20-25").')
@click.option('--mask', default=True, help='Attempt to download the mask for the fragment (default: true).')
def download_fragment(scroll_id, frag_id, volpkg_name, output_dir, slices, mask):
    """
    Download slices from a fragment.

    Mandatory arguments:
      scroll-id: Numeric scroll ID (e.g., 5). This value will be prepended with "Scroll" (e.g., Scroll5).
      frag-id: Fragment ID (e.g., 20241024131838).
    """
    downloader = FragmentDownloader()
    downloader.download(
        output_dir=output_dir,
        scroll_name=f"Scroll{scroll_id}",
        volpkg_name=volpkg_name,
        fragment_id=frag_id,
        slices=slices,
        mask=mask
    )


if __name__ == '__main__':
    cli()
