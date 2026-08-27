# BL-04 — Рекурсивное сканирование: задачи

## Задачи

```
T-01 [opus] — Добавить рекурсивное сканирование в scanner.py
  Traces to: US-01, US-02, AC-01, AC-02, AC-03, AC-05
  Files: shared/scanner.py
  Task:
    1. Добавить параметры recursive: bool = False и destination_dir: str = "" в scan_directory()
    2. При recursive=True: заменить os.listdir() на os.walk() с исключением destination_dir
    3. При recursive=False: оставить текущее поведение без изменений
    4. Обработать os.walk() ошибки доступа к подпапкам (логирование, пропуск)
  Context: scan_directory() сейчас использует os.listdir() (строка 80) и пропускает директории (строка 91)
  Depends on: нет
  Verify: python -m pytest shared/tests/test_scanner.py -v
  Status: [✓] done

T-02 [opus] — Добавить настройку и передачу параметра в main.py
  Traces to: US-02
  Files:
    - script.library.organizer/python/main.py
    - script.library.organizer/resources/settings.xml
    - script.library.organizer/resources/language/resource.language.en_gb/strings.po
    - script.library.organizer/resources/language/resource.language.ru_ru/strings.po
  Task:
    1. settings.xml: добавить recursive_scan toggle в advanced/filters после handle_multipart
    2. strings.po: добавить строки 30315 (label) и 30316 (help)
    3. main.py: читать recursive_scan, передавать в scan_directory() вместе с destination_dir
  Context: main.py вызывает scan_directory() на строке 297-299
  Depends on: T-01
  Verify: python -m pytest script.library.organizer/tests/ -v
  Status: [✓] done

T-03 [sonnet] — Тесты рекурсивного сканирования
  Traces to: AC-01, AC-02, AC-03, AC-04, AC-05
  File: shared/tests/test_scanner.py
  Task: Добавить тесты:
    - test_recursive_finds_files_in_subdirs (AC-01)
    - test_recursive_multilevel_depth (AC-02)
    - test_nonrecursive_skips_subdirs (AC-03)
    - test_recursive_associated_files_in_subdir (AC-04)
    - test_recursive_excludes_destination_dir (AC-05)
    - test_recursive_empty_subdirs
  Context: Тесты используют tmp_path (pytest), _create_file() helper
  Depends on: T-01
  Verify: python -m pytest shared/tests/test_scanner.py -v -k "recursive"
  Status: [✓] done
```
