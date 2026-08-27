[![CI](https://github.com/afr13nd77/kodi_library_organizer/actions/workflows/ci.yml/badge.svg)](https://github.com/afr13nd77/kodi_library_organizer/actions/workflows/ci.yml)

# Kodi Library Organizer

Kodi-аддон для реорганизации фильмотеки из плоской структуры (все файлы в одной директории) в per-folder структуру (каждый фильм в своей папке). Тип: `xbmc.python.script`.

## Возможности

- Сканирование директории и группировка файлов (видео + субтитры + NFO + артворк)
- Перемещение или копирование (настраиваемый режим)
- Нормализация имён папок: "Movie.Name.2014.1080p.mkv" → папка "Movie Name (2014)"
- Подстановка года из библиотеки Kodi (JSON-RPC), если год отсутствует в имени файла
- Поддержка multi-part фильмов (CD1/CD2, Part1/Part2)
- Превью операций перед выполнением (dry-run)
- Экран подтверждения путей и операции с интуитивными кнопками
- Журнал отката для отмены операций
- Поддержка кириллицы в именах файлов

## Требования

- Kodi v20+ (Python 3.8)

## Установка

1. Скачать ZIP из Releases
2. В Kodi перейти в Settings → Add-ons → Install from zip file
3. Выбрать скачанный ZIP

## Использование

1. Перейти в Programs → Library Organizer
2. Выбрать "Организовать библиотеку"
3. Выбрать директорию-источник (плоская библиотека)
4. Выбрать директорию назначения
5. Просмотреть превью операций
6. Подтвердить выполнение
7. После завершения — обновить источники в настройках Kodi

## Настройки

| Параметр | Описание | По умолчанию |
|---|---|---|
| source_directory | Директория-источник | — |
| destination_directory | Директория назначения | — |
| operation_mode | Перемещение / Копирование | Перемещение |
| dry_run | Только превью без выполнения | Да |
| enrich_from_library | Подставлять год из библиотеки Kodi | Да |
| clean_names | Нормализация имён папок | Да |
| min_file_size_mb | Минимальный размер файла (MB) | 100 |
| handle_multipart | Группировка multi-part | Да |
| undo_enabled | Сохранять журнал для отката | Да |
| debug_logging | Подробное логирование | Нет |

## Сборка из исходников

```bash
python build_zip.py
```

## Тестирование

```bash
pip install -r requirements.txt
python -m pytest shared/tests/ script.library.organizer/tests/ -v
```

## Лицензия

MIT
