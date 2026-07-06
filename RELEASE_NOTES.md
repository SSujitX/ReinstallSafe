# Changelog

All notable changes to [ReinstallSafe](https://github.com/SSujitX/ReinstallSafe) are documented in this file.

## [Unreleased]

### Added

- **Full software inventory CSV** — registry (all uninstall hives) + Microsoft Store/UWP apps; columns include install directory, website links, uninstall command, and `RestoreMethod` (`winget auto-reinstall`, `manual reinstall`, etc.).

### Fixed

- **Manifest load (critical)** — `BackupManifest.load()` was accidentally nested inside a helper and unreachable; restore, verify, and restore-page manifest preview were broken.
- **Browser restore path** — saves actual backed-up profile path in `browser_profile_paths` manifest field; restore uses saved path when parent exists, otherwise falls back to current install (fixes Opera/Tor Roaming vs Local mismatch and new Windows user paths).
- **Restore cancel** — cancelled restores no longer show “Restore complete”; `RestoreWorker` emits `cancelled` signal; robocopy cancel and post-category cancel checks stop restore reliably.
- **Backup page UI** — custom folders panel disabled on load when category is unchecked (matches browsers/user files panels).
- **Cancel responsiveness** — background thread kills silent subprocesses (reg/winget/netsh) on cancel; registry/Wi-Fi/game/email restore loops stop mid-category; closing the app during backup/restore prompts to cancel first.
- **winget CSV accuracy** — only marks `winget auto-reinstall` when package is in winget export JSON (no false fuzzy matches).
- **winget import failures** — tighter failure detection; ignores “0 failed” / “no errors” lines.
- **Manifest loading** — null/malformed list fields coerced safely; numeric strings parsed.
- **Backup progress** — user-file steps skipped when folder missing still advance progress bar.
- **Custom folders** — duplicate paths (`C:\Foo` vs `C:\Foo\`) deduplicated in UI.

---

## [1.0.0] - 2026-07-07

First public release. Windows backup and restore assistant for use **before and after** reinstalling Windows.

### Added

#### Core backup & restore

- **14 backup categories:** user files, custom folders, browser profiles, installed apps (winget + registry), AppData (Roaming), drivers, Wi‑Fi, fonts, registry, printers list, Windows settings, game saves, email profiles.
- **12 restore categories** with Safe, Full, and Custom restore modes.
- **Safe Restore** default: user files, custom folders, browsers, Wi‑Fi, fonts (skips risky registry/AppData/drivers).
- **`backup_manifest.json`** — records PC name, Windows version, selected categories, browser list, custom folder paths, file counts, warnings, and errors.
- **Backup verification** — sanity-check backup folder against manifest.
- **Cooperative cancel** — stop backup/restore without false “complete” status.
- **Progress tracking** — step-based progress bar with robocopy sub-progress.
- **TEMP redirect** — backup workspace uses `<backup>/.workspace/tmp` instead of filling `C:` temp.

#### User files & custom folders

- **User folder picker** — choose Desktop, Documents, Downloads, Pictures, Videos, Music individually.
- **Custom folders** — add arbitrary paths; original paths saved in manifest and `folder_map.json`.
- **Custom folder restore** — files copied back to original locations (e.g. `D:\Projects`).

#### Browsers

- **65+ browser definitions** — Chrome (stable, Beta, Dev, Canary), Edge channels, Brave, Firefox family, Opera variants, Chromium forks, security browsers, and more.
- **Automatic detection** — only installed browsers shown as “Detected”.
- **Cache excludes** — skips Cache, GPUCache, Service Worker, etc. for faster backups.
- **Close-browser prompts** on backup and restore.

#### Apps, system, and settings

- **winget export/import** for supported app reinstall after clean Windows.
- **Registry app inventory** CSV when winget is unavailable.
- **Driver export/import** via `pnputil`.
- **Wi‑Fi profile export/import** via `netsh` (home networks).
- **User font backup/restore** with registry registration.
- **Safe HKCU registry export/import.**
- **Windows settings restore** — personalization `.reg` files (taskbar, mouse, keyboard, desktop).
- **Game saves** — `Saved Games` and `Documents\My Games`.
- **Email** — Thunderbird profiles and Outlook PST copy.
- **Printers** — name list (reference only, no auto-restore).

#### UI

- **Vault Green theme** — cream paper backgrounds, deep forest green accent (`#1e5d43`), soft cards, no gradients.
- **Four pages:** Backup, Restore, Logs, Settings.
- **Collapsible sidebar** with floating toggle on the content border.
- **Custom hand-drawn nav icons** (backup, restore, logs, settings).
- **Selectable category cards**, browser grid, user-folder grid, custom folder list.
- **Preflight dialogs** — honest notes before backup/restore (`category_info.py`).
- **Toast notifications** and live mini console on Backup/Restore pages.
- **Logs page** with rotating file log via `LogBus`.

#### Settings & packaging

- **Default backup destination** in Settings — browse auto-saves; syncs to Backup page via `QSettings`.
- **System diagnostics** — admin, winget, robocopy availability badges.
- **App icon** — `assets/icon.ico` (Vault Green backup arrow tile).
- **PyInstaller build** — `uv run build.py` → `dist/ReinstallSafe.exe` with bundled theme and icon.
- **Path normalization** — fixes drive-relative paths like `D:` → `D:\` so backups don’t land on `C:` by mistake.
- **System drive warning** when backup destination is on `C:`.

#### Documentation

- **README.md** — user guide, SEO-focused, pre-reinstall checklist, FAQ, restore tables.
- **AGENT.md** — codebase architecture guide for developers and LLM agents.
- **Clone instructions** — `git clone https://github.com/SSujitX/ReinstallSafe`.

### Changed

- Restore page summary shows custom folder paths and selected user folders from manifest.
- Category card subtitles reflect honest restore expectations (extensions OK, logins need sync, etc.).
- `pyproject.toml` description updated for user-facing package metadata.

### Fixed

- **Settings → Backup destination** — saved default now appears on Backup page immediately (was only read once at startup).
- **Exe icon** — runtime window icon works in PyInstaller builds (`assets/icon.ico` bundled via `--add-data`).
- **Browser backup progress** — activity-based progress during winget/registry steps.
- **Cancel backup** — no false “Backup complete” toast on user cancel.
- **Toast shutdown crash** — removed fragile `destroyed` signal chain.
- **C: drive backup destination** — path normalization and warnings when destination is on system drive.
- **Chrome Beta** — included in browser detection (along with 60+ other browsers).

### Known limitations

- Not a full disk/system image — cannot clone Windows itself.
- Browser saved passwords and cookies may not survive a clean install (Windows DPAPI) — use browser sync.
- winget reinstalls only a subset of installed software.
- AppData backup is Roaming only — not `%LOCALAPPDATA%`.
- Printers: names only — no driver/port restore.
- Game saves: two standard folders — not Steam/Epic/Xbox launchers.

---

## Links

- [Repository](https://github.com/SSujitX/ReinstallSafe)
- [Unreleased changes](https://github.com/SSujitX/ReinstallSafe/compare/v1.0.0...HEAD)
- [1.0.0](https://github.com/SSujitX/ReinstallSafe/releases/tag/v1.0.0)