# Kodi Library Organizer — Индекс проекта

**Версия:** 1.0.0 (MVP завершён)
**Дата создания:** 27.08.2026
**Дата релиза v1.0.0:** 27.08.2026

## Описание

Kodi-аддон для реорганизации фильмотеки из плоской структуры (все файлы в одной директории) в структуру "каждый фильм в своей папке". Актуально при переходе на per-folder хранение в настройках источников Kodi.

## Tech Stack

| Компонент | Технология |
|---|---|
| Язык | Python 3.8 (встроен в Kodi v20) |
| Платформа | Kodi v20 Nexus / v21 Omega |
| Тип аддона | `xbmc.python.script` (программа) |
| CI/CD | GitHub Actions (планируется) |
| Линтер | ruff (target py38, line-length 120) |
| Тесты | pytest |

## Структура проекта

```
kodi_library_organizer/
├── shared/                            # Общие модули (ядро логики)
│   ├── scanner.py                     # Сканирование директории, группировка файлов
│   ├── organizer.py                   # Перемещение/копирование, dry-run, прогресс
│   ├── name_parser.py                 # Парсинг имён файлов → название + год
│   ├── undo_journal.py                # Журнал операций для отката
│   ├── file_patterns.py               # Расширения, паттерны multi-part
│   ├── logger.py                      # Логирование
│   └── tests/                         # Тесты shared-модулей
├── script.library.organizer/          # Kodi-аддон
│   ├── addon.xml                      # Манифест
│   ├── python/
│   │   └── main.py                    # Точка входа, UI (диалоги Kodi)
│   ├── resources/
│   │   ├── settings.xml               # Настройки аддона
│   │   └── language/                  # Локализации (en_gb, ru_ru)
│   ├── icon.png
│   ├── fanart.jpg
│   └── tests/                         # Тесты аддона
├── docs/                              # Спецификации
├── build_zip.py                       # Сборка ZIP-пакета
├── index.md                           # Этот файл
├── BACKLOG.md                         # Бэклог задач
├── CHANGELOG.md                       # Журнал изменений
└── README.md                          # Описание проекта
```

**Статус:** v1.0.0 MVP released (164 тестов пройдено, CI/CD настроена).

## Зависимости

- Только встроенные модули Python 3.8 (os, shutil, json, re, xml.etree.ElementTree)
- Kodi API: xbmc, xbmcgui, xbmcaddon, xbmcvfs (доступны только в runtime Kodi)

## Связь с другими проектами

- **kodi_metadata_scraper** — аналогичная структура проекта, те же конвенции. Library Organizer подготавливает библиотеку к per-folder формату, который лучше работает с метаданными UMS.

## Команды

| Команда | Описание |
|---|---|
| `cd shared && python -m pytest tests/ -v` | Тесты shared-модулей |
| `cd script.library.organizer && python -m pytest tests/ -v` | Тесты аддона |
| `python build_zip.py` | Сборка ZIP-пакета |
| `ruff check .` | Проверка стиля |
