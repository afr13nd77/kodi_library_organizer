"""Kodi UI entry point for Library Organizer addon.

Thin UI layer connecting Kodi dialogs to shared business-logic modules.
All heavy lifting is done by scanner, organizer, and undo_journal.
"""
from __future__ import annotations

import datetime
import os

# Shared modules live next to main.py after build_zip.py assembly.
# In the dev tree they are importable as a package via shared.*.
try:
    from scanner import ScanResult, scan_directory
    from organizer import (
        ConflictResolution,
        FileConflictResolution,
        OperationMode,
        OperationPlan,
        OperationResult,
        build_plan,
        check_disk_space,
        execute_plan,
        format_preview,
        validate_paths,
    )
    from undo_journal import (
        UndoJournal,
        UndoResult,
        execute_undo,
        get_latest_journal,
        load_journal,
    )
    from logger import Logger
except ImportError:
    from shared.scanner import ScanResult, scan_directory
    from shared.organizer import (
        ConflictResolution,
        FileConflictResolution,
        OperationMode,
        OperationPlan,
        OperationResult,
        build_plan,
        check_disk_space,
        execute_plan,
        format_preview,
        validate_paths,
    )
    from shared.undo_journal import (
        UndoJournal,
        UndoResult,
        execute_undo,
        get_latest_journal,
        load_journal,
    )
    from shared.logger import Logger

# ---------------------------------------------------------------------------
# Module-level logger (no debug until addon settings are read)
# ---------------------------------------------------------------------------
_logger = Logger(debug_enabled=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Return human-readable file size string."""
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Addon entry point invoked by Kodi."""
    _logger.info("main: Library Organizer started")
    try:
        show_main_menu()
    except Exception as exc:
        _logger.error(f"main: unhandled exception: {exc}")
        try:
            import xbmcgui
            xbmcgui.Dialog().ok("Library Organizer", f"Unexpected error: {exc}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def show_main_menu() -> None:
    """Display the top-level menu: Organize / Undo / Settings."""
    import xbmcgui
    import xbmcaddon

    _logger.info("show_main_menu: displaying menu")

    MENU_ITEMS = [
        "Organize library",
        "Undo last operation",
        "Settings",
    ]

    choice = xbmcgui.Dialog().select("Library Organizer", MENU_ITEMS)
    _logger.info(f"show_main_menu: user chose {choice}")

    if choice == 0:
        run_organize()
    elif choice == 1:
        run_undo()
    elif choice == 2:
        xbmcaddon.Addon().openSettings()
    else:
        _logger.info("show_main_menu: cancelled (choice=-1)")


# ---------------------------------------------------------------------------
# Organize flow
# ---------------------------------------------------------------------------

def run_organize() -> None:
    """Full organize flow: settings -> path confirm -> scan -> op confirm -> execute."""
    import xbmcgui
    import xbmcaddon
    import xbmcvfs

    addon = xbmcaddon.Addon()
    global _logger
    _logger = Logger(debug_enabled=addon.getSettingBool("debug_logging"))
    _logger.info("run_organize: started")

    dialog = xbmcgui.Dialog()

    # -- 1. Read settings + prompt for dirs if empty -----------------------
    source_dir = addon.getSetting("source_directory")
    destination_dir = addon.getSetting("destination_directory")

    if not source_dir:
        source_dir = dialog.browseSingle(0, "Select source directory", "files")
        if not source_dir:
            _logger.info("run_organize: user cancelled source dir selection")
            return

    if not destination_dir:
        destination_dir = dialog.browseSingle(
            0, "Select destination directory", "files",
        )
        if not destination_dir:
            _logger.info("run_organize: user cancelled destination dir selection")
            return

    # -- 2. Path confirmation loop -----------------------------------------
    while True:
        # Re-read settings each iteration (user may have changed them in Settings)
        source_dir = addon.getSetting("source_directory") or source_dir
        destination_dir = addon.getSetting("destination_directory") or destination_dir
        mode_int = addon.getSettingInt("operation_mode")
        mode = OperationMode.MOVE if mode_int == 0 else OperationMode.COPY
        dry_run = addon.getSettingBool("dry_run")
        clean_names = addon.getSettingBool("clean_names")
        min_size_mb = addon.getSettingInt("min_file_size_mb")
        handle_multipart = addon.getSettingBool("handle_multipart")
        undo_enabled = addon.getSettingBool("undo_enabled")

        mode_label = "Move" if mode == OperationMode.MOVE else "Copy"
        summary = (
            f"Source: {source_dir}\n"
            f"Destination: {destination_dir}\n"
            f"Mode: {mode_label}"
        )
        if dry_run:
            summary += "\n[Dry run enabled]"

        _logger.info(
            f"run_organize: showing path confirmation. "
            f"source={source_dir}, dest={destination_dir}, mode={mode.value}"
        )

        choice = dialog.yesnocustom(
            "Library Organizer",
            summary,
            customlabel="Change",
            nolabel="Cancel",
            yeslabel="Continue",
        )
        _logger.info(f"run_organize: path confirmation choice={choice}")

        if choice == 1:  # Continue
            break
        elif choice == 2:  # Change -> open Settings
            _logger.info("run_organize: user opened settings to change paths")
            addon.openSettings()
            continue
        else:  # Cancel (0) or Escape (-1)
            _logger.info("run_organize: user cancelled at path confirmation")
            return

    # -- 3. Validate paths -------------------------------------------------
    _logger.info(
        f"run_organize: settings mode={mode.value} dry_run={dry_run} "
        f"clean_names={clean_names} min_size_mb={min_size_mb} "
        f"handle_multipart={handle_multipart} undo_enabled={undo_enabled}"
    )

    error = validate_paths(source_dir, destination_dir)
    if error:
        dialog.ok("Library Organizer", error)
        _logger.error(f"run_organize: validation failed: {error}")
        return

    # -- 4. Scan -----------------------------------------------------------
    _logger.info(f"run_organize: scanning {source_dir}")
    min_size_bytes = min_size_mb * 1024 * 1024

    try:
        scan_result: ScanResult = scan_directory(
            source_dir, min_size_bytes, handle_multipart, clean_names,
        )
    except Exception as exc:
        dialog.ok("Library Organizer", f"Scan error: {exc}")
        _logger.error(f"run_organize: scan_directory raised: {exc}")
        return

    if not scan_result.groups:
        dialog.ok(
            "Library Organizer",
            "No video files matching criteria were found.",
        )
        _logger.info("run_organize: no video files found")
        return

    _logger.info(f"run_organize: found {len(scan_result.groups)} groups")

    # -- 5. Build plan -----------------------------------------------------
    try:
        plan: OperationPlan = build_plan(scan_result, destination_dir, mode)
    except Exception as exc:
        dialog.ok("Library Organizer", f"Plan error: {exc}")
        _logger.error(f"run_organize: build_plan raised: {exc}")
        return

    preview_text = format_preview(plan)

    # -- 6. Operation confirmation loop ------------------------------------
    mode_label = "move" if mode == OperationMode.MOVE else "copy"
    while True:
        op_summary = (
            f"Movies found: {len(plan.groups)}\n"
            f"Files to {mode_label}: {plan.total_files}\n"
            f"Total size: {_format_size(plan.total_size_bytes)}"
        )

        _logger.info("run_organize: showing operation confirmation")

        choice = dialog.yesnocustom(
            "Library Organizer",
            op_summary,
            customlabel="Details",
            nolabel="Cancel",
            yeslabel="Start",
        )
        _logger.info(f"run_organize: operation confirmation choice={choice}")

        if choice == 1:  # Start
            break
        elif choice == 2:  # Details -> show preview, then loop back
            _logger.info("run_organize: user requested operation details")
            dialog.textviewer("Operation preview", preview_text)
            continue
        else:  # Cancel (0) or Escape (-1)
            _logger.info("run_organize: user cancelled after preview")
            return

    # -- 7. Dry run -> show preview and exit --------------------------------
    if dry_run:
        _logger.info("run_organize: dry_run mode, showing preview")
        dialog.textviewer("Operation preview (dry run)", preview_text)
        return

    # -- 8. Disk space check for COPY --------------------------------------
    if mode == OperationMode.COPY:
        if not check_disk_space(destination_dir, plan.total_size_bytes):
            dialog.ok(
                "Library Organizer",
                "Not enough free disk space on the destination drive.",
            )
            _logger.error("run_organize: insufficient disk space")
            return

    # -- 9. Execute with progress ------------------------------------------
    progress = xbmcgui.DialogProgress()
    progress.create("Library Organizer", "Preparing...")
    _logger.info("run_organize: executing plan")

    def progress_callback(current: int, total: int, filename: str) -> bool:
        if progress.iscanceled():
            return False
        percent = int(current * 100 / total) if total > 0 else 0
        progress.update(percent, f"File {current} of {total}", filename)
        return True

    def folder_conflict_callback(folder_name: str) -> ConflictResolution:
        progress.close()
        result_code = dialog.yesnocustom(
            "Folder conflict",
            f"Folder '{folder_name}' already exists.",
            customlabel="Rename",
            nolabel="Skip",
            yeslabel="Merge",
        )
        progress.create("Library Organizer", "Continuing...")
        if result_code == 0:
            return ConflictResolution.SKIP
        elif result_code == 1:
            return ConflictResolution.MERGE
        else:
            return ConflictResolution.RENAME

    def file_conflict_callback(filename: str) -> FileConflictResolution:
        progress.close()
        result_code = dialog.yesnocustom(
            "File conflict",
            f"File '{filename}' already exists.",
            customlabel="Rename",
            nolabel="Skip",
            yeslabel="Overwrite",
        )
        progress.create("Library Organizer", "Continuing...")
        if result_code == 0:
            return FileConflictResolution.SKIP
        elif result_code == 1:
            return FileConflictResolution.OVERWRITE
        else:
            return FileConflictResolution.RENAME

    # -- Undo journal path -----------------------------------------------
    undo_path = ""
    if undo_enabled:
        undo_dir = xbmcvfs.translatePath(
            "special://profile/addon_data/script.library.organizer/undo/",
        )
        xbmcvfs.mkdirs(undo_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        undo_path = os.path.join(undo_dir, f"undo_{timestamp}.json")
        _logger.info(f"run_organize: undo journal path: {undo_path}")

    try:
        result: OperationResult = execute_plan(
            plan=plan,
            undo_journal_path=undo_path,
            progress_callback=progress_callback,
            folder_conflict_callback=folder_conflict_callback,
            file_conflict_callback=file_conflict_callback,
        )
    except Exception as exc:
        progress.close()
        dialog.ok("Library Organizer", f"Execution error: {exc}")
        _logger.error(f"run_organize: execute_plan raised: {exc}")
        return

    progress.close()

    # -- 10. Show result --------------------------------------------------
    if result.was_cancelled:
        msg = (
            f"Operation cancelled.\n"
            f"Processed: {result.success_count} of {result.total_count} files.\n"
            f"Use 'Undo last operation' to revert."
        )
    elif result.error_count > 0:
        msg = (
            f"Finished with errors.\n"
            f"Success: {result.success_count}, Errors: {result.error_count}\n"
            f"Skipped: {result.skipped_count}"
        )
    else:
        msg = (
            f"Done!\n"
            f"Organized: {result.success_count} files.\n"
            f"Remember to update sources in Kodi settings."
        )

    dialog.ok("Library Organizer", msg)
    _logger.info(
        f"run_organize: finished. "
        f"success={result.success_count}, errors={result.error_count}, "
        f"skipped={result.skipped_count}"
    )


# ---------------------------------------------------------------------------
# Undo flow
# ---------------------------------------------------------------------------

def run_undo() -> None:
    """Undo the last completed operation."""
    import xbmcgui
    import xbmcaddon
    import xbmcvfs

    addon = xbmcaddon.Addon()
    global _logger
    _logger = Logger(debug_enabled=addon.getSettingBool("debug_logging"))
    _logger.info("run_undo: started")

    dialog = xbmcgui.Dialog()

    undo_dir = xbmcvfs.translatePath(
        "special://profile/addon_data/script.library.organizer/undo/",
    )

    _logger.info(f"run_undo: looking for journals in {undo_dir}")
    journal_path = get_latest_journal(undo_dir)
    if not journal_path:
        dialog.ok("Library Organizer", "No operations to undo.")
        _logger.info("run_undo: no journals found")
        return

    _logger.info(f"run_undo: loading journal {journal_path}")
    try:
        journal: UndoJournal = load_journal(journal_path)
    except Exception as exc:
        dialog.ok("Library Organizer", f"Failed to load journal: {exc}")
        _logger.error(f"run_undo: load_journal raised: {exc}")
        return

    success_entries = [e for e in journal.entries if e.success]
    confirmed = dialog.yesno(
        "Library Organizer",
        f"Undo operation from {journal.timestamp}?\n"
        f"{len(success_entries)} files will be returned to {journal.source_dir}",
    )
    if not confirmed:
        _logger.info("run_undo: user cancelled")
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Library Organizer", "Undoing...")

    def progress_callback(current: int, total: int, filename: str) -> bool:
        if progress.iscanceled():
            return False
        percent = int(current * 100 / total) if total > 0 else 0
        progress.update(percent, f"File {current} of {total}", filename)
        return True

    _logger.info("run_undo: executing undo")
    try:
        result: UndoResult = execute_undo(journal, journal_path, progress_callback)
    except Exception as exc:
        progress.close()
        dialog.ok("Library Organizer", f"Undo error: {exc}")
        _logger.error(f"run_undo: execute_undo raised: {exc}")
        return

    progress.close()

    if result.error_count > 0:
        errors_preview = ", ".join(result.errors[:3])
        msg = (
            f"Undo partially completed.\n"
            f"Restored: {result.success_count} of {result.total_count}\n"
            f"Errors: {errors_preview}"
        )
    else:
        msg = f"Undo complete. Restored {result.success_count} files."

    dialog.ok("Library Organizer", msg)
    _logger.info(
        f"run_undo: finished. "
        f"success={result.success_count}, errors={result.error_count}"
    )


# ---------------------------------------------------------------------------
# Kodi invocation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
