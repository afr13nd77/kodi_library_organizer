from __future__ import annotations

import os
import re
from dataclasses import dataclass

try:
    from file_patterns import QUALITY_TAGS
except ImportError:
    from .file_patterns import QUALITY_TAGS

_YEAR_RE = re.compile(r'\b((?:19|20)\d{2})\b')
_SANITIZE_RE = re.compile(r'[<>:"/\\|?*]')
_EMPTY_BRACKETS_RE = re.compile(r'\(\s*\)|\[\s*\]')
_SEPARATOR_RE = re.compile(r'[._\[\]()\{\}]')
_MAX_FOLDER_LEN = 200


@dataclass
class ParsedName:
    title: str
    year: int | None
    clean_folder_name: str
    raw_name: str


def parse_name(filename: str) -> ParsedName:
    raw_name = filename

    name = _SEPARATOR_RE.sub(' ', filename)
    name = name.replace('-', ' ')

    year = None
    title_part = name
    for match in _YEAR_RE.finditer(name):
        candidate = int(match.group(1))
        if 1920 <= candidate <= 2099:
            year = candidate
            year_match = match

    if year is not None:
        title_part = name[:year_match.start()]
    else:
        words = name.split()
        cut_index = len(words)
        for i, w in enumerate(words):
            if w.lower() in QUALITY_TAGS:
                cut_index = i
                break
        title_part = ' '.join(words[:cut_index])

    tokens = title_part.split()
    cleaned_tokens = [t for t in tokens if t.lower() not in QUALITY_TAGS]

    title = ' '.join(cleaned_tokens)

    title = title.rstrip(' -.')
    title = _EMPTY_BRACKETS_RE.sub('', title)
    title = title.rstrip(' -.')

    if not title.strip():
        title = raw_name

    if year is not None:
        clean_folder_name = f"{title} ({year})"
    else:
        clean_folder_name = title

    clean_folder_name = _SANITIZE_RE.sub('', clean_folder_name)
    clean_folder_name = clean_folder_name.rstrip('. ')

    if len(clean_folder_name) > _MAX_FOLDER_LEN:
        clean_folder_name = clean_folder_name[:_MAX_FOLDER_LEN]

    return ParsedName(
        title=title,
        year=year,
        clean_folder_name=clean_folder_name,
        raw_name=raw_name,
    )


def normalize_filename(filename: str) -> str:
    """Normalize a filename using parse_name logic, preserving extension."""
    name, ext = os.path.splitext(filename)
    parsed = parse_name(name)
    if not parsed.title.strip():
        return filename
    return f"{parsed.title}{ext}"
