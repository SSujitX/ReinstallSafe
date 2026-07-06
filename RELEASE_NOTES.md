# 🚀 ReinstallSafe v1.0.0 — First Public Release

**Version:** 1.0.0  
**Date:** July 7, 2026  
**Platform:** Windows 10 / Windows 11

---

ReinstallSafe is a free Windows backup and restore assistant for **before and after reinstalling Windows**. Save your files, browser profiles, Wi‑Fi, apps list, and settings to an external drive — then restore them on a clean install.

---

## 🐛 Bug Fixes

- **📋 Manifest Load (Critical)**: Fixed `BackupManifest.load()` being unreachable (nested inside a helper) — restore, backup verification, and restore-page manifest preview now work correctly
- **🌐 Browser Restore Path**: Saves the actual backed-up profile path in `browser_profile_paths`; restore uses that path when valid, otherwise falls back to the current install (fixes Opera/Tor Roaming vs Local mismatch and new Windows user paths)
- **⏹️ Restore Cancel**: Cancelled restores no longer show “Restore complete”; `RestoreWorker` emits a dedicated `cancelled` signal; robocopy and post-category cancel checks stop restore reliably
- **⏹️ Cancel Responsiveness**: Background thread kills silent subprocesses (reg, winget, netsh) on cancel; registry, Wi‑Fi, game, and email restore loops stop mid-category; closing the app during backup/restore prompts to cancel first
- **⚙️ Settings → Backup Sync**: Default backup destination from Settings now appears on the Backup page immediately (was only read once at startup)
- **🖼️ Exe Icon**: Runtime window icon works in PyInstaller builds (`assets/icon.ico` bundled via `--add-data`)
- **📊 Backup Progress**: User-file steps skipped when a folder is missing still advance the progress bar; browser backup shows activity during winget/registry steps
- **❌ Cancel Backup**: No false “Backup complete” toast when the user cancels
- **🔔 Toast Shutdown**: Removed fragile `destroyed` signal chain that could crash on exit
- **💾 Backup Destination**: Path normalization fixes drive-relative paths like `D:` → `D:\` so backups don’t land on `C:` by mistake; warning when destination is on the system drive
- **🌐 Chrome Beta & Browsers**: Chrome Beta and 60+ other browsers included in detection and backup grid
- **📦 winget CSV Accuracy**: Only marks `winget auto-reinstall` when the package is in the winget export JSON (no false fuzzy matches)
- **📦 winget Import Failures**: Tighter failure detection; ignores “0 failed” / “no errors” lines
- **📄 Manifest Loading**: Null/malformed list fields coerced safely; numeric strings parsed correctly
- **📁 Custom Folders UI**: Duplicate paths (`C:\Foo` vs `C:\Foo\`) deduplicated in the picker
- **📁 Backup Page UI**: Custom folders panel disabled on load when the category is unchecked (matches browsers/user files panels)

### Reliability & safety (v1.0.0 audit)

- **🔒 Custom folder traversal**: Tampered manifest `backup_name` values can no longer escape the custom-folder backup root
- **📂 Restore category detection**: Restore page enables categories from manifest data, not empty pre-created backup folders
- **🌐 Browser restore picker**: Choose which backed-up browser profiles to restore; empty browser selection blocked on backup
- **⚠️ Partial failures visible**: AppData, fonts, games, and email robocopy failures mark categories partial and add manifest warnings
- **⏱️ Robocopy timeout**: 12-hour default timeout; cancel/timeout kills the full process tree (`taskkill /T /F`)
- **📊 Restore file counts**: Overwrite restores no longer report 0 copied files when destination count did not increase
- **📁 Relative backup paths**: Relative destinations resolve under the user home directory, not the current working directory
- **📶 Wi‑Fi export**: Quoted netsh paths; explicit `WIFI_PASSWORDS_ARE_CLEARTEXT.txt` warning in backup folder
- **🖨️ Printer backup**: Respects cooperative cancel during PowerShell enumeration
- **🔧 Driver export/import**: Partial pnputil output kept with warnings instead of whole-category fatal failure
- **📋 Restore UI feedback**: Warning dialog when restore report has warnings; cancelled restore shows partial report path in a dialog
- **📍 Backup path note**: Restore summary warns when selected folder differs from manifest `backup_path`
- **📦 winget detection**: Broader localized failure detection; improved list parsing; 32-bit registry hive fallback
- **🔤 Subprocess encoding**: Uses system preferred encoding instead of hard-coded OEM
- **🔤 Font registry labels**: OTF/TTC fonts registered with correct OpenType / TrueType Collection labels
- **📈 Robocopy progress**: Sub-progress advances on output activity, less dependent on English `"New File"` lines
- **📝 Session log**: Backup writes `logs/backup_session_summary.txt`
- **📜 Logs page**: In-memory log export list capped at 5000 lines (matches console block count)
- **🪟 Platform guard**: App exits cleanly on non-Windows instead of crashing mid-import
- **✅ Tests & CI**: 12 unit tests in `tests/`; GitHub Actions workflow on Windows

---

## ✨ New Features & Optimizations

### 💾 Core Backup & Restore

- **14 backup categories**: user files, custom folders, browser profiles, installed apps (winget + registry), AppData (Roaming), drivers, Wi‑Fi, fonts, registry, printers list, Windows settings, game saves, email profiles
- **12 restore categories** with **Safe**, **Full**, and **Custom** restore modes
- **Safe Restore default**: user files, custom folders, browsers, Wi‑Fi, fonts (skips risky registry / AppData / drivers)
- **`backup_manifest.json`**: records PC name, Windows version, selected categories, browser list, custom folder paths, file counts, warnings, and errors
- **Backup verification**: sanity-check backup folder against manifest
- **Cooperative cancel**: stop backup or restore without a false “complete” status
- **Progress tracking**: step-based progress bar with robocopy sub-progress
- **TEMP redirect**: backup workspace uses `<backup>/.workspace/tmp` instead of filling `C:` temp

### 📂 User Files & Custom Folders

- **User folder picker**: choose Desktop, Documents, Downloads, Pictures, Videos, Music individually
- **Custom folders**: add arbitrary paths; original paths saved in manifest and `folder_map.json`
- **Custom folder restore**: files copied back to original locations (e.g. `D:\Projects`)

### 🌐 Browsers

- **65+ browser definitions**: Chrome (stable, Beta, Dev, Canary), Edge channels, Brave, Firefox family, Opera variants, Chromium forks, security browsers, and more
- **Automatic detection**: only installed browsers shown as “Detected”
- **Cache excludes**: skips Cache, GPUCache, Service Worker, etc. for faster backups
- **Close-browser prompts** on backup and restore

### 📦 Apps, System & Settings

- **Full software inventory CSV**: registry (all uninstall hives) + Microsoft Store/UWP apps — install directory, website links, uninstall command, and `RestoreMethod` (`winget auto-reinstall`, `manual reinstall`, etc.)
- **winget export/import** for supported app reinstall after clean Windows
- **Registry app inventory** CSV when winget is unavailable
- **Driver export/import** via `pnputil`
- **Wi‑Fi profile export/import** via `netsh` (home networks)
- **User font backup/restore** with registry registration
- **Safe HKCU registry export/import**
- **Windows settings restore**: personalization `.reg` files (taskbar, mouse, keyboard, desktop)
- **Game saves**: `Saved Games` and `Documents\My Games`
- **Email**: Thunderbird profiles and Outlook PST copy
- **Printers**: name list (reference only, no auto-restore)

### 🎨 UI & Experience

- **Vault Green theme**: cream paper backgrounds, deep forest green accent (`#1e5d43`), soft cards, no gradients
- **Four pages**: Backup, Restore, Logs, Settings
- **Collapsible sidebar** with floating toggle on the content border
- **Custom hand-drawn nav icons** (backup, restore, logs, settings)
- **Selectable category cards**, browser grid, user-folder grid, custom folder list
- **Preflight dialogs**: honest notes before backup/restore (what will and won’t restore)
- **Toast notifications** and live mini console on Backup/Restore pages
- **Logs page** with rotating file log

### ⚙️ Settings & Packaging

- **Default backup destination** in Settings — browse auto-saves; syncs to Backup page via `QSettings`
- **System diagnostics**: admin, winget, robocopy availability badges
- **App icon**: `assets/icon.ico` (Vault Green backup arrow tile)
- **PyInstaller build**: `uv run build.py` → `dist/ReinstallSafe.exe` with bundled theme and icon
- **Honest category subtitles**: restore expectations shown on each card (extensions OK, logins need sync, etc.)
- **GitHub Actions CI**: Windows workflow runs unit tests and compile check on push/PR

### 📚 Documentation

- **README.md**: user guide, pre-reinstall checklist, FAQ, restore tables
- **AGENT.md**: codebase architecture guide for developers and LLM agents

---

## ⚠️ Known Limitations

- Not a full disk/system image — cannot clone Windows itself
- Browser saved passwords and cookies may not survive a clean install (Windows DPAPI) — use browser sync
- winget reinstalls only a subset of installed software
- AppData backup is Roaming only — not `%LOCALAPPDATA%`
- Printers: names only — no driver/port restore
- Game saves: two standard folders — not Steam/Epic/Xbox launchers
- Outlook OST files are backed up but often useless after a clean Windows install
- Thunderbird restore merges into an existing profile folder rather than creating an isolated profile
- Restore may finish with warnings (partial robocopy, driver, or winget failures) — check `logs/restore_report_*.txt`

---

## 🔗 Links

- [Repository](https://github.com/SSujitX/ReinstallSafe)
- [Download Release](https://github.com/SSujitX/ReinstallSafe/releases/tag/v1.0.0)
- [Report an Issue](https://github.com/SSujitX/ReinstallSafe/issues)

---

**Made with ❤️ for everyone reinstalling Windows**
