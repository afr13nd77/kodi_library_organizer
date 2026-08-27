# Kodi Library Organizer — Журнал изменений

## [1.0.0] — 27.08.2026

### Добавлено
- Полный MVP аддона Library Organizer (BL-01)
- shared/file_patterns.py — константы расширений и паттерны (16 видео, 7 субтитров, 7 артворк)
- shared/logger.py — логирование с fallback для среды без Kodi
- shared/name_parser.py — парсинг имён файлов (title, year, clean folder name)
- shared/undo_journal.py — журнал операций для отката (JSON, version 1)
- shared/scanner.py — сканирование директории, группировка файлов, multi-part
- shared/organizer.py — планирование и выполнение move/copy, конфликт-резолюция
- script.library.organizer/python/main.py — Kodi UI точка входа
- addon.xml, settings.xml — манифест и 9 настроек (3 категории)
- Локализация: en_GB + ru_RU (24 строки)
- build_zip.py — сборка ZIP-пакета аддона
- ruff.toml — линтер (Python 3.8, line-length 120)
- CI pipeline — lint → test → build → release (.github/workflows/ci.yml)
- 164 теста (152 shared + 12 main.py)

## [0.1.0] — 27.08.2026

### Добавлено
- Инициализация проекта
- Структура директорий
- index.md, BACKLOG.md
- Phase 1 requirements для BL-01 (MVP)
