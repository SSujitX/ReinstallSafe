"""Backup verification: sanity-checks a backup folder against its manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.manifest import BackupManifest
from app.utils.file_utils import count_files, write_json
from app.utils.paths import MANIFEST_FILENAME


@dataclass
class VerificationReport:
    backup_path: str
    manifest_found: bool = False
    ok: bool = True
    issues: list[str] = field(default_factory=list)
    category_findings: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "backup_path": self.backup_path,
            "manifest_found": self.manifest_found,
            "ok": self.ok,
            "issues": self.issues,
            "category_findings": self.category_findings,
        }


def verify_backup(backup_dir: Path) -> VerificationReport:
    """Check that the manifest exists and that backed-up categories have files on disk."""
    report = VerificationReport(backup_path=str(backup_dir))

    if not backup_dir.exists():
        report.ok = False
        report.issues.append("Backup folder does not exist.")
        return report

    manifest_file = backup_dir / MANIFEST_FILENAME
    if not manifest_file.exists():
        report.ok = False
        report.issues.append(f"Manifest file '{MANIFEST_FILENAME}' is missing.")
        return report

    report.manifest_found = True
    try:
        manifest = BackupManifest.load(backup_dir)
    except Exception as exc:
        report.ok = False
        report.issues.append(f"Manifest could not be parsed: {exc}")
        return report

    if manifest.errors:
        report.issues.append(f"Backup recorded {len(manifest.errors)} error(s) during creation.")

    for key, info in manifest.categories.items():
        if not info.get("selected"):
            continue
        rel_path = info.get("relative_path") or key
        category_dir = backup_dir / rel_path
        if not category_dir.exists():
            report.ok = False
            msg = f"Category '{info.get('label', key)}' folder is missing on disk."
            report.issues.append(msg)
            report.category_findings[key] = "MISSING"
            continue

        actual_count = count_files(category_dir)
        expected = info.get("file_count", 0)
        if actual_count == 0 and expected and expected > 0:
            report.ok = False
            report.category_findings[key] = "EMPTY"
            report.issues.append(f"Category '{info.get('label', key)}' has no files but expected data.")
        else:
            report.category_findings[key] = f"OK ({actual_count} files)"

    if not report.issues:
        report.issues.append("All selected categories verified successfully.")

    write_json(backup_dir / "logs" / "verify_report.json", report.to_dict())
    return report
