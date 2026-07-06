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

---

## 🔗 Links

- [Repository](https://github.com/SSujitX/ReinstallSafe)
- [Download Release](https://github.com/SSujitX/ReinstallSafe/releases/tag/v1.0.0)
- [Report an Issue](https://github.com/SSujitX/ReinstallSafe/issues)

---

**Made with ❤️ for everyone reinstalling Windows**
