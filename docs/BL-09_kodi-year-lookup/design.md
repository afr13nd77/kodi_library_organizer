# BL-09 — Technical Design

## Архитектура

Обогащение года — **UI-layer операция** в main.py. Shared-модули не меняются. Новая функция `_enrich_years_from_library()` вызывается между `scan_directory()` и `build_plan()`.

### Место в флоу run_organize()

```
scan_directory()
  ↓
_enrich_years_from_library(scan_result)   ← НОВОЕ
  ↓
build_plan()
```

### JSON-RPC запрос

```python
import json
import xbmc

request = json.dumps({
    "jsonrpc": "2.0",
    "method": "VideoLibrary.GetMovies",
    "params": {
        "properties": ["year", "file"]
    },
    "id": 1
})

response = json.loads(xbmc.executeJSONRPC(request))
```

Ответ:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "movies": [
      {
        "movieid": 1,
        "label": "Interstellar",
        "year": 2014,
        "file": "I:\\BKP_Video\\movies_sf\\Interstellar.2014.1080p.BDRip.x264.mkv"
      },
      ...
    ]
  }
}
```

### Матчинг

По **полному пути файла**. Kodi хранит в `file` абсолютный путь к файлу. Сравниваем с `MovieFile.full_path`.

Для надёжности: нормализация путей через `os.path.normcase()` + `os.path.normpath()` (Windows: обе стороны приводятся к lower-case + backslashes).

```python
def _enrich_years_from_library(scan_result: ScanResult) -> int:
    """Подставляет год из библиотеки Kodi для групп с year=None.
    
    Returns: количество обогащённых групп.
    """
    import json
    import xbmc
    
    # 1. Собрать группы, которым нужен год
    needs_year = [g for g in scan_result.groups if g.parsed_name.year is None]
    if not needs_year:
        _logger.info("enrich: все группы уже имеют год, пропускаем JSON-RPC")
        return 0
    
    # 2. Запросить библиотеку
    try:
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {"properties": ["year", "file"]},
            "id": 1,
        })
        raw = xbmc.executeJSONRPC(request)
        data = json.loads(raw)
    except Exception as exc:
        _logger.warning(f"enrich: JSON-RPC ошибка: {exc}")
        return 0
    
    movies = data.get("result", {}).get("movies", [])
    if not movies:
        _logger.info("enrich: библиотека пуста или нет фильмов")
        return 0
    
    # 3. Построить маппинг normalized_path → year
    lib_map = {}
    for m in movies:
        year = m.get("year", 0)
        file_path = m.get("file", "")
        if year and file_path:
            key = os.path.normcase(os.path.normpath(file_path))
            lib_map[key] = year
    
    _logger.info(f"enrich: загружено {len(lib_map)} фильмов из библиотеки")
    
    # 4. Матчинг по full_path каждого видеофайла группы
    enriched = 0
    for group in needs_year:
        matched_year = None
        for vf in group.video_files:
            key = os.path.normcase(os.path.normpath(vf.full_path))
            if key in lib_map:
                matched_year = lib_map[key]
                break
        
        if matched_year:
            old_name = group.parsed_name
            group.parsed_name = ParsedName(
                title=old_name.title,
                year=matched_year,
                clean_folder_name=f"{old_name.title} ({matched_year})",
                raw_name=old_name.raw_name,
            )
            enriched += 1
            _logger.info(
                f"enrich: год подставлен для '{old_name.title}': "
                f"{matched_year} из библиотеки Kodi"
            )
        else:
            _logger.debug(
                f"enrich: нет совпадения для '{group.video_files[0].filename}'"
            )
    
    return enriched
```

### clean_folder_name при обогащении

При подстановке года пересобираем `clean_folder_name` как `f"{title} ({year})"`. Санитизация спецсимволов уже была применена к `title` в name_parser, поэтому дополнительная не нужна. Но длину ограничиваем — если `len(clean_folder_name) > 200`, обрезаем.

### Настройка settings.xml

Новый toggle в категории "General", группа "Operation":

```xml
<setting id="enrich_from_library" type="boolean" label="30127" help="30128">
  <level>0</level>
  <default>true</default>
  <control type="toggle"/>
</setting>
```

Строки локализации:
- 30127: "Enrich year from Kodi library" / "Подставлять год из библиотеки Kodi"
- 30128: "Look up movie year from Kodi database when not found in filename" / "Искать год фильма в базе Kodi, если не найден в имени файла"

### Что меняется

| Файл | Изменение |
|------|-----------|
| main.py | Новая функция `_enrich_years_from_library()`, вызов между scan и build_plan, чтение настройки |
| settings.xml | Новый toggle `enrich_from_library` |
| strings.po (en_GB) | +2 строки (30127, 30128) |
| strings.po (ru_RU) | +2 строки (30127, 30128) |
| test_main.py | Новые тесты на обогащение |

### Что НЕ меняется

- shared/scanner.py, shared/name_parser.py, shared/organizer.py — без изменений
- ParsedName dataclass — без изменений (создаём новый экземпляр)
- Остальной флоу run_organize() — без изменений

### Edge cases

1. **Библиотека пуста** — `movies: []` → enriched=0, продолжаем
2. **JSON-RPC ошибка** — try/except → warning в лог, продолжаем
3. **year=0 в БД** — фильм без года в Kodi → пропускаем (условие `if year`)
4. **Multi-part файлы** — группа с 2+ видеофайлами: проверяем каждый, берём первое совпадение
5. **Путь с кириллицей** — normcase + normpath на обеих сторонах
6. **Файл в библиотеке, но year уже в имени** — группа не попадает в `needs_year`, пропускается
