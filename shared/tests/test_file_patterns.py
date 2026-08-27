from __future__ import annotations

from shared.file_patterns import (
    ARTWORK_EXTENSIONS,
    ASSOCIATED_EXTENSIONS,
    METADATA_EXTENSIONS,
    MULTIPART_PATTERN,
    QUALITY_TAGS,
    SUBTITLE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)


class TestVideoExtensions:
    def test_count(self):
        assert len(VIDEO_EXTENSIONS) == 16

    def test_all_start_with_dot(self):
        for ext in VIDEO_EXTENSIONS:
            assert ext.startswith("."), f"{ext} does not start with dot"

    def test_all_lowercase(self):
        for ext in VIDEO_EXTENSIONS:
            assert ext == ext.lower(), f"{ext} is not lowercase"

    def test_contains_all_expected(self):
        expected = {
            ".mkv", ".avi", ".mp4", ".m4v", ".mov", ".wmv", ".flv", ".ts",
            ".m2ts", ".vob", ".divx", ".mpg", ".mpeg", ".ogm", ".webm", ".3gp",
        }
        assert VIDEO_EXTENSIONS == expected


class TestSubtitleExtensions:
    def test_contains_srt(self):
        assert ".srt" in SUBTITLE_EXTENSIONS

    def test_contains_sub(self):
        assert ".sub" in SUBTITLE_EXTENSIONS

    def test_contains_ass(self):
        assert ".ass" in SUBTITLE_EXTENSIONS


class TestArtworkExtensions:
    def test_contains_jpg(self):
        assert ".jpg" in ARTWORK_EXTENSIONS

    def test_contains_png(self):
        assert ".png" in ARTWORK_EXTENSIONS

    def test_contains_tbn(self):
        assert ".tbn" in ARTWORK_EXTENSIONS


class TestMetadataExtensions:
    def test_contains_nfo(self):
        assert ".nfo" in METADATA_EXTENSIONS


class TestAssociatedExtensions:
    def test_is_union(self):
        assert ASSOCIATED_EXTENSIONS == SUBTITLE_EXTENSIONS | ARTWORK_EXTENSIONS | METADATA_EXTENSIONS


class TestMultipartPattern:
    def test_cd1(self):
        m = MULTIPART_PATTERN.match("Movie.Name.CD1.avi")
        assert m is not None
        assert m.group(1) == "Movie.Name"
        assert m.group(2) == "1"

    def test_disc2(self):
        m = MULTIPART_PATTERN.match("Movie_Name_disc2.mkv")
        assert m is not None
        assert m.group(1) == "Movie_Name"
        assert m.group(2) == "2"

    def test_pt1(self):
        m = MULTIPART_PATTERN.match("Movie-pt1.avi")
        assert m is not None
        assert m.group(1) == "Movie"
        assert m.group(2) == "1"

    def test_part_with_dot(self):
        m = MULTIPART_PATTERN.match("Movie.Part.1.extra")
        assert m is not None
        assert m.group(1) == "Movie"
        assert m.group(2) == "1"

    def test_no_match_year(self):
        m = MULTIPART_PATTERN.match("Movie.Name.2014.mkv")
        assert m is None

    def test_no_match_plain(self):
        m = MULTIPART_PATTERN.match("Movie.Name.mkv")
        assert m is None


class TestQualityTags:
    def test_contains_1080p(self):
        assert "1080p" in QUALITY_TAGS

    def test_contains_bdrip(self):
        assert "bdrip" in QUALITY_TAGS

    def test_contains_web_dl(self):
        assert "web-dl" in QUALITY_TAGS

    def test_contains_x264(self):
        assert "x264" in QUALITY_TAGS
