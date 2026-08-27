"""Центральный модуль планирования и выполнения файловых операций.

Строит план перемещения/копирования файлов на основе результатов
сканирования, генерирует превью, выполняет операции с поддержкой
конфликтов, отмены и журналирования.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

from .logger import Logger
from .name_parser import ParsedName
from .scanner import MovieFile, ScanResult
from .undo_journal import UndoEntry, UndoJournal, save_journal

_logger = Logger(debug_enabled=False)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OperationMode(Enum):
    MOVE = "move"
    COPY = "copy"


class ConflictResolution(Enum):
    SKIP = "skip"
    MERGE = "merge"
    RENAME = "rename"


class FileConflictResolution(Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PlannedOperation:
    source_path: str
    destination_path: str
    is_video: bool
    file_size_bytes: int


@dataclass
class PlannedGroup:
    folder_name: str
    folder_path: str
    operations: list[PlannedOperation]
    parsed_name: ParsedName


@dataclass
class OperationPlan:
    mode: OperationMode
    source_dir: str
    destination_dir: str
    groups: list[PlannedGroup]
    skipped_files: list[MovieFile]
    total_files: int
    total_size_bytes: int


@dataclass
class OperationResult:
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    total_count: int = 0
    errors: list[str] = field(default_factory=list)
    was_cancelled: bool = False


# ---------------------------------------------------------------------------
# Callback types
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int, str], bool]
FolderConflictCallback = Callable[[str], ConflictResolution]
FileConflictCallback = Callable[[str], FileConflictResolution]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Форматирует размер файла в человекочитаемый вид."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        kb = size_bytes / 1024
        return f"{kb:.0f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB"
    gb = size_bytes / (1024 * 1024 * 1024)
    return f"{gb:.1f} GB"


def _find_unique_name(path: str) -> str:
    """Находит уникальное имя папки, добавляя _2, _3, ... к пути."""
    counter = 2
    while True:
        candidate = f"{path}_{counter}"
        if not os.path.exists(candidate):
            _logger.debug(f"Уникальное имя папки: {candidate}")
            return candidate
        counter += 1


def _find_unique_filename(path: str) -> str:
    """Находит уникальное имя файла, добавляя _2, _3, ... перед расширением."""
    base, ext = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not os.path.exists(candidate):
            _logger.debug(f"Уникальное имя файла: {candidate}")
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_plan(
    scan_result: ScanResult,
    destination_dir: str,
    mode: OperationMode,
) -> OperationPlan:
    """Строит план операций на основе результатов сканирования.

    Args:
        scan_result: Результат scan_directory().
        destination_dir: Путь к целевой директории.
        mode: Режим операции (MOVE/COPY).

    Returns:
        OperationPlan с группами плановых операций.
    """
    _logger.info(
        f"Построение плана: mode={mode.value}, destination={destination_dir}, "
        f"groups={len(scan_result.groups)}"
    )

    planned_groups: List[PlannedGroup] = []
    total_files = 0
    total_size = 0

    for group in scan_result.groups:
        folder_name = group.parsed_name.clean_folder_name
        folder_path = os.path.join(destination_dir, folder_name)

        operations: List[PlannedOperation] = []

        # Видеофайлы
        for vf in group.video_files:
            dest_path = os.path.join(folder_path, vf.filename)
            operations.append(PlannedOperation(
                source_path=vf.full_path,
                destination_path=dest_path,
                is_video=True,
                file_size_bytes=vf.size_bytes,
            ))

        # Ассоциированные файлы
        for af in group.associated_files:
            dest_path = os.path.join(folder_path, af.filename)
            operations.append(PlannedOperation(
                source_path=af.full_path,
                destination_path=dest_path,
                is_video=False,
                file_size_bytes=af.size_bytes,
            ))

        planned_groups.append(PlannedGroup(
            folder_name=folder_name,
            folder_path=folder_path,
            operations=operations,
            parsed_name=group.parsed_name,
        ))

        total_files += len(operations)
        total_size += sum(op.file_size_bytes for op in operations)

    plan = OperationPlan(
        mode=mode,
        source_dir=scan_result.groups[0].video_files[0].full_path.rsplit(os.sep, 1)[0]
        if scan_result.groups else "",
        destination_dir=destination_dir,
        groups=planned_groups,
        skipped_files=scan_result.skipped_files,
        total_files=total_files,
        total_size_bytes=total_size,
    )

    _logger.info(
        f"План построен: {len(planned_groups)} групп, "
        f"{total_files} файлов, {_format_size(total_size)}"
    )
    return plan


def format_preview(plan: OperationPlan) -> str:
    """Формирует текстовое превью плана для отображения в Kodi.

    Args:
        plan: План операций.

    Returns:
        Многострочная строка для Dialog.textviewer().
    """
    _logger.info("Формирование превью плана")

    mode_label = "Перемещение" if plan.mode == OperationMode.MOVE else "Копирование"

    lines: List[str] = [
        "--- Превью операций ---",
        f"Режим: {mode_label}",
        f"Источник: {plan.source_dir}",
        f"Назначение: {plan.destination_dir}",
        "",
    ]

    warnings: List[str] = []

    for idx, group in enumerate(plan.groups, start=1):
        lines.append(f"[{idx}] {group.folder_name}")

        # Проверяем год для предупреждений
        if group.parsed_name.year is None:
            # Находим имя видеофайла для предупреждения
            video_name = ""
            for op in group.operations:
                if op.is_video:
                    video_name = os.path.basename(op.source_path)
                    break
            if video_name:
                warnings.append(f"[?] {video_name} -- год не распознан")

        # Видеофайлы идут первыми
        for op in group.operations:
            fname = os.path.basename(op.destination_path)
            size_str = _format_size(op.file_size_bytes)
            if op.is_video:
                lines.append(f"    {fname} ({size_str})")
            else:
                lines.append(f"    + {fname} ({size_str})")

        lines.append("")

    # Секция пропущенных файлов
    if plan.skipped_files:
        lines.append("--- Пропущено ---")
        for sf in plan.skipped_files:
            size_str = _format_size(sf.size_bytes)
            lines.append(f"[!] {sf.filename} ({size_str})")
        lines.append("")

    # Секция предупреждений
    if warnings:
        lines.append("--- Предупреждения ---")
        for w in warnings:
            lines.append(w)
        lines.append("")

    # Итого
    lines.append("--- Итого ---")
    lines.append(f"Фильмов: {len(plan.groups)}")
    lines.append(f"Файлов: {plan.total_files}")
    lines.append(f"Объём: {_format_size(plan.total_size_bytes)}")
    lines.append(f"Пропущено: {len(plan.skipped_files)}")

    preview = "\n".join(lines)
    _logger.info(f"Превью сформировано: {len(lines)} строк")
    return preview


def execute_plan(
    plan: OperationPlan,
    undo_journal_path: str,
    progress_callback: Optional[ProgressCallback] = None,
    folder_conflict_callback: Optional[FolderConflictCallback] = None,
    file_conflict_callback: Optional[FileConflictCallback] = None,
) -> OperationResult:
    """Выполняет план файловых операций.

    Args:
        plan: План операций из build_plan().
        undo_journal_path: Путь для сохранения журнала отмены.
        progress_callback: (current, total, filename) -> continue?
        folder_conflict_callback: (folder_name) -> ConflictResolution.
        file_conflict_callback: (filename) -> FileConflictResolution.

    Returns:
        OperationResult с результатами выполнения.
    """
    _logger.info(
        f"Начало выполнения плана: mode={plan.mode.value}, "
        f"groups={len(plan.groups)}, total_files={plan.total_files}"
    )

    journal = UndoJournal(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        source_dir=plan.source_dir,
        destination_dir=plan.destination_dir,
        operation_mode=plan.mode.value,
    )

    result = OperationResult(total_count=plan.total_files)
    current_file = 0

    for group in plan.groups:
        folder_path = group.folder_path

        # --- Проверка/создание папки ---
        if os.path.exists(folder_path):
            if folder_conflict_callback is not None:
                resolution = folder_conflict_callback(group.folder_name)
            else:
                resolution = ConflictResolution.MERGE

            if resolution == ConflictResolution.SKIP:
                result.skipped_count += len(group.operations)
                current_file += len(group.operations)
                _logger.info(
                    f"Группа пропущена (конфликт папки SKIP): {group.folder_name}"
                )
                continue

            if resolution == ConflictResolution.RENAME:
                folder_path = _find_unique_name(folder_path)
                _logger.info(
                    f"Папка переименована (конфликт): "
                    f"{group.folder_name} -> {os.path.basename(folder_path)}"
                )

            # MERGE: продолжаем с тем же folder_path

        try:
            os.makedirs(folder_path, exist_ok=True)
            if folder_path not in journal.folders_created:
                journal.folders_created.append(folder_path)
            _logger.debug(f"Папка создана/существует: {folder_path}")
        except OSError as exc:
            _logger.error(f"Ошибка создания папки {folder_path}: {exc}")
            for _op in group.operations:
                result.error_count += 1
                result.errors.append(f"Ошибка создания папки {folder_path}: {exc}")
                current_file += 1
            continue

        # --- Обработка файлов ---
        for op in group.operations:
            current_file += 1
            filename = os.path.basename(op.source_path)

            # Progress callback
            if progress_callback is not None:
                try:
                    should_continue = progress_callback(
                        current_file, plan.total_files, filename
                    )
                except Exception as exc:
                    _logger.warning(f"Ошибка в progress_callback: {exc}")
                    should_continue = True

                if not should_continue:
                    journal.completed = False
                    save_journal(journal, undo_journal_path)
                    result.was_cancelled = True
                    _logger.info(
                        f"Выполнение отменено пользователем на файле {current_file}/{plan.total_files}"
                    )
                    return result

            # Вычисляем фактический destination_path (может измениться при RENAME папки)
            actual_dest = os.path.join(folder_path, filename)

            # Проверка конфликта файла
            if os.path.exists(actual_dest):
                if file_conflict_callback is not None:
                    file_resolution = file_conflict_callback(filename)
                else:
                    file_resolution = FileConflictResolution.SKIP

                if file_resolution == FileConflictResolution.SKIP:
                    result.skipped_count += 1
                    _logger.info(f"Файл пропущен (конфликт SKIP): {filename}")
                    continue

                if file_resolution == FileConflictResolution.OVERWRITE:
                    try:
                        os.remove(actual_dest)
                        _logger.info(f"Файл удалён для перезаписи: {actual_dest}")
                    except OSError as exc:
                        msg = f"Ошибка удаления файла {actual_dest}: {exc}"
                        _logger.error(msg)
                        result.error_count += 1
                        result.errors.append(msg)
                        journal.entries.append(UndoEntry(
                            source_path=op.source_path,
                            destination_path=actual_dest,
                            operation=plan.mode.value,
                            file_size_bytes=op.file_size_bytes,
                            success=False,
                        ))
                        continue

                if file_resolution == FileConflictResolution.RENAME:
                    actual_dest = _find_unique_filename(actual_dest)
                    _logger.info(f"Файл переименован (конфликт): {filename} -> {os.path.basename(actual_dest)}")

            # Выполнение операции
            try:
                if plan.mode == OperationMode.MOVE:
                    shutil.move(op.source_path, actual_dest)
                    _logger.info(f"Файл перемещён: {op.source_path} -> {actual_dest}")
                elif plan.mode == OperationMode.COPY:
                    shutil.copy2(op.source_path, actual_dest)
                    # Проверка размера копии
                    actual_size = os.path.getsize(actual_dest)
                    if actual_size != op.file_size_bytes:
                        os.remove(actual_dest)
                        raise IOError(
                            f"Incomplete copy: expected {op.file_size_bytes} bytes, "
                            f"got {actual_size} bytes"
                        )
                    _logger.info(f"Файл скопирован: {op.source_path} -> {actual_dest}")

                journal.entries.append(UndoEntry(
                    source_path=op.source_path,
                    destination_path=actual_dest,
                    operation=plan.mode.value,
                    file_size_bytes=op.file_size_bytes,
                    success=True,
                ))
                result.success_count += 1

            except Exception as exc:
                msg = f"Ошибка операции {plan.mode.value} для {filename}: {exc}"
                _logger.error(msg)
                journal.entries.append(UndoEntry(
                    source_path=op.source_path,
                    destination_path=actual_dest,
                    operation=plan.mode.value,
                    file_size_bytes=op.file_size_bytes,
                    success=False,
                ))
                result.errors.append(str(exc))
                result.error_count += 1

    journal.completed = True
    save_journal(journal, undo_journal_path)

    _logger.info(
        f"Выполнение завершено: success={result.success_count}, "
        f"errors={result.error_count}, skipped={result.skipped_count}, "
        f"total={result.total_count}"
    )
    return result


def check_disk_space(destination_dir: str, required_bytes: int) -> bool:
    """Проверяет достаточность свободного места на диске.

    Args:
        destination_dir: Путь к целевой директории.
        required_bytes: Требуемое место в байтах.

    Returns:
        True если места достаточно (или невозможно проверить).
    """
    _logger.info(
        f"Проверка свободного места: destination={destination_dir}, "
        f"required={_format_size(required_bytes)}"
    )
    try:
        usage = shutil.disk_usage(destination_dir)
        margin = max(required_bytes * 0.05, 100 * 1024 * 1024)  # 5% или 100MB
        enough = usage.free >= required_bytes + margin
        _logger.info(
            f"Свободно: {_format_size(usage.free)}, "
            f"требуется: {_format_size(required_bytes)} + margin {_format_size(int(margin))}, "
            f"достаточно: {enough}"
        )
        return enough
    except OSError as exc:
        _logger.warning(
            f"Не удалось проверить свободное место для {destination_dir}: {exc}. "
            f"Разрешаем операцию (возможно сетевой путь)."
        )
        return True


def validate_paths(source_dir: str, destination_dir: str) -> Optional[str]:
    """Валидирует исходную и целевую директории.

    Args:
        source_dir: Путь к исходной директории.
        destination_dir: Путь к целевой директории.

    Returns:
        Текст ошибки или None, если всё OK.
    """
    _logger.info(f"Валидация путей: source={source_dir}, destination={destination_dir}")

    if not source_dir or not source_dir.strip():
        msg = "Не указан путь источника"
        _logger.error(msg)
        return msg

    if not destination_dir or not destination_dir.strip():
        msg = "Не указан путь назначения"
        _logger.error(msg)
        return msg

    norm_source = os.path.normpath(os.path.abspath(source_dir))
    norm_dest = os.path.normpath(os.path.abspath(destination_dir))

    if norm_source == norm_dest:
        msg = "Путь источника и назначения совпадают"
        _logger.error(msg)
        return msg

    # Проверка: destination внутри source
    # Добавляем sep чтобы /media/movies не матчил /media/movies2
    if norm_dest.startswith(norm_source + os.sep):
        msg = "Путь назначения находится внутри источника"
        _logger.error(msg)
        return msg

    if not os.path.exists(norm_source):
        msg = f"Путь источника не существует: {source_dir}"
        _logger.error(msg)
        return msg

    _logger.info("Валидация путей пройдена успешно")
    return None


def is_network_path(path: str) -> bool:
    """Проверяет, является ли путь сетевым.

    Args:
        path: Проверяемый путь.

    Returns:
        True если путь начинается с сетевого префикса.
    """
    network_prefixes = ("smb://", "nfs://", "ftp://", "sftp://", "upnp://")
    result = path.lower().startswith(network_prefixes)
    _logger.debug(f"Проверка сетевого пути: {path} -> {result}")
    return result
