"""Unit tests for ReinstallSafe core backup/restore logic."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from app.core.apps import _looks_like_winget_failure
from app.core.browsers import _browser_definitions, _restore_destination
from app.core.custom_folders import _is_safe_custom_restore_destination, _safe_custom_backup_source
from app.core.detectors import detect_printers
from app.core.drivers import export_drivers
from app.core.wifi import export_wifi_profiles
from app.utils.paths import normalize_backup_destination
from app.widgets import Toast


class BrowserDefinitionTests(unittest.TestCase):
    def test_opera_restore_fallback_uses_roaming_profile(self) -> None:
        opera = next(browser for browser in _browser_definitions() if browser.key == "opera")
        saved_local = str(Path.home() / "AppData" / "Local" / "Opera Software" / "Opera Stable" / "User Data")
        with patch.object(type(opera), "active_profile_root", return_value=opera.profile_root):
            destination = _restore_destination(opera, {opera.key: saved_local}, opera.key)
        self.assertEqual(destination, opera.profile_root)


class PrinterDetectionTests(unittest.TestCase):
    @patch("app.core.detectors.CommandRunner")
    def test_failed_powershell_output_is_not_returned_as_printer_name(self, runner_cls: MagicMock) -> None:
        runner = runner_cls.return_value
        runner.run.return_value = MagicMock(
            succeeded=False,
            output_lines=["Get-Printer : Access is denied", "At line:1 char:1"],
        )
        lines: list[str] = []

        names = detect_printers(on_line=lines.append)

        self.assertEqual(names, [])
        self.assertTrue(any("Could not enumerate printers" in line for line in lines))


class OutlookLayoutTests(unittest.TestCase):
    @patch("app.core.detectors.detect_outlook_data_files")
    @patch("app.core.detectors.safe_copy_file", return_value=True)
    @patch("app.core.detectors.detect_thunderbird_profiles", return_value=None)
    def test_outlook_backup_uses_pst_and_ost_subfolders(
        self,
        _thunderbird: MagicMock,
        _copy: MagicMock,
        outlook_files: MagicMock,
    ) -> None:
        from app.core.detectors import backup_email_profiles

        pst = Path("C:/Users/me/Documents/Outlook Files/mail.pst")
        ost = Path("C:/Users/me/AppData/Local/Microsoft/Outlook/mail.ost")
        outlook_files.return_value = {"pst": [pst], "ost": [ost]}

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            copied, _warnings = backup_email_profiles(dest, on_line=lambda _line: None)

            self.assertEqual(copied, 2)
            self.assertTrue((dest / "outlook" / "pst").exists())
            self.assertTrue((dest / "outlook" / "ost").exists())


class CustomFolderRestoreSafetyTests(unittest.TestCase):
    def test_external_drive_custom_folder_destination_is_allowed(self) -> None:
        self.assertTrue(_is_safe_custom_restore_destination(Path("D:/Projects")))

    def test_protected_or_root_custom_folder_destinations_are_blocked(self) -> None:
        self.assertFalse(_is_safe_custom_restore_destination(Path("C:/Windows")))
        self.assertFalse(_is_safe_custom_restore_destination(Path("C:/")))

    def test_active_backup_folder_destination_is_blocked(self) -> None:
        backup_dir = Path("E:/Backups/ReinstallSafe_Backup_2026-07-07_12-00-00")
        self.assertFalse(_is_safe_custom_restore_destination(backup_dir / "custom_folders" / "Projects", backup_dir))

    def test_manifest_backup_name_cannot_escape_custom_folder_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            custom_root = Path(tmp) / "custom_folders"
            custom_root.mkdir()
            safe_dir = custom_root / "Projects"
            safe_dir.mkdir()
            self.assertEqual(_safe_custom_backup_source(custom_root, "Projects"), safe_dir.resolve())
            self.assertIsNone(_safe_custom_backup_source(custom_root, "../secrets"))
            self.assertIsNone(_safe_custom_backup_source(custom_root, "..\\secrets"))


class AppsParsingTests(unittest.TestCase):
    def test_localized_winget_failure_lines_are_detected(self) -> None:
        self.assertTrue(_looks_like_winget_failure("Installation fehlgeschlagen"))
        self.assertTrue(_looks_like_winget_failure("Erreur lors de l'installation"))
        self.assertFalse(_looks_like_winget_failure("Successfully installed Package"))
        self.assertFalse(_looks_like_winget_failure("0 failed"))


class PathNormalizationTests(unittest.TestCase):
    def test_relative_backup_destination_resolves_under_user_home(self) -> None:
        resolved = normalize_backup_destination("Backups")
        self.assertEqual(resolved.parent, Path.home().resolve())


class WifiAndDriverRobustnessTests(unittest.TestCase):
    @patch("app.core.wifi.CommandRunner")
    def test_wifi_failed_netsh_without_xml_logs_warning(self, runner_cls: MagicMock) -> None:
        runner = runner_cls.return_value
        runner.run.return_value = MagicMock(succeeded=False, return_code=1)
        lines: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            count = export_wifi_profiles(Path(tmp), on_line=lines.append)

        self.assertEqual(count, 0)
        self.assertTrue(any("Wi-Fi export failed" in line for line in lines))

    @patch("app.core.drivers.CommandRunner")
    def test_driver_export_keeps_partial_export_on_pnputil_error(self, runner_cls: MagicMock) -> None:
        runner = runner_cls.return_value
        runner.run.return_value = MagicMock(succeeded=False, return_code=5)
        lines: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "driver1").mkdir()
            exported = export_drivers(dest, on_line=lines.append)

        self.assertEqual(exported, 1)
        self.assertTrue(any("Partial driver export kept" in line for line in lines))


class ToastLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_toasts_delete_on_close_without_destroyed_prune_hook(self) -> None:
        parent = QWidget()
        toast = Toast(parent, "hello", kind="info", duration_ms=1)
        self.assertTrue(toast.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose))


if __name__ == "__main__":
    unittest.main()
