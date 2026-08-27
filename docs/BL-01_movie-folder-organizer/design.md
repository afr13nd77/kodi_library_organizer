# BL-01: Техническое проектирование — Реорганизация фильмотеки в per-folder

**Статус:** draft
**Версия:** 1.0
**Дата:** 27.08.2026
**Автор:** Architect (opus)

---

## 1. Архитектура

### 1.1 Диаграмма модулей и потока данных

```
                          Kodi Runtime (Python 3.8)
 +---------------------------------------------------------------------+
 |                                                                     |
 |  script.library.organizer/python/main.py                            |
 |  +---------------------------------------------------------------+  |
 |  |  KodiUI                                                       |  |
 |  |  - Главное меню (Dialog.select)                               |  |
 |  |  - Выбор папок (Dialog.browseSingle)                          |  |
 |  |  - Dry-run превью (Dialog.textviewer)                         |  |
 |  |  - Подтверждение (Dialog.yesno)                               |  |
 |  |  - Прогресс (DialogProgress)                                  |  |
 |  |  - Конфликты (Dialog.yesnocustom)                             |  |
 |  |  - Результаты (Dialog.ok)                                     |  |
 |  +-------+---+---+---+---+---+---+-------------------------------+  |
 |          |   |   |   |   |   |   |                                  |
 |          v   |   v   |   v   |   v                                  |
 |  +-------+   |  +----+  |  +-+---+------+   +------------------+   |
 |  |scanner|   |  |name |  |  |undo       |   |  file_patterns   |   |
 |  |  .py  |   |  |_par |  |  |_journal   |   |    .py           |   |
 |  |       |<--+  |ser  |  |  |  .py      |   | VIDEO_EXTENSIONS |   |
 |  | scan_ |   |  |.py  |  |  |           |   | SUB_EXTENSIONS   |   |
 |  | dir() |   |  |     |  |  | save()    |   | MULTIPART_RE     |   |
 |  | group |   |  |parse|  |  | load()    |   +--------+---------+   |
 |  | _files|   |  |_name|  |  | execute   |            |             |
 |  |  ()   |   |  | ()  |  |  | _undo()   |            |             |
 |  +---+---+   |  +--+--+  |  +-----+-----+            |             |
 |      |       |     |     |        |                   |             |
 |      +-------+-----+-----+--------+-------------------+             |
 |              |                                                      |
 |              v                                                      |
 |  +-----------+-----------------------------------------------+      |
 |  |  organizer.py                                             |      |
 |  |                                                           |      |
 |  |  build_plan()  -->  OperationPlan                         |      |
 |  |  execute_plan()  -->  OperationResult                     |      |
 |  |  format_preview()  -->  str (для textviewer)              |      |
 |  |                                                           |      |
 |  |  Использует: xbmcvfs (создание папок, копирование)        |      |
 |  |              os/shutil (move, disk_usage, stat)           |      |
 |  +-----------------------------------------------------------+      |
 |                                                                     |
 |  +-----------------------------------------------------------+      |
 |  |  logger.py                                                |      |
 |  |  Logger(debug_enabled) — используется всеми модулями      |      |
 |  +-----------------------------------------------------------+      |
 +---------------------------------------------------------------------+
```

### 1.2 Поток данных (основной сценарий)

```
main.py                scanner.py         name_parser.py     organizer.py         undo_journal.py
  |                        |                    |                  |                     |
  |--scan_directory()----->|                    |                  |                     |
  |                        |--parse_name()----->|                  |                     |
  |                        |<--ParsedName-------|                  |                     |
  |<--List[MovieGroup]----|                    |                  |                     |
  |                        |                    |                  |                     |
  |--build_plan(groups)----|--------------------+---------------->|                     |
  |<--OperationPlan--------|--------------------+-----------------|                     |
  |                        |                    |                  |                     |
  |  [показать превью, получить подтверждение]  |                  |                     |
  |                        |                    |                  |                     |
  |--execute_plan(plan, callback)-------------->|                  |                     |
  |                        |                    |  [для каждой операции:]                |
  |                        |                    |  xbmcvfs.mkdir() |                     |
  |                        |                    |  xbmcvfs.copy()  |                     |
  |                        |                    |  os.rename()     |                     |
  |                        |                    |                  |--save(entry)------->|
  |<--OperationResult------|--------------------+-----------------|                     |
  |                        |                    |                  |                     |
```

### 1.3 Описание модулей

#### `shared/file_patterns.py` -- Константы и паттерны

Центральное хранилище расширений файлов и regex-паттернов. Не содержит логики -- только данные.

**Public API:**

```python
from __future__ import annotations

# Расширения видеофайлов (нижний регистр, с точкой)
VIDEO_EXTENSIONS: frozenset[str]
# {".mkv", ".avi", ".mp4", ".m4v", ".mov", ".wmv", ".flv", ".ts",
#  ".m2ts", ".vob", ".divx", ".mpg", ".mpeg", ".ogm", ".webm", ".3gp"}

# Расширения файлов субтитров
SUBTITLE_EXTENSIONS: frozenset[str]
# {".srt", ".sub", ".ssa", ".ass", ".idx", ".sup", ".vtt"}

# Расширения артворка
ARTWORK_EXTENSIONS: frozenset[str]
# {".jpg", ".jpeg", ".png", ".tbn", ".gif", ".bmp", ".webp"}

# Расширение метаданных
METADATA_EXTENSIONS: frozenset[str]
# {".nfo"}

# Все расширения связанных файлов (субтитры + артворк + метаданные)
ASSOCIATED_EXTENSIONS: frozenset[str]
# SUBTITLE_EXTENSIONS | ARTWORK_EXTENSIONS | METADATA_EXTENSIONS

# Regex для определения multi-part: захватывает базовое имя и номер части
# Паттерн: (base_name)[._-](cd|disc|disk|part|pt)[._-]?(\d+)
MULTIPART_PATTERN: re.Pattern[str]

# Теги качества для очистки имени (case-insensitive)
QUALITY_TAGS: frozenset[str]
# {"1080p", "720p", "480p", "2160p", "4K", "BDRip", "BRRip", "WEB-DL",
#  "WEBRip", "HDRip", "DVDRip", "x264", "x265", "H264", "H265", "HEVC",
#  "AAC", "AC3", "DTS", "BluRay", "Blu-Ray", "HDTV", "REMUX", "Atmos",
#  "TrueHD", "DD5.1", "DD7.1", "10bit", "HDR", "HDR10", "HDR10+",
#  "Dolby.Vision", "DV", "IMAX", "PROPER", "REPACK", "EXTENDED",
#  "UNRATED", "Directors.Cut", "Theatrical", "COMPLETE", "MULTI",
#  "DUAL", "RUS", "ENG", "NNM-CLUB", "RARBG", "YTS", "YIFY",
#  "FGT", "SPARKS", "AMIABLE", "GECKOS", "DRONES", "ETRG"}
```

**Обоснование:** вынесение констант в отдельный модуль позволяет scanner.py и name_parser.py не дублировать данные, а также упрощает расширение списков при добавлении новых форматов.

---

#### `shared/name_parser.py` -- Парсинг имён файлов

Извлечение человекочитаемого названия и года из имени видеофайла.

**Public API:**

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ParsedName:
    """Результат парсинга имени файла."""
    title: str           # Название фильма ("Interstellar", "Dune Part Two")
    year: int | None      # Год выпуска (2014) или None если не распознан
    clean_folder_name: str  # Готовое имя папки: "Interstellar (2014)" или "Interstellar"
    raw_name: str         # Исходное имя файла без расширения

def parse_name(filename: str) -> ParsedName:
    """Парсит имя видеофайла и извлекает название + год.

    Args:
        filename: имя файла БЕЗ расширения (например, "Interstellar.2014.1080p.BDRip.x264")

    Returns:
        ParsedName с извлечёнными данными.
    """
```

Детальный алгоритм `parse_name()` описан в разделе 3.2.

---

#### `shared/scanner.py` -- Сканирование и группировка

Сканирует директорию, находит видеофайлы, группирует их со связанными файлами.

**Public API:**

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class MovieFile:
    """Один файл с метаданными."""
    filename: str         # Имя файла ("Interstellar.2014.1080p.mkv")
    full_path: str        # Абсолютный путь
    size_bytes: int       # Размер файла в байтах
    extension: str        # Расширение с точкой (".mkv")

@dataclass
class MovieGroup:
    """Фильм = главный видеофайл + связанные файлы."""
    video_files: list[MovieFile]     # Видеофайлы (1 для обычного, 2+ для multi-part)
    associated_files: list[MovieFile] # Субтитры, NFO, артворк
    parsed_name: ParsedName          # Результат парсинга имени
    base_name: str                   # Базовое имя для группировки (без расширения)

@dataclass
class ScanResult:
    """Полный результат сканирования директории."""
    groups: list[MovieGroup]         # Найденные группы фильмов
    skipped_files: list[MovieFile]   # Пропущенные файлы (< min_size)
    unmatched_files: list[MovieFile] # Файлы, не привязанные ни к одному видео
    total_size_bytes: int            # Суммарный размер всех файлов в группах

def scan_directory(
    source_path: str,
    min_file_size_bytes: int,
    handle_multipart: bool,
    clean_names: bool,
) -> ScanResult:
    """Сканирует source_path (плоский, без рекурсии) и возвращает группы фильмов.

    Args:
        source_path: путь к директории-источнику
        min_file_size_bytes: минимальный размер видеофайла в байтах (меньше -- пропускаются)
        handle_multipart: группировать ли multi-part файлы (CD1/CD2 и т.д.)
        clean_names: применять ли нормализацию имён для папок

    Returns:
        ScanResult с группами, пропущенными и несвязанными файлами.
    """
```

Детальный алгоритм описан в разделе 3.1.

---

#### `shared/organizer.py` -- Планирование и выполнение операций

Центральный модуль -- формирует план операций из ScanResult и выполняет файловые операции.

**Public API:**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

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

@dataclass
class PlannedOperation:
    """Одна планируемая файловая операция."""
    source_path: str           # Откуда
    destination_path: str      # Куда
    is_video: bool             # Это видеофайл (или связанный)
    file_size_bytes: int       # Размер

@dataclass
class OperationPlan:
    """Полный план операций."""
    mode: OperationMode
    source_dir: str
    destination_dir: str
    groups: list[PlannedGroup]     # Группы (фильм + файлы + целевая папка)
    skipped_files: list[MovieFile] # Пропущенные (для превью)
    total_files: int
    total_size_bytes: int

@dataclass
class PlannedGroup:
    """Группа операций для одного фильма."""
    folder_name: str                     # Имя целевой папки
    operations: list[PlannedOperation]   # Файловые операции
    parsed_name: ParsedName              # Метаданные имени

@dataclass
class OperationResult:
    """Результат выполнения плана."""
    success_count: int         # Успешно обработанных файлов
    error_count: int           # Файлов с ошибками
    skipped_count: int         # Пропущенных (конфликты, выбран skip)
    total_count: int           # Всего файлов в плане
    errors: list[str]          # Список сообщений об ошибках
    was_cancelled: bool        # Прервано пользователем

# Тип callback для прогресса: (current: int, total: int, filename: str) -> bool
# Возвращает False если пользователь нажал Cancel
ProgressCallback = Callable[[int, int, str], bool]

# Тип callback для разрешения конфликтов папок
# (folder_name: str) -> ConflictResolution
FolderConflictCallback = Callable[[str], ConflictResolution]

# Тип callback для разрешения конфликтов файлов
# (filename: str) -> FileConflictResolution
FileConflictCallback = Callable[[str], FileConflictResolution]

def build_plan(
    scan_result: ScanResult,
    destination_dir: str,
    mode: OperationMode,
) -> OperationPlan:
    """Строит план операций из результата сканирования.

    Args:
        scan_result: результат scan_directory()
        destination_dir: целевая директория
        mode: move или copy

    Returns:
        OperationPlan, готовый к превью или выполнению.
    """

def format_preview(plan: OperationPlan) -> str:
    """Форматирует план в текстовый вид для dry-run превью.

    Returns:
        Многострочная строка для Dialog.textviewer().
    """

def execute_plan(
    plan: OperationPlan,
    undo_journal_path: str,
    progress_callback: Optional[ProgressCallback] = None,
    folder_conflict_callback: Optional[FolderConflictCallback] = None,
    file_conflict_callback: Optional[FileConflictCallback] = None,
) -> OperationResult:
    """Выполняет план файловых операций.

    Args:
        plan: OperationPlan из build_plan()
        undo_journal_path: путь для сохранения undo-журнала
        progress_callback: вызывается для обновления прогресса, возвращает False для cancel
        folder_conflict_callback: вызывается при конфликте папок (папка уже существует)
        file_conflict_callback: вызывается при конфликте файлов (файл уже существует)

    Returns:
        OperationResult с итогами.
    """

def check_disk_space(destination_dir: str, required_bytes: int) -> bool:
    """Проверяет, достаточно ли свободного места.

    Returns:
        True если места достаточно, False иначе.
    """
```

**Обоснование callback-подхода:** organizer.py не знает о Kodi UI. Callbacks позволяют main.py подключить DialogProgress и Dialog.yesnocustom, сохраняя разделение ответственности. Это же позволяет в будущем подключить CLI (BL-02) без изменения organizer.py.

---

#### `shared/undo_journal.py` -- Журнал операций

Сохранение и загрузка журнала для возможности отката.

**Public API:**

```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class UndoEntry:
    """Одна операция для отката."""
    source_path: str          # Оригинальный путь файла (до операции)
    destination_path: str     # Путь файла после операции
    operation: str            # "move" или "copy"
    file_size_bytes: int      # Размер файла
    success: bool             # Была ли операция успешной

@dataclass
class UndoJournal:
    """Полный журнал одной операции организации."""
    timestamp: str            # ISO-8601 datetime когда операция была выполнена
    source_dir: str           # Исходная директория
    destination_dir: str      # Целевая директория
    operation_mode: str       # "move" или "copy"
    entries: list[UndoEntry]  # Список операций
    folders_created: list[str]  # Список созданных папок (для удаления при откате)
    completed: bool           # Операция завершена полностью (True) или прервана (False)
    undone: bool              # Откат уже выполнен (True)

def save_journal(journal: UndoJournal, file_path: str) -> None:
    """Сохраняет журнал в JSON-файл.

    Args:
        journal: объект UndoJournal
        file_path: путь к файлу журнала
    """

def load_journal(file_path: str) -> UndoJournal:
    """Загружает журнал из JSON-файла.

    Args:
        file_path: путь к файлу журнала

    Returns:
        UndoJournal

    Raises:
        FileNotFoundError: файл не существует
        json.JSONDecodeError: невалидный JSON
        KeyError: отсутствует обязательное поле
    """

def get_latest_journal(journal_dir: str) -> str | None:
    """Находит последний неиспользованный журнал в директории.

    Args:
        journal_dir: директория с журналами

    Returns:
        Путь к файлу журнала или None если нет доступных.
    """

def execute_undo(
    journal: UndoJournal,
    progress_callback: ProgressCallback | None = None,
) -> OperationResult:
    """Выполняет откат операций из журнала.

    Для mode=move: перемещает файлы обратно в source.
    Для mode=copy: удаляет файлы в destination.
    После отката: удаляет пустые папки из folders_created.
    Помечает журнал как undone=True.

    Args:
        journal: загруженный UndoJournal
        progress_callback: callback для прогресса

    Returns:
        OperationResult с итогами отката.
    """
```

---

#### `shared/logger.py` -- Логирование

Адаптация Logger из kodi_metadata_scraper. Упрощена (без санитизации API-ключей).

**Public API:**

```python
from __future__ import annotations

class Logger:
    """Логгер для Kodi-аддона."""

    def __init__(self, debug_enabled: bool = False) -> None:
        """Инициализация. Считывает addon ID из Kodi API."""

    def debug(self, message: str) -> None:
        """Лог уровня DEBUG (только при debug_enabled=True)."""

    def info(self, message: str) -> None:
        """Лог уровня INFO."""

    def warning(self, message: str) -> None:
        """Лог уровня WARNING."""

    def error(self, message: str) -> None:
        """Лог уровня ERROR."""
```

**Правила использования:**
- Каждая публичная функция логирует результат (success) и ошибку (error).
- Формат: только f-strings, один аргумент. Никогда `%s`.
- Пример: `logger.info(f"scan_directory: found {len(videos)} videos in {source_path}")`
- Пример: `logger.error(f"scan_directory: failed to stat file {path}: {e}")`

---

#### `script.library.organizer/python/main.py` -- Точка входа и UI

Точка входа аддона. Связывает Kodi UI с shared-модулями. Содержит только UI-логику, без бизнес-логики.

**Public API:**

```python
from __future__ import annotations

def main() -> None:
    """Точка входа аддона. Показывает главное меню и обрабатывает выбор пользователя."""

def show_main_menu() -> None:
    """Показывает главное меню: Организовать / Откатить / Настройки."""

def run_organize() -> None:
    """Полный flow организации: выбор папок -> сканирование -> превью -> выполнение."""

def run_undo() -> None:
    """Flow отката: загрузка журнала -> подтверждение -> выполнение."""

def _progress_callback(dialog: xbmcgui.DialogProgress, current: int, total: int, filename: str) -> bool:
    """Обновляет DialogProgress. Возвращает False если Cancel нажат."""

def _folder_conflict_callback(folder_name: str) -> ConflictResolution:
    """Показывает Dialog.yesnocustom для разрешения конфликта папки."""

def _file_conflict_callback(filename: str) -> FileConflictResolution:
    """Показывает Dialog.yesnocustom для разрешения конфликта файла."""
```

**Взаимодействие main.py с shared-модулями:**

1. `main.py` создаёт `Logger` и передаёт его в модули (или модули создают свой экземпляр через `_resolve_addon_id()`).
2. Читает настройки через `xbmcaddon.Addon().getSetting()` / `.getSettingBool()` / `.getSettingInt()`.
3. Вызывает `scanner.scan_directory()` с параметрами из настроек.
4. Вызывает `organizer.build_plan()` с результатом сканирования.
5. Если dry_run: вызывает `organizer.format_preview()` и показывает через `Dialog.textviewer()`.
6. После подтверждения: вызывает `organizer.execute_plan()` с callback-ами для прогресса и конфликтов.
7. Для отката: вызывает `undo_journal.get_latest_journal()`, `load_journal()`, `execute_undo()`.

---

## 2. Data Model

### 2.1 Dataclasses (полные определения)

Все dataclass определены в соответствующих модулях (не в отдельном models.py). Обоснование: каждый модуль владеет своими типами данных, зависимости минимальны.

**Типизация для Python 3.8:**
- `from __future__ import annotations` -- обязательно в каждом файле
- `list[X]` вместо `List[X]` (работает с `__future__`)
- `X | None` вместо `Optional[X]` (работает с `__future__`)
- Нет `match/case` (Python 3.10+)
- Нет `Self` type (Python 3.11+)

### 2.2 Формат undo-журнала (JSON Schema)

Файл сохраняется в директории `special://profile/addon_data/script.library.organizer/undo/`.
Имя файла: `undo_{timestamp}.json` (timestamp в формате `YYYYMMDD_HHMMSS`).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "timestamp", "source_dir", "destination_dir",
                "operation_mode", "entries", "folders_created", "completed", "undone"],
  "properties": {
    "version": {
      "type": "integer",
      "const": 1,
      "description": "Версия формата журнала для будущей миграции"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO-8601 datetime создания журнала",
      "example": "2026-08-27T14:30:00"
    },
    "source_dir": {
      "type": "string",
      "description": "Исходная директория",
      "example": "/media/movies/"
    },
    "destination_dir": {
      "type": "string",
      "description": "Целевая директория",
      "example": "/media/movies_organized/"
    },
    "operation_mode": {
      "type": "string",
      "enum": ["move", "copy"],
      "description": "Режим операции"
    },
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source_path", "destination_path", "operation",
                      "file_size_bytes", "success"],
        "properties": {
          "source_path": {
            "type": "string",
            "description": "Абсолютный путь файла до операции"
          },
          "destination_path": {
            "type": "string",
            "description": "Абсолютный путь файла после операции"
          },
          "operation": {
            "type": "string",
            "enum": ["move", "copy"]
          },
          "file_size_bytes": {
            "type": "integer",
            "minimum": 0
          },
          "success": {
            "type": "boolean",
            "description": "True если операция прошла успешно"
          }
        }
      }
    },
    "folders_created": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Список абсолютных путей созданных папок (для удаления при откате)"
    },
    "completed": {
      "type": "boolean",
      "description": "True если все операции завершены, False если прервано"
    },
    "undone": {
      "type": "boolean",
      "description": "True если откат уже выполнен",
      "default": false
    }
  }
}
```

**Пример реального файла:**

```json
{
  "version": 1,
  "timestamp": "2026-08-27T14:30:00",
  "source_dir": "/media/movies/",
  "destination_dir": "/media/movies_organized/",
  "operation_mode": "move",
  "entries": [
    {
      "source_path": "/media/movies/Interstellar.2014.1080p.BDRip.x264.mkv",
      "destination_path": "/media/movies_organized/Interstellar (2014)/Interstellar.2014.1080p.BDRip.x264.mkv",
      "operation": "move",
      "file_size_bytes": 4509715660,
      "success": true
    },
    {
      "source_path": "/media/movies/Interstellar.2014.1080p.srt",
      "destination_path": "/media/movies_organized/Interstellar (2014)/Interstellar.2014.1080p.srt",
      "operation": "move",
      "file_size_bytes": 87452,
      "success": true
    }
  ],
  "folders_created": [
    "/media/movies_organized/Interstellar (2014)"
  ],
  "completed": true,
  "undone": false
}
```

**Обоснование JSON (а не SQLite):**
- Журнал пишется последовательно, одна сессия -- один файл.
- Размер мал (максимум тысячи записей, десятки КБ).
- Человекочитаем -- пользователь может открыть и понять.
- Не требует дополнительных зависимостей.
- SQLite избыточен для write-once / read-once сценария.

### 2.3 settings.xml (полный)

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
  <section id="script.library.organizer">
    <category id="general" label="30100" help="">
      <group id="directories" label="30110">
        <setting id="source_directory" type="string" label="30111" help="30112">
          <level>0</level>
          <default></default>
          <control type="edit" format="path"/>
        </setting>
        <setting id="destination_directory" type="string" label="30113" help="30114">
          <level>0</level>
          <default></default>
          <control type="edit" format="path"/>
        </setting>
      </group>
      <group id="operation" label="30120">
        <setting id="operation_mode" type="integer" label="30121" help="30122">
          <level>0</level>
          <default>0</default>
          <constraints>
            <options>
              <option label="30123">0</option>
              <option label="30124">1</option>
            </options>
          </constraints>
          <control type="spinner" format="string"/>
        </setting>
        <setting id="dry_run" type="boolean" label="30125" help="30126">
          <level>0</level>
          <default>true</default>
          <control type="toggle"/>
        </setting>
      </group>
    </category>
    <category id="naming" label="30200" help="">
      <group id="naming_options" label="30210">
        <setting id="clean_names" type="boolean" label="30211" help="30212">
          <level>0</level>
          <default>true</default>
          <control type="toggle"/>
        </setting>
      </group>
    </category>
    <category id="advanced" label="30300" help="">
      <group id="filters" label="30310">
        <setting id="min_file_size_mb" type="integer" label="30311" help="30312">
          <level>1</level>
          <default>100</default>
          <constraints>
            <minimum>0</minimum>
            <step>10</step>
            <maximum>1000</maximum>
          </constraints>
          <control type="spinner" format="integer"/>
        </setting>
        <setting id="handle_multipart" type="boolean" label="30313" help="30314">
          <level>1</level>
          <default>true</default>
          <control type="toggle"/>
        </setting>
      </group>
      <group id="undo_options" label="30320">
        <setting id="undo_enabled" type="boolean" label="30321" help="30322">
          <level>1</level>
          <default>true</default>
          <control type="toggle"/>
        </setting>
      </group>
      <group id="debug_options" label="30330">
        <setting id="debug_logging" type="boolean" label="30331" help="30332">
          <level>2</level>
          <default>false</default>
          <control type="toggle"/>
        </setting>
      </group>
    </category>
  </section>
</settings>
```

**Label IDs (для strings.po):**

| ID | en_GB | ru_RU |
|---|---|---|
| 30100 | General | Основные |
| 30110 | Directories | Директории |
| 30111 | Source directory | Директория-источник |
| 30112 | Directory with movies in flat structure | Директория с фильмами в плоской структуре |
| 30113 | Destination directory | Директория назначения |
| 30114 | Directory where organized folders will be created | Директория, куда будут созданы папки с фильмами |
| 30120 | Operation | Операция |
| 30121 | Mode | Режим |
| 30122 | Move files or copy them | Переместить файлы или скопировать |
| 30123 | Move | Переместить |
| 30124 | Copy | Скопировать |
| 30125 | Dry run (preview only) | Пробный запуск (только превью) |
| 30126 | Show planned operations without executing | Показать план без выполнения |
| 30200 | Naming | Именование |
| 30210 | Folder naming | Именование папок |
| 30211 | Clean folder names | Нормализовать имена папок |
| 30212 | Extract movie title and year from filename | Извлекать название и год из имени файла |
| 30300 | Advanced | Расширенные |
| 30310 | Filters | Фильтры |
| 30311 | Minimum file size (MB) | Минимальный размер файла (МБ) |
| 30312 | Files smaller than this will be skipped | Файлы меньше этого размера будут пропущены |
| 30313 | Handle multi-part files | Обработка multi-part файлов |
| 30314 | Group CD1/CD2, Part1/Part2 into one folder | Группировать CD1/CD2, Part1/Part2 в одну папку |
| 30320 | Undo | Отмена |
| 30321 | Enable undo journal | Включить журнал отмены |
| 30322 | Save operation log for possible rollback | Сохранять журнал для возможного отката |
| 30330 | Debug | Отладка |
| 30331 | Debug logging | Подробное логирование |
| 30332 | Enable verbose debug logging | Включить подробные отладочные логи |

---

## 3. Алгоритмы

### 3.1 Сканирование и группировка (scanner.py)

**Алгоритм `scan_directory()`:**

```
Вход: source_path, min_file_size_bytes, handle_multipart, clean_names

1. Получить список файлов в source_path (плоский, без рекурсии):
   - Использовать xbmcvfs.listdir(source_path) -> (dirs, files)
   - Для каждого файла получить размер через xbmcvfs.Stat(path).st_size()
   - Если xbmcvfs недоступен (тесты): fallback на os.listdir() + os.path.getsize()

2. Классифицировать файлы по расширению:
   - VIDEO_EXTENSIONS -> video_files: dict[str, MovieFile]
     (ключ = имя файла без расширения, значение = MovieFile)
   - ASSOCIATED_EXTENSIONS -> associated_files: dict[str, list[MovieFile]]
     (ключ = prefix имени, значение = список связанных файлов)
   - Все остальные -> unmatched_files

3. Фильтрация видеофайлов по размеру:
   - Если video.size_bytes < min_file_size_bytes -> в skipped_files
   - Иначе -> остаётся в video_files

4. Multi-part группировка (если handle_multipart=True):
   - Для каждого видеофайла: попробовать MULTIPART_PATTERN
   - Если match: извлечь base_name (без CDx/Partx)
   - Группировать видеофайлы с одним base_name в один MovieGroup.video_files

5. Привязка associated файлов к видео:
   - Для каждого associated файла: найти видео, чьё base_name является
     префиксом имени associated файла
   - Пример: видео "Interstellar.2014.1080p" ->
     "Interstellar.2014.1080p.srt" привязывается
     "Interstellar.2014.1080p-poster.jpg" привязывается
   - Алгоритм: отсортировать video base_names по длине (desc),
     для каждого associated файла найти самое длинное совпадение

6. Парсинг имён:
   - Для каждой группы: вызвать name_parser.parse_name(base_name)
   - Если clean_names=False: ParsedName.clean_folder_name = base_name

7. Формирование ScanResult:
   - groups: список MovieGroup
   - skipped_files: файлы < min_size
   - unmatched_files: файлы, не привязанные ни к одному видео

Выход: ScanResult
```

**Edge cases:**
- Пустая директория: `ScanResult(groups=[], skipped_files=[], unmatched_files=[], total_size_bytes=0)`
- Только субтитры (нет видео): все файлы в `unmatched_files`
- Видеофайл без связанных файлов: MovieGroup с пустым `associated_files`
- Файл `.nfo` с именем, совпадающим с видео: привязывается к группе
- Символьные ссылки: `os.path.islink()` -> пропустить с warning

### 3.2 Парсинг имён (name_parser.py)

**Алгоритм `parse_name()`:**

```
Вход: filename (без расширения), например "Interstellar.2014.1080p.BDRip.x264"

1. Сохранить raw_name = filename

2. Замена разделителей на пробелы:
   - Заменить точки (.), подчёркивания (_), дефисы между словами на пробелы
   - Не заменять дефис в составных словах (пока что заменяем все, т.к. точная
     детекция сложна; для MVP приемлемо)
   - Результат: "Interstellar 2014 1080p BDRip x264"

3. Поиск года:
   - Regex: r'\b((?:19|20)\d{2})\b'
   - Ищем ПОСЛЕДНЕЕ вхождение 4-значного числа в диапазоне 1920-2099
   - Почему последнее: "2001 A Space Odyssey 1968" -> год = 1968
   - Если найден: year = int(match), title_part = всё ДО года
   - Если не найден: year = None, title_part = вся строка

4. Очистка от тегов качества:
   - Разбить title_part на токены по пробелам
   - Для каждого токена: если token.lower() in {tag.lower() for tag in QUALITY_TAGS} -> убрать
   - Это ловит случаи, когда теги качества стоят ПЕРЕД годом
     (редко, но бывает: "Movie REMASTER 2020")

5. Обрезка trailing мусора:
   - Убрать trailing пробелы, дефисы, точки
   - Убрать пустые скобки: "Movie ()" -> "Movie"

6. Формирование clean_folder_name:
   - Если year != None: f"{title} ({year})"
   - Если year == None: title
   - Если title пустой после очистки: использовать raw_name

7. Санитизация имени папки:
   - Убрать символы, недопустимые в именах папок: < > : " / \ | ? *
   - Обрезать trailing точки и пробелы (Windows не позволяет)
   - Ограничить длину: если > 200 символов, обрезать до 200

Выход: ParsedName(title, year, clean_folder_name, raw_name)
```

**Примеры:**

| Вход | title | year | clean_folder_name |
|---|---|---|---|
| `Interstellar.2014.1080p.BDRip.x264` | Interstellar | 2014 | Interstellar (2014) |
| `Dune.Part.Two.2024.WEB-DL` | Dune Part Two | 2024 | Dune Part Two (2024) |
| `The.Matrix.1999.REMASTERED.BluRay` | The Matrix | 1999 | The Matrix (1999) |
| `some_random_movie` | some random movie | None | some random movie |
| `2001.A.Space.Odyssey.1968.BDRip` | 2001 A Space Odyssey | 1968 | 2001 A Space Odyssey (1968) |
| `Movie (2020) [1080p]` | Movie | 2020 | Movie (2020) |

**Обоснование "последний год":** Имена вида "2001 A Space Odyssey 1968" содержат год в названии. Последнее 4-значное число с большей вероятностью -- год выпуска, а не часть названия. Если в имени всего одно число, оно и будет и первым, и последним.

### 3.3 Multi-part определение (file_patterns.py)

**Regex:**

```python
MULTIPART_PATTERN = re.compile(
    r'^(.+?)[._\- ]+'        # base_name (non-greedy)
    r'(?:cd|disc|disk|part|pt)'  # маркер multi-part
    r'[._\- ]*'              # опциональный разделитель
    r'(\d+)'                 # номер части
    r'(.*)$',                # остаток (теги качества и т.д.)
    re.IGNORECASE,
)
```

**Алгоритм группировки (в scanner.py):**

```
1. Для каждого видеофайла: применить MULTIPART_PATTERN
2. Если match:
   - base_name = match.group(1).rstrip("._- ")
   - part_number = int(match.group(2))
   - Добавить в multipart_groups[base_name] с сортировкой по part_number
3. Если не match: одиночный файл, отдельный MovieGroup
4. Каждая группа в multipart_groups -> один MovieGroup с несколькими video_files
5. Для ParsedName: использовать base_name (без CDx)
```

**Примеры:**

| Файл | base_name | part |
|---|---|---|
| `Movie.Name.CD1.avi` | Movie.Name | 1 |
| `Movie.Name.CD2.avi` | Movie.Name | 2 |
| `Movie.Name.Part.1.mkv` | Movie.Name | 1 |
| `Movie_Name_disc2.mkv` | Movie_Name | 2 |
| `Movie-pt1.avi` | Movie | 1 |

### 3.4 Конфликт-резолюция (organizer.py)

**Конфликт папок (папка уже существует в destination):**

```
1. Перед созданием папки: проверить xbmcvfs.exists(folder_path)
   (xbmcvfs.exists для папок требует trailing slash)
2. Если существует:
   - Вызвать folder_conflict_callback(folder_name)
   - SKIP: пропустить всю группу файлов, записать в skipped_count
   - MERGE: продолжить, файлы будут добавлены в существующую папку
   - RENAME: сгенерировать новое имя: "{folder_name}_2", проверить, если тоже существует -> "_3" и т.д.
3. Если callback = None (нет UI, тесты): по умолчанию MERGE
```

**Конфликт файлов (файл уже существует в целевой папке):**

```
1. Перед копированием/перемещением: проверить xbmcvfs.exists(dest_file_path)
2. Если существует:
   - Вызвать file_conflict_callback(filename)
   - SKIP: пропустить файл
   - OVERWRITE: удалить существующий, затем записать новый
   - RENAME: добавить суффикс к имени файла (до расширения): "movie_2.mkv"
3. Если callback = None: по умолчанию SKIP
```

**Обоснование умолчаний:** MERGE для папок (чтобы не терять фильмы), SKIP для файлов (чтобы не затирать данные). Безопасный default.

---

## 4. Kodi UI (main.py)

### 4.1 Используемые диалоги

| Диалог | Назначение | Метод |
|---|---|---|
| Главное меню | Выбор действия (3 пункта) | `xbmcgui.Dialog().select(heading, list)` |
| Выбор папки | Source / Destination | `xbmcgui.Dialog().browseSingle(0, heading, 'files')` |
| Dry-run превью | Показ плана операций | `xbmcgui.Dialog().textviewer(heading, text)` |
| Подтверждение | Перед выполнением / откатом | `xbmcgui.Dialog().yesno(heading, message)` |
| Прогресс | Выполнение операций | `xbmcgui.DialogProgress()` |
| Конфликт папки | 3 кнопки: Skip/Merge/Rename | `xbmcgui.Dialog().yesnocustom(heading, message, customlabel)` |
| Конфликт файла | 3 кнопки: Skip/Overwrite/Rename | `xbmcgui.Dialog().yesnocustom(heading, message, customlabel)` |
| Ошибка | Информирование об ошибке | `xbmcgui.Dialog().ok(heading, message)` |
| Результат | Итоги операции | `xbmcgui.Dialog().ok(heading, message)` |
| Нотификация | Быстрое уведомление | `xbmcgui.Dialog().notification(heading, message, icon)` |

**`Dialog().yesnocustom()` -- 3 кнопки:**
- Доступен с Kodi v19 (Matrix).
- Возвращает: 0 = No (первая кнопка), 1 = Yes (вторая), 2 = Custom (третья).
- Пример: `yesnocustom("Конфликт", msg, customlabel="Переименовать", nolabel="Пропустить", yeslabel="Объединить")`
- Маппинг: 0 -> SKIP, 1 -> MERGE, 2 -> RENAME.

### 4.2 Главное меню

```python
MENU_ITEMS = [
    "Организовать библиотеку",      # index 0
    "Откатить последнюю операцию",   # index 1
    "Настройки",                     # index 2
]

choice = xbmcgui.Dialog().select("Library Organizer", MENU_ITEMS)

if choice == 0:
    run_organize()
elif choice == 1:
    run_undo()
elif choice == 2:
    xbmcaddon.Addon().openSettings()
# choice == -1: пользователь закрыл диалог, ничего не делаем
```

**Обоснование Dialog.select (а не ListItem/Plugin):** Аддон типа `xbmc.python.script` не может использовать Plugin directory listing (setResolvedUrl, addDirectoryItems). Dialog.select -- простой, предсказуемый способ показать меню из 3 пунктов. Для MVP это оптимально.

### 4.3 Формат dry-run превью

```
--- Превью операций ---
Режим: Перемещение
Источник: /media/movies/
Назначение: /media/movies_organized/

[1] Interstellar (2014)
    Interstellar.2014.1080p.BDRip.x264.mkv (4.2 GB)
    + Interstellar.2014.1080p.srt (85 KB)
    + Interstellar.2014.1080p.nfo (2 KB)

[2] Dune Part Two (2024)
    Dune.Part.Two.2024.WEB-DL.mkv (2.8 GB)
    + Dune.Part.Two.2024.WEB-DL.srt (92 KB)

[3] The Matrix (1999)
    The.Matrix.1999.CD1.avi (700 MB)
    The.Matrix.1999.CD2.avi (700 MB)
    + The.Matrix.1999.srt (78 KB)

--- Пропущено ---
[!] sample_video.avi (45 MB) -- меньше 100 MB
[!] trailer.mp4 (32 MB) -- меньше 100 MB

--- Предупреждения ---
[?] some_random_movie.mkv -- год не распознан

--- Итого ---
Фильмов: 3
Файлов: 9
Объём: 8.5 GB
Пропущено: 2
```

**Форматирование размеров:**
- < 1 KB: `{bytes} B`
- < 1 MB: `{kb:.0f} KB`
- < 1 GB: `{mb:.1f} MB`
- >= 1 GB: `{gb:.1f} GB`

### 4.4 Flow прогресс-бара

```python
dialog = xbmcgui.DialogProgress()
dialog.create("Организация библиотеки", "Подготовка...")

def progress_callback(current: int, total: int, filename: str) -> bool:
    if dialog.iscanceled():
        return False
    percent = int(current * 100 / total) if total > 0 else 0
    dialog.update(percent, f"Файл {current} из {total}", filename)
    return True

result = organizer.execute_plan(plan, undo_path, progress_callback, ...)

dialog.close()
```

---

## 5. Безопасность и edge cases

### 5.1 Проверка дискового пространства

Перед началом Copy-операции (не Move, т.к. move на одном томе не требует места):

```python
def check_disk_space(destination_dir: str, required_bytes: int) -> bool:
    # Приоритет: shutil.disk_usage (работает на всех локальных FS)
    # Fallback для сетевых путей: нет надёжного способа через xbmcvfs,
    # поэтому для SMB/NFS пропускаем проверку с warning
    try:
        usage = shutil.disk_usage(destination_dir)
        # Запас 5% или 100MB (что больше)
        margin = max(required_bytes * 0.05, 100 * 1024 * 1024)
        return usage.free >= required_bytes + margin
    except OSError:
        logger.warning(f"check_disk_space: cannot check free space for {destination_dir}, skipping check")
        return True  # Не блокируем на сетевых путях
```

**Во время операции:** после каждого файла проверять, что копия записана полностью (сравнить size). Если размер не совпадает -- удалить partial файл, записать ошибку, остановить операцию.

### 5.2 Атомарность и прерывание

**Move на одном томе:**
- Использовать `os.rename()` -- атомарная операция на одном томе.
- Определение "один том": `os.stat(source).st_dev == os.stat(dest_parent).st_dev`.
- Если разные тома: copy-then-delete (сначала копировать, потом удалять исходник).

**Copy:**
- Копировать через `xbmcvfs.copy(source, dest)` для кроссплатформенности.
- Fallback на `shutil.copy2()` для локальных путей (сохраняет метаданные).
- После копирования: проверить `xbmcvfs.Stat(dest).st_size() == source_size`.

**Прерывание (Cancel):**
- Прервать МЕЖДУ файлами, не ВНУТРИ копирования файла.
- Текущий файл всегда завершается.
- Undo-журнал содержит записи для всех уже выполненных операций.
- `completed = False` в журнале.

**Ошибка нехватки места (Copy):**
- После ошибки: удалить частично скопированный файл (`xbmcvfs.delete()`).
- Записать в журнал все успешные операции (`success=True`).
- Записать неуспешную (`success=False`).
- Установить `completed = False`.
- Показать пользователю: сколько скопировано, предложить откат.

### 5.3 Спецсимволы в именах файлов

- **Кириллица:** поддерживается нативно (Python 3 str = unicode). xbmcvfs работает с unicode.
- **Пробелы:** не проблема для xbmcvfs/os, но в путях для `xbmcvfs.copy()` нужно убедиться, что путь не urlencode-ен случайно.
- **Скобки, апострофы:** допустимы во всех ОС, не требуют экранирования.
- **Недопустимые символы в именах папок (Windows):** `< > : " / \ | ? *` -- удаляются при формировании clean_folder_name в name_parser.py.
- **Trailing точка/пробел (Windows):** Windows автоматически обрезает, но лучше делать это явно в name_parser.py.

### 5.4 Сетевые пути (SMB/NFS)

Kodi транслирует сетевые пути в формат `smb://server/share/path/`. Ключевые отличия:

| Операция | Локальный путь | Сетевой путь |
|---|---|---|
| Листинг | `os.listdir()` | `xbmcvfs.listdir()` |
| Существование | `os.path.exists()` | `xbmcvfs.exists()` |
| Размер | `os.path.getsize()` | `xbmcvfs.Stat().st_size()` |
| Создание папки | `os.makedirs()` | `xbmcvfs.mkdirs()` |
| Копирование | `shutil.copy2()` | `xbmcvfs.copy()` |
| Перемещение | `os.rename()` / `shutil.move()` | `xbmcvfs.rename()` |
| Удаление файла | `os.remove()` | `xbmcvfs.delete()` |
| Удаление папки | `os.rmdir()` | `xbmcvfs.rmdir()` |

**Стратегия:** определить тип пути по префиксу (`smb://`, `nfs://`, `ftp://`). Если сетевой -- использовать только xbmcvfs. Если локальный -- использовать os/shutil (быстрее, надёжнее), с xbmcvfs как fallback.

```python
def is_network_path(path: str) -> bool:
    """Определяет, является ли путь сетевым (SMB/NFS/FTP)."""
    network_prefixes = ("smb://", "nfs://", "ftp://", "sftp://", "upnp://")
    return path.lower().startswith(network_prefixes)
```

**Ограничение:** `xbmcvfs.rename()` не работает между разными хранилищами (например, SMB -> локальный). В этом случае: copy + delete.

### 5.5 Валидация путей

```
1. source_path не пустой
2. destination_path не пустой
3. source_path существует (xbmcvfs.exists)
4. destination_path существует (xbmcvfs.exists)
5. source_path != destination_path (нормализовать перед сравнением:
   - os.path.normpath для локальных
   - rstrip("/") для сетевых
   - case-insensitive на Windows)
6. destination_path не является подпапкой source_path
   (иначе файлы будут перемещены в подпапку самих себя)
7. source_path содержит хотя бы один видеофайл (иначе: info, не error)
```

### 5.6 Длина пути (Windows MAX_PATH)

Windows по умолчанию ограничивает пути 260 символами. Mitigations:

```
1. При формировании clean_folder_name: ограничить до 200 символов.
2. Перед созданием файла: проверить len(destination_path) < 250.
3. Если превышает:
   - Обрезать имя папки (сохранив "(Год)" суффикс).
   - Если всё равно превышает: пропустить с предупреждением.
4. На Linux/macOS: ограничение 255 символов на компонент пути, не на весь путь.
   Имя папки <= 200 символов гарантирует соответствие.
```

### 5.7 Символьные ссылки

```
Если os.path.islink(file_path):
    logger.warning(f"scan_directory: skipping symlink {file_path}")
    -> unmatched_files (не обрабатываем)
```

Обоснование: перемещение/копирование symlink без понимания target может привести к потере данных или битым ссылкам.

### 5.8 Пустая директория

Если после сканирования `len(scan_result.groups) == 0`:
- Показать `Dialog().ok("Library Organizer", "В директории не найдено видеофайлов, соответствующих критериям.")`
- Не показывать ошибку, не предлагать дальнейшие действия.

---

## 6. Интеграция с существующим кодом

### 6.1 addon.xml (полный)

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="script.library.organizer"
       name="Library Organizer"
       version="1.0.0"
       provider-name="kodi_library_organizer">
  <requires>
    <import addon="xbmc.python" version="3.0.1"/>
  </requires>
  <extension point="xbmc.python.script"
             library="python/main.py">
    <provides>executable</provides>
  </extension>
  <extension point="xbmc.addon.metadata">
    <reuselanguageinvoker>false</reuselanguageinvoker>
    <summary lang="en_GB">Organize movie library into per-folder structure</summary>
    <summary lang="ru_RU">Организация фильмотеки в структуру по папкам</summary>
    <description lang="en_GB">Reorganize flat movie directory into per-folder structure. Each movie gets its own folder with associated files (subtitles, NFO, artwork). Supports dry-run preview, undo, multi-part files, and smart name parsing.</description>
    <description lang="ru_RU">Реорганизация плоской директории с фильмами в структуру по папкам. Каждый фильм получает свою папку с субтитрами, NFO и артворком. Поддержка превью, отката, multi-part файлов и парсинга имён.</description>
    <assets>
      <icon>icon.png</icon>
      <fanart>fanart.jpg</fanart>
    </assets>
    <platform>all</platform>
    <license>MIT</license>
  </extension>
</addon>
```

**Отличия от kodi_metadata_scraper:**
- `extension point="xbmc.python.script"` вместо `xbmc.metadata.scraper.movies`.
- `<provides>executable</provides>` -- аддон запускается как программа из меню Kodi.
- `<reuselanguageinvoker>false</reuselanguageinvoker>` -- каждый запуск в отдельном Python-процессе. Это обеспечивает чистое состояние. Для однократной операции (организация библиотеки) это безопасный выбор.
- `requires` только `xbmc.python`, без `xbmc.metadata`.

### 6.2 settings.xml

Полный XML представлен в разделе 2.3.

### 6.3 build_zip.py

Адаптация build_zip.py из kodi_metadata_scraper. Изменения:

```python
ADDONS = [
    {"addon_dir": "script.library.organizer", "archive_root": "script.library.organizer"},
]
```

Один аддон вместо двух. Остальная логика (walk файлов, исключение tests/__pycache__, копирование shared/*.py в addon/python/, создание ZIP) идентична.

### 6.4 Структура language-файлов

```
script.library.organizer/
  resources/
    language/
      resource.language.en_gb/
        strings.po
      resource.language.ru_ru/
        strings.po
```

Формат strings.po (Kodi standard):

```
# script.library.organizer language file
msgid ""
msgstr ""

msgctxt "#30100"
msgid "General"
msgstr ""

msgctxt "#30111"
msgid "Source directory"
msgstr ""
```

Для ru_RU -- аналогично, но с переводом в msgstr.

### 6.5 Хранение данных аддона

Undo-журналы сохраняются в:
```
special://profile/addon_data/script.library.organizer/undo/
```

Kodi транслирует `special://profile/` в:
- Windows: `%APPDATA%\Kodi\userdata\`
- Linux: `~/.kodi/userdata/`
- Android: `/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi/userdata/`
- macOS: `~/Library/Application Support/Kodi/userdata/`

Для получения реального пути: `xbmcvfs.translatePath("special://profile/addon_data/script.library.organizer/undo/")`.

---

## 7. Решения и альтернативы

### 7.1 xbmcvfs vs os/shutil

| Критерий | xbmcvfs | os/shutil |
|---|---|---|
| SMB/NFS | Работает | Не работает |
| Скорость (локальные) | Медленнее (через Kodi VFS layer) | Быстрее (прямой syscall) |
| Атомарный rename | `xbmcvfs.rename()` -- не гарантирует атомарность | `os.rename()` -- атомарный на одном томе |
| copy с метаданными | Нет (только данные) | `shutil.copy2()` (timestamps, permissions) |
| disk_usage | Нет прямого аналога | `shutil.disk_usage()` |

**Решение:** гибридный подход.
- Сетевые пути (`smb://`, `nfs://` и т.д.): только xbmcvfs.
- Локальные пути: os/shutil для критичных операций (rename, disk_usage, stat), xbmcvfs для совместимости (mkdir, exists).
- Определение типа пути через `is_network_path()`.

**Обоснование:** чистый xbmcvfs не даёт атомарного rename и проверки диска. Чистый os не работает с сетевыми путями. Гибрид покрывает оба сценария.

### 7.2 JSON vs SQLite для undo-журнала

| Критерий | JSON | SQLite |
|---|---|---|
| Зависимости | Нет (json в stdlib) | sqlite3 в stdlib, но файл БД -- сложнее |
| Человекочитаемость | Да | Нет |
| Сценарий | Write-once, read-once | Частые read/write |
| Размер | Десятки KB | Избыточен |
| Атомарность | Запись целиком | Транзакции |
| Миграция формата | Версионирование в JSON | ALTER TABLE |

**Решение:** JSON. Журнал пишется один раз (при организации) и читается один раз (при откате). Нет concurrent access, нет сложных запросов.

### 7.3 Плоское сканирование (не рекурсивное) для MVP

Рекурсивное сканирование добавляет сложность:
- Как определить, какие подпапки -- это "уже организованные фильмы", а какие -- мусор?
- Как обрабатывать вложенные VIDEO_TS/BDMV?
- Как не сломать уже существующую per-folder структуру?

**Решение:** для MVP только плоский scan. Покрывает основной use case (плоская библиотека). Рекурсия -- отдельная задача (BL-04).

### 7.4 Dry-run по умолчанию

**Решение:** `dry_run = true` по умолчанию.

**Обоснование:** операция перемещения файлов потенциально деструктивна. Пользователь ДОЛЖЕН видеть превью перед реальным выполнением. Это предотвращает случайные потери данных и повышает доверие к аддону. Даже при `dry_run = false` в настройках, превью всё равно показывается (через format_preview), но с кнопкой "Выполнить" вместо только "OK".

### 7.5 Callback-архитектура для UI-интеграции

**Альтернатива 1:** organizer.py напрямую вызывает xbmcgui для диалогов.
- Минус: tight coupling, невозможно тестировать без Kodi, невозможно подключить CLI.

**Альтернатива 2:** organizer.py возвращает промежуточные результаты, main.py решает.
- Минус: сложнее для конфликтов (нужно останавливать и возобновлять операцию).

**Решение:** callback-функции. organizer.py получает callback и вызывает его. main.py реализует callback через xbmcgui. В тестах -- mock-callback. Для будущего CLI -- callback через stdin/stdout.

### 7.6 reuselanguageinvoker = false

В kodi_metadata_scraper используется `true` (scraper вызывается часто, важна скорость).

Для Library Organizer: `false`. Обоснование:
- Аддон запускается редко (раз в месяц / год).
- Каждый запуск -- отдельная тяжёлая операция.
- Чистый Python-процесс = нет утечек памяти, нет stale state.
- Нет выигрыша от reuse.

---

## Приложение A. Полная таблица расширений видеофайлов

| Расширение | Формат |
|---|---|
| .mkv | Matroska |
| .avi | AVI |
| .mp4 | MPEG-4 |
| .m4v | MPEG-4 Video (Apple) |
| .mov | QuickTime |
| .wmv | Windows Media Video |
| .flv | Flash Video |
| .ts | MPEG Transport Stream |
| .m2ts | Blu-ray Transport Stream |
| .vob | DVD Video Object |
| .divx | DivX |
| .mpg | MPEG |
| .mpeg | MPEG |
| .ogm | Ogg Media |
| .webm | WebM |
| .3gp | 3GPP |

Набор выбран на основе расширений, которые Kodi v20+ поддерживает нативно. Исключены: ISO, VIDEO_TS, BDMV (disc images -- out of scope).

## Приложение B. Диаграмма состояний операции

```
                    +--------+
                    | IDLE   |
                    +---+----+
                        |
                  scan_directory()
                        |
                    +---v----+
                    |SCANNED |
                    +---+----+
                        |
                  build_plan()
                        |
                    +---v----+
                    |PLANNED |----> format_preview() ----> [textviewer]
                    +---+----+
                        |
                  user confirms
                        |
                    +---v-------+
                    |EXECUTING  |----> progress_callback()
                    +---+---+---+
                        |   |
                   success  cancel/error
                        |   |
                 +------v-+ +--v-------+
                 | DONE   | | PARTIAL  |
                 +--------+ +----------+
                    |           |
              (оба сохраняют undo journal)
```

## Приложение C. Sequence для отката

```
main.py             undo_journal.py       xbmcvfs/os
  |                       |                    |
  |--get_latest_journal-->|                    |
  |<--path or None--------|                    |
  |                       |                    |
  |--load_journal(path)-->|                    |
  |<--UndoJournal---------|                    |
  |                       |                    |
  |  [показать сводку, подтверждение]          |
  |                       |                    |
  |--execute_undo(journal, callback)---------->|
  |                       |                    |
  |  [для каждой entry с success=True:]        |
  |                       |  if mode=move:     |
  |                       |  rename(dest,src)  |-->
  |                       |  if mode=copy:     |
  |                       |  delete(dest)      |-->
  |                       |                    |
  |  [для каждой папки в folders_created:]     |
  |                       |  if empty:         |
  |                       |  rmdir(folder)     |-->
  |                       |                    |
  |  [journal.undone=True]|                    |
  |  [save_journal()]     |                    |
  |<--OperationResult-----|                    |
```
