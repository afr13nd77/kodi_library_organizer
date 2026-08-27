[![CI](https://github.com/afr13nd77/kodi_library_organizer/actions/workflows/ci.yml/badge.svg)](https://github.com/afr13nd77/kodi_library_organizer/actions/workflows/ci.yml)
[![Kodi version](https://img.shields.io/badge/kodi%20versions-20--21-blue)](https://kodi.tv/)
[![GitHub release](https://img.shields.io/github/release/afr13nd77/kodi_library_organizer.svg)](https://github.com/afr13nd77/kodi_library_organizer/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Русская версия](README.md)

# Kodi Library Organizer

**Version:** 1.2.0 | **Platform:** Kodi v20 Nexus / v21 Omega | **Language:** Python 3.8 | **License:** MIT

A Kodi addon that reorganizes a flat movie directory into a per-folder structure where each movie gets its own folder with all associated files (subtitles, NFO, artwork). Addon type: `xbmc.python.script`.

## Features

- Directory scanning with file grouping (video + subtitles + NFO + artwork)
- Move or copy mode (configurable)
- Smart folder naming: "Movie.Name.2014.1080p.mkv" → folder "Movie Name (2014)"
- Year lookup from Kodi library (JSON-RPC) when year is missing from filename
- Multi-part file support (CD1/CD2, Part1/Part2)
- Operation preview before execution (dry-run)
- Path and operation confirmation screens with intuitive button flow
- Undo journal for rolling back operations
- Full Cyrillic filename support

## Requirements

- Kodi v20+ (Python 3.8)

## Installation

1. Download ZIP from [Releases](https://github.com/afr13nd77/kodi_library_organizer/releases)
2. In Kodi go to Settings → Add-ons → Install from zip file
3. Select the downloaded ZIP

## Usage

1. Go to Programs → Library Organizer
2. Select "Organize library"
3. Review source and destination paths on the confirmation screen
4. Click "Continue" (or "Change" to open Settings)
5. Review operation summary (movie count, file count, total size)
6. Click "Start" (or "Details" to see the full operation list)
7. After completion — update sources in Kodi settings

## Settings

| Setting | Description | Default |
|---|---|---|
| source_directory | Source directory (flat library) | — |
| destination_directory | Destination directory | — |
| operation_mode | Move / Copy | Move |
| dry_run | Preview only, no execution | Yes |
| enrich_from_library | Look up year from Kodi library | Yes |
| clean_names | Normalize folder names | Yes |
| min_file_size_mb | Minimum file size (MB) | 100 |
| handle_multipart | Group multi-part files | Yes |
| undo_enabled | Save journal for undo | Yes |
| debug_logging | Verbose debug logging | No |

## Building from source

```bash
python build_zip.py
```

## Testing

```bash
pip install -r requirements.txt
python -m pytest shared/tests/ script.library.organizer/tests/ -v
```

174 tests (154 shared + 20 addon).

## License

MIT
