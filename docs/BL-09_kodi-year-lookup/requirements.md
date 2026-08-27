# BL-09 — Подстановка года из БД Kodi

## 1.1 Обзор

- **Что**: Для фильмов без года в имени файла — запрашивать год из видеобиблиотеки Kodi (JSON-RPC) и использовать его при создании папки.
- **Кто**: Пользователь аддона с уже отсканированной Kodi-библиотекой.
- **Зачем**: Файлы типа "Star.Wars.The.Mandalorian.And.Grogu.720p.rus.LostFilm.TV" не содержат год в имени, но если фильм уже в библиотеке Kodi — год можно взять оттуда. Папка получит формат "Title (YYYY)" вместо "Title".

## 1.2 User Stories

```
US-01: Как пользователь, я хочу чтобы аддон автоматически подставлял год из библиотеки Kodi
       для файлов без года в имени, чтобы папки всегда имели формат "Title (YYYY)".

US-02: Как пользователь, я хочу иметь возможность отключить эту функцию в настройках,
       если мне не нужна подстановка из БД.
```

## 1.3 User Flows

```
FLOW-01: Обогащение года (happy path)

1. Пользователь запускает Organize → подтверждает пути → Continue
2. Система сканирует директорию → ScanResult с N групп
3. Система находит группы с year=None (M из N)
4. Если M > 0 и настройка enrich_from_library включена:
   a. Система вызывает VideoLibrary.GetMovies через JSON-RPC
   b. Для каждой группы с year=None: ищет совпадение по пути файла
   c. Если год найден → подставляет в ParsedName, пересобирает clean_folder_name
   d. Логирует: "Enriched year for 'Title': YYYY from Kodi library"
5. Система строит план (build_plan) с обогащёнными данными
6. В превью пользователь видит папки с годами

FLOW-02: Файл не в библиотеке

1-3. Как в FLOW-01
4b. Файл не найден в результатах VideoLibrary.GetMovies
    → year остаётся None, папка без года ("Title")
    → Логирует: "No library match for 'filename'"

FLOW-03: Функция отключена

1-2. Как в FLOW-01
3. Настройка enrich_from_library = false → шаг 4 пропускается
4. build_plan работает с оригинальными ParsedName
```

## 1.4 Acceptance Criteria

```
AC-01 (US-01):
  GIVEN: файл "MovieTitle.720p.mkv" в source_dir, этот файл есть в библиотеке Kodi с годом 2025
  WHEN: аддон выполняет organize с enrich_from_library=true
  THEN: папка создаётся как "MovieTitle (2025)"
        AND в логе записано "Enriched year for 'MovieTitle': 2025 from Kodi library"

AC-02 (US-01):
  GIVEN: файл "MovieTitle.720p.mkv" в source_dir, этот файл НЕ в библиотеке Kodi
  WHEN: аддон выполняет organize с enrich_from_library=true
  THEN: папка создаётся как "MovieTitle" (без года)
        AND в логе записано "No library match for 'MovieTitle.720p.mkv'"

AC-03 (US-01):
  GIVEN: файл "MovieTitle.2024.720p.mkv" в source_dir (год уже в имени)
  WHEN: аддон выполняет organize
  THEN: год из парсера (2024) используется, JSON-RPC НЕ вызывается для этого файла
        AND папка создаётся как "MovieTitle (2024)"

AC-04 (US-02):
  GIVEN: enrich_from_library=false в настройках
  WHEN: аддон выполняет organize
  THEN: JSON-RPC VideoLibrary.GetMovies НЕ вызывается
        AND файлы без года в имени → папки без года

AC-05 (US-01):
  GIVEN: JSON-RPC вызов завершается ошибкой (библиотека пуста, ошибка парсинга)
  WHEN: аддон выполняет organize
  THEN: ошибка логируется как warning
        AND organize продолжается с оригинальными ParsedName (graceful degradation)
```

## 1.5 Вне скоупа

- Подстановка других метаданных (жанр, режиссёр) — только год
- Изменение shared-модулей (scanner.py, name_parser.py) — обогащение в main.py
- CLI-режим (BL-02) — JSON-RPC доступен только в Kodi runtime
- Переименование самих файлов — только папки

## 1.6 Зависимости

- Kodi JSON-RPC API: `xbmc.executeJSONRPC` (доступен в runtime)
- Метод: `VideoLibrary.GetMovies` с properties `["year", "file"]`
- Настройка: новый toggle в settings.xml
