# BL-10 — Добавление года в имя файла при переносе

## 1.1 Обзор

- **Что**: При перемещении/копировании файла — если год известен (из парсера или БД Kodi), но отсутствует в имени файла — добавить год перед расширением.
- **Кто**: Пользователь аддона Library Organizer.
- **Зачем**: Папка получает имя "Title (2025)", но файл внутри остаётся "Title.720p.rus.LostFilm.TV.mkv". Хочется, чтобы имя файла тоже содержало год для удобства навигации.

## 1.2 User Stories

```
US-01: Как пользователь, я хочу чтобы файлы при переносе получали год в имени,
       если год был определён, но отсутствовал в оригинальном имени файла.

US-02: Как пользователь, я хочу иметь возможность отключить переименование файлов,
       оставив только переименование папок.
```

## 1.3 User Flows

```
FLOW-01: Файл без года → год добавляется

1. Файл: "Star.Wars.Mandalorian.And.Grogu.720p.mkv"
2. Год из парсера: None. Год из Kodi DB (BL-09): 2025
3. parsed_name.year = 2025 после enrich
4. build_plan строит destination_path:
   - Папка: "Star Wars Mandalorian And Grogu (2025)/"
   - Файл (БЫЛО): "Star.Wars.Mandalorian.And.Grogu.720p.mkv"
   - Файл (СТАЛО): "Star.Wars.Mandalorian.And.Grogu.720p (2025).mkv"
5. В превью видно новое имя файла

FLOW-02: Файл уже содержит год

1. Файл: "Interstellar.2014.1080p.mkv"
2. Год из парсера: 2014
3. Год уже в имени файла → имя не меняется
4. destination: "Interstellar (2014)/Interstellar.2014.1080p.mkv"

FLOW-03: Функция отключена

1. rename_files = false
2. Файл переносится с оригинальным именем (как сейчас)
```

## 1.4 Acceptance Criteria

```
AC-01 (US-01):
  GIVEN: файл "Movie.720p.mkv" без года, год известен = 2025
  WHEN: build_plan формирует plan
  THEN: PlannedOperation.destination_path заканчивается на "Movie.720p (2025).mkv"

AC-02 (US-01):
  GIVEN: файл "Movie.2024.720p.mkv" с годом в имени
  WHEN: build_plan формирует plan
  THEN: имя файла не меняется: "Movie.2024.720p.mkv"

AC-03 (US-02):
  GIVEN: настройка rename_files = false
  WHEN: build_plan формирует plan
  THEN: все файлы сохраняют оригинальные имена

AC-04 (US-01):
  GIVEN: multi-part файлы "Movie.720p.CD1.mkv" и "Movie.720p.CD2.mkv", год = 2025
  WHEN: build_plan формирует plan
  THEN: оба файла получают год: "Movie.720p.CD1 (2025).mkv", "Movie.720p.CD2 (2025).mkv"

AC-05 (US-01):
  GIVEN: ассоциированный файл "Movie.720p.srt" (субтитры), год группы = 2025
  WHEN: build_plan формирует plan
  THEN: субтитры тоже получают год: "Movie.720p (2025).srt"
```

## 1.5 Вне скоупа

- Полная нормализация имени файла (удаление тегов качества, замена точек на пробелы) — это BL-05
- Переименование файлов, у которых год уже есть
- Переименование файлов при undo (откат возвращает оригинальные имена — это уже работает через undo_journal)

## 1.6 Зависимости

- shared/organizer.py — `build_plan()` формирует `PlannedOperation.destination_path`
- shared/scanner.py — `MovieGroup.parsed_name.year` как источник года
- settings.xml — новый toggle
