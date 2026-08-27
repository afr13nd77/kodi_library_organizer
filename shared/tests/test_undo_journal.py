"""Тесты для shared.undo_journal.

Все файловые операции через tmp_path fixture pytest.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from shared.undo_journal import (
    UndoEntry,
    UndoJournal,
    execute_undo,
    get_latest_journal,
    load_journal,
    save_journal,
)


def _make_journal(
    timestamp: str = "2026-08-27T14:30:00",
    source_dir: str = "/media/movies/",
    destination_dir: str = "/media/movies_organized/",
    operation_mode: str = "move",
    entries: list = None,
    folders_created: list = None,
    completed: bool = True,
    undone: bool = False,
) -> UndoJournal:
    """Создаёт UndoJournal с разумными дефолтами для тестов."""
    return UndoJournal(
        timestamp=timestamp,
        source_dir=source_dir,
        destination_dir=destination_dir,
        operation_mode=operation_mode,
        entries=entries or [],
        folders_created=folders_created or [],
        completed=completed,
        undone=undone,
    )


def _make_entry(
    source_path: str = "/src/movie.mkv",
    destination_path: str = "/dst/Movie (2020)/movie.mkv",
    operation: str = "move",
    file_size_bytes: int = 4509715660,
    success: bool = True,
) -> UndoEntry:
    """Создаёт UndoEntry с разумными дефолтами."""
    return _make_entry_raw(source_path, destination_path, operation, file_size_bytes, success)


def _make_entry_raw(
    source_path: str,
    destination_path: str,
    operation: str,
    file_size_bytes: int,
    success: bool,
) -> UndoEntry:
    return UndoEntry(
        source_path=source_path,
        destination_path=destination_path,
        operation=operation,
        file_size_bytes=file_size_bytes,
        success=success,
    )


class TestSaveLoadRoundtrip:
    """Тесты save_journal -> load_journal."""

    def test_roundtrip_all_fields_preserved(self, tmp_path: Path) -> None:
        """save_journal -> load_journal: все поля сохранены и восстановлены."""
        entry = _make_entry()
        journal = _make_journal(
            entries=[entry],
            folders_created=["/dst/Movie (2020)"],
        )
        file_path = str(tmp_path / "undo_20260827_143000.json")

        save_journal(journal, file_path)
        loaded = load_journal(file_path)

        assert loaded.timestamp == journal.timestamp
        assert loaded.source_dir == journal.source_dir
        assert loaded.destination_dir == journal.destination_dir
        assert loaded.operation_mode == journal.operation_mode
        assert loaded.completed == journal.completed
        assert loaded.undone == journal.undone
        assert loaded.folders_created == journal.folders_created
        assert len(loaded.entries) == 1

        le = loaded.entries[0]
        assert le.source_path == entry.source_path
        assert le.destination_path == entry.destination_path
        assert le.operation == entry.operation
        assert le.file_size_bytes == entry.file_size_bytes
        assert le.success == entry.success

    def test_saved_json_has_version_1(self, tmp_path: Path) -> None:
        """Сохранённый JSON содержит "version": 1."""
        journal = _make_journal()
        file_path = str(tmp_path / "undo_test.json")

        save_journal(journal, file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["version"] == 1

    def test_roundtrip_empty_entries(self, tmp_path: Path) -> None:
        """Roundtrip с пустым списком entries."""
        journal = _make_journal(entries=[], folders_created=[])
        file_path = str(tmp_path / "undo_empty.json")

        save_journal(journal, file_path)
        loaded = load_journal(file_path)

        assert loaded.entries == []
        assert loaded.folders_created == []

    def test_roundtrip_multiple_entries(self, tmp_path: Path) -> None:
        """Roundtrip с несколькими entries."""
        entries = [
            _make_entry(source_path="/src/a.mkv", destination_path="/dst/a.mkv"),
            _make_entry(source_path="/src/b.mkv", destination_path="/dst/b.mkv", success=False),
        ]
        journal = _make_journal(entries=entries)
        file_path = str(tmp_path / "undo_multi.json")

        save_journal(journal, file_path)
        loaded = load_journal(file_path)

        assert len(loaded.entries) == 2
        assert loaded.entries[0].source_path == "/src/a.mkv"
        assert loaded.entries[1].success is False


class TestLoadJournalErrors:
    """Тесты ошибок load_journal."""

    def test_load_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """load_journal: несуществующий файл -> FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_journal(str(tmp_path / "nonexistent.json"))

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """load_journal: невалидный JSON -> JSONDecodeError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_journal(str(bad_file))

    def test_load_missing_field_raises(self, tmp_path: Path) -> None:
        """load_journal: отсутствует обязательное поле -> KeyError."""
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text(
            json.dumps({"version": 1, "timestamp": "2026-01-01T00:00:00"}),
            encoding="utf-8",
        )
        with pytest.raises(KeyError):
            load_journal(str(incomplete))


class TestGetLatestJournal:
    """Тесты get_latest_journal."""

    def test_returns_latest_not_undone(self, tmp_path: Path) -> None:
        """3 файла: 2 undone=True, 1 undone=False -> возвращает путь к третьему."""
        j1 = _make_journal(timestamp="2026-08-27T14:00:00", undone=True)
        j2 = _make_journal(timestamp="2026-08-27T15:00:00", undone=True)
        j3 = _make_journal(timestamp="2026-08-27T16:00:00", undone=False)

        save_journal(j1, str(tmp_path / "undo_20260827_140000.json"))
        save_journal(j2, str(tmp_path / "undo_20260827_150000.json"))
        save_journal(j3, str(tmp_path / "undo_20260827_160000.json"))

        result = get_latest_journal(str(tmp_path))
        assert result is not None
        assert result == str(tmp_path / "undo_20260827_160000.json")

    def test_all_undone_returns_none(self, tmp_path: Path) -> None:
        """Все журналы undone=True -> None."""
        j1 = _make_journal(undone=True)
        j2 = _make_journal(undone=True)

        save_journal(j1, str(tmp_path / "undo_20260827_140000.json"))
        save_journal(j2, str(tmp_path / "undo_20260827_150000.json"))

        result = get_latest_journal(str(tmp_path))
        assert result is None

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        """Пустая директория -> None."""
        result = get_latest_journal(str(tmp_path))
        assert result is None

    def test_nonexistent_directory_returns_none(self, tmp_path: Path) -> None:
        """Несуществующая директория -> None."""
        result = get_latest_journal(str(tmp_path / "nonexistent"))
        assert result is None

    def test_returns_latest_by_filename(self, tmp_path: Path) -> None:
        """Из нескольких undone=False возвращает последний по имени файла."""
        j1 = _make_journal(undone=False)
        j2 = _make_journal(undone=False)

        save_journal(j1, str(tmp_path / "undo_20260827_100000.json"))
        save_journal(j2, str(tmp_path / "undo_20260827_200000.json"))

        result = get_latest_journal(str(tmp_path))
        assert result is not None
        assert "200000" in result


class TestExecuteUndoMove:
    """Тесты execute_undo для mode=move."""

    def test_move_files_restored_to_source(self, tmp_path: Path) -> None:
        """execute_undo mode=move: файлы перемещены обратно в source."""
        src_dir = tmp_path / "source"
        dst_dir = tmp_path / "destination" / "Movie (2020)"
        dst_dir.mkdir(parents=True)

        dst_file = dst_dir / "movie.mkv"
        dst_file.write_bytes(b"fake movie content")

        src_file_path = str(src_dir / "movie.mkv")
        dst_file_path = str(dst_file)

        entry = _make_entry(
            source_path=src_file_path,
            destination_path=dst_file_path,
            operation="move",
        )
        journal = _make_journal(
            operation_mode="move",
            entries=[entry],
            folders_created=[str(dst_dir)],
        )
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path)

        assert result.success_count == 1
        assert result.error_count == 0
        assert os.path.exists(src_file_path)
        assert not os.path.exists(dst_file_path)

    def test_move_missing_file_error(self, tmp_path: Path) -> None:
        """execute_undo mode=move: файл отсутствует в destination -> error."""
        entry = _make_entry(
            source_path=str(tmp_path / "src" / "movie.mkv"),
            destination_path=str(tmp_path / "dst" / "movie.mkv"),
            operation="move",
        )
        journal = _make_journal(operation_mode="move", entries=[entry])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path)

        assert result.error_count == 1
        assert result.success_count == 0
        assert len(result.errors) == 1

    def test_move_skips_failed_entries(self, tmp_path: Path) -> None:
        """execute_undo: записи с success=False пропускаются."""
        entry_ok = _make_entry(
            source_path=str(tmp_path / "src" / "ok.mkv"),
            destination_path=str(tmp_path / "dst" / "ok.mkv"),
            success=True,
        )
        entry_fail = _make_entry(
            source_path=str(tmp_path / "src" / "fail.mkv"),
            destination_path=str(tmp_path / "dst" / "fail.mkv"),
            success=False,
        )

        dst_dir = tmp_path / "dst"
        dst_dir.mkdir(parents=True)
        (dst_dir / "ok.mkv").write_bytes(b"ok content")

        journal = _make_journal(
            operation_mode="move",
            entries=[entry_ok, entry_fail],
        )
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path)

        assert result.total_count == 1
        assert result.success_count == 1


class TestExecuteUndoCopy:
    """Тесты execute_undo для mode=copy."""

    def test_copy_destination_files_removed(self, tmp_path: Path) -> None:
        """execute_undo mode=copy: файлы в destination удалены, в source не тронуты."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        dst_dir = tmp_path / "destination"
        dst_dir.mkdir()

        src_file = src_dir / "movie.mkv"
        dst_file = dst_dir / "movie.mkv"
        src_file.write_bytes(b"original")
        dst_file.write_bytes(b"copy")

        entry = _make_entry(
            source_path=str(src_file),
            destination_path=str(dst_file),
            operation="copy",
        )
        journal = _make_journal(operation_mode="copy", entries=[entry])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path)

        assert result.success_count == 1
        assert result.error_count == 0
        assert not os.path.exists(str(dst_file))
        assert os.path.exists(str(src_file))
        assert src_file.read_bytes() == b"original"

    def test_copy_missing_file_is_success(self, tmp_path: Path) -> None:
        """execute_undo mode=copy: файл уже удалён -> success, не ошибка."""
        entry = _make_entry(
            source_path=str(tmp_path / "src" / "movie.mkv"),
            destination_path=str(tmp_path / "dst" / "nonexistent.mkv"),
            operation="copy",
        )
        journal = _make_journal(operation_mode="copy", entries=[entry])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path)

        assert result.success_count == 1
        assert result.error_count == 0
        assert len(result.errors) == 0


class TestExecuteUndoFolders:
    """Тесты удаления пустых папок."""

    def test_empty_folders_removed(self, tmp_path: Path) -> None:
        """execute_undo: пустые папки из folders_created удалены после отката."""
        nested = tmp_path / "dst" / "Movie (2020)" / "Subs"
        nested.mkdir(parents=True)

        journal = _make_journal(
            operation_mode="move",
            entries=[],
            folders_created=[
                str(tmp_path / "dst" / "Movie (2020)"),
                str(nested),
            ],
        )
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        execute_undo(journal, journal_path)

        assert not os.path.exists(str(nested))
        assert not os.path.exists(str(tmp_path / "dst" / "Movie (2020)"))

    def test_nonempty_folders_not_removed(self, tmp_path: Path) -> None:
        """execute_undo: непустые папки не удаляются (rmdir на них -> OSError)."""
        folder = tmp_path / "dst" / "Movie (2020)"
        folder.mkdir(parents=True)
        (folder / "leftover.txt").write_text("keep me", encoding="utf-8")

        journal = _make_journal(
            operation_mode="move",
            entries=[],
            folders_created=[str(folder)],
        )
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        execute_undo(journal, journal_path)

        assert os.path.exists(str(folder))


class TestExecuteUndoJournalState:
    """Тесты состояния журнала после отката."""

    def test_journal_marked_undone_after_execute(self, tmp_path: Path) -> None:
        """execute_undo: journal.undone=True после выполнения."""
        journal = _make_journal(operation_mode="move", entries=[])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        execute_undo(journal, journal_path)

        reloaded = load_journal(journal_path)
        assert reloaded.undone is True

    def test_journal_saved_with_undone_true(self, tmp_path: Path) -> None:
        """execute_undo: файл журнала перезаписан с undone=True."""
        entry = _make_entry(
            source_path=str(tmp_path / "src" / "movie.mkv"),
            destination_path=str(tmp_path / "dst" / "movie.mkv"),
        )
        journal = _make_journal(operation_mode="move", entries=[entry])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        execute_undo(journal, journal_path)

        with open(journal_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["undone"] is True


class TestExecuteUndoProgressCallback:
    """Тесты progress_callback."""

    def test_callback_called_with_correct_values(self, tmp_path: Path) -> None:
        """execute_undo: progress_callback вызван с правильными current/total."""
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        (dst_dir / "a.mkv").write_bytes(b"a")
        (dst_dir / "b.mkv").write_bytes(b"b")

        entries = [
            _make_entry(
                source_path=str(tmp_path / "src" / "a.mkv"),
                destination_path=str(dst_dir / "a.mkv"),
            ),
            _make_entry(
                source_path=str(tmp_path / "src" / "b.mkv"),
                destination_path=str(dst_dir / "b.mkv"),
            ),
        ]
        journal = _make_journal(operation_mode="move", entries=entries)
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        calls = []

        def callback(current: int, total: int, path: str) -> bool:
            calls.append((current, total, path))
            return True

        execute_undo(journal, journal_path, progress_callback=callback)

        assert len(calls) == 2
        assert calls[0][0] == 1
        assert calls[0][1] == 2
        assert calls[1][0] == 2
        assert calls[1][1] == 2

    def test_callback_not_required(self, tmp_path: Path) -> None:
        """execute_undo: работает без progress_callback (None)."""
        journal = _make_journal(operation_mode="move", entries=[])
        journal_path = str(tmp_path / "undo_test.json")
        save_journal(journal, journal_path)

        result = execute_undo(journal, journal_path, progress_callback=None)
        assert result.total_count == 0
