"""Tests for script.library.organizer/python/main.py.

All Kodi modules (xbmc, xbmcgui, xbmcaddon, xbmcvfs) are mocked.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make main.py importable from the test runner
# ---------------------------------------------------------------------------
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), os.pardir, "python"),
)


# ---------------------------------------------------------------------------
# Kodi module mocks (autouse)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_kodi(monkeypatch):
    """Inject fake Kodi modules into sys.modules before every test."""
    mock_xbmc = MagicMock()
    mock_xbmcgui = MagicMock()
    mock_xbmcaddon = MagicMock()
    mock_xbmcvfs = MagicMock()

    monkeypatch.setitem(sys.modules, "xbmc", mock_xbmc)
    monkeypatch.setitem(sys.modules, "xbmcgui", mock_xbmcgui)
    monkeypatch.setitem(sys.modules, "xbmcaddon", mock_xbmcaddon)
    monkeypatch.setitem(sys.modules, "xbmcvfs", mock_xbmcvfs)

    return {
        "xbmc": mock_xbmc,
        "xbmcgui": mock_xbmcgui,
        "xbmcaddon": mock_xbmcaddon,
        "xbmcvfs": mock_xbmcvfs,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dialog(kodi_mocks) -> MagicMock:
    """Return the Dialog *instance* that Dialog() returns."""
    return kodi_mocks["xbmcgui"].Dialog.return_value


def _get_addon(kodi_mocks) -> MagicMock:
    """Return the Addon *instance* that Addon() returns."""
    return kodi_mocks["xbmcaddon"].Addon.return_value


def _import_main():
    """(Re)import main.py so it picks up mocked Kodi modules."""
    # Remove cached main module so re-import is clean
    for key in list(sys.modules):
        if key == "main" or key.endswith(".main"):
            del sys.modules[key]
    import main
    return main


# ===========================================================================
# show_main_menu tests
# ===========================================================================

class TestShowMainMenu:
    """Tests for the top-level menu."""

    def test_choice_0_calls_run_organize(self, mock_kodi):
        main_mod = _import_main()
        _get_dialog(mock_kodi).select.return_value = 0

        with patch.object(main_mod, "run_organize") as mock_run:
            main_mod.show_main_menu()
            mock_run.assert_called_once()

    def test_choice_1_calls_run_undo(self, mock_kodi):
        main_mod = _import_main()
        _get_dialog(mock_kodi).select.return_value = 1

        with patch.object(main_mod, "run_undo") as mock_run:
            main_mod.show_main_menu()
            mock_run.assert_called_once()

    def test_choice_2_opens_settings(self, mock_kodi):
        main_mod = _import_main()
        _get_dialog(mock_kodi).select.return_value = 2

        main_mod.show_main_menu()
        _get_addon(mock_kodi).openSettings.assert_called_once()

    def test_choice_minus1_does_nothing(self, mock_kodi):
        main_mod = _import_main()
        _get_dialog(mock_kodi).select.return_value = -1

        with patch.object(main_mod, "run_organize") as mock_org, \
             patch.object(main_mod, "run_undo") as mock_undo:
            main_mod.show_main_menu()
            mock_org.assert_not_called()
            mock_undo.assert_not_called()
            _get_addon(mock_kodi).openSettings.assert_not_called()


# ===========================================================================
# run_organize tests
# ===========================================================================

def _configure_addon_defaults(addon_mock):
    """Set up addon mock to return sensible default settings."""
    def _get_setting(setting_id):
        defaults = {
            "source_directory": "",
            "destination_directory": "",
        }
        return defaults.get(setting_id, "")

    def _get_setting_bool(setting_id):
        defaults = {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }
        return defaults.get(setting_id, False)

    def _get_setting_int(setting_id):
        defaults = {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }
        return defaults.get(setting_id, 0)

    addon_mock.getSetting.side_effect = _get_setting
    addon_mock.getSettingBool.side_effect = _get_setting_bool
    addon_mock.getSettingInt.side_effect = _get_setting_int


class TestRunOrganize:
    """Tests for the organize flow."""

    def test_validation_same_paths_shows_error(self, mock_kodi, tmp_path):
        """source == destination -> dialog.ok with validation error."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        same_dir = str(tmp_path)
        os.makedirs(same_dir, exist_ok=True)

        def _get_setting(sid):
            return {
                "source_directory": same_dir,
                "destination_directory": same_dir,
            }.get(sid, "")

        addon.getSetting.side_effect = _get_setting
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        # Continue past path confirmation screen
        dialog.yesnocustom.return_value = 1

        main_mod.run_organize()

        # dialog.ok must have been called with an error message
        dialog.ok.assert_called_once()
        call_args = dialog.ok.call_args
        # Second positional arg is the message
        assert "Library Organizer" in call_args[0][0]

    def test_empty_directory_shows_no_files(self, mock_kodi, tmp_path):
        """Directory with no video files -> 'no video files' dialog."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        src = str(tmp_path / "source")
        dst = str(tmp_path / "dest")
        os.makedirs(src)
        os.makedirs(dst)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": src,
            "destination_directory": dst,
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 0,
        }.get(sid, 0)

        # Continue past path confirmation screen
        dialog.yesnocustom.return_value = 1

        main_mod.run_organize()

        dialog.ok.assert_called_once()
        msg = dialog.ok.call_args[0][1]
        assert "No video files" in msg

    def test_dry_run_shows_preview_only(self, mock_kodi, tmp_path):
        """dry_run=True -> preview shown, no execute_plan call."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        src = str(tmp_path / "source")
        dst = str(tmp_path / "dest")
        os.makedirs(src)
        os.makedirs(dst)

        # Create a video file big enough
        video_file = os.path.join(src, "TestMovie.2020.mkv")
        with open(video_file, "wb") as f:
            f.truncate(200 * 1024 * 1024)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": src,
            "destination_directory": dst,
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": True,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        # yesnocustom called twice: path confirm -> Continue(1), op confirm -> Start(1)
        dialog.yesnocustom.side_effect = [1, 1]

        with patch.object(main_mod, "execute_plan") as mock_exec:
            main_mod.run_organize()
            # Preview shown (dry_run shows textviewer)
            dialog.textviewer.assert_called_once()
            # execute_plan NOT called because dry_run=True
            mock_exec.assert_not_called()

    def test_user_cancels_source_browse(self, mock_kodi):
        """User cancels source directory browse -> return immediately."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)
        _configure_addon_defaults(addon)

        # browseSingle returns empty string (cancelled)
        dialog.browseSingle.return_value = ""

        with patch.object(main_mod, "scan_directory") as mock_scan:
            main_mod.run_organize()
            mock_scan.assert_not_called()

    def test_user_cancels_confirmation(self, mock_kodi, tmp_path):
        """User cancels at operation confirmation -> no execution."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        src = str(tmp_path / "source")
        dst = str(tmp_path / "dest")
        os.makedirs(src)
        os.makedirs(dst)

        video_file = os.path.join(src, "TestMovie.2020.mkv")
        with open(video_file, "wb") as f:
            f.truncate(200 * 1024 * 1024)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": src,
            "destination_directory": dst,
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        # path confirm -> Continue(1), op confirm -> Cancel(0)
        dialog.yesnocustom.side_effect = [1, 0]

        with patch.object(main_mod, "execute_plan") as mock_exec:
            main_mod.run_organize()
            mock_exec.assert_not_called()

    def test_path_confirm_change_reopens_settings(self, mock_kodi, tmp_path):
        """User clicks Change on path confirmation -> Settings opens, then Continue."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        src = str(tmp_path / "source")
        dst = str(tmp_path / "dest")
        os.makedirs(src)
        os.makedirs(dst)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": src,
            "destination_directory": dst,
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        # First call: Change(2), second call: Continue(1), then cancel at op confirm
        dialog.yesnocustom.side_effect = [2, 1, 0]

        with patch.object(main_mod, "scan_directory") as mock_scan:
            mock_scan.return_value = MagicMock(groups=[])
            main_mod.run_organize()

        addon.openSettings.assert_called_once()

    def test_operation_confirm_details_shows_preview(self, mock_kodi, tmp_path):
        """User clicks Details on operation confirmation -> textviewer shown, then Start."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        src = str(tmp_path / "source")
        dst = str(tmp_path / "dest")
        os.makedirs(src)
        os.makedirs(dst)

        video_file = os.path.join(src, "TestMovie.2020.mkv")
        with open(video_file, "wb") as f:
            f.truncate(200 * 1024 * 1024)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": src,
            "destination_directory": dst,
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        # path confirm -> Continue(1), op confirm -> Details(2), then Start(1)
        dialog.yesnocustom.side_effect = [1, 2, 1]

        xbmcgui = mock_kodi["xbmcgui"]
        xbmcvfs = mock_kodi["xbmcvfs"]
        xbmcvfs.translatePath.return_value = str(tmp_path / "undo")
        xbmcvfs.mkdirs.return_value = True
        progress_mock = xbmcgui.DialogProgress.return_value
        progress_mock.iscanceled.return_value = False

        with patch.object(main_mod, "execute_plan") as mock_exec:
            mock_exec.return_value = MagicMock(
                was_cancelled=False,
                success_count=1,
                error_count=0,
                skipped_count=0,
                total_count=1,
            )
            main_mod.run_organize()

        dialog.textviewer.assert_called_once()
        assert "Operation preview" in dialog.textviewer.call_args[0][0]

    def test_path_confirm_cancel_exits(self, mock_kodi):
        """User cancels at path confirmation -> no scan runs."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)

        addon.getSetting.side_effect = lambda sid: {
            "source_directory": "/some/source",
            "destination_directory": "/some/dest",
        }.get(sid, "")
        addon.getSettingBool.side_effect = lambda sid: {
            "debug_logging": False,
            "dry_run": False,
            "clean_names": True,
            "handle_multipart": True,
            "undo_enabled": True,
        }.get(sid, False)
        addon.getSettingInt.side_effect = lambda sid: {
            "operation_mode": 0,
            "min_file_size_mb": 100,
        }.get(sid, 0)

        dialog.yesnocustom.return_value = 0  # Cancel

        with patch.object(main_mod, "scan_directory") as mock_scan:
            main_mod.run_organize()
            mock_scan.assert_not_called()


# ===========================================================================
# run_undo tests
# ===========================================================================

class TestRunUndo:
    """Tests for the undo flow."""

    def test_no_journal_shows_message(self, mock_kodi):
        """No undo journals -> dialog.ok 'No operations to undo'."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)
        xbmcvfs = mock_kodi["xbmcvfs"]

        addon.getSettingBool.side_effect = lambda sid: False

        xbmcvfs.translatePath.return_value = "/nonexistent/undo/"

        with patch.object(main_mod, "get_latest_journal", return_value=None):
            main_mod.run_undo()

        dialog.ok.assert_called_once()
        msg = dialog.ok.call_args[0][1]
        assert "No operations to undo" in msg

    def test_user_cancels_undo_confirmation(self, mock_kodi):
        """User says No to undo confirmation -> no execute_undo call."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)
        xbmcvfs = mock_kodi["xbmcvfs"]

        addon.getSettingBool.side_effect = lambda sid: False

        xbmcvfs.translatePath.return_value = "/some/undo/"

        fake_journal = MagicMock()
        fake_journal.entries = []
        fake_journal.timestamp = "2026-01-01 12:00:00"
        fake_journal.source_dir = "/movies"

        with patch.object(main_mod, "get_latest_journal", return_value="/some/undo/undo_123.json"), \
             patch.object(main_mod, "load_journal", return_value=fake_journal), \
             patch.object(main_mod, "execute_undo") as mock_exec:
            dialog.yesno.return_value = False
            main_mod.run_undo()
            mock_exec.assert_not_called()

    def test_successful_undo(self, mock_kodi):
        """Successful undo -> dialog.ok with success message."""
        main_mod = _import_main()
        addon = _get_addon(mock_kodi)
        dialog = _get_dialog(mock_kodi)
        xbmcvfs = mock_kodi["xbmcvfs"]
        xbmcgui = mock_kodi["xbmcgui"]

        addon.getSettingBool.side_effect = lambda sid: False

        xbmcvfs.translatePath.return_value = "/some/undo/"

        fake_entry = MagicMock()
        fake_entry.success = True
        fake_journal = MagicMock()
        fake_journal.entries = [fake_entry]
        fake_journal.timestamp = "2026-01-01 12:00:00"
        fake_journal.source_dir = "/movies"

        from shared.undo_journal import UndoResult
        fake_result = UndoResult(success_count=1, error_count=0, total_count=1)

        with patch.object(main_mod, "get_latest_journal", return_value="/some/undo/undo_123.json"), \
             patch.object(main_mod, "load_journal", return_value=fake_journal), \
             patch.object(main_mod, "execute_undo", return_value=fake_result):
            dialog.yesno.return_value = True
            progress_mock = xbmcgui.DialogProgress.return_value
            progress_mock.iscanceled.return_value = False

            main_mod.run_undo()

        # Should show success message
        dialog.ok.assert_called_once()
        msg = dialog.ok.call_args[0][1]
        assert "Undo complete" in msg
        assert "1" in msg
