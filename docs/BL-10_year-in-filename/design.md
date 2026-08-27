# BL-10 — Technical Design: Добавление года в имя файла

## Архитектура

### Затронутые модули

| Модуль | Изменение |
|---|---|
| `shared/organizer.py` | Новый хелпер `_add_year_to_filename()`, параметр `rename_files` в `build_plan()` |
| `script.library.organizer/python/main.py` | Чтение настройки `rename_files`, передача в `build_plan()` |
| `script.library.organizer/resources/settings.xml` | Новый toggle `rename_files` в категории `naming` |
| `strings.po` (en_gb + ru_ru) | Строки 30129 (label), 30130 (help) |
| `shared/tests/test_organizer.py` | Тесты для `_add_year_to_filename()` и `build_plan(rename_files=True)` |

### Data flow

```
settings.xml  -->  main.py читает rename_files
                      |
                      v
scan_directory()  -->  ScanResult (groups с parsed_name.year)
                      |
                      v
build_plan(scan_result, dest, mode, rename_files=True)
    |
    +-- для каждого файла в группе:
    |     если rename_files=True И parsed_name.year is not None:
    |       filename = _add_year_to_filename(original_filename, year)
    |     dest_path = os.path.join(folder_path, filename)
    |
    v
OperationPlan (destination_path содержит переименованные файлы)
    |
    v
execute_plan() -- использует destination_path как есть (без изменений)
```

## Решения

### 1. Хелпер `_add_year_to_filename(filename, year)`

```python
def _add_year_to_filename(filename: str, year: int) -> str:
    name, ext = os.path.splitext(filename)
    year_str = str(year)
    if year_str in name:
        return filename
    return f"{name} ({year}){ext}"
```

**Почему проверка `year_str in name`**: если файл уже содержит год (напр. `Movie.2024.720p.mkv`), не нужно добавлять второй раз.

**Альтернатива**: regex `\b{year}\b` — отклонено, т.к. год может быть частью технических тегов (x264→не год, но 2024 — год). Простая проверка `in` достаточна: если строка "2024" уже есть в имени файла, повторное добавление не нужно.

### 2. Применение к ассоциированным файлам

Год добавляется и к видео, и к ассоциированным файлам (.srt, .nfo и т.д.), используя тот же `parsed_name.year` группы. Это обеспечивает консистентность имён в папке.

### 3. Параметр `rename_files` в `build_plan()`

Добавлен как keyword-only argument с default `False` для обратной совместимости. Существующие вызовы без параметра продолжат работать без изменений.

### 4. Настройка в settings.xml

Размещение: категория `naming` (id="naming"), группа `naming_options`, после `clean_names`. Default: `true` (включено). Level: 0 (видно всем).

### Security & Edge Cases

- Файл без расширения: `os.path.splitext("noext")` → `("noext", "")` → `"noext (2024)"` — корректно
- Год = None: хелпер не вызывается (guard в build_plan)
- Двойное добавление невозможно: проверка `year_str in name`
- Длинные имена файлов: ОС ограничение ~255 символов. Добавление ` (YYYY)` = 7 символов — пренебрежимо

### Влияние на execute_plan

Никакого. `execute_plan()` работает с `PlannedOperation.destination_path` — какой path построен в `build_plan()`, такой и используется. Undo журнал сохраняет `destination_path` с новым именем, `source_path` — оригинал. Undo возвращает файл в source с оригинальным именем.
