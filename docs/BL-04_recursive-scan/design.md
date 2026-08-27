# BL-04 — Рекурсивное сканирование: технический дизайн

## Архитектура

### Затронутые модули

1. **shared/scanner.py** — `scan_directory()`: основной модуль, замена `os.listdir()` на `os.walk()` при `recursive=True`
2. **shared/organizer.py** — `validate_paths()`: ослабление проверки «destination внутри source» при рекурсии
3. **script.library.organizer/python/main.py** — чтение настройки `recursive_scan`, передача в `scan_directory()`
4. **script.library.organizer/resources/settings.xml** — новый toggle
5. **strings.po** (en_gb, ru_ru) — строки 30315, 30316

### Поток данных

```
main.py:
  recursive = addon.getSettingBool("recursive_scan")
  destination_dir = addon.getSetting("destination_directory")
        |
        v
scan_directory(source, ..., recursive=recursive, destination_dir=destination_dir)
        |
        v
scanner.py:
  if recursive:
    os.walk() с исключением destination_dir
  else:
    os.listdir() (текущее поведение)
        |
        v
ScanResult (MovieFile.full_path = абсолютный путь из подпапки)
```

## Изменения в scan_directory()

### Новая сигнатура

```python
def scan_directory(
    source_path: str,
    min_file_size_bytes: int,
    handle_multipart: bool,
    clean_names: bool,
    recursive: bool = False,
    destination_dir: str = "",
) -> ScanResult:
```

### Логика сбора файлов

**Режим flat (recursive=False)** — без изменений, `os.listdir()` + `os.path.isdir()` skip.

**Режим recursive (recursive=True)**:

```python
if recursive:
    dest_norm = os.path.normcase(os.path.normpath(destination_dir)) if destination_dir else ""
    all_entries = []
    for dirpath, dirnames, filenames in os.walk(source_path):
        # Исключить destination_dir
        if dest_norm:
            dir_norm = os.path.normcase(os.path.normpath(dirpath))
            if dir_norm == dest_norm or dir_norm.startswith(dest_norm + os.sep):
                dirnames.clear()  # не заходить глубже
                continue
        for fname in filenames:
            all_entries.append(os.path.join(dirpath, fname))
```

После сбора `all_entries` — итерация по полным путям (вместо `os.path.join(source_path, entry)`).

### Привязка associated файлов

Текущая логика (longest-prefix по base_name) остаётся. При рекурсии base_name всё равно извлекается из имени файла (без пути), поэтому файлы из разных подпапок с одинаковым base_name попадут в одну группу. Это корректно: sub.srt рядом с video.mkv в одной папке будет привязан.

**Важно**: `base_name` (ключ группировки) строится из `filename`, не из `full_path`. Файлы из разных подпапок с одним именем будут в одной группе — это правильное поведение для рекурсивного сканирования (flat merge в destination).

## Изменения в validate_paths()

Текущая проверка `norm_dest.startswith(norm_source + os.sep)` блокирует destination внутри source. При рекурсии это допустимо, если scanner исключает destination. Однако validate_paths не знает о recursive — поэтому **оставляем проверку как есть**. Она выполняется в main.py до scan_directory. Пользователь может настроить destination вне source.

Если в будущем потребуется destination внутри source при рекурсии — это отдельная задача.

## Настройки

### settings.xml

Новый toggle в категории `advanced`, группа `filters`, после `handle_multipart`:

```xml
<setting id="recursive_scan" type="boolean" label="30315" help="30316">
  <level>1</level>
  <default>false</default>
  <control type="toggle"/>
</setting>
```

Default: `false` — обратная совместимость.

### strings.po

| ID | en_gb | ru_ru |
|---|---|---|
| 30315 | Recursive directory scan | Рекурсивное сканирование |
| 30316 | Scan subdirectories inside source directory | Сканировать подпапки внутри директории-источника |

## Безопасность и edge cases

1. **destination внутри source**: scanner исключает destination subtree при `os.walk()` через `dirnames.clear()` + `continue`
2. **Символические ссылки**: `os.walk()` по умолчанию не следует symlinks (`followlinks=False`), что совпадает с текущим поведением (пропуск symlinks)
3. **Пустые подпапки**: `os.walk()` их обходит, но файлов не найдёт — не влияет
4. **Огромная вложенность**: `os.walk()` рекурсивен, но Python stack limit ~1000 — для реальных фильмотек не проблема
5. **Права доступа**: если подпапка недоступна, `os.walk()` выбросит `OSError` — ловим через `onerror` или логируем

## Интеграция с существующим кодом

- `MovieFile.full_path` уже содержит абсолютный путь — при рекурсии он просто включает подпапку
- `build_plan()` в organizer.py использует `MovieFile.filename` (только имя файла) для `destination_path` — работает корректно
- `format_preview()` не зависит от глубины вложенности
- `execute_plan()` использует `PlannedOperation.source_path` (полный путь) — работает корректно
