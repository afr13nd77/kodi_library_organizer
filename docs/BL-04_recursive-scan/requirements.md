# BL-04 — Рекурсивное сканирование вложенных директорий

## 1.1 Обзор

- **Что**: Сканирование не только верхнего уровня source_dir, но и всех вложенных директорий.
- **Кто**: Пользователь с фильмотекой, частично разложенной по папкам (смешанная структура: часть файлов на верхнем уровне, часть во вложенных папках).
- **Зачем**: Сейчас scanner.py пропускает директории (`os.path.isdir → skip`). Если фильмотека уже частично организована или содержит подпапки — эти файлы не попадают в план.

## 1.2 User Stories

```
US-01: Как пользователь, я хочу чтобы аддон сканировал вложенные папки источника,
       чтобы собрать ВСЕ видеофайлы, включая лежащие в подпапках.

US-02: Как пользователь, я хочу иметь возможность отключить рекурсию и сканировать
       только верхний уровень (текущее поведение).
```

## 1.3 User Flows

```
FLOW-01: Рекурсивное сканирование

Структура источника:
  movies/
  ├── Interstellar.2014.1080p.mkv
  ├── Interstellar.2014.1080p.srt
  ├── old_movies/
  │   ├── Matrix.1999.720p.mkv
  │   └── Matrix.1999.720p.srt
  └── temp/
      └── Dune.2024.mkv

1. recursive_scan = true
2. scanner обходит movies/, movies/old_movies/, movies/temp/
3. Результат: 3 группы (Interstellar, Matrix, Dune)
4. Все файлы переносятся в destination:
   dest/Interstellar (2014)/Interstellar.2014.1080p.mkv
   dest/Matrix (1999)/Matrix.1999.720p.mkv
   dest/Dune (2024)/Dune.2024.mkv

FLOW-02: Фильм уже в своей папке (дедупликация)

Структура:
  movies/
  ├── Interstellar (2014)/
  │   ├── Interstellar.2014.1080p.mkv
  │   └── Interstellar.2014.srt
  └── Dune.2024.mkv

1. recursive_scan = true
2. Scanner находит Interstellar в подпапке и Dune на верхнем уровне
3. destination = movies/ (тот же путь)
4. Interstellar уже в per-folder → validate или skip (папка уже существует)
5. Dune → создаётся "Dune (2024)/"

FLOW-03: Рекурсия отключена

1. recursive_scan = false
2. Поведение идентично текущему (os.listdir, без рекурсии)
```

## 1.4 Acceptance Criteria

```
AC-01 (US-01):
  GIVEN: source_dir с вложенной папкой, содержащей видеофайл
  WHEN: scan_directory вызван с recursive=true
  THEN: видеофайл из вложенной папки включён в ScanResult.groups
        AND MovieFile.full_path содержит полный путь (включая подпапку)

AC-02 (US-01):
  GIVEN: source_dir с видеофайлами на нескольких уровнях вложенности
  WHEN: scan_directory вызван с recursive=true
  THEN: все видеофайлы со всех уровней включены в результат

AC-03 (US-02):
  GIVEN: recursive=false (по умолчанию для обратной совместимости)
  WHEN: scan_directory вызван
  THEN: поведение идентично текущему — только верхний уровень

AC-04 (US-01):
  GIVEN: ассоциированный файл (.srt) в той же подпапке что и видео
  WHEN: scan_directory с recursive=true
  THEN: субтитры привязаны к видеофайлу в той же подпапке

AC-05 (US-01):
  GIVEN: destination_dir вложен в source_dir (напр. source/organized/)
  WHEN: scan_directory с recursive=true
  THEN: файлы из destination_dir НЕ включаются в результат (исключение destination)
```

## 1.5 Вне скоупа

- Перенос структуры вложенных папок (фильмы из подпапок → плоские per-folder в destination)
- Обработка дублей (один фильм в двух подпапках)
- Символические ссылки — по-прежнему пропускаются

## 1.6 Зависимости

- shared/scanner.py — `scan_directory()`, замена `os.listdir()` на `os.walk()`
- shared/organizer.py — `validate_paths()` должен учитывать рекурсию (destination внутри source)
- settings.xml — новый toggle
- main.py — передача настройки в scan_directory()
