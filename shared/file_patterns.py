from __future__ import annotations

import re

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mkv", ".avi", ".mp4", ".m4v", ".mov", ".wmv", ".flv", ".ts",
    ".m2ts", ".vob", ".divx", ".mpg", ".mpeg", ".ogm", ".webm", ".3gp",
})

SUBTITLE_EXTENSIONS: frozenset[str] = frozenset({
    ".srt", ".sub", ".ssa", ".ass", ".idx", ".sup", ".vtt",
})

ARTWORK_EXTENSIONS: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".tbn", ".gif", ".bmp", ".webp",
})

METADATA_EXTENSIONS: frozenset[str] = frozenset({".nfo"})

ASSOCIATED_EXTENSIONS: frozenset[str] = SUBTITLE_EXTENSIONS | ARTWORK_EXTENSIONS | METADATA_EXTENSIONS

MULTIPART_PATTERN: re.Pattern[str] = re.compile(
    r'^(.+?)[._\- ]+'
    r'(?:cd|disc|disk|part|pt)'
    r'[._\- ]*'
    r'(\d+)'
    r'(.*)$',
    re.IGNORECASE,
)

QUALITY_TAGS: frozenset[str] = frozenset({
    "1080p", "720p", "480p", "2160p", "4k",
    "bdrip", "brrip", "web-dl", "webrip", "hdrip", "dvdrip",
    "x264", "x265", "h264", "h265", "hevc",
    "aac", "ac3", "dts",
    "bluray", "blu-ray", "hdtv", "remux",
    "atmos", "truehd", "dd5.1", "dd7.1",
    "10bit", "hdr", "hdr10", "hdr10+", "dolby.vision", "dv", "imax",
    "proper", "repack", "extended", "unrated", "directors.cut", "theatrical",
    "complete", "multi", "dual", "rus", "eng",
    "nnm-club", "rarbg", "yts", "yify",
    "fgt", "sparks", "amiable", "geckos", "drones", "etrg",
})
