# AGENT.md — ReinstallSafe codebase guide for LLMs

This document explains **what ReinstallSafe is**, **how the code is organized**, **what each file does**, and **how data flows** through backup and restore. Read this before editing any file.

---

## 1. Product summary

**ReinstallSafe** is a **Windows-only** desktop app that helps users:

1. **Back up** personal data and settings **before** reinstalling/resetting Windows.
2. **Restore** that data **after** a clean Windows install.

It is **not** a full disk imaging tool. It copies files and exports Windows tools output (`robocopy`, `winget`, `pnputil`, `netsh`, `reg`) into a timestamped backup folder with a JSON manifest.

**Target users:** people wiping `C:` who need Documents, browsers, Wi‑Fi, apps list, etc. on an external drive.

**Honest limits:** browser passwords/cookies often fail after clean install (DPAPI); winget only reinstalls a subset of apps; printers are name-list only; Outlook OST files may be useless after reinstall; Thunderbird restore merges into an existing profile tree.

**Platform guard:** `main.py` exits immediately on non-Windows (`sys.platform != "win32"`).

---

## 2. Architecture (layers)

```
┌─────────────────────────────────────────────────────────────┐
│  main.py          → QApplication + MainWindow               │
├─────────────────────────────────────────────────────────────┤
│  UI LAYER         pages/  navigation  widgets  icons  theme │
│                   (PyQt6 widgets, signals, user input)      │
├─────────────────────────────────────────────────────────────┤
│  WORKER LAYER     workers/backup_worker  restore_worker     │
│                   (QThread — keeps UI responsive)             │
├─────────────────────────────────────────────────────────────┤
│  CORE LAYER       core/backup_manager  restore_manager     │
│                   + category modules (browsers, apps, …)    │
│                   (pure logic, no QWidget imports)          │
├─────────────────────────────────────────────────────────────┤
│  UTILS LAYER      paths, file_utils, logging, admin, …      │
├─────────────────────────────────────────────────────────────┤
│  WINDOWS TOOLS    robocopy, winget, pnputil, netsh, reg     │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** `app/core/` must **not** import Qt widgets. UI talks to core via workers and dataclass options.

---

## 3. End-to-end flows

### 3.1 Backup flow

```
BackupPage._start_backup()
  → builds BackupOptions (destination, categories, browser_keys, user_file_keys, custom_folders)
  → BackupWorker (QThread)
      → BackupManager.run(options)
          → creates ReinstallSafe_Backup_YYYY-MM-DD_HH-MM-SS/
          → use_backup_workspace() redirects TEMP into backup/.workspace/tmp
          → for each selected category: _run_category()
          → writes backup_manifest.json
  → signals: log_line, progress, finished_ok | cancelled | failed
  → BackupPage shows result; emits backup_completed → RestorePage prefilled
```

### 3.2 Restore flow

```
RestorePage._start_restore(mode: safe | full | custom)
  → builds RestoreOptions (backup_dir, selected_categories, browser_keys)
  → preflight dialogs (close browsers, email, notes, overwrite confirm)
  → RestoreWorker (QThread)
      → RestoreManager.run(options)
          → loads BackupManifest from backup_manifest.json
          → if mode==safe: strips RISKY_CATEGORIES (registry, appdata, drivers)
          → for each category: _run_category()
          → writes logs/restore_report_*.txt
  → RestorePage shows summary
```

### 3.3 Settings → Backup destination sync

```
SettingsPage Browse / Save
  → QSettings("ReinstallSafe", "ReinstallSafe") key: default_backup_destination
  → settings.sync()
  → emits default_destination_changed(path)
  → MainWindow connects → BackupPage.apply_default_destination(path)
  → on nav to Backup: refresh_destination_if_empty()
```

---

## 4. Backup categories (14 backup / 12 restore)

| Key | Backup | Restore | Safe Restore default |
|-----|--------|---------|----------------------|
| `user_files` | ✅ pick Desktop/Docs/… | ✅ | ✅ |
| `custom_folders` | ✅ path map saved | ✅ | ✅ |
| `browsers` | ✅ 65+ definitions | ✅ | ✅ |
| `apps` | ✅ winget + registry CSV | ✅ winget import only | ❌ |
| `appdata` | ✅ Roaming only | ✅ | ❌ (risky) |
| `drivers` | ✅ pnputil export | ✅ | ❌ (risky) |
| `wifi` | ✅ netsh export | ✅ | ✅ |
| `fonts` | ✅ user fonts | ✅ | ✅ |
| `registry` | ✅ safe HKCU keys | ✅ | ❌ (risky) |
| `windows_settings` | ✅ personalization .reg | ✅ | ❌ |
| `printers` | ✅ name list txt | ❌ | ❌ |
| `games` | ✅ 2 standard folders | ✅ | ❌ |
| `email` | ✅ Thunderbird + PST | ✅ | ❌ |

Category labels and honest UI notes live in **`app/core/category_info.py`**.

---

## 5. File map (every important file)

### Root

| File | Purpose |
|------|---------|
| `main.py` | Entry point: Windows-only guard, `QApplication`, load `theme.qss`, set icon via `app_icon_path()`, show `MainWindow`. |
| `build.py` | PyInstaller onefile build. Bundles `theme.qss` + `assets/icon.ico` (`--icon` + `--add-data`). Output: `dist/ReinstallSafe.exe`. |
| `_make_icon.py` | Generates `assets/icon.ico` (Vault Green tile + backup arrow). Run: `uv run _make_icon.py`. |
| `pyproject.toml` | Project metadata, `pyqt6` dep, dev `pyinstaller`. |
| `requirements.txt` | Pip-compatible deps list. |
| `README.md` | User-facing docs (SEO, workflow, FAQ). |
| `AGENT.md` | This file — LLM/onboarding guide. |
| `RELEASE_NOTES.md` | v1.0.0 release notes (features, fixes, limitations). |
| `tests/test_antigravity_fixes.py` | Unit tests for audit fixes (paths, custom folders, winget, Wi‑Fi, drivers, UI helpers). |
| `.github/workflows/ci.yml` | Windows GitHub Actions: unittest + compileall. |

### `assets/`

| File | Purpose |
|------|---------|
| `icon.ico` | App/window/exe icon. Loaded via `paths.app_icon_path()` (works in dev + frozen). |

### `app/` — shell & presentation

| File | Purpose |
|------|---------|
| `main_window.py` | `QMainWindow`: sidebar + `QStackedWidget` pages, floating sidebar toggle, toasts, admin warning. Wires `backup_completed` → restore folder, `default_destination_changed` → backup field. |
| `navigation.py` | Left sidebar nav buttons (Backup, Restore, Logs, Settings). Collapsible. Custom icons per tab. |
| `widgets.py` | Reusable UI: `glass_card`, `SelectableCard`, `Toast`, `section_title`, `hint_label`, `warning_banner`, `status_badge`. Cards use `QGraphicsDropShadowEffect`. |
| `icons.py` | Hand-drawn nav icons (backup/restore/logs/settings) + chevron for sidebar toggle. QPainter-based, recolors active/inactive. |
| `styles.py` | Loads `theme.qss`; `bundle_root()` for PyInstaller. Exports palette constants (`ACCENT`, `BG`, …). |
| `theme.qss` | Full app stylesheet — **Vault Green** theme (cream paper `#f4f1e8`, accent `#1e5d43`). No gradients. |

### `app/pages/` — one widget per screen

| File | Purpose |
|------|---------|
| `backup_page.py` | Destination picker, 14 category cards, user-folder checkboxes, 65+ browser checkboxes, custom folder list, progress + mini console. Builds `BackupOptions`, runs `BackupWorker`. Preflight dialogs (close browsers, category notes). |
| `restore_page.py` | Pick backup folder, manifest summary, 12 restore category cards **enabled from manifest data** (not empty pre-created folders). Browser picker on restore. Shows backup-path mismatch note, warning dialogs when `report.warnings` exist, and cancelled-restore dialog with partial report path. Safe/Full/Custom restore. Runs `RestoreWorker`. |
| `logs_page.py` | Live log viewer backed by `LogBus` (rotating file + in-memory `_all_lines` capped at 5000). |
| `settings_page.py` | Default backup destination (`QSettings`), diagnostics (admin/winget/robocopy), about/disclaimers. Browse auto-saves. Signal: `default_destination_changed`. |

### `app/workers/` — background threads

| File | Purpose |
|------|---------|
| `backup_worker.py` | `QThread` wrapping `BackupManager`. `cancel_event` for cooperative cancel. Signals: `log_line`, `progress`, `finished_ok`, `cancelled`, `failed`. |
| `restore_worker.py` | `QThread` wrapping `RestoreManager`. Signals: `finished_ok`, `cancelled`, `failed`. |

### `app/core/` — business logic (no UI)

| File | Purpose |
|------|---------|
| `backup_manager.py` | **Backup orchestrator.** `ALL_CATEGORIES`, `BackupOptions`, `ProgressTracker`, `BackupManager.run()`. Loops categories, calls module functions, fills manifest. |
| `restore_manager.py` | **Restore orchestrator.** `RESTORE_CATEGORIES`, `RISKY_CATEGORIES`, `RestoreOptions`, `RestoreReport`, `RestoreManager.run()`. |
| `manifest.py` | `BackupManifest` + `CategoryResult`. Fields: `selected_user_folders`, `custom_folders`, `detected_browsers`, `browser_profile_paths`, counts, warnings/errors. `from_dict()` coerces null/malformed JSON safely. `load(backup_dir)` reads `backup_manifest.json`. |
| `category_info.py` | UI copy: backup/restore card subtitles, preflight warning text builders. Single source of honest expectations. |
| `custom_folders.py` | Backup custom paths with `folder_map.json` + manifest entries. Restore to **original source paths** (including external drives). Blocks traversal via tampered `backup_name`, protected/system destinations, and active backup folders. Handles name collisions (`Projects_2`). |
| `browsers.py` | 65+ browsers. Backup saves `browser_profile_paths` in manifest. Restore uses saved path when parent exists, else `active_profile_root()` / `profile_root`. |
| `robocopy.py` | Wrapper around Windows `robocopy`. Flags: `/E /MT:32 /R:1 /W:1 /XJ`. Exit codes 0–7 = success. **12-hour default timeout.** File counts use filesystem delta (locale-neutral); overwrite restores fall back to source count. Sub-progress advances on output ticks (not English `"New File"` only). Supports cancel + sub-progress callbacks. |
| `command_runner.py` | Generic subprocess runner with live stdout lines, **system preferred encoding** (`locale.getpreferredencoding`), optional timeout, and cancel. On cancel/timeout kills process tree via `taskkill /T /F`. Used by reg, pnputil, netsh, winget. |
| `apps.py` | `winget export/import`, full `installed-programs.csv` (registry + AppX, install dir, links, RestoreMethod), `apps-list.txt`. |
| `appdata.py` | Backup/restore `%APPDATA%` Roaming only (excludes Temp, caches). |
| `drivers.py` | `pnputil /export-driver` and `/add-driver … /install`. Partial export kept on nonzero exit; restore warns instead of claiming full success. |
| `wifi.py` | `netsh wlan export profile key=clear` (quoted paths) and `netsh wlan add profile`. Writes `WIFI_PASSWORDS_ARE_CLEARTEXT.txt` warning. Distinguishes netsh failure from “no profiles”. |
| `fonts.py` | User fonts folder robocopy + HKCU registry registration on restore (TrueType / OpenType / TrueType Collection labels by extension). |
| `registry.py` | Export/import safe HKCU keys + `WINDOWS_SETTINGS_KEYS` for personalization. `import_windows_settings()` aliases registry import. |
| `detectors.py` | Printers list (PowerShell), game saves (2 folders), email (Thunderbird + Outlook PST/OST). |
| `validation.py` | `verify_backup()` — manifest vs on-disk folders, writes `logs/verify_report.json`. |
| `exceptions.py` | `BackupCancelled`, `RestoreCancelled`. |

### `app/utils/`

| File | Purpose |
|------|---------|
| `paths.py` | **Central path logic.** `SUBFOLDERS`, `user_files_locations()`, `user_file_options()`, `resolve_user_file_locations()`, `normalize_backup_destination()` (fixes `D:` → `D:\`; **relative paths resolve under user home**, not CWD), `is_system_drive()`, `bundle_root()`, `app_icon_path()`, `timestamped_backup_name()`. |
| `backup_workspace.py` | Context manager: redirects `TEMP`/`TMP` into `<backup>/.workspace/tmp` so C: temp doesn't fill during backup. |
| `file_utils.py` | `ensure_dir`, `read_json`/`write_json`, `human_size`, `count_files`, `safe_copy_file`, `which`. |
| `logging_utils.py` | `LogBus` singleton — Qt signal + rotating log file under `%LOCALAPPDATA%/ReinstallSafe/logs`. |
| `log_format.py` | Filters robocopy/winget spam from backup page mini console. |
| `admin.py` | `is_admin()` — ctypes Windows elevation check. |
| `windows_info.py` | Computer name, username, Windows version for manifest. |

---

## 6. Key data structures

### `BackupOptions` (`backup_manager.py`)

```python
destination: Path
selected_categories: set[str]
custom_folders: list[Path]
browser_keys: list[str]      # empty → blocked in UI (must pick at least one)
user_file_keys: list[str]    # empty → all standard folders
```

### `RestoreOptions` (`restore_manager.py`)

```python
backup_dir: Path
mode: "safe" | "full" | "custom"
selected_categories: set[str]
browser_keys: list[str]      # restore page browser picker; empty blocked when browsers category selected
```

### `BackupManifest` (`manifest.py`)

Written to `<backup>/backup_manifest.json`. Critical fields for restore:

- `selected_items` — categories backed up
- `selected_user_folders` — e.g. `["Desktop", "Documents"]`
- `custom_folders` — `[{"source_path": "D:\\Projects", "backup_name": "Projects"}]`
- `detected_browsers` — e.g. `["chrome", "chrome_beta", "edge"]`
- `browser_profile_paths` — e.g. `{"chrome": "C:\\Users\\...\\User Data"}` (exact path backed up)
- `categories` — per-category file counts and detail strings

### Custom folder mapping

- **Backup:** `custom_folders/<backup_name>/` + `custom_folders/folder_map.json`
- **Restore:** reads manifest or `folder_map.json`, robocopy back to `source_path`

---

## 7. UI theme & conventions

- **Theme name:** Vault Green
- **Accent:** `#1e5d43` (hover `#174a35`, pressed `#0f3826`)
- **Backgrounds:** `#f4f1e8`, cards `#fdfcf9`
- **No gradients** in QSS
- **SelectableCard:** checkbox card for categories/browsers/folders; emits `toggled`
- **Sidebar toggle:** lives on `MainWindow` (not `Sidebar`), positioned on sidebar/content border via `_position_sidebar_toggle()`
- **Toasts:** stacked bottom-right; pruned on close; no fragile `destroyed` signal chains

---

## 8. PyInstaller / frozen exe notes

| Concern | Solution |
|---------|----------|
| `theme.qss` path | `styles._base_dir()` → `sys._MEIPASS` when frozen |
| `icon.ico` at runtime | `paths.app_icon_path()` → `_MEIPASS/assets/icon.ico`; bundled via `build.py --add-data` |
| exe file icon | `build.py --icon=assets/icon.ico` |
| Dev vs frozen root | `paths.bundle_root()` |

---

## 9. Windows tools used (by category)

| Category | Tool | Module |
|----------|------|--------|
| User files, custom folders, browsers, appdata, fonts, games, email | `robocopy` | `robocopy.py` |
| Apps | `winget export/import/list` | `apps.py` |
| Drivers | `pnputil` | `drivers.py` |
| Wi‑Fi | `netsh wlan` | `wifi.py` |
| Registry, Windows settings | `reg export/import` | `registry.py` |
| Printers | PowerShell `Get-Printer` | `detectors.py` |

All subprocess output streams to UI via `on_line` callbacks.

---

## 10. Progress & cancel

- **`ProgressTracker`** (`backup_manager.py`): discrete steps + robocopy sub-fraction per step → 0–100%.
- **Cancel:** `threading.Event` passed to manager/modules. `BackupCancelled` / `RestoreCancelled` raised; workers emit `cancelled` with partial backup/report path.
- **Robocopy cancel:** checked between output lines; `CommandRunner` kills full process tree (`taskkill /T /F`) on cancel or timeout.
- **Partial failures:** AppData, fonts, games, email robocopy warnings propagate to manifest `warnings` and set category `succeeded=False` when robocopy exits with code ≥ 8.
- **Session summary:** `_write_session_log()` writes `logs/backup_session_summary.txt` at end of backup.

---

## 11. What was built / evolved (project history for agents)

Recent major work in this repo:

1. **Vault Green UI** — replaced earlier blue/dark themes; `theme.qss`, `styles.py`, `widgets.py` shadows.
2. **Browser expansion** — 65+ browsers in `browsers.py`; UI grid on backup page; dedupe by profile path.
3. **User folder picker** — choose Desktop/Documents/… individually; `selected_user_folders` in manifest.
4. **Custom folder restore** — `custom_folders.py` saves original paths; restore to same locations; Safe Restore includes it.
5. **Windows settings restore** — was backup-only; now imports via `registry.import_windows_settings()`.
6. **Category honesty** — `category_info.py` + preflight dialogs on backup/restore pages.
7. **Restore prompts** — close browsers/email before restore; install browsers first reminder.
8. **Settings → Backup sync** — `QSettings` + signal; browse auto-saves; backup page refreshes.
9. **Icon** — `assets/icon.ico` via `_make_icon.py`; PyInstaller bundles for exe + runtime window icon.
10. **Path normalization** — `normalize_backup_destination()` prevents `D:` landing on C:.
11. **TEMP redirect** — `backup_workspace.py` keeps working files inside backup folder.
12. **README** — SEO user-facing docs; `AGENT.md` for developers/agents.
13. **Software inventory CSV** — registry + AppX scan, install paths, links, `RestoreMethod` column.
14. **Restore audit fixes** — `BackupManifest.load()` restored; post-category cancel checks; browser path fallback on new Windows user; winget CSV accuracy; restore cancel UI signal; CommandRunner cancel watcher; close-window prompt during active jobs.
15. **Reliability hardening (v1.0.0 audit)** — custom-folder `backup_name` traversal blocked; restore categories from manifest (not empty folders); browser picker on restore + empty browser backup blocked; partial robocopy/driver failures surfaced in manifest/report; robocopy 12h timeout + process-tree kill; overwrite restore counts fixed; relative backup paths under user home; Wi‑Fi cleartext warning file; restore UI shows warnings and cancelled partial report dialog; manifest backup-path mismatch note; localized winget failure detection; 32-bit registry fallback; printer backup respects cancel.
16. **Tests & CI** — `tests/test_antigravity_fixes.py` (12 unit tests); `.github/workflows/ci.yml` runs tests + `compileall` on `windows-latest`.

**Not bug-free:** remaining known gaps are mostly product limits (see README). Minor edges: winget failure heuristics may false-positive; winget list table parsing is improved but not locale-proof; no GUI/integration tests; browser passwords may still fail after clean install (DPAPI).

---

## 12. Safe editing guide for agents

### Adding a new backup category

1. Add to `ALL_CATEGORIES` in `backup_manager.py`.
2. Implement backup in `_run_category()` switch.
3. Add subfolder to `paths.SUBFOLDERS`.
4. If restorable: add to `RESTORE_CATEGORIES` + `restore_manager._run_category()`.
5. Add descriptions to `category_info.py`.
6. Add card on backup/restore pages (or it won't be selectable).
7. Update `validation.py` expectations if needed.

### Adding a browser

1. Add `BrowserDefinition` to `_browser_definitions()` in `browsers.py`.
2. Use `c()` for Chromium `%LOCALAPPDATA%/.../User Data` or `r()` for Roaming.
3. For Opera-style dual paths, use `c_multi()` with `detect_roots`.
4. UI auto-lists via `browser_options()` — no backup_page change needed.

### Do not

- Import QWidget into `app/core/`.
- Commit secrets or `.env`.
- Use robocopy `/Z` or `/ZB` (removed intentionally — no hidden temp files on C:).
- Assume browser passwords restore on clean install (document limitation).

---

## 13. Run / test / build

```powershell
# Dev
uv sync
uv run main.py

# Unit tests (also run in GitHub Actions CI)
uv run python -m unittest discover -s tests -v

# Regenerate icon
uv run _make_icon.py

# Build exe
uv run build.py

# Syntax check
uv run python -c "from app.main_window import MainWindow"
```

**Platform:** Windows only (`main.py` guard + robocopy, reg, pnputil, netsh, QStandardPaths).

**Admin:** optional but recommended for drivers/registry; warned at startup in `main_window.py`.

---

## 14. Backup folder layout (on disk)

```
ReinstallSafe_Backup_YYYY-MM-DD_HH-MM-SS/
├── backup_manifest.json       ← source of truth for restore UI
├── user_files/{Desktop,Documents,…}/
├── custom_folders/
│   ├── folder_map.json        ← redundant copy of path map
│   └── {backup_name}/         ← e.g. Projects, Projects_2
├── browsers/{chrome,edge,…}/
├── apps/{winget-apps.json, installed-programs.csv, …}/
├── wifi/*.xml
├── fonts/
├── registry/*.reg
├── windows_settings/*.reg
├── appdata/                   ← mirror of Roaming
├── drivers/                   ← pnputil export tree
├── games/
├── email/
├── printers/printers-list.txt
└── logs/                      ← session logs, verify_report, restore_report, failed-apps
```

---

## 15. Quick dependency graph

```
main.py
 └── MainWindow
      ├── BackupPage → BackupWorker → BackupManager → [core modules]
      ├── RestorePage → RestoreWorker → RestoreManager → [core modules]
      ├── LogsPage → LogBus
      └── SettingsPage → QSettings

BackupManager / RestoreManager
 ├── robocopy.py → subprocess robocopy
 ├── command_runner.py → subprocess reg/winget/pnputil/netsh
 ├── browsers.py, custom_folders.py, apps.py, …
 └── manifest.py → backup_manifest.json

paths.py ← used everywhere for folders, bundle root, destination normalization
category_info.py ← used by pages for UI copy only
```

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| Safe Restore | Files, custom folders, browsers, Wi‑Fi, fonts — no registry/appdata/drivers |
| Full Restore | All selected categories that have restore code |
| Risky categories | `registry`, `appdata`, `drivers` — excluded from Safe Restore |
| Manifest | `backup_manifest.json` describing one backup run |
| Frozen build | PyInstaller onefile exe with `_MEIPASS` extraction |
| winget | Windows Package Manager — app reinstall channel |

---

*Last updated for v1.0.0: audit hardening, unit tests, GitHub Actions CI, restore UI warnings, manifest-driven restore categories, and documented product limits.*
