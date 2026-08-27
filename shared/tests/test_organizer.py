"""Тесты для модуля shared/organizer.py."""
from __future__ import annotations

import json
import os


from shared.name_parser import ParsedName
from shared.organizer import (
    ConflictResolution,
    FileConflictResolution,
    OperationMode,
    OperationPlan,
    PlannedGroup,
    PlannedOperation,
    _add_year_to_filename,
    _find_unique_filename,
    _find_unique_name,
    _format_size,
    build_plan,
    check_disk_space,
    execute_plan,
    format_preview,
    is_network_path,
    validate_paths,
)
from shared.scanner import MovieFile, MovieGroup, ScanResult


def _create_file(directory, name: str, size: int = 10) -> str:
    """Создать файл заданного размера в директории. Возвращает полный путь.

    Для больших логических размеров (>10KB) создаёт файл реального размера = size,
    но при size > 10KB ограничивает реальный файл до size (без truncate для гигантов).
    """
    path = os.path.join(str(directory), name)
    os.makedirs(str(directory), exist_ok=True)
    with open(path, "wb") as f:
        # Записываем реальные байты (для copy-проверки размера)
        f.write(b"\x00" * size)
    return path


def _make_scan_result(
    tmp_path,
    groups_data: list[dict],
    skipped: list[dict] | None = None,
) -> ScanResult:
    """Вспомогательная функция для создания ScanResult с реальными файлами.

    groups_data: [{"name": "...", "year": int|None, "videos": [("name", size)], "assoc": [("name", size)]}]
    Размеры должны быть маленькими (десятки-сотни байт) для реальных файловых операций.
    Для тестирования форматирования размеров используйте отдельные PlannedOperation.
    """
    groups = []
    total_size = 0
    skipped_files = []

    for gd in groups_data:
        video_files = []
        for vname, vsize in gd.get("videos", []):
            path = _create_file(tmp_path, vname, vsize)
            ext = os.path.splitext(vname)[1].lower()
            video_files.append(MovieFile(
                filename=vname, full_path=path,
                size_bytes=vsize, extension=ext,
            ))
            total_size += vsize

        associated_files = []
        for aname, asize in gd.get("assoc", []):
            path = _create_file(tmp_path, aname, asize)
            ext = os.path.splitext(aname)[1].lower()
            associated_files.append(MovieFile(
                filename=aname, full_path=path,
                size_bytes=asize, extension=ext,
            ))
            total_size += asize

        year = gd.get("year")
        title = gd["name"]
        if year is not None:
            folder_name = f"{title} ({year})"
        else:
            folder_name = title

        parsed = ParsedName(
            title=title, year=year,
            clean_folder_name=folder_name, raw_name=title,
        )

        base_name = gd.get("base_name", title)
        groups.append(MovieGroup(
            video_files=video_files,
            associated_files=associated_files,
            parsed_name=parsed,
            base_name=base_name,
        ))

    if skipped:
        for sd in skipped:
            path = _create_file(tmp_path, sd["name"], sd["size"])
            ext = os.path.splitext(sd["name"])[1].lower()
            skipped_files.append(MovieFile(
                filename=sd["name"], full_path=path,
                size_bytes=sd["size"], extension=ext,
            ))

    return ScanResult(
        groups=groups,
        skipped_files=skipped_files,
        unmatched_files=[],
        total_size_bytes=total_size,
    )


# =========================================================================
# Тест 1: build_plan - 2 группы -> 2 PlannedGroup
# =========================================================================

class TestBuildPlan:

    def test_two_groups_correct_structure(self, tmp_path):
        """Тест 1: 2 группы -> OperationPlan с 2 PlannedGroup, корректные пути."""
        source_dir = str(tmp_path / "source")
        dest_dir = str(tmp_path / "dest")
        os.makedirs(source_dir)

        scan_result = _make_scan_result(tmp_path / "source", [
            {
                "name": "Interstellar",
                "year": 2014,
                "videos": [("Interstellar.2014.1080p.mkv", 4200)],
                "assoc": [("Interstellar.2014.1080p.srt", 85)],
            },
            {
                "name": "Dune Part Two",
                "year": 2024,
                "videos": [("Dune.Part.Two.2024.WEB-DL.mkv", 2800)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, dest_dir, OperationMode.MOVE)

        assert len(plan.groups) == 2
        assert plan.mode == OperationMode.MOVE
        assert plan.destination_dir == dest_dir

        # Первая группа
        g1 = plan.groups[0]
        assert g1.folder_name == "Interstellar (2014)"
        assert g1.folder_path == os.path.join(dest_dir, "Interstellar (2014)")
        assert len(g1.operations) == 2  # 1 video + 1 srt

        # Вторая группа
        g2 = plan.groups[1]
        assert g2.folder_name == "Dune Part Two (2024)"
        assert len(g2.operations) == 1

    def test_total_files_and_size(self, tmp_path):
        """Тест 2: total_files и total_size_bytes корректны."""
        source_dir = str(tmp_path / "source")
        dest_dir = str(tmp_path / "dest")
        os.makedirs(source_dir)

        scan_result = _make_scan_result(tmp_path / "source", [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 1000)],
                "assoc": [("FilmA.srt", 200)],
            },
            {
                "name": "Film B",
                "year": 2021,
                "videos": [("FilmB.mkv", 3000)],
                "assoc": [("FilmB.nfo", 100)],
            },
        ])

        plan = build_plan(scan_result, dest_dir, OperationMode.COPY)

        assert plan.total_files == 4
        assert plan.total_size_bytes == 1000 + 200 + 3000 + 100


# =========================================================================
# Тесты format_preview
# =========================================================================

class TestFormatPreview:

    def _build_preview_plan(self, mode=OperationMode.MOVE, skipped=None, no_year=False):
        """Строит план напрямую (без реальных файлов) для тестирования preview."""
        source_dir = "/media/movies"
        dest_dir = "/media/movies_organized"

        if no_year:
            parsed = ParsedName(
                title="some_movie", year=None,
                clean_folder_name="some_movie", raw_name="some_movie",
            )
            groups = [PlannedGroup(
                folder_name="some_movie",
                folder_path=os.path.join(dest_dir, "some_movie"),
                operations=[PlannedOperation(
                    source_path="/media/movies/some_movie.mkv",
                    destination_path=os.path.join(dest_dir, "some_movie", "some_movie.mkv"),
                    is_video=True,
                    file_size_bytes=1000,
                )],
                parsed_name=parsed,
            )]
            total_files = 1
            total_size = 1000
        else:
            parsed = ParsedName(
                title="Interstellar", year=2014,
                clean_folder_name="Interstellar (2014)", raw_name="Interstellar",
            )
            groups = [PlannedGroup(
                folder_name="Interstellar (2014)",
                folder_path=os.path.join(dest_dir, "Interstellar (2014)"),
                operations=[
                    PlannedOperation(
                        source_path="/media/movies/Interstellar.2014.1080p.mkv",
                        destination_path=os.path.join(dest_dir, "Interstellar (2014)", "Interstellar.2014.1080p.mkv"),
                        is_video=True,
                        file_size_bytes=4_200_000_000,
                    ),
                    PlannedOperation(
                        source_path="/media/movies/Interstellar.2014.1080p.srt",
                        destination_path=os.path.join(dest_dir, "Interstellar (2014)", "Interstellar.2014.1080p.srt"),
                        is_video=False,
                        file_size_bytes=85_000,
                    ),
                ],
                parsed_name=parsed,
            )]
            total_files = 2
            total_size = 4_200_000_000 + 85_000

        skipped_list = []
        if skipped:
            for sd in skipped:
                skipped_list.append(MovieFile(
                    filename=sd["name"], full_path=f"/media/movies/{sd['name']}",
                    size_bytes=sd["size"], extension=os.path.splitext(sd["name"])[1],
                ))

        return OperationPlan(
            mode=mode,
            source_dir=source_dir,
            destination_dir=dest_dir,
            groups=groups,
            skipped_files=skipped_list,
            total_files=total_files,
            total_size_bytes=total_size,
        )

    def test_contains_movie_names_and_sizes(self):
        """Тест 3: format_preview содержит имена фильмов, размеры, строку 'Итого'."""
        plan = self._build_preview_plan()
        preview = format_preview(plan)

        assert "Interstellar (2014)" in preview
        assert "Interstellar.2014.1080p.mkv" in preview
        assert "Итого" in preview
        assert "Фильмов: 1" in preview

    def test_mode_move_label(self):
        """Тест 4a: mode=MOVE -> 'Перемещение'."""
        plan = self._build_preview_plan(mode=OperationMode.MOVE)
        preview = format_preview(plan)
        assert "Перемещение" in preview

    def test_mode_copy_label(self):
        """Тест 4b: mode=COPY -> 'Копирование'."""
        plan = self._build_preview_plan(mode=OperationMode.COPY)
        preview = format_preview(plan)
        assert "Копирование" in preview

    def test_skipped_files_section(self):
        """Тест 5: skipped_files отображены в секции 'Пропущено'."""
        plan = self._build_preview_plan(
            skipped=[{"name": "sample_video.avi", "size": 45_000_000}],
        )
        preview = format_preview(plan)

        assert "Пропущено" in preview
        assert "sample_video.avi" in preview
        assert "Пропущено: 1" in preview

    def test_warnings_no_year(self):
        """Тест 6: фильм без года -> секция 'Предупреждения'."""
        plan = self._build_preview_plan(no_year=True)
        preview = format_preview(plan)

        assert "Предупреждения" in preview
        assert "some_movie.mkv" in preview


# =========================================================================
# Тест 7: _format_size
# =========================================================================

class TestFormatSize:

    def test_bytes(self):
        assert _format_size(500) == "500 B"

    def test_kilobytes(self):
        assert _format_size(2048) == "2 KB"

    def test_megabytes(self):
        assert _format_size(1_500_000) == "1.4 MB"

    def test_gigabytes(self):
        assert _format_size(2_500_000_000) == "2.3 GB"

    def test_zero_bytes(self):
        assert _format_size(0) == "0 B"


# =========================================================================
# Тесты execute_plan
# =========================================================================

class TestExecutePlanMove:

    def test_move_files_transferred(self, tmp_path):
        """Тест 8: execute_plan (MOVE) - файлы перемещены, source пуст."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)
        result = execute_plan(plan, journal_path)

        assert result.success_count == 1
        assert result.error_count == 0
        assert not result.was_cancelled

        # Файл перемещён
        moved_path = dest_dir / "Film A (2020)" / "FilmA.mkv"
        assert moved_path.exists()

        # Source пуст
        assert not (source_dir / "FilmA.mkv").exists()


class TestExecutePlanCopy:

    def test_copy_files_preserved(self, tmp_path):
        """Тест 9: execute_plan (COPY) - файлы скопированы, source не тронут."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film B",
                "year": 2021,
                "videos": [("FilmB.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.COPY)
        result = execute_plan(plan, journal_path)

        assert result.success_count == 1
        assert result.error_count == 0

        # Файл скопирован
        copied_path = dest_dir / "Film B (2021)" / "FilmB.mkv"
        assert copied_path.exists()

        # Source НЕ тронут
        assert (source_dir / "FilmB.mkv").exists()


class TestExecutePlanCancel:

    def test_cancel_partial_result(self, tmp_path):
        """Тест 10: execute_plan с cancel - was_cancelled=True, partial result."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
            {
                "name": "Film B",
                "year": 2021,
                "videos": [("FilmB.mkv", 200)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        call_count = [0]

        def cancel_on_second(current, total, filename):
            call_count[0] += 1
            if call_count[0] >= 2:
                return False  # Cancel
            return True

        result = execute_plan(plan, journal_path, progress_callback=cancel_on_second)

        assert result.was_cancelled is True
        # Первый файл обработан, второй отменён
        assert result.success_count == 1


class TestExecuteFolderConflicts:

    def test_folder_conflict_skip(self, tmp_path):
        """Тест 11: execute_plan конфликт папки SKIP - группа пропущена."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        # Создаём папку-конфликт
        conflict_folder = dest_dir / "Film A (2020)"
        conflict_folder.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        result = execute_plan(
            plan, journal_path,
            folder_conflict_callback=lambda name: ConflictResolution.SKIP,
        )

        assert result.skipped_count == 1
        assert result.success_count == 0

    def test_folder_conflict_merge(self, tmp_path):
        """Тест 12: execute_plan конфликт папки MERGE - файлы добавлены."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        # Папка уже существует с файлом
        existing_folder = dest_dir / "Film A (2020)"
        existing_folder.mkdir()
        _create_file(existing_folder, "existing.txt", 50)

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        result = execute_plan(
            plan, journal_path,
            folder_conflict_callback=lambda name: ConflictResolution.MERGE,
        )

        assert result.success_count == 1
        # Оба файла на месте
        assert (existing_folder / "existing.txt").exists()
        assert (existing_folder / "FilmA.mkv").exists()

    def test_folder_conflict_rename(self, tmp_path):
        """Тест 13: execute_plan конфликт папки RENAME - папка переименована _2."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        # Папка уже существует
        existing_folder = dest_dir / "Film A (2020)"
        existing_folder.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        result = execute_plan(
            plan, journal_path,
            folder_conflict_callback=lambda name: ConflictResolution.RENAME,
        )

        assert result.success_count == 1
        renamed_folder = dest_dir / "Film A (2020)_2"
        assert renamed_folder.exists()
        assert (renamed_folder / "FilmA.mkv").exists()


class TestExecuteFileConflicts:

    def test_file_conflict_skip(self, tmp_path):
        """Тест 14: execute_plan конфликт файла SKIP - файл пропущен."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        # Файл-конфликт в целевой папке
        target_folder = dest_dir / "Film A (2020)"
        target_folder.mkdir()
        _create_file(target_folder, "FilmA.mkv", 50)  # Уже есть файл

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        result = execute_plan(
            plan, journal_path,
            file_conflict_callback=lambda name: FileConflictResolution.SKIP,
        )

        assert result.skipped_count == 1
        assert result.success_count == 0

    def test_file_conflict_overwrite(self, tmp_path):
        """Тест 15: execute_plan конфликт файла OVERWRITE - файл перезаписан."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        # Файл-конфликт (маленький) в целевой папке
        target_folder = dest_dir / "Film A (2020)"
        target_folder.mkdir()
        _create_file(target_folder, "FilmA.mkv", 50)

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        result = execute_plan(
            plan, journal_path,
            file_conflict_callback=lambda name: FileConflictResolution.OVERWRITE,
        )

        assert result.success_count == 1
        # Файл перезаписан: новый размер
        overwritten = target_folder / "FilmA.mkv"
        assert overwritten.exists()
        assert overwritten.stat().st_size == 100


# =========================================================================
# Тесты validate_paths
# =========================================================================

class TestValidatePaths:

    def test_same_paths_error(self, tmp_path):
        """Тест 16: source == destination -> ошибка."""
        path = str(tmp_path / "folder")
        os.makedirs(path)
        result = validate_paths(path, path)
        assert result is not None
        assert "совпадают" in result

    def test_valid_paths_none(self, tmp_path):
        """Тест 17: оба валидны -> None."""
        source = str(tmp_path / "source")
        dest = str(tmp_path / "dest")
        os.makedirs(source)
        result = validate_paths(source, dest)
        assert result is None

    def test_destination_inside_source_error(self, tmp_path):
        """Тест 18: destination внутри source -> ошибка."""
        source = str(tmp_path / "source")
        dest = str(tmp_path / "source" / "sub")
        os.makedirs(source)
        result = validate_paths(source, dest)
        assert result is not None
        assert "внутри" in result

    def test_empty_source_error(self):
        """Source пустой -> ошибка."""
        result = validate_paths("", "/dest")
        assert result is not None

    def test_empty_destination_error(self, tmp_path):
        """Destination пустой -> ошибка."""
        source = str(tmp_path / "source")
        os.makedirs(source)
        result = validate_paths(source, "")
        assert result is not None

    def test_nonexistent_source_error(self, tmp_path):
        """Source не существует -> ошибка."""
        result = validate_paths(str(tmp_path / "nonexistent"), str(tmp_path / "dest"))
        assert result is not None
        assert "не существует" in result


# =========================================================================
# Тест 19: check_disk_space
# =========================================================================

class TestCheckDiskSpace:

    def test_returns_bool(self, tmp_path):
        """Тест 19: check_disk_space возвращает bool."""
        result = check_disk_space(str(tmp_path), 1024)
        assert isinstance(result, bool)

    def test_large_requirement_false(self, tmp_path):
        """Требуется невозможно большой объём -> False."""
        # 100 экзабайт - точно не хватит
        result = check_disk_space(str(tmp_path), 100 * 1024**6)
        assert result is False


# =========================================================================
# Тест 20: is_network_path
# =========================================================================

class TestIsNetworkPath:

    def test_smb_path(self):
        assert is_network_path("smb://server/share") is True

    def test_nfs_path(self):
        assert is_network_path("nfs://server/path") is True

    def test_ftp_path(self):
        assert is_network_path("ftp://server/file") is True

    def test_sftp_path(self):
        assert is_network_path("sftp://server/file") is True

    def test_upnp_path(self):
        assert is_network_path("upnp://server/media") is True

    def test_local_path(self):
        assert is_network_path("/local/path") is False

    def test_windows_path(self):
        assert is_network_path("C:\\Users\\Movies") is False

    def test_case_insensitive(self):
        assert is_network_path("SMB://Server/Share") is True


# =========================================================================
# Тест 21: Undo-журнал создан после execute_plan
# =========================================================================

class TestUndoJournalCreated:

    def test_journal_file_exists(self, tmp_path):
        """Тест 21: Undo-журнал создан после execute_plan."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)
        execute_plan(plan, journal_path)

        assert os.path.exists(journal_path)

        # Проверяем содержимое журнала
        with open(journal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["operation_mode"] == "move"
        assert data["completed"] is True
        assert len(data["entries"]) == 1
        assert data["entries"][0]["success"] is True

    def test_journal_on_cancel_not_completed(self, tmp_path):
        """Журнал создан при отмене, completed=False."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        # Отменяем сразу
        result = execute_plan(
            plan, journal_path,
            progress_callback=lambda c, t, f: False,
        )

        assert result.was_cancelled is True
        assert os.path.exists(journal_path)

        with open(journal_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["completed"] is False


# =========================================================================
# Дополнительные тесты для полноты покрытия
# =========================================================================

class TestFindUniqueName:

    def test_unique_name_no_conflict(self, tmp_path):
        """Путь не существует -> возвращает _2 вариант."""
        path = str(tmp_path / "folder")
        os.makedirs(path)
        result = _find_unique_name(path)
        assert result.endswith("_2")

    def test_unique_name_with_existing_2(self, tmp_path):
        """_2 уже занят -> возвращает _3."""
        path = str(tmp_path / "folder")
        os.makedirs(path)
        os.makedirs(path + "_2")
        result = _find_unique_name(path)
        assert result.endswith("_3")


class TestFindUniqueFilename:

    def test_unique_filename(self, tmp_path):
        """Файл существует -> возвращает _2 вариант."""
        filepath = str(tmp_path / "file.mkv")
        _create_file(tmp_path, "file.mkv", 10)
        result = _find_unique_filename(filepath)
        assert result == str(tmp_path / "file_2.mkv")

    def test_unique_filename_chain(self, tmp_path):
        """_2 уже занят -> возвращает _3."""
        _create_file(tmp_path, "file.mkv", 10)
        _create_file(tmp_path, "file_2.mkv", 10)
        result = _find_unique_filename(str(tmp_path / "file.mkv"))
        assert result == str(tmp_path / "file_3.mkv")


class TestExecutePlanMultipleFilesInGroup:

    def test_group_with_video_and_subtitles(self, tmp_path):
        """Группа с видео + субтитрами -> все файлы перенесены."""
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        journal_path = str(tmp_path / "journal.json")
        source_dir.mkdir()
        dest_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Interstellar",
                "year": 2014,
                "videos": [("Interstellar.2014.1080p.mkv", 4000)],
                "assoc": [
                    ("Interstellar.2014.1080p.srt", 85),
                    ("Interstellar.2014.1080p.nfo", 2),
                ],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.COPY)
        result = execute_plan(plan, journal_path)

        assert result.success_count == 3
        assert result.error_count == 0

        target = dest_dir / "Interstellar (2014)"
        assert (target / "Interstellar.2014.1080p.mkv").exists()
        assert (target / "Interstellar.2014.1080p.srt").exists()
        assert (target / "Interstellar.2014.1080p.nfo").exists()


# =========================================================================
# Тесты _add_year_to_filename (BL-10)
# =========================================================================

class TestAddYearToFilename:

    def test_year_added_before_extension(self):
        result = _add_year_to_filename("Movie.720p.mkv", 2025)
        assert result == "Movie.720p (2025).mkv"

    def test_year_already_in_name(self):
        result = _add_year_to_filename("Movie.2024.720p.mkv", 2024)
        assert result == "Movie.2024.720p.mkv"

    def test_no_extension(self):
        result = _add_year_to_filename("Movie", 2025)
        assert result == "Movie (2025)"

    def test_subtitle_file(self):
        result = _add_year_to_filename("Movie.720p.srt", 2025)
        assert result == "Movie.720p (2025).srt"

    def test_multipart_cd1(self):
        result = _add_year_to_filename("Movie.720p.CD1.mkv", 2025)
        assert result == "Movie.720p.CD1 (2025).mkv"

    def test_multipart_cd2(self):
        result = _add_year_to_filename("Movie.720p.CD2.mkv", 2025)
        assert result == "Movie.720p.CD2 (2025).mkv"


# =========================================================================
# Тесты build_plan с rename_files (BL-10)
# =========================================================================

class TestBuildPlanRenameFiles:

    def test_rename_files_true_adds_year(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.720p.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(
            scan_result, str(dest_dir), OperationMode.MOVE, rename_files=True,
        )

        dest_filename = os.path.basename(plan.groups[0].operations[0].destination_path)
        assert dest_filename == "FilmA.720p (2020).mkv"

    def test_rename_files_false_keeps_original(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.720p.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(
            scan_result, str(dest_dir), OperationMode.MOVE, rename_files=False,
        )

        dest_filename = os.path.basename(plan.groups[0].operations[0].destination_path)
        assert dest_filename == "FilmA.720p.mkv"

    def test_rename_files_true_no_year_keeps_original(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Unknown Movie",
                "year": None,
                "videos": [("unknown_movie.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(
            scan_result, str(dest_dir), OperationMode.MOVE, rename_files=True,
        )

        dest_filename = os.path.basename(plan.groups[0].operations[0].destination_path)
        assert dest_filename == "unknown_movie.mkv"

    def test_rename_files_associated_gets_year(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.720p.mkv", 100)],
                "assoc": [("FilmA.720p.srt", 50)],
            },
        ])

        plan = build_plan(
            scan_result, str(dest_dir), OperationMode.MOVE, rename_files=True,
        )

        ops = plan.groups[0].operations
        video_dest = os.path.basename(ops[0].destination_path)
        srt_dest = os.path.basename(ops[1].destination_path)
        assert video_dest == "FilmA.720p (2020).mkv"
        assert srt_dest == "FilmA.720p (2020).srt"

    def test_rename_files_year_already_in_filename(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.2020.720p.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(
            scan_result, str(dest_dir), OperationMode.MOVE, rename_files=True,
        )

        dest_filename = os.path.basename(plan.groups[0].operations[0].destination_path)
        assert dest_filename == "FilmA.2020.720p.mkv"

    def test_rename_files_default_is_false(self, tmp_path):
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()

        scan_result = _make_scan_result(source_dir, [
            {
                "name": "Film A",
                "year": 2020,
                "videos": [("FilmA.720p.mkv", 100)],
                "assoc": [],
            },
        ])

        plan = build_plan(scan_result, str(dest_dir), OperationMode.MOVE)

        dest_filename = os.path.basename(plan.groups[0].operations[0].destination_path)
        assert dest_filename == "FilmA.720p.mkv"
