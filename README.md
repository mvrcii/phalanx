![UniversityHeader](https://github.com/mvrcii/phalanx/blob/main/assets/phalanx_banner.jpg)

# phalanx

[![PyPI version](https://img.shields.io/pypi/v/vesuvius-phalanx.svg)](https://pypi.org/project/vesuvius-phalanx/)
[![Python versions](https://img.shields.io/pypi/pyversions/vesuvius-phalanx.svg)](https://pypi.org/project/vesuvius-phalanx/)
[![License](https://img.shields.io/github/license/mvrcii/phalanx.svg)](https://github.com/mvrcii/phalanx/blob/main/LICENSE)

A specialized tool for downloading scrolls and fragments from the Vesuvius Challenge dataset. Phalanx allows users to efficiently retrieve specific slices from volumes and fragments with parallel downloading capability.

The name "phalanx" draws inspiration from the mythical phoenix, symbolizing rebirth and revival. Just as the phoenix rises from its ashes, phalanx helps resurrect and breathe new life into ancient scrolls buried under the ashes of Mount Vesuvius.

## Key Features

- **Selective Downloads**: Download specific slice ranges instead of entire volumes
- **Multi-Fragment Support**: Download multiple fragments with a single command
- **Parallel/Sequential Mode**: Choose between parallel or sequential download modes
- **Rich Terminal Interface**: Color-coded progress bars and status messages
- **Multithreaded Downloading**: Parallel download operations for improved performance
- **Progress Tracking**: Visual progress bars showing completion status and data transfer
- **Operation Summaries**: Detailed download summaries showing success rates and statistics
- **Smart Defaults**: Automatically selects appropriate volume/fragment IDs when possible
- **Error Handling**: Robust retry mechanism and helpful error messages
- **Clean CLI**: Intuitive command-line interface with comprehensive help documentation

## Installation
```sh
pip install vesuvius-phalanx
```

### Dependencies

| Package | Purpose |
|---------|---------|
| requests | HTTP requests and content downloading |
| beautifulsoup4 | HTML parsing and web page data extraction |
| rich | Terminal formatting and progress visualization |
| click | User-friendly command-line interface |


## Command-line Usage

### Download Volume Slices

```sh
phalanx download-volume SCROLL_ID --output-path OUTPUT_PATH [OPTIONS]
```

#### Parameters:

- `SCROLL_ID`: Numeric ID (e.g., 5) - will be prepended with "Scroll" automatically
- `--output-path`: Path to store downloaded data (full_scrolls directory)
- `--volpkg-name`: (Optional) Specific volpkg name if multiple are available
- `--volume-id`: (Optional) Specific volume identifier
- `--slices`: (Optional) Slice ranges to download (default: all)
  - Format: "start-end" or "start-end,another-range"
  - Example: "1-5,10,15-20"
- `--verbosity`: (Optional) Control output detail level (quiet, normal, verbose)


### Download Fragment Slices

```sh
phalanx download-fragment SCROLL_ID FRAG_IDS [OPTIONS]
```

#### Parameters:

- `SCROLL_ID`: Numeric ID (e.g., 5) - will be prepended with "Scroll" automatically
- `FRAG_IDS`: Fragment identifier(s) - can be a single ID or comma-separated list 
  - Example single: 20241024131838
  - Example multiple: 20241024131838,20241024131839,20241024131840
- `--output-dir`: (Optional) Output data root directory (default: data)
- `--volpkg-name`: (Optional) Specific volpkg name if multiple are available
- `--slices`: (Optional) Slice ranges to download (default: all)
- `--mask/--no-mask`: (Optional) Whether to download the mask (default: true)
- `--parallel/--sequential`: (Optional) Download mode for multiple fragments (default: parallel)
- `--verbosity`: (Optional) Control output detail level (quiet, normal, verbose)

## Examples

### Basic Usage

Download all volume slices for Scroll 1 with auto-detected defaults:

```sh
phalanx download-volume 1 --output-path ./data
```

Download specific slices from Scroll 1:

```sh
phalanx download-volume 1 --output-path ./data --slices 1-5
```

### Advanced Usage

Download with explicit volume identifier:

```sh
phalanx download-volume 1 --output-path ./data --volume-id 20230205180739 --slices 1-5
```

Download a single fragment with its mask:

```sh
phalanx download-fragment 1 20230503225234 --output-dir ./vesuvius_data --slices all
```

Download multiple fragments in parallel:

```sh
phalanx download-fragment 5 20241108120732,20241108111522,20241113090990 --slices 17-20 --parallel
```

Download multiple fragments sequentially:

```sh
phalanx download-fragment 5 20241108120732,20241108111522 --slices 17-20 --sequential --no-mask
```

Download with minimal console output:

```sh
phalanx download-fragment 5 20241108120732 --verbosity quiet
```


## How It Works

Phalanx operates by:

1. **Discovery**: Identifying available volpkgs and volumes for the requested scroll
2. **Selection**: Choosing appropriate defaults or using user-specified identifiers
3. **Metadata Retrieval**: Fetching slice information and other metadata
4. **Parallel Downloads**: Creating multiple worker threads for faster downloading
5. **Error Handling**: Implementing retries and cleanup for failed or interrupted downloads
6. **Operation Summary**: Providing detailed statistics about the download operation

## Technical Details

- **Intelligent Defaults**: The tool maintains a defaults.json file with preferred volpkg and volume IDs for common scrolls
- **Session Management**: Creates optimized HTTP sessions with retry capabilities
- **Resource Management**: Cleans up partial downloads on startup and handles interruptions
- **Progress Reporting**: Shows real-time download progress with data transfer rates
- **Rich Terminal Interface**: Uses the Rich library for enhanced console output
- **Parallel Processing**: Manages concurrent downloads while maintaining readable output


## Command Aliases

For convenience, you can also use the shorter `phnx` command instead of `phalanx`:

```sh
phnx download-volume 1 --output-path ./data
```

## Contributing

Contributions are welcome! Please submit a pull request or open an issue on GitHub.

Before contributing:
- Fork the repository
- Create a feature branch
- Add your changes
- Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.