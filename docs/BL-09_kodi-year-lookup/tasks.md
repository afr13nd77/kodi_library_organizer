# BL-09 — Tasks

Статус: in-progress (27.08.2026)

## Задачи

```
T-01 [opus] — Добавить _enrich_years_from_library() в main.py + настройка + вызов
  Traces to: US-01, US-02, AC-01, AC-02, AC-03, AC-04, AC-05
  Files:
    - script.library.organizer/python/main.py
    - script.library.organizer/resources/settings.xml
    - script.library.organizer/resources/language/resource.language.en_gb/strings.po
    - script.library.organizer/resources/language/resource.language.ru_ru/strings.po
  Task:
    1. В main.py добавить функцию _enrich_years_from_library(scan_result: ScanResult) -> int
       - Расположить между _format_size() и main()
       - Импортировать json (уже в stdlib, добавить в начало файла)
       - xbmc импортировать внутри функции (как в остальных функциях main.py)
       - Логика: см. design.md
       - ParsedName импортирован через try/except блок (уже доступен через scanner → name_parser)
       - НО ParsedName напрямую не импортирован в main.py! Нужно добавить в import block:
         from name_parser import ParsedName (try) / from shared.name_parser import ParsedName (except)
    2. В run_organize(), после scan + "found N groups" лога, перед build_plan:
       - Прочитать настройку: enrich_from_library = addon.getSettingBool("enrich_from_library")
       (В path confirmation loop уже читаются все настройки — добавить туда же)
       - Если enrich_from_library=true → вызвать _enrich_years_from_library(scan_result)
       - Залогировать результат: "enriched N groups with year from Kodi library"
    3. В settings.xml: добавить toggle enrich_from_library в группу "operation" (после dry_run)
    4. В strings.po (en_GB и ru_RU): добавить строки 30127, 30128
  Context:
    - ParsedName: dataclass(title, year, clean_folder_name, raw_name)
    - ScanResult.groups: list[MovieGroup], MovieGroup.parsed_name: ParsedName
    - MovieGroup.video_files: list[MovieFile], MovieFile.full_path: str
    - JSON-RPC: xbmc.executeJSONRPC(json_string) → json_string
    - Нормализация путей: os.path.normcase(os.path.normpath(path)) для Windows-совместимости
    - clean_folder_name при обогащении: f"{title} ({year})", обрезать до 200 символов
  Acceptance criteria: AC-01, AC-02, AC-03, AC-04, AC-05
  Verify: python -m ruff check script.library.organizer/python/main.py
  Live test: установить ZIP в Kodi → Organize → проверить подстановку года
  Status: [ ] pending

T-02 [sonnet] — Тесты на обогащение
  Status: [✓] done

T-03 [haiku] — Версия + документация
  Status: [✓] done
```
