"""Тесты для модуля shared/scanner.py."""
from __future__ import annotations

import os

import pytest

from shared.scanner import ScanResult, scan_directory


def _create_file(directory, name: str, size: int = 10) -> str:
    """Создать файл заданного размера в директории. Возвращает полный путь."""
    path = os.path.join(str(directory), name)
    with open(path, "wb") as f:
        f.truncate(size)
    return path


class TestBasicScan:
    """Тест 1: 3 видео (.mkv, .avi, .mp4) + по 1 .srt каждому -> 3 группы."""

    def test_three_videos_with_subtitles(self, tmp_path):
        _create_file(tmp_path, "Interstellar.2014.1080p.mkv")
        _create_file(tmp_path, "Interstellar.2014.1080p.srt")
        _create_file(tmp_path, "Dune.2021.WEB-DL.avi")
        _create_file(tmp_path, "Dune.2021.WEB-DL.srt")
        _create_file(tmp_path, "Matrix.1999.mp4")
        _create_file(tmp_path, "Matrix.1999.srt")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert isinstance(result, ScanResult)
        assert len(result.groups) == 3
        assert len(result.skipped_files) == 0
        assert len(result.unmatched_files) == 0

        for group in result.groups:
            assert len(group.video_files) == 1
            assert len(group.associated_files) == 1
            assert group.associated_files[0].extension == ".srt"


class TestFullAssociatedSet:
    """Тест 2 (AC-02): 1 видео + .srt + .sub + .ass + .nfo + poster.jpg + fanart.jpg."""

    def test_all_associated_types(self, tmp_path):
        base = "Interstellar.2014.1080p"
        _create_file(tmp_path, f"{base}.mkv")
        _create_file(tmp_path, f"{base}.srt")
        _create_file(tmp_path, f"{base}.sub")
        _create_file(tmp_path, f"{base}.ass")
        _create_file(tmp_path, f"{base}.nfo")
        _create_file(tmp_path, f"{base}-poster.jpg")
        _create_file(tmp_path, f"{base}-fanart.jpg")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        group = result.groups[0]
        assert len(group.video_files) == 1
        assert len(group.associated_files) == 6


class TestSizeFilter:
    """Тест 3 (AC-03): фильтрация по размеру."""

    def test_small_file_skipped(self, tmp_path):
        _create_file(tmp_path, "Small.Movie.mkv", size=50)
        _create_file(tmp_path, "Big.Movie.mkv", size=200)

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=100,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        assert result.groups[0].video_files[0].filename == "Big.Movie.mkv"
        assert len(result.skipped_files) == 1
        assert result.skipped_files[0].filename == "Small.Movie.mkv"


class TestMultipart:
    """Тест 4: Multi-part группировка."""

    def test_cd1_cd2_grouped(self, tmp_path):
        _create_file(tmp_path, "Movie.CD1.avi", size=200)
        _create_file(tmp_path, "Movie.CD2.avi", size=200)
        _create_file(tmp_path, "Movie.srt")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        group = result.groups[0]
        assert len(group.video_files) == 2
        # Части отсортированы по номеру
        assert "CD1" in group.video_files[0].filename
        assert "CD2" in group.video_files[1].filename
        # Субтитры привязаны
        assert len(group.associated_files) == 1
        assert group.associated_files[0].extension == ".srt"

    def test_multipart_base_name_stripped(self, tmp_path):
        """base_name должен быть очищен от разделителей."""
        _create_file(tmp_path, "Movie.CD1.avi")
        _create_file(tmp_path, "Movie.CD2.avi")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        assert result.groups[0].base_name == "Movie"


class TestMultipartDisabled:
    """Тест 5: handle_multipart=False -> CD1+CD2 = 2 отдельные группы."""

    def test_no_grouping_when_disabled(self, tmp_path):
        _create_file(tmp_path, "Movie.CD1.avi")
        _create_file(tmp_path, "Movie.CD2.avi")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=False,
            clean_names=True,
        )

        assert len(result.groups) == 2


class TestEmptyDirectory:
    """Тест 6: Пустая директория."""

    def test_empty_dir(self, tmp_path):
        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 0
        assert len(result.skipped_files) == 0
        assert len(result.unmatched_files) == 0
        assert result.total_size_bytes == 0


class TestOnlySubtitles:
    """Тест 7: Только субтитры (нет видео) -> всё в unmatched_files."""

    def test_subs_without_video(self, tmp_path):
        _create_file(tmp_path, "Movie.srt")
        _create_file(tmp_path, "Movie.sub")
        _create_file(tmp_path, "Movie.ass")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 0
        assert len(result.unmatched_files) == 3


class TestCleanNamesTrue:
    """Тест 8: clean_names=True -> parsed_name.clean_folder_name нормализован."""

    def test_normalized_folder_name(self, tmp_path):
        _create_file(tmp_path, "Interstellar.2014.1080p.BDRip.x264.mkv")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        group = result.groups[0]
        assert group.parsed_name.clean_folder_name == "Interstellar (2014)"
        assert group.parsed_name.year == 2014


class TestCleanNamesFalse:
    """Тест 9: clean_names=False -> clean_folder_name = raw base_name."""

    def test_raw_base_name(self, tmp_path):
        _create_file(tmp_path, "Movie.2020.1080p.mkv")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=False,
        )

        assert len(result.groups) == 1
        group = result.groups[0]
        assert group.parsed_name.clean_folder_name == "Movie.2020.1080p"


class TestTotalSizeBytes:
    """Тест 10: total_size_bytes = сумма размеров всех файлов в groups."""

    def test_total_size_calculated(self, tmp_path):
        _create_file(tmp_path, "Movie1.mkv", size=100)
        _create_file(tmp_path, "Movie1.srt", size=20)
        _create_file(tmp_path, "Movie2.avi", size=150)

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert result.total_size_bytes == 100 + 20 + 150


class TestVideoWithoutAssociated:
    """Тест 11: Видео без associated -> MovieGroup с пустым associated_files."""

    def test_empty_associated(self, tmp_path):
        _create_file(tmp_path, "LonelyMovie.mkv")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        assert len(result.groups[0].associated_files) == 0


class TestUnrecognizedFiles:
    """Тест 12: Нераспознанный файл (.txt, .exe) -> unmatched_files."""

    def test_txt_and_exe_unmatched(self, tmp_path):
        _create_file(tmp_path, "readme.txt")
        _create_file(tmp_path, "installer.exe")
        _create_file(tmp_path, "Movie.mkv")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        assert len(result.unmatched_files) == 2
        unmatched_names = {f.filename for f in result.unmatched_files}
        assert "readme.txt" in unmatched_names
        assert "installer.exe" in unmatched_names


class TestCaseInsensitiveExtensions:
    """Тест 13: Case-insensitive расширения: VIDEO.MKV и video.mkv."""

    def test_uppercase_extension(self, tmp_path):
        _create_file(tmp_path, "Movie1.MKV")
        _create_file(tmp_path, "Movie2.mkv")
        _create_file(tmp_path, "Movie3.Avi")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 3
        assert len(result.unmatched_files) == 0


class TestDirectoriesSkipped:
    """Директории внутри source_path должны пропускаться."""

    def test_subdir_ignored(self, tmp_path):
        os.mkdir(os.path.join(str(tmp_path), "subdir"))
        _create_file(tmp_path, "Movie.mkv")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1


class TestNonexistentDirectory:
    """Несуществующая директория -> пустой ScanResult без краша."""

    def test_missing_dir(self, tmp_path):
        bad_path = os.path.join(str(tmp_path), "nonexistent")

        result = scan_directory(
            source_path=bad_path,
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 0
        assert result.total_size_bytes == 0


class TestMovieFileDataclass:
    """Проверка полей MovieFile."""

    def test_movie_file_fields(self, tmp_path):
        _create_file(tmp_path, "Test.Movie.2020.mkv", size=42)

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        mf = result.groups[0].video_files[0]
        assert mf.filename == "Test.Movie.2020.mkv"
        assert mf.full_path == os.path.join(str(tmp_path), "Test.Movie.2020.mkv")
        assert mf.size_bytes == 42
        assert mf.extension == ".mkv"


class TestTotalSizeExcludesSkipped:
    """total_size_bytes НЕ включает skipped файлы."""

    def test_skipped_not_counted(self, tmp_path):
        _create_file(tmp_path, "Small.mkv", size=10)
        _create_file(tmp_path, "Big.mkv", size=200)
        _create_file(tmp_path, "Big.srt", size=5)

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=50,
            handle_multipart=True,
            clean_names=True,
        )

        assert result.total_size_bytes == 200 + 5
        assert len(result.skipped_files) == 1


class TestMultipartVariants:
    """Разные варианты multi-part паттернов."""

    @pytest.mark.parametrize(
        "filenames",
        [
            ("Movie.part1.mkv", "Movie.part2.mkv"),
            ("Movie.disc1.mkv", "Movie.disc2.mkv"),
            ("Movie.disk1.mkv", "Movie.disk2.mkv"),
            ("Movie.pt1.mkv", "Movie.pt2.mkv"),
        ],
        ids=["part", "disc", "disk", "pt"],
    )
    def test_multipart_patterns(self, tmp_path, filenames):
        for fn in filenames:
            _create_file(tmp_path, fn)

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 1
        assert len(result.groups[0].video_files) == 2


class TestLongestPrefixMatch:
    """Associated файл привязывается к самому длинному совпадающему base_name."""

    def test_longest_prefix_wins(self, tmp_path):
        # Два видео с перекрывающимися именами
        _create_file(tmp_path, "Movie.mkv")
        _create_file(tmp_path, "Movie.Extended.mkv")
        # Субтитры должны привязаться к более длинному base_name
        _create_file(tmp_path, "Movie.Extended.srt")

        result = scan_directory(
            source_path=str(tmp_path),
            min_file_size_bytes=0,
            handle_multipart=True,
            clean_names=True,
        )

        assert len(result.groups) == 2
        for group in result.groups:
            if group.base_name == "Movie.Extended":
                assert len(group.associated_files) == 1
            elif group.base_name == "Movie":
                assert len(group.associated_files) == 0
