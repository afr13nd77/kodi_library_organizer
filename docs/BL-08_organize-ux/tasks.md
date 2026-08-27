# BL-08 — Tasks

Статус: in-progress (27.08.2026)

## Задачи

```
T-01 [opus] — Переписать run_organize(): экран подтверждения путей + операции
  Traces to: US-01, US-02, US-03, AC-01, AC-02, AC-03, AC-04, AC-05
  File: script.library.organizer/python/main.py (функция run_organize, строки 116-327)
  Task:
    1. Добавить _format_size() — хелпер для человекочитаемого размера (5 строк)
    2. После чтения настроек — добавить цикл "экран подтверждения путей":
       - dialog.yesnocustom с текстом Source/Destination/Mode
       - "Continue" (1) → break, "Change" (2) → openSettings → continue, Cancel/Escape → return
       - При каждой итерации перечитывать настройки из addon
       - Если пути пустые — сначала browseSingle, потом показать экран
    3. После build_plan — заменить textviewer + yesno на цикл "экран подтверждения операции":
       - dialog.yesnocustom с саммари (N movies, N files, size, mode)
       - "Start" (1) → break, "Details" (2) → textviewer(preview) → continue, Cancel/Escape → return
    4. dry_run: при "Start" → textviewer с превью + return
    5. Убрать старый dialog.textviewer (строка 202) и dialog.yesno (строки 209-214)
    6. Все _logger вызовы сохранить для каждого нового пути
  Context:
    - yesnocustom возвращает: 0=nolabel, 1=yeslabel, 2=customlabel, -1=Escape
    - OperationPlan имеет поля: groups, total_files, total_size_bytes, mode
    - format_preview() из organizer.py генерирует полный текст превью
    - Текущая структура: settings→browse→validate→scan→textviewer→yesno→execute
    - Новая структура: settings→browse→path_confirm_loop→validate→scan→op_confirm_loop→execute
  Acceptance criteria: AC-01, AC-02, AC-03, AC-04, AC-05
  Verify: python -m pytest script.library.organizer/tests/test_main.py -v
  Live test: установить ZIP в Kodi → Organize → проверить оба новых экрана
  Status: [✓] done

T-02 [sonnet] — Обновить тесты main.py под новый UI-флоу
  Status: [✓] done

T-03 [haiku] — Версия + документация
  Status: [✓] done
```
