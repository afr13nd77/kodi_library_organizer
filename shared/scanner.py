"""Модуль сканирования директории и группировки файлов.

Сканирует указанную директорию, классифицирует файлы по расширению,
группирует видеофайлы с ассоциированными файлами (субтитры, NFO, артворк),
поддерживает multi-part группировку.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from file_patterns import ASSOCIATED_EXTENSIONS, MULTIPART_PATTERN, VIDEO_EXTENSIONS
    from logger import Logger
    from name_parser import ParsedName, parse_name
except ImportError:
    from .file_patterns import ASSOCIATED_EXTENSIONS, MULTIPART_PATTERN, VIDEO_EXTENSIONS
    from .logger import Logger
    from .name_parser import ParsedName, parse_name

_logger = Logger(debug_enabled=False)


@dataclass
class MovieFile:
    """Представление одного файла."""

    filename: str       # Имя файла ("Interstellar.2014.1080p.mkv")
    full_path: str      # Абсолютный путь
    size_bytes: int     # Размер файла
    extension: str      # Расширение с точкой (".mkv")


@dataclass
class MovieGroup:
    """Группа: видеофайл(ы) + ассоциированные файлы."""

    video_files: list[MovieFile]          # 1 для обычного, 2+ для multi-part
    associated_files: list[MovieFile]     # Субтитры, NFO, артворк
    parsed_name: ParsedName              # Из name_parser
    base_name: str                        # Базовое имя для группировки


@dataclass
class ScanResult:
    """Результат сканирования директории."""

    groups: list[MovieGroup]
    skipped_files: list[MovieFile]       # < min_size
    unmatched_files: list[MovieFile]     # Не привязаны к видео
    total_size_bytes: int                # Суммарный размер файлов в groups


def _collect_files_flat(source_path: str) -> Optional[List[str]]:
    """Собирает файлы из верхнего уровня директории (без рекурсии)."""
    try:
        entries = os.listdir(source_path)
    except OSError as exc:
        _logger.error(f"Ошибка чтения директории {source_path}: {exc}")
        return None

    result: List[str] = []
    for entry in entries:
        full_path = os.path.join(source_path, entry)
        if os.path.isdir(full_path):
            _logger.debug(f"Пропущена директория: {entry}")
            continue
        result.append(full_path)

    return result


def _collect_files_recursive(
    source_path: str,
    destination_dir: str,
) -> Optional[List[str]]:
    """Собирает файлы рекурсивно из всех вложенных директорий."""
    dest_norm = ""
    if destination_dir:
        dest_norm = os.path.normcase(os.path.normpath(destination_dir))

    result: List[str] = []

    try:
        for dirpath, dirnames, filenames in os.walk(source_path):
            if dest_norm:
                dir_norm = os.path.normcase(os.path.normpath(dirpath))
                if dir_norm == dest_norm or dir_norm.startswith(dest_norm + os.sep):
                    dirnames.clear()
                    _logger.debug(f"Исключена destination директория: {dirpath}")
                    continue
            for fname in filenames:
                result.append(os.path.join(dirpath, fname))
    except OSError as exc:
        _logger.error(f"Ошибка рекурсивного обхода {source_path}: {exc}")
        return None

    return result


def scan_directory(
    source_path: str,
    min_file_size_bytes: int,
    handle_multipart: bool,
    clean_names: bool,
    recursive: bool = False,
    destination_dir: str = "",
) -> ScanResult:
    """Сканирует директорию и группирует файлы.

    Args:
        source_path: Путь к директории для сканирования.
        min_file_size_bytes: Минимальный размер видеофайла в байтах.
        handle_multipart: Группировать ли multi-part файлы (CD1, CD2).
        clean_names: Использовать ли нормализованные имена из name_parser.
        recursive: Сканировать вложенные директории.
        destination_dir: Путь назначения (исключается при рекурсивном сканировании).

    Returns:
        ScanResult с группами, пропущенными и непривязанными файлами.
    """
    _logger.info(f"Начало сканирования директории: {source_path} (recursive={recursive})")

    video_files: Dict[str, MovieFile] = {}
    associated_files: List[MovieFile] = []
    unmatched_files: List[MovieFile] = []

    # 1. Сбор файлов: рекурсивный или плоский режим
    if recursive:
        all_file_paths = _collect_files_recursive(source_path, destination_dir)
    else:
        all_file_paths = _collect_files_flat(source_path)

    if all_file_paths is None:
        return ScanResult(groups=[], skipped_files=[], unmatched_files=[], total_size_bytes=0)

    _logger.info(f"Найдено файлов: {len(all_file_paths)}")

    for full_path in all_file_paths:
        entry = os.path.basename(full_path)

        # Пропускать символьные ссылки
        if os.path.islink(full_path):
            _logger.warning(f"Пропущена символьная ссылка: {entry}")
            continue

        try:
            size = os.path.getsize(full_path)
        except OSError as exc:
            _logger.error(f"Ошибка получения размера файла {entry}: {exc}")
            continue

        _, ext = os.path.splitext(entry)
        ext_lower = ext.lower()

        movie_file = MovieFile(
            filename=entry,
            full_path=full_path,
            size_bytes=size,
            extension=ext_lower,
        )

        # 2. Классификация по расширению (case-insensitive)
        if ext_lower in VIDEO_EXTENSIONS:
            basename_no_ext = entry[:len(entry) - len(ext)]
            video_files[basename_no_ext] = movie_file
            _logger.debug(f"Видеофайл: {entry} ({size} bytes)")
        elif ext_lower in ASSOCIATED_EXTENSIONS:
            associated_files.append(movie_file)
            _logger.debug(f"Associated файл: {entry}")
        else:
            unmatched_files.append(movie_file)
            _logger.debug(f"Нераспознанный файл: {entry}")

    _logger.info(
        f"Классификация: {len(video_files)} видео, "
        f"{len(associated_files)} associated, "
        f"{len(unmatched_files)} нераспознанных"
    )

    # 3. Фильтрация по размеру
    skipped_files: List[MovieFile] = []
    filtered_video: Dict[str, MovieFile] = {}
    for basename, mf in video_files.items():
        if mf.size_bytes < min_file_size_bytes:
            skipped_files.append(mf)
            _logger.info(
                f"Пропущен по размеру: {mf.filename} "
                f"({mf.size_bytes} < {min_file_size_bytes})"
            )
        else:
            filtered_video[basename] = mf

    # 4. Группировка (multi-part или одиночные)
    # Структура: base_name -> list of (MovieFile, part_number|0)
    groups_dict: Dict[str, List[Tuple[MovieFile, int]]] = {}

    for basename, mf in filtered_video.items():
        if handle_multipart:
            match = MULTIPART_PATTERN.match(basename)
            if match:
                raw_base = match.group(1).rstrip("._- ")
                part_num = int(match.group(2))
                groups_dict.setdefault(raw_base, []).append((mf, part_num))
                _logger.debug(
                    f"Multi-part: {mf.filename} -> base='{raw_base}', part={part_num}"
                )
                continue

        # Одиночный файл или handle_multipart=False
        groups_dict.setdefault(basename, []).append((mf, 0))

    # Сортировать multi-part по номеру части
    for base_name in groups_dict:
        groups_dict[base_name].sort(key=lambda x: x[1])

    # 5. Привязка associated файлов
    # Отсортировать base_names по длине DESC для longest-prefix match
    sorted_bases = sorted(groups_dict.keys(), key=len, reverse=True)

    associated_mapping: Dict[str, List[MovieFile]] = {base: [] for base in groups_dict}
    remaining_unmatched: List[MovieFile] = []

    for af in associated_files:
        af_basename_no_ext, _ = os.path.splitext(af.filename)
        matched = False
        for base_name in sorted_bases:
            if af_basename_no_ext.startswith(base_name):
                associated_mapping[base_name].append(af)
                _logger.debug(
                    f"Associated привязан: {af.filename} -> '{base_name}'"
                )
                matched = True
                break
        if not matched:
            remaining_unmatched.append(af)
            _logger.debug(f"Associated не привязан: {af.filename}")

    unmatched_files.extend(remaining_unmatched)

    # 6. Парсинг имён и формирование MovieGroup
    groups: List[MovieGroup] = []
    total_size: int = 0

    for base_name, file_parts in groups_dict.items():
        video_list = [fp[0] for fp in file_parts]
        assoc_list = associated_mapping.get(base_name, [])

        parsed = parse_name(base_name)
        if not clean_names:
            # Заменяем clean_folder_name на raw base_name
            parsed = ParsedName(
                title=parsed.title,
                year=parsed.year,
                clean_folder_name=base_name,
                raw_name=parsed.raw_name,
            )

        group = MovieGroup(
            video_files=video_list,
            associated_files=assoc_list,
            parsed_name=parsed,
            base_name=base_name,
        )
        groups.append(group)

        # Считаем total_size из файлов в группах
        for vf in video_list:
            total_size += vf.size_bytes
        for af in assoc_list:
            total_size += af.size_bytes

    _logger.info(
        f"Сканирование завершено: {len(groups)} групп, "
        f"{len(skipped_files)} пропущено, "
        f"{len(unmatched_files)} не привязано, "
        f"total_size={total_size} bytes"
    )

    return ScanResult(
        groups=groups,
        skipped_files=skipped_files,
        unmatched_files=unmatched_files,
        total_size_bytes=total_size,
    )
