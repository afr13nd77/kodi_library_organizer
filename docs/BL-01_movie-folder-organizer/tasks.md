# BL-01: Task Breakdown — Реорганизация фильмотеки в per-folder

**Статус:** done (27.08.2026)
**Дата:** 27.08.2026

---

## Граф зависимостей

```
T-01 (file_patterns) ──┬──→ T-03 (name_parser) ──┬──→ T-05 (scanner) ──→ T-07 (organizer) ──→ T-09 (main.py)
                       │                          │                       ↑
T-02 (logger) ─────────┼──────────────────────────┘                       │
                       │                                                  │
                       └──→ T-04 (undo_journal) ──────────────────────────┘

T-06 (addon files) ──────────────────────────────────────────────────────→ T-09 (main.py)
                   └──→ T-10 (build_zip.py)

T-11 (ruff, CI) ← после всех задач с кодом
T-12 (README) ← последняя
```

## Параллельные группы

- **Группа 1** [P]: T-01, T-02, T-06 — независимы, запускаются параллельно
- **Группа 2** [P]: T-03, T-04 — после T-01, T-02, параллельно между собой
- **Группа 3**: T-05 — после T-01, T-02, T-03
- **Группа 4**: T-07 — после T-05, T-04
- **Группа 5**: T-09 — после T-07, T-06
- **Группа 6** [P]: T-10, T-08 — после T-06 (T-10 — после T-06; T-08 — после T-06)
- **Группа 7** [P]: T-11, T-12 — после всего кода

---

## Задачи

### T-01 [sonnet] — shared/file_patterns.py + тесты

```
Traces to: AC-02, AC-03, AC-13, AC-14, AC-16
File: kodi_library_organizer/shared/file_patterns.py
      kodi_library_organizer/shared/__init__.py
      kodi_library_organizer/shared/tests/__init__.py
      kodi_library_organizer/shared/tests/test_file_patterns.py
Task: Создать модуль констант и паттернов.
Context: Центральное хранилище расширений и regex. Используется scanner.py и name_parser.py.
         Нет бизнес-логики — только данные. Python 3.8, from __future__ import annotations.

Содержимое (из design.md раздел 1.3):
- VIDEO_EXTENSIONS: frozenset — 16 расширений (.mkv, .avi, .mp4, .m4v, .mov, .wmv, .flv, .ts, .m2ts, .vob, .divx, .mpg, .mpeg, .ogm, .webm, .3gp)
- SUBTITLE_EXTENSIONS: frozenset — 7 расширений (.srt, .sub, .ssa, .ass, .idx, .sup, .vtt)
- ARTWORK_EXTENSIONS: frozenset — 7 расширений (.jpg, .jpeg, .png, .tbn, .gif, .bmp, .webp)
- METADATA_EXTENSIONS: frozenset — 1 расширение (.nfo)
- ASSOCIATED_EXTENSIONS: frozenset — объединение субтитров + артворк + метаданные
- MULTIPART_PATTERN: re.Pattern — regex для CD1/CD2, Part1/Part2, Disc1/Disc2
  Regex: r'^(.+?)[._\- ]+(?:cd|disc|disk|part|pt)[._\- ]*(\d+)(.*)$' (IGNORECASE)
- QUALITY_TAGS: frozenset — ~40 тегов (1080p, 720p, BDRip, WEB-DL, x264, x265, AAC, DTS, BluRay и т.д.)
  Полный список в design.md раздел 1.3.

Тесты:
- VIDEO_EXTENSIONS содержит все 16 расширений, все с точкой, все lowercase
- MULTIPART_PATTERN матчит: "Movie.Name.CD1.avi" → base="Movie.Name", part=1
- MULTIPART_PATTERN матчит: "Movie_Name_disc2.mkv" → base="Movie_Name", part=2
- MULTIPART_PATTERN матчит: "Movie-pt1.avi" → base="Movie", part=1
- MULTIPART_PATTERN НЕ матчит: "Movie.Name.2014.mkv"
- QUALITY_TAGS содержит "1080p", "BDRip", "WEB-DL", "x264"
- ASSOCIATED_EXTENSIONS = SUBTITLE_EXTENSIONS | ARTWORK_EXTENSIONS | METADATA_EXTENSIONS

Depends on: нет
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_file_patterns.py -v
Live test: python -c "from shared.file_patterns import VIDEO_EXTENSIONS, MULTIPART_PATTERN; print(len(VIDEO_EXTENSIONS)); import re; print(MULTIPART_PATTERN.match('Movie.CD1.avi').groups())"
Status: [ ] pending
```

---

### T-02 [sonnet] — shared/logger.py + тесты

```
Traces to: Blocking rule #1 (логирование обязательно)
File: kodi_library_organizer/shared/logger.py
      kodi_library_organizer/shared/tests/test_logger.py
Task: Создать модуль логирования.
Context: Адаптация Logger из kodi_metadata_scraper, упрощённая версия (без санитизации API-ключей).
         Должен работать И в Kodi (xbmc.log), И без Kodi (print/logging для тестов).
         Python 3.8, from __future__ import annotations. Только f-strings, один аргумент.

Public API (из design.md раздел 1.3):
- class Logger:
    - __init__(self, debug_enabled: bool = False)
    - debug(self, message: str) → xbmc.LOGDEBUG (только при debug_enabled)
    - info(self, message: str) → xbmc.LOGINFO
    - warning(self, message: str) → xbmc.LOGWARNING
    - error(self, message: str) → xbmc.LOGERROR

Важно:
- try/except ImportError для xbmc — fallback на print() для тестов
- Prefix: "[LibOrganizer] " перед каждым сообщением
- debug_enabled проверяется ТОЛЬКО для debug(), остальные уровни всегда активны

Тесты (mock xbmc):
- Logger(debug_enabled=False).debug("msg") — не вызывает print/log
- Logger(debug_enabled=True).debug("msg") — вызывает
- Logger().info("msg") — всегда вызывает
- Logger().error("msg") — всегда вызывает
- Prefix "[LibOrganizer] " присутствует в выводе

Depends on: нет
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_logger.py -v
Live test: cd kodi_library_organizer && python -c "from shared.logger import Logger; l = Logger(debug_enabled=True); l.info('test info'); l.debug('test debug'); l.error('test error')"
Status: [ ] pending
```

---

### T-03 [sonnet] — shared/name_parser.py + тесты

```
Traces to: US-05, AC-13, AC-14, AC-15, AC-16
File: kodi_library_organizer/shared/name_parser.py
      kodi_library_organizer/shared/tests/test_name_parser.py
Task: Создать модуль парсинга имён видеофайлов → название + год.
Context: Используется scanner.py для генерации имён папок.
         Алгоритм из design.md раздел 3.2, 7 шагов.
         Python 3.8, from __future__ import annotations.

Public API:
- @dataclass ParsedName:
    - title: str — название фильма
    - year: int | None — год или None
    - clean_folder_name: str — готовое имя папки
    - raw_name: str — исходное имя без расширения

- def parse_name(filename: str) -> ParsedName
  filename — имя файла БЕЗ расширения

Алгоритм parse_name() (design.md раздел 3.2):
1. Сохранить raw_name = filename
2. Заменить . _ - на пробелы
3. Найти ПОСЛЕДНИЙ год (regex r'\b((?:19|20)\d{2})\b'), title = всё ДО года
4. Очистить от QUALITY_TAGS (из file_patterns.py)
5. Обрезать trailing мусор (пробелы, дефисы, точки, пустые скобки)
6. clean_folder_name: "{title} ({year})" или просто "{title}"
7. Санитизация: убрать < > : " / \ | ? *, trailing точки/пробелы, limit 200 символов

Тесты (таблица из design.md раздел 3.2):
| Вход                                  | title                 | year | clean_folder_name          |
| Interstellar.2014.1080p.BDRip.x264    | Interstellar          | 2014 | Interstellar (2014)        |
| Dune.Part.Two.2024.WEB-DL             | Dune Part Two         | 2024 | Dune Part Two (2024)       |
| The.Matrix.1999.REMASTERED.BluRay     | The Matrix            | 1999 | The Matrix (1999)          |
| some_random_movie                     | some random movie     | None | some random movie          |
| 2001.A.Space.Odyssey.1968.BDRip       | 2001 A Space Odyssey  | 1968 | 2001 A Space Odyssey (1968)|
| Movie (2020) [1080p]                  | Movie                 | 2020 | Movie (2020)               |

Дополнительные тесты:
- Кириллица: "Брат.1997.DVDRip" → title="Брат", year=1997
- Спецсимволы: 'Movie: The Sequel.2020' → clean_folder_name без ":"
- Пустой title после очистки → fallback на raw_name
- Длинное имя > 200 символов → обрезка до 200

Depends on: T-01 (file_patterns.py — QUALITY_TAGS)
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_name_parser.py -v
Live test: cd kodi_library_organizer && python -c "from shared.name_parser import parse_name; r = parse_name('Interstellar.2014.1080p.BDRip.x264'); print(f'{r.title} | {r.year} | {r.clean_folder_name}')"
Status: [✓] done (27.08.2026)
```

---

### T-04 [sonnet] — shared/undo_journal.py + тесты

```
Traces to: US-04, AC-10, AC-11, AC-12
File: kodi_library_organizer/shared/undo_journal.py
      kodi_library_organizer/shared/tests/test_undo_journal.py
Task: Создать модуль журнала операций для отката.
Context: Записывает каждую файловую операцию в JSON. Позволяет откатить.
         Формат JSON Schema из design.md раздел 2.2.
         Хранится в special://profile/addon_data/script.library.organizer/undo/
         Python 3.8, from __future__ import annotations.

Public API (из design.md раздел 1.3):
- @dataclass UndoEntry:
    - source_path: str
    - destination_path: str
    - operation: str ("move" / "copy")
    - file_size_bytes: int
    - success: bool

- @dataclass UndoJournal:
    - timestamp: str (ISO-8601)
    - source_dir: str
    - destination_dir: str
    - operation_mode: str ("move" / "copy")
    - entries: list[UndoEntry]
    - folders_created: list[str]
    - completed: bool
    - undone: bool

- def save_journal(journal: UndoJournal, file_path: str) -> None
  Добавляет "version": 1 при сериализации.

- def load_journal(file_path: str) -> UndoJournal
  Raises: FileNotFoundError, json.JSONDecodeError, KeyError

- def get_latest_journal(journal_dir: str) -> str | None
  Находит последний неиспользованный (undone=False) журнал.

- def execute_undo(journal: UndoJournal, progress_callback=None) -> OperationResult
  Для move: rename(dest, src). Для copy: delete(dest).
  Удаляет пустые папки из folders_created.
  Помечает journal.undone = True, сохраняет.
  
  OperationResult — импортировать нельзя (circular dependency с organizer.py).
  Решение: определить простой OperationResult прямо в undo_journal.py:
  @dataclass UndoResult:
    - success_count: int
    - error_count: int
    - total_count: int
    - errors: list[str]

Важно:
- Логирование каждой операции (logger.py)
- try/except для каждого файлового действия при откате
- Файлы которых нет при откате → warning, не error (AC-12)
- Формат имени файла журнала: undo_YYYYMMDD_HHMMSS.json

Тесты:
- save_journal → load_journal → roundtrip, все поля сохранены
- get_latest_journal: 3 файла, 2 undone=True, 1 undone=False → возвращает последний с undone=False
- get_latest_journal: все undone=True → возвращает None
- get_latest_journal: пустая директория → None
- execute_undo для mode=move: файлы перемещены обратно
- execute_undo для mode=copy: файлы в destination удалены
- execute_undo: файл отсутствует в destination → warning в errors, не crash
- execute_undo: пустые папки удалены после отката
- version=1 в JSON

Depends on: T-02 (logger.py)
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_undo_journal.py -v
Live test: cd kodi_library_organizer && python -c "
from shared.undo_journal import UndoJournal, UndoEntry, save_journal, load_journal
import tempfile, os
j = UndoJournal(timestamp='2026-08-27T14:00:00', source_dir='/src', destination_dir='/dst', operation_mode='move', entries=[], folders_created=[], completed=True, undone=False)
p = os.path.join(tempfile.gettempdir(), 'test_undo.json')
save_journal(j, p)
j2 = load_journal(p)
print(f'loaded: {j2.timestamp}, undone={j2.undone}')
os.unlink(p)
"
Status: [ ] pending
```

---

### T-05 [opus] — shared/scanner.py + тесты

```
Traces to: US-01, AC-01, AC-02, AC-03, AC-15
File: kodi_library_organizer/shared/scanner.py
      kodi_library_organizer/shared/tests/test_scanner.py
      kodi_library_organizer/shared/tests/fixtures/ (тестовые данные)
Task: Создать модуль сканирования директории и группировки файлов.
Context: Ядро логики — находит видеофайлы, группирует со связанными файлами (субтитры, NFO, артворк).
         Алгоритм из design.md раздел 3.1, 7 шагов.
         Использует file_patterns.py (расширения, MULTIPART_PATTERN), name_parser.py (parse_name), logger.py.
         Python 3.8, from __future__ import annotations.
         Работает без Kodi (os.listdir для тестов), с Kodi — xbmcvfs.listdir.

Public API (из design.md раздел 1.3):
- @dataclass MovieFile:
    - filename: str
    - full_path: str
    - size_bytes: int
    - extension: str

- @dataclass MovieGroup:
    - video_files: list[MovieFile] (1 для обычного, 2+ для multi-part)
    - associated_files: list[MovieFile]
    - parsed_name: ParsedName
    - base_name: str

- @dataclass ScanResult:
    - groups: list[MovieGroup]
    - skipped_files: list[MovieFile]
    - unmatched_files: list[MovieFile]
    - total_size_bytes: int

- def scan_directory(source_path, min_file_size_bytes, handle_multipart, clean_names) -> ScanResult

Алгоритм (design.md 3.1):
1. Листинг файлов (os.listdir fallback, xbmcvfs.listdir если доступен)
2. Классификация по расширению (VIDEO / ASSOCIATED / unmatched)
3. Фильтрация видео по min_file_size_bytes → skipped_files
4. Multi-part группировка через MULTIPART_PATTERN (если handle_multipart=True)
5. Привязка associated файлов по longest-prefix match базового имени видео
6. Парсинг имён через parse_name() (если clean_names=True, иначе raw_name)
7. Формирование ScanResult

Тесты (создать temp-директорию с файлами через fixtures):
- 3 видео + по 1 субтитру каждому → 3 группы, каждая с 1 associated
- Видео + 3 субтитры (.srt, .sub, .ass) + NFO + 2 артворка → 1 группа с 6 associated (AC-02)
- Файл 45MB при min_size=100MB → в skipped_files (AC-03)
- CD1 + CD2 + общий .srt → 1 группа с 2 video_files (multi-part)
- handle_multipart=False → CD1 и CD2 как отдельные группы
- Пустая директория → ScanResult с пустыми списками
- Только .srt файлы (нет видео) → всё в unmatched_files
- clean_names=True → parsed_name.clean_folder_name нормализован
- clean_names=False → parsed_name.clean_folder_name = raw базовое имя
- Символьная ссылка → пропускается с warning (если на Windows — можно skip этот тест)
- total_size_bytes считает только файлы в groups

Depends on: T-01 (file_patterns), T-02 (logger), T-03 (name_parser)
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_scanner.py -v
Live test: cd kodi_library_organizer && python -c "
from shared.scanner import scan_directory
# Создаём temp-директорию с фейковыми файлами для теста
import tempfile, os
d = tempfile.mkdtemp()
# Создаём файлы > 100MB невозможно быстро, используем min_size=0
for f in ['Movie.2020.mkv', 'Movie.2020.srt', 'Other.2021.avi']:
    open(os.path.join(d, f), 'w').close()
r = scan_directory(d, min_file_size_bytes=0, handle_multipart=True, clean_names=True)
for g in r.groups:
    print(f'{g.parsed_name.clean_folder_name}: {len(g.video_files)} video, {len(g.associated_files)} assoc')
import shutil; shutil.rmtree(d)
"
Status: [ ] pending
```

---

### T-06 [sonnet] — Kodi addon scaffold: addon.xml + settings.xml + language files

```
Traces to: design.md раздел 6.1, 6.3, 6.4
File: kodi_library_organizer/script.library.organizer/addon.xml
      kodi_library_organizer/script.library.organizer/resources/settings.xml
      kodi_library_organizer/script.library.organizer/resources/language/resource.language.en_gb/strings.po
      kodi_library_organizer/script.library.organizer/resources/language/resource.language.ru_ru/strings.po
      kodi_library_organizer/script.library.organizer/LICENSE.txt
      kodi_library_organizer/script.library.organizer/python/__init__.py
Task: Создать Kodi addon scaffold — манифест, настройки, локализация.
Context: Тип аддона xbmc.python.script. Формат settings v1.
         addon.xml — полный текст в design.md раздел 6.1.
         settings.xml — полный текст в design.md раздел 2.3.
         Label IDs — таблица в design.md раздел 2.3.
         LICENSE.txt — MIT (аналогично kodi_metadata_scraper).

addon.xml:
- id="script.library.organizer"
- version="1.0.0"
- provider-name="kodi_library_organizer"
- requires: xbmc.python 3.0.1
- extension point: xbmc.python.script, library="python/main.py"
- provides: executable
- reuselanguageinvoker: false
- summary/description на en_GB и ru_RU
- assets: icon.png, fanart.jpg

settings.xml (9 настроек, 3 категории):
- general: source_directory, destination_directory, operation_mode, dry_run
- naming: clean_names
- advanced: min_file_size_mb, handle_multipart, undo_enabled, debug_logging

strings.po: все 24 label ID из таблицы (30100-30332), en_GB и ru_RU

Depends on: нет
Verify: python -c "import xml.etree.ElementTree as ET; tree = ET.parse('kodi_library_organizer/script.library.organizer/addon.xml'); print(tree.getroot().attrib['id'], tree.getroot().attrib['version'])"
Live test: Проверить что XML валиден, все label ID присутствуют в strings.po
Status: [✓] done (27.08.2026)
```

---

### T-07 [opus] — shared/organizer.py + тесты

```
Traces to: US-01, US-02, US-03, AC-01, AC-04, AC-05, AC-06, AC-07, AC-08, AC-09
File: kodi_library_organizer/shared/organizer.py
      kodi_library_organizer/shared/tests/test_organizer.py
Task: Создать центральный модуль — планирование и выполнение файловых операций.
Context: Самый сложный модуль. Формирует план из ScanResult, выполняет move/copy с callback-ами.
         Design.md разделы 1.3 (API), 3.4 (конфликт-резолюция), 4.3 (format_preview),
         5.1 (disk space), 5.2 (атомарность), 5.4 (сетевые пути).
         Python 3.8, from __future__ import annotations.

Public API (из design.md раздел 1.3):
- enum OperationMode: MOVE, COPY
- enum ConflictResolution: SKIP, MERGE, RENAME
- enum FileConflictResolution: SKIP, OVERWRITE, RENAME

- @dataclass PlannedOperation:
    - source_path, destination_path, is_video, file_size_bytes

- @dataclass PlannedGroup:
    - folder_name, operations: list[PlannedOperation], parsed_name

- @dataclass OperationPlan:
    - mode, source_dir, destination_dir, groups: list[PlannedGroup],
      skipped_files, total_files, total_size_bytes

- @dataclass OperationResult:
    - success_count, error_count, skipped_count, total_count,
      errors: list[str], was_cancelled: bool

- ProgressCallback = Callable[[int, int, str], bool]
- FolderConflictCallback = Callable[[str], ConflictResolution]
- FileConflictCallback = Callable[[str], FileConflictResolution]

Функции:
- build_plan(scan_result, destination_dir, mode) -> OperationPlan
  Для каждой группы: folder_name = group.parsed_name.clean_folder_name,
  operations = видеофайлы + associated файлы с destination_path.

- format_preview(plan) -> str
  Текстовый формат из design.md раздел 4.3.
  Форматирование размеров: B/KB/MB/GB.
  Секции: заголовок, фильмы, пропущенные, предупреждения, итого.

- execute_plan(plan, undo_journal_path, progress_callback=None,
               folder_conflict_callback=None, file_conflict_callback=None) -> OperationResult
  Для каждой группы:
    1. Проверить/создать папку (xbmcvfs.mkdirs или os.makedirs)
    2. Для каждой операции: move (os.rename / copy+delete) или copy (xbmcvfs.copy / shutil.copy2)
    3. Записывать в undo-журнал
    4. Вызывать progress_callback, прервать если вернул False
  При конфликте папки → folder_conflict_callback (default: MERGE)
  При конфликте файла → file_conflict_callback (default: SKIP)

- check_disk_space(destination_dir, required_bytes) -> bool
  shutil.disk_usage с запасом 5% или 100MB.
  Для сетевых путей → True (warning).

- is_network_path(path) -> bool
  Проверка по префиксу smb://, nfs://, ftp://, sftp://, upnp://.

Валидация путей (design.md 5.5):
- source_path == destination_path → ошибка (AC-04)
- destination подпапка source → ошибка

Тесты (через temp-директории с реальными файлами):
- build_plan: 2 группы → OperationPlan с 2 PlannedGroup
- format_preview: формат содержит имена фильмов, размеры, итого
- execute_plan (mode=MOVE): файлы перемещены, source пуст
- execute_plan (mode=COPY): файлы в обоих местах
- execute_plan с cancel: was_cancelled=True, часть файлов перемещена
- execute_plan с конфликтом папки (SKIP): группа пропущена
- execute_plan с конфликтом папки (MERGE): файлы добавлены
- execute_plan с конфликтом папки (RENAME): папка переименована _2
- source == destination → ValueError (AC-04)
- check_disk_space: достаточно места → True
- is_network_path: "smb://server/share" → True, "/local/path" → False
- Undo-журнал создан после execute_plan
- Размеры в format_preview корректно форматируются (KB, MB, GB)

Depends on: T-01 (file_patterns), T-02 (logger), T-04 (undo_journal), T-05 (scanner — dataclasses)
Verify: cd kodi_library_organizer && python -m pytest shared/tests/test_organizer.py -v
Live test: cd kodi_library_organizer && python -c "
from shared.scanner import scan_directory
from shared.organizer import build_plan, format_preview, OperationMode
import tempfile, os
# Создаём source с фейковыми файлами
src = tempfile.mkdtemp()
dst = tempfile.mkdtemp()
for f in ['Movie.2020.mkv', 'Movie.2020.srt']:
    open(os.path.join(src, f), 'w').close()
result = scan_directory(src, 0, True, True)
plan = build_plan(result, dst, OperationMode.MOVE)
print(format_preview(plan))
import shutil; shutil.rmtree(src); shutil.rmtree(dst)
"
Status: [ ] pending
```

---

### T-08 [sonnet] — build_zip.py

```
Traces to: design.md раздел 6.3
File: kodi_library_organizer/build_zip.py
Task: Создать скрипт сборки ZIP-пакета аддона.
Context: Адаптация build_zip.py из kodi_metadata_scraper.
         Один аддон (не два как в scraper). Копирует shared/*.py в addon/python/.
         Исключает tests/, __pycache__, .pytest_cache, .pyc.

Конфигурация:
ADDONS = [
    {"addon_dir": "script.library.organizer", "archive_root": "script.library.organizer"},
]

Алгоритм (идентичен kodi_metadata_scraper):
1. Парсинг версии из addon.xml
2. Удаление старого ZIP
3. Walk addon_dir, исключая tests/__pycache__/.pytest_cache/.pyc
4. Копирование shared/*.py в {archive_root}/python/
5. Отчёт: имя, версия, количество файлов, размер KB

Зависимости: xml.etree.ElementTree, zipfile, os — только stdlib.

Depends on: T-06 (addon.xml должен существовать для парсинга версии)
Verify: cd kodi_library_organizer && python build_zip.py
Live test: python build_zip.py && python -c "
import zipfile
z = zipfile.ZipFile('kodi_library_organizer/script.library.organizer-1.0.0.zip')
names = z.namelist()
print(f'Files in ZIP: {len(names)}')
assert any('python/file_patterns.py' in n for n in names), 'shared modules missing'
print('OK: shared modules found in ZIP')
"
Status: [✓] done (27.08.2026)
```

---

### T-09 [opus] — main.py (Kodi UI точка входа)

```
Traces to: US-01, US-02, US-03, US-04, US-05, FLOW-01..05, AC-04, AC-05, AC-06
File: kodi_library_organizer/script.library.organizer/python/main.py
      kodi_library_organizer/script.library.organizer/tests/__init__.py
      kodi_library_organizer/script.library.organizer/tests/test_main.py
Task: Создать точку входа Kodi-аддона — UI и связку с shared-модулями.
Context: Связывает Kodi UI (диалоги) с бизнес-логикой из shared/.
         Содержит ТОЛЬКО UI-логику, без бизнес-логики.
         Design.md раздел 4 (Kodi UI), раздел 1.3 (main.py API).
         Python 3.8, from __future__ import annotations.

Структура (design.md 4.1-4.4):
- main() → show_main_menu()
- show_main_menu(): Dialog.select → 3 пункта (Организовать / Откатить / Настройки)
- run_organize():
    1. Читать настройки через xbmcaddon.Addon()
    2. Если source/destination не заданы → Dialog.browseSingle для выбора
    3. Валидация (source != dest, оба существуют)
    4. scan_directory() с параметрами из настроек
    5. Если groups пустой → Dialog.ok("Нет видеофайлов")
    6. build_plan()
    7. format_preview() → Dialog.textviewer()
    8. Dialog.yesno("Выполнить?")
    9. check_disk_space() для Copy
    10. DialogProgress → execute_plan() с callbacks
    11. Dialog.ok с результатами
- run_undo():
    1. get_latest_journal()
    2. Если None → Dialog.ok("Нет операций для отката")
    3. load_journal() → Dialog.yesno с информацией
    4. DialogProgress → execute_undo() с callback
    5. Dialog.ok с результатами
- _progress_callback(): DialogProgress.update + iscanceled()
- _folder_conflict_callback(): Dialog.yesnocustom (Skip/Merge/Rename)
- _file_conflict_callback(): Dialog.yesnocustom (Skip/Overwrite/Rename)

Путь к undo-журналам:
  xbmcvfs.translatePath("special://profile/addon_data/script.library.organizer/undo/")

Логирование: Logger(debug_enabled=settings.debug_logging)
Каждый шаг flow логируется.

Тесты (mock xbmc, xbmcgui, xbmcaddon, xbmcvfs):
- show_main_menu: choice=0 → вызван run_organize
- show_main_menu: choice=1 → вызван run_undo
- show_main_menu: choice=2 → вызван openSettings
- show_main_menu: choice=-1 → ничего не вызвано
- run_organize: source == dest → Dialog.ok с ошибкой, операция не выполняется
- run_organize: пустая директория → Dialog.ok "Нет видеофайлов"
- run_undo: нет журнала → Dialog.ok "Нет операций"

Depends on: T-05 (scanner), T-04 (undo_journal), T-07 (organizer), T-06 (addon.xml)
Verify: cd kodi_library_organizer && python -m pytest script.library.organizer/tests/test_main.py -v
Live test: Установить ZIP в Kodi → открыть из Programs → проверить меню
Status: [ ] pending
```

---

### T-10 [sonnet] — Инфраструктура: ruff.toml, requirements.txt, CI

```
Traces to: index.md (команды), аналогия с kodi_metadata_scraper
File: kodi_library_organizer/ruff.toml
      kodi_library_organizer/requirements.txt
      kodi_library_organizer/.github/workflows/ci.yml
Task: Создать конфигурацию линтера, зависимости для тестов, CI pipeline.
Context: По аналогии с kodi_metadata_scraper.

ruff.toml:
- target-version = "py38"
- line-length = 120
- select = ["E", "F", "W"]

requirements.txt:
- pytest>=7.0
- ruff

CI pipeline (.github/workflows/ci.yml):
- trigger: push + pull_request
- jobs:
    1. lint: ruff check (Python 3.8)
    2. test: pytest shared/tests/ + script.library.organizer/tests/ (Python 3.8)
    3. build: python build_zip.py, upload-artifact

Depends on: T-06 (addon файлы должны существовать для build)
Verify: cd kodi_library_organizer && ruff check .
Live test: cd kodi_library_organizer && python -m pytest shared/tests/ script.library.organizer/tests/ -v
Status: [ ] pending
```

---

### T-11 [haiku] — README.md

```
Traces to: blocking rule #6 (документация)
File: kodi_library_organizer/README.md
Task: Создать README проекта на русском языке.
Context: По аналогии с kodi_metadata_scraper/README.md.

Содержимое:
- Название и описание (что делает аддон)
- Скриншоты (placeholder — TODO)
- Установка (скачать ZIP, установить через Kodi → Install from zip file)
- Использование (пошаговый flow)
- Настройки (таблица всех 9 параметров)
- FAQ (что делать после организации — обновить источники в Kodi)
- Сборка из исходников (build_zip.py)
- Тестирование (pytest)
- Лицензия (MIT)

Depends on: все задачи завершены (чтобы описание было актуальным)
Verify: файл README.md существует и не пустой
Live test: N/A (документация)
Status: [ ] pending
```

---

### T-12 [haiku] — Обновление CHANGELOG.md и BACKLOG.md

```
Traces to: blocking rule (обновление документации после задач)
File: kodi_library_organizer/CHANGELOG.md
      kodi_library_organizer/BACKLOG.md
      kodi_library_organizer/index.md
Task: Обновить документацию проекта после завершения всех задач.
Context: CHANGELOG — добавить записи v1.0.0 с перечнем всего реализованного.
         BACKLOG — пометить BL-01 как [✓] done.
         index.md — обновить счётчики файлов, статус проекта.

Depends on: все задачи T-01..T-11 завершены
Verify: grep -q "✓" kodi_library_organizer/BACKLOG.md
Live test: N/A (документация)
Status: [ ] pending
```

---

## Сводка

| ID | Агент | Модуль | Зависимости | Статус |
|---|---|---|---|---|
| T-01 | sonnet | shared/file_patterns.py | — | [✓] done (27.08.2026) |
| T-02 | sonnet | shared/logger.py | — | [✓] done (27.08.2026) |
| T-03 | sonnet | shared/name_parser.py | T-01 | [✓] done (27.08.2026) |
| T-04 | sonnet | shared/undo_journal.py | T-02 | [✓] done (27.08.2026) |
| T-05 | opus | shared/scanner.py | T-01, T-02, T-03 | [✓] done (27.08.2026) |
| T-06 | sonnet | addon.xml + settings + lang | — | [✓] done (27.08.2026) |
| T-07 | opus | shared/organizer.py | T-01, T-02, T-04, T-05 | [✓] done (27.08.2026) |
| T-08 | sonnet | build_zip.py | T-06 | [✓] done (27.08.2026) |
| T-09 | opus | main.py (Kodi UI) | T-05, T-04, T-07, T-06 | [✓] done (27.08.2026) |
| T-10 | sonnet | ruff + CI | T-06 | [✓] done (27.08.2026) |
| T-11 | haiku | README.md | все | [✓] done (27.08.2026) |
| T-12 | haiku | CHANGELOG + BACKLOG | все | [✓] done (27.08.2026) |

**Итого:** 12 задач (4 opus, 6 sonnet, 2 haiku)
