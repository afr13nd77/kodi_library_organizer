# BL-08 — Technical Design

## Архитектура

Все изменения локализованы в **UI-слое** — `script.library.organizer/python/main.py`, функция `run_organize()`. Shared-модули не затрагиваются.

### Текущий флоу (main.py:116-327)

```
run_organize()
  1. Читает настройки из addon
  2. browseSingle для пустых путей
  3. validate_paths()
  4. scan_directory()
  5. build_plan()
  6. dialog.textviewer("Operation preview", preview_text)  ← ПРОБЛЕМА: Escape-only
  7. dialog.yesno("Proceed with move?")                    ← отдельный шаг
  8. check_disk_space() + execute_plan()
```

### Новый флоу

```
run_organize()
  1. Читает настройки из addon
  2. browseSingle для пустых путей (если нужно)
  3. НОВОЕ — Экран подтверждения путей (цикл):
     ┌─ dialog.yesnocustom(paths_summary)
     │  → "Да" (1): break → шаг 4
     │  → "Изменить" (2): addon.openSettings() → continue (перечитать настройки)
     │  → "Отмена" (0) / Escape (-1): return
     └─
  4. validate_paths()  ← ПЕРЕМЕЩЕНО внутрь цикла или сразу после
  5. scan_directory()
  6. build_plan()
  7. НОВОЕ — Экран подтверждения операции (цикл):
     ┌─ dialog.yesnocustom(operation_summary)
     │  → "Да" (1): break → шаг 8
     │  → "Список" (2): dialog.textviewer(preview) → continue
     │  → "Отмена" (0) / Escape (-1): return
     └─
  8. (dry_run → textviewer + return)
  9. check_disk_space() + execute_plan()
```

## Детали реализации

### Экран подтверждения путей (шаг 3)

```python
while True:
    # Перечитываем настройки при каждой итерации (после возврата из Settings)
    source_dir = addon.getSetting("source_directory")
    destination_dir = addon.getSetting("destination_directory")
    mode_int = addon.getSettingInt("operation_mode")
    mode = OperationMode.MOVE if mode_int == 0 else OperationMode.COPY
    # ... остальные настройки

    mode_label = "Move" if mode == OperationMode.MOVE else "Copy"
    summary = (
        f"Source:      {source_dir}\n"
        f"Destination: {destination_dir}\n"
        f"Mode:        {mode_label}"
    )

    choice = dialog.yesnocustom(
        "Library Organizer",
        summary,
        customlabel="Change",  # → 2
        nolabel="Cancel",      # → 0
        yeslabel="Continue",   # → 1
    )

    if choice == 1:   # Continue
        break
    elif choice == 2:  # Change → open Settings, loop back
        addon.openSettings()
        continue
    else:              # Cancel / Escape
        return
```

**yesnocustom return values** (Kodi v19+):
- `0` = nolabel (левая кнопка)
- `1` = yeslabel (правая кнопка)
- `2` = customlabel (средняя кнопка)
- `-1` = Escape / Back

### Экран подтверждения операции (шаг 7)

```python
while True:
    summary = (
        f"Movies found: {len(plan.groups)}\n"
        f"Files to {mode_label.lower()}: {plan.total_files}\n"
        f"Total size: {_format_size(plan.total_size_bytes)}"
    )

    choice = dialog.yesnocustom(
        "Library Organizer",
        summary,
        customlabel="Details",  # → 2
        nolabel="Cancel",       # → 0
        yeslabel="Start",       # → 1
    )

    if choice == 1:    # Start
        break
    elif choice == 2:  # Details → textviewer, loop back
        dialog.textviewer("Operation preview", preview_text)
        continue
    else:              # Cancel / Escape
        return
```

### Вспомогательная функция _format_size

Нужна для человекочитаемого вывода размера. Либо импортируем из organizer (если доступна), либо дублируем простую версию в main.py.

```python
def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
```

Проверим: `_format_size` уже есть в organizer.py — её использует `format_preview()`. Она приватная (prefix `_`), но мы можем её импортировать, добавив в try/except блок main.py. Альтернативно — дублируем 5-строчную функцию в main.py, чтобы не расширять API organizer.

**Решение**: дублируем в main.py — проще, нет зависимости на приватный API.

### Локализация

Текущие строки 30100-30332. Новые строки для UI-экранов. Нужны для полной локализации, но в первой итерации — hardcoded English в `dialog.yesnocustom()` labels (Kodi не поддерживает string refs в label-параметрах yesnocustom — только plain text).

Текст body-сообщений можно оставить на английском, т.к. пути файловой системы и режимы уже на английском.

**Решение**: новые строки локализации не нужны. Используем plain text в параметрах yesnocustom (Kodi API ограничение).

## Безопасность и edge cases

1. **Пустые пути после Settings** — если пользователь не настроил пути в Settings и нажал "Continue", `validate_paths()` поймает ошибку и покажет dialog.ok.
2. **Пользователь зациклился** — "Change" → Settings → не поменял → "Change" → ... Безобидно, пользователь может выйти через Cancel/Escape в любой момент.
3. **dry_run** — если dry_run включён, после нажатия "Start" показываем textviewer с превью и завершаем. Сообщение должно быть явным: "Dry run — no files were changed."

## Что НЕ меняется

- shared/organizer.py — `format_preview()`, `build_plan()`, `OperationPlan`
- shared/scanner.py, shared/name_parser.py, shared/undo_journal.py
- settings.xml, addon.xml (кроме версии)
- Тесты shared/ — UI-тесты main.py обновятся
