![UniversityHeader](https://github.com/mvrcii/phalanx/blob/main/assets/phalanx_banner.jpg)

# phalanx

phalanx is a specialized tool for downloading scrolls and fragments, allowing users to efficiently retrieve specific slices from volumes and fragments. The name "phalanx" draws inspiration from the mythical phoenix, symbolizing rebirth and revival. Just as the phoenix rises from its ashes, phalanx is designed to help resurrect and breathe new life into ancient scrolls buried under the ashes of Mount Vesuvius, offering a modern way to explore and preserve these fragments of history.

## Installation

```sh
pip install vesuvius-phalanx
```

## Requirements
- Python 3.8+

### Core Dependencies

- **requests**: For handling HTTP requests and downloading content from the web.
- **beautifulsoup4**: For parsing HTML and extracting useful information from web pages.
- **tqdm**: Provides a progress bar to visualize the download progress.
- **click**: A package for creating user-friendly command-line interfaces.

## Usage

### Download Slices from a Volume

```sh
phalanx download-volume --scroll-name SCROLL_NAME [--volpkg-name VOLPKG_NAME] [--volume-id VOLUME_ID] [--slices SLICES]
```

- `--scroll-name`: Name of the scroll (e.g., 'Scroll1').
- `--volpkg-name`: Name of the volpkg (optional).
- `--volume-id`: Volume identifier (optional).
- `--slices`: Slice ranges to download (default is all).

### Download Slices from a Fragment

```sh
phalanx download-fragment --scroll-name SCROLL_NAME [--volpkg-name VOLPKG_NAME] --fragment-id FRAGMENT_ID [--slices SLICES] [--mask]
```

- `--scroll-name`: Name of the scroll (e.g., 'Scroll1').
- `--volpkg-name`: Name of the volpkg (optional).
- `--fragment-id`: Fragment identifier.
- `--slices`: Slice ranges to download (default is all).
- `--mask`: Download mask (default is true).

## Examples

### Download Slices 1-5 from a Scroll Volume

```sh
phnx download-volume --scroll-name Scroll1 --volume-id 20230205180739 --slices 1-5
```

### Download All Slices from a Scroll Volume

```sh
phnx download-volume --scroll-name Scroll1 --volume-id 20230205180739
```

### Download All Slices from a Scroll Fragment 

```sh
phnx download-fragment --scroll-name Scroll1 --fragment-id 20230503225234 --slices all
```

## Features

- **Multithreaded Downloads**: Download slices in parallel for improved performance.
- **Flexible Slice Selection**: Download specific slices, ranges, or all slices.
- **User-Friendly CLI**: Command-line interface built with [Click](https://click.palletsprojects.com/en/stable/).

## Contributing

Contributions are welcome! Please submit a pull request or open an issue.

## License

This project is licensed under the MIT License.

## Additional Notes

- **Progress Bar**: Tracks the number of files downloaded and total data.
- **Error Handling**: Informs users if any files fail to download after retries.
- **Extensibility**: Easily add new downloaders or features.

