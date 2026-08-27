"""Журнал операций для отката (undo) в Kodi Library Organizer.

Сохраняет информацию о перемещениях/копированиях файлов и позволяет
откатить операцию, вернув файлы на исходные позиции.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from typing import Callable, List, Optional

try:
    from logger import Logger
except ImportError:
    from .logger import Logger

_logger = Logger()

ProgressCallback = Callable[[int, int, str], bool]


@dataclass
class UndoEntry:
    """Запись об одной файловой операции."""

    source_path: str
    destination_path: str
    operation: str
    file_size_bytes: int
    success: bool


@dataclass
class UndoJournal:
    """Журнал операций для отката."""

    timestamp: str
    source_dir: str
    destination_dir: str
    operation_mode: str
    entries: List[UndoEntry] = field(default_factory=list)
    folders_created: List[str] = field(default_factory=list)
    completed: bool = False
    undone: bool = False


@dataclass
class UndoResult:
    """Результат операции отката."""

    success_count: int = 0
    error_count: int = 0
    total_count: int = 0
    errors: List[str] = field(default_factory=list)


def save_journal(journal: UndoJournal, file_path: str) -> None:
    """Сохраняет журнал в JSON-файл. Добавляет "version": 1."""
    _logger.info(f"Сохранение журнала в {file_path}")
    try:
        data = asdict(journal)
        data["version"] = 1
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _logger.info(f"Журнал успешно сохранён: {file_path} ({len(journal.entries)} записей)")
    except Exception as e:
        _logger.error(f"Ошибка сохранения журнала {file_path}: {e}")
        raise


def load_journal(file_path: str) -> UndoJournal:
    """Загружает журнал из JSON-файла.

    Raises:
        FileNotFoundError: файл не найден.
        json.JSONDecodeError: невалидный JSON.
        KeyError: отсутствует обязательное поле.
    """
    _logger.info(f"Загрузка журнала из {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = [
            UndoEntry(
                source_path=e["source_path"],
                destination_path=e["destination_path"],
                operation=e["operation"],
                file_size_bytes=e["file_size_bytes"],
                success=e["success"],
            )
            for e in data["entries"]
        ]

        journal = UndoJournal(
            timestamp=data["timestamp"],
            source_dir=data["source_dir"],
            destination_dir=data["destination_dir"],
            operation_mode=data["operation_mode"],
            entries=entries,
            folders_created=data.get("folders_created", []),
            completed=data.get("completed", False),
            undone=data.get("undone", False),
        )
        _logger.info(
            f"Журнал загружен: {file_path} ({len(journal.entries)} записей, "
            f"undone={journal.undone})"
        )
        return journal
    except FileNotFoundError:
        _logger.error(f"Файл журнала не найден: {file_path}")
        raise
    except json.JSONDecodeError as e:
        _logger.error(f"Невалидный JSON в журнале {file_path}: {e}")
        raise
    except KeyError as e:
        _logger.error(f"Отсутствует обязательное поле в журнале {file_path}: {e}")
        raise


def get_latest_journal(journal_dir: str) -> Optional[str]:
    """Находит последний неиспользованный (undone=False) журнал.

    Сортирует по имени файла (timestamp в имени).
    Возвращает полный путь или None.
    """
    _logger.info(f"Поиск последнего журнала в {journal_dir}")
    try:
        if not os.path.isdir(journal_dir):
            _logger.info(f"Директория не существует: {journal_dir}")
            return None

        files = sorted(
            [
                f
                for f in os.listdir(journal_dir)
                if f.startswith("undo_") and f.endswith(".json")
            ]
        )

        if not files:
            _logger.info(f"Журналы не найдены в {journal_dir}")
            return None

        for file_name in reversed(files):
            file_path = os.path.join(journal_dir, file_name)
            try:
                journal = load_journal(file_path)
                if not journal.undone:
                    _logger.info(f"Найден актуальный журнал: {file_path}")
                    return file_path
            except (json.JSONDecodeError, KeyError, FileNotFoundError):
                _logger.warning(f"Не удалось прочитать журнал {file_path}, пропускаем")
                continue

        _logger.info(f"Все журналы в {journal_dir} уже откачены (undone=True)")
        return None
    except Exception as e:
        _logger.error(f"Ошибка поиска журнала в {journal_dir}: {e}")
        return None


def execute_undo(
    journal: UndoJournal,
    journal_path: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> UndoResult:
    """Выполняет откат операций из журнала.

    Для mode=move: перемещает файлы обратно (shutil.move).
    Для mode=copy: удаляет файлы в destination (os.remove).
    Удаляет пустые папки из folders_created (os.rmdir).
    Помечает journal.undone=True и перезаписывает файл.
    """
    _logger.info(
        f"Начало отката: mode={journal.operation_mode}, "
        f"entries={len(journal.entries)}, journal={journal_path}"
    )

    successful_entries = [e for e in journal.entries if e.success]
    result = UndoResult(total_count=len(successful_entries))

    for i, entry in enumerate(reversed(successful_entries), start=1):
        if journal.operation_mode == "move":
            result = _undo_move_entry(entry, result)
        elif journal.operation_mode == "copy":
            result = _undo_copy_entry(entry, result)

        if progress_callback is not None:
            try:
                progress_callback(i, result.total_count, entry.source_path)
            except Exception as e:
                _logger.warning(f"Ошибка в progress_callback: {e}")

    _remove_empty_folders(journal.folders_created)

    journal.undone = True
    try:
        save_journal(journal, journal_path)
    except Exception as e:
        _logger.error(f"Не удалось сохранить журнал после отката: {e}")

    _logger.info(
        f"Откат завершён: success={result.success_count}, "
        f"errors={result.error_count}, total={result.total_count}"
    )
    return result


def _undo_move_entry(entry: UndoEntry, result: UndoResult) -> UndoResult:
    """Откатывает одну операцию move: перемещает файл из destination в source."""
    try:
        src_dir = os.path.dirname(entry.source_path)
        if src_dir:
            os.makedirs(src_dir, exist_ok=True)
        shutil.move(entry.destination_path, entry.source_path)
        result.success_count += 1
        _logger.info(f"Файл перемещён обратно: {entry.destination_path} -> {entry.source_path}")
    except FileNotFoundError:
        msg = f"Файл не найден в destination: {entry.destination_path}"
        _logger.warning(msg)
        result.errors.append(msg)
        result.error_count += 1
    except Exception as e:
        msg = f"Ошибка отката {entry.destination_path}: {e}"
        _logger.error(msg)
        result.errors.append(msg)
        result.error_count += 1
    return result


def _undo_copy_entry(entry: UndoEntry, result: UndoResult) -> UndoResult:
    """Откатывает одну операцию copy: удаляет файл из destination."""
    try:
        os.remove(entry.destination_path)
        result.success_count += 1
        _logger.info(f"Копия удалена: {entry.destination_path}")
    except FileNotFoundError:
        _logger.warning(f"Файл уже удалён: {entry.destination_path}")
        result.success_count += 1
    except Exception as e:
        msg = f"Ошибка удаления {entry.destination_path}: {e}"
        _logger.error(msg)
        result.errors.append(msg)
        result.error_count += 1
    return result


def _remove_empty_folders(folders: List[str]) -> None:
    """Удаляет пустые папки из списка (в обратном порядке)."""
    for folder in reversed(folders):
        try:
            os.rmdir(folder)
            _logger.info(f"Пустая папка удалена: {folder}")
        except OSError:
            _logger.debug(f"Папка не пустая или не существует: {folder}")
