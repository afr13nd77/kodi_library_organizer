from __future__ import annotations

import pytest

from shared.name_parser import ParsedName, parse_name, normalize_filename


class TestParseNameTable:
    """Обязательные тест-кейсы из design.md."""

    @pytest.mark.parametrize(
        "filename, expected_title, expected_year, expected_folder",
        [
            ("Interstellar.2014.1080p.BDRip.x264", "Interstellar", 2014, "Interstellar (2014)"),
            ("Dune.Part.Two.2024.WEB-DL", "Dune Part Two", 2024, "Dune Part Two (2024)"),
            ("The.Matrix.1999.REMASTERED.BluRay", "The Matrix", 1999, "The Matrix (1999)"),
            ("some_random_movie", "some random movie", None, "some random movie"),
            ("2001.A.Space.Odyssey.1968.BDRip", "2001 A Space Odyssey", 1968, "2001 A Space Odyssey (1968)"),
            ("Movie (2020) [1080p]", "Movie", 2020, "Movie (2020)"),
        ],
        ids=[
            "interstellar",
            "dune-part-two",
            "matrix-remastered",
            "no-year-underscores",
            "2001-space-odyssey",
            "brackets-and-parens",
        ],
    )
    def test_parse_name(self, filename, expected_title, expected_year, expected_folder):
        result = parse_name(filename)
        assert result.title == expected_title
        assert result.year == expected_year
        assert result.clean_folder_name == expected_folder


class TestCyrillic:
    def test_cyrillic_name_with_year(self):
        result = parse_name("Брат.1997.DVDRip")
        assert result.title == "Брат"
        assert result.year == 1997
        assert result.clean_folder_name == "Брат (1997)"


class TestSpecialCharacters:
    def test_colon_removed_from_folder_name(self):
        result = parse_name("Movie: The Sequel.2020")
        assert ":" not in result.clean_folder_name
        assert result.year == 2020
        assert "Movie" in result.title

    def test_all_forbidden_chars_removed(self):
        result = parse_name('A<B>C:D"E/F\\G|H?I*J.2020')
        for ch in '<>:"/\\|?*':
            assert ch not in result.clean_folder_name


class TestEmptyTitleFallback:
    def test_fallback_to_raw_name(self):
        # WHY: all tokens are quality tags, so title becomes empty after cleanup
        result = parse_name("1080p.BDRip.x264")
        assert result.title == "1080p.BDRip.x264"
        assert result.clean_folder_name == "1080p.BDRip.x264"


class TestLongName:
    def test_truncation_at_200(self):
        long_name = "A" * 250
        result = parse_name(long_name)
        assert len(result.clean_folder_name) <= 200

    def test_long_name_with_year(self):
        long_title = "A" * 250
        filename = f"{long_title}.2020"
        result = parse_name(filename)
        assert len(result.clean_folder_name) <= 200
        assert result.year == 2020


class TestRawName:
    def test_raw_name_preserved(self):
        filename = "Interstellar.2014.1080p.BDRip.x264"
        result = parse_name(filename)
        assert result.raw_name == filename

    def test_raw_name_no_modification(self):
        filename = "some_random_movie"
        result = parse_name(filename)
        assert result.raw_name == filename

    def test_raw_name_with_cyrillic(self):
        filename = "Брат.1997.DVDRip"
        result = parse_name(filename)
        assert result.raw_name == filename


class TestReturnType:
    def test_returns_parsed_name_dataclass(self):
        result = parse_name("Test.2020")
        assert isinstance(result, ParsedName)


class TestEdgeCases:
    def test_year_at_boundary_1920(self):
        result = parse_name("OldFilm.1920")
        assert result.year == 1920

    def test_year_at_boundary_2099(self):
        result = parse_name("FutureFilm.2099")
        assert result.year == 2099

    def test_year_below_range(self):
        result = parse_name("Film.1919.something")
        assert result.year is None

    def test_trailing_dots_stripped_from_folder(self):
        result = parse_name("Movie...2020")
        assert not result.clean_folder_name.endswith(".")

    def test_trailing_spaces_stripped_from_folder(self):
        result = parse_name("Movie   2020")
        assert not result.clean_folder_name.endswith(" ")

    def test_multiple_quality_tags_removed(self):
        result = parse_name("Film.2020.1080p.BluRay.x264.DTS")
        assert result.title == "Film"
        assert result.year == 2020

    def test_hyphenated_separator(self):
        result = parse_name("My-Movie-2021-720p")
        assert result.title == "My Movie"
        assert result.year == 2021

    def test_no_year_truncate_at_first_tag(self):
        result = parse_name("Star.Wars.The.Mandalorian.And.Grogu.720p.rus.LostFilm.TV")
        assert result.title == "Star Wars The Mandalorian And Grogu"
        assert result.year is None
        assert result.clean_folder_name == "Star Wars The Mandalorian And Grogu"

    def test_no_year_no_tags(self):
        result = parse_name("some_random_movie")
        assert result.title == "some random movie"
        assert result.clean_folder_name == "some random movie"


class TestNormalizeFilename:
    """Tests for normalize_filename()."""

    def test_dirty_name_cleaned(self):
        result = normalize_filename("Movie.Name.720p.BluRay.x264.mp4")
        assert result == "Movie Name.mp4"

    def test_clean_name_unchanged(self):
        result = normalize_filename("Movie Name.mp4")
        assert result == "Movie Name.mp4"

    def test_with_year_in_name(self):
        result = normalize_filename("Movie.Name.2024.720p.BluRay.mp4")
        assert result == "Movie Name.mp4"

    def test_preserves_extension(self):
        result = normalize_filename("Movie.Name.720p.srt")
        assert result == "Movie Name.srt"

    def test_empty_title_returns_original(self):
        result = normalize_filename("720p.mp4")
        assert result.endswith(".mp4")
