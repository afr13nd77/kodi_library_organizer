# BL-10 — Tasks: Добавление года в имя файла

## T-01 — Хелпер и параметр rename_files в build_plan

- **Agent**: opus
- **Traces to**: US-01, AC-01, AC-02, AC-03, AC-04, AC-05
- **Files**: `shared/organizer.py`
- **Task**:
  1. Добавить приватный хелпер `_add_year_to_filename(filename: str, year: int) -> str`
  2. Добавить параметр `rename_files: bool = False` в `build_plan()`
  3. В цикле формирования operations: если `rename_files=True` и `group.parsed_name.year is not None`, применить хелпер к filename перед построением dest_path
  4. Применить к ОБОИМ циклам: video_files и associated_files
- **Depends on**: нет
- **Status**: [✓] done

## T-02 — Настройка rename_files в settings.xml и strings.po

- **Agent**: opus
- **Traces to**: US-02, AC-03
- **Files**: `script.library.organizer/resources/settings.xml`, `resources/language/resource.language.en_gb/strings.po`, `resources/language/resource.language.ru_ru/strings.po`
- **Task**:
  1. В settings.xml: добавить toggle `rename_files` (type=boolean, default=true) в категорию naming, группу naming_options, после clean_names. Label=30129, help=30130
  2. В en_gb strings.po: добавить 30129="Add year to filenames", 30130="Insert year before file extension when missing"
  3. В ru_ru strings.po: добавить 30129="Добавлять год в имена файлов", 30130="Вставлять год перед расширением, если отсутствует"
- **Depends on**: нет
- **Status**: [✓] done

## T-03 — Передача rename_files из main.py в build_plan

- **Agent**: opus
- **Traces to**: US-02, AC-03
- **File**: `script.library.organizer/python/main.py`
- **Task**:
  1. В path confirmation loop (рядом с другими settings): добавить чтение `rename_files = addon.getSettingBool("rename_files")`
  2. В вызове `build_plan()` (строка ~324): передать `rename_files=rename_files`
  3. Добавить `rename_files` в лог-строку settings
- **Depends on**: T-01
- **Status**: [✓] done

## T-04 — Тесты для _add_year_to_filename и build_plan с rename_files

- **Agent**: sonnet
- **Traces to**: AC-01, AC-02, AC-03, AC-04, AC-05
- **File**: `shared/tests/test_organizer.py`
- **Task**: Добавить тесты:
  1. `_add_year_to_filename("Movie.720p.mkv", 2025)` → `"Movie.720p (2025).mkv"`
  2. `_add_year_to_filename("Movie.2024.720p.mkv", 2024)` → без изменений
  3. `_add_year_to_filename("Movie", 2025)` → `"Movie (2025)"` (без расширения)
  4. `build_plan(rename_files=True)` с year=2020 → dest filename содержит `(2020)`
  5. `build_plan(rename_files=False)` → dest filename = оригинал
  6. `build_plan(rename_files=True)` с year=None → dest filename = оригинал
  7. Ассоциированный файл (.srt) тоже получает год при rename_files=True
  8. Multi-part файлы (CD1, CD2) оба получают год
- **Depends on**: T-01
- **Status**: [✓] done
