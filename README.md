# ReinstallSafe — Back Up Your PC Before Reinstalling Windows

**ReinstallSafe** is a free Windows backup and restore assistant built for one job: **save everything important before you reset, reinstall, or clean-install Windows** — then bring it back on the new setup.

Back up your **Desktop, Documents, Downloads, custom folders, browser profiles (Chrome, Edge, Brave, Firefox, and 60+ others), Wi‑Fi passwords, fonts, app list, drivers, email profiles, game saves, and Windows personalization** to an external drive. After Windows is fresh, run **Safe Restore** or **Full Restore** to recover your data.

> **Do this before you wipe your PC.** ReinstallSafe is not a full disk image tool — it backs up your **files, profiles, settings, and app inventory**, then reinstalls supported apps with **winget** on the new Windows install. Browser saved passwords and cookies may not survive a clean install (Windows encryption) — **turn on browser sync or export passwords first.**

---

## Table of contents

- [Why use ReinstallSafe?](#why-use-reinstallsafe)
- [Before you reinstall Windows — checklist](#before-you-reinstall-windows--checklist)
- [What gets backed up](#what-gets-backed-up)
- [What restores after a fresh Windows install](#what-restores-after-a-fresh-windows-install)
- [Quick start](#quick-start)
- [How to use: backup → reinstall → restore](#how-to-use-backup--reinstall--restore)
- [Safe Restore vs Full Restore](#safe-restore-vs-full-restore)
- [Important limitations](#important-limitations)
- [FAQ](#faq)
- [Build from source](#build-from-source)
- [Project structure](#project-structure)

---

## Why use ReinstallSafe?

Reinstalling Windows is the best way to fix a slow PC, remove bloatware, or start clean after malware — but a fresh install **deletes your files, browser data, Wi‑Fi networks, and installed programs**.

ReinstallSafe gives you a **guided backup before reinstall** and a **guided restore after reinstall**, without needing to hunt through `%AppData%` paths or write batch scripts.

| Problem | How ReinstallSafe helps |
|--------|-------------------------|
| “I’m about to reset Windows — what do I save?” | One-click **Full Backup** with 14 categories |
| “I only want Documents + Chrome + Wi‑Fi” | **Custom Backup** — pick folders and categories |
| “Where do I put the backup?” | Save to an **external drive** (recommended) or any folder |
| “How do I get my stuff back?” | **Safe Restore** or **Full Restore** from your backup folder |
| “Will my apps come back?” | **winget** reinstalls supported apps; others need manual install |

Works on **Windows 10 and Windows 11**.

---

## Before you reinstall Windows — checklist

Complete these steps **before** you start Windows Setup, “Reset this PC”, or a clean install:

1. **Plug in an external drive** (USB HDD/SSD) — avoid backing up only to `C:` if you are wiping `C:`.
2. **Open ReinstallSafe → Backup** and set your destination (or set a default in **Settings**).
3. Run **One-Click Full Backup** (or choose categories manually).
4. **Close all browsers** when prompted — profiles copy cleanly only when browsers are not running.
5. **Enable browser sync** (Chrome, Edge, Firefox) or export saved passwords.
6. **Verify Backup** — confirms folders and manifest match.
7. **Safely eject the drive** — keep it unplugged until Windows is reinstalled.
8. After the new Windows is ready, install ReinstallSafe again and run **Restore**.

---

## What gets backed up

ReinstallSafe organizes everything into a timestamped folder, e.g. `ReinstallSafe_Backup_2026-07-07_22-30-00/`.

| Category | What it includes |
|----------|------------------|
| **User files** | Desktop, Documents, Downloads, Pictures, Videos, Music — **you choose which folders** |
| **Custom folders** | Any path you add (e.g. `D:\Projects`) — **original paths saved for restore** |
| **Browser profiles** | Chrome, Chrome Beta, Edge, Brave, Firefox, Opera, Vivaldi, and **60+ browsers** — extensions and bookmarks; caches skipped |
| **Installed apps** | `winget export` + registry inventory (CSV list) |
| **AppData** | `%APPDATA%` Roaming settings (not Local AppData) |
| **Drivers** | Third-party drivers via `pnputil` export |
| **Wi‑Fi** | Saved wireless profiles and passwords (`netsh`) |
| **Fonts** | User-installed fonts |
| **Registry** | Safe HKCU keys (Explorer, environment, mapped drives) |
| **Windows settings** | Taskbar, mouse, keyboard, desktop personalization |
| **Printers** | Printer name list (reference only) |
| **Game saves** | `Saved Games` and `Documents\My Games` |
| **Email** | Thunderbird profiles + Outlook PST files |

Every backup writes **`backup_manifest.json`** — a record of what was backed up, when, and from which PC. The Restore page reads this automatically.

---

## What restores after a fresh Windows install

| Category | Restores automatically? | Notes |
|----------|-------------------------|-------|
| User files | ✅ Yes | Files return to standard Windows folders |
| Custom folders | ✅ Yes | Restored to **original paths** |
| Browser profiles | ✅ Yes | Install browser first, close it, then restore; use sync for passwords |
| Wi‑Fi | ✅ Yes | Home networks usually work; corporate Wi‑Fi may need IT |
| Fonts | ✅ Yes | User fonts re-registered |
| Apps (winget) | ⚠️ Partial | Only winget packages; check `logs/failed-apps.txt` |
| AppData | ✅ Yes | Full Restore / Custom only — can overwrite new app defaults |
| Drivers | ⚠️ Partial | Best run **as Administrator** |
| Registry | ✅ Yes | Full Restore / Custom only |
| Windows settings | ✅ Yes | Personalization `.reg` files imported |
| Game saves | ✅ Yes | Standard save locations |
| Email | ⚠️ Partial | Thunderbird often works; re-add Outlook PST manually |
| Printers | ❌ No | Name list only — reinstall printers yourself |

---

## Quick start

### Clone the repository

```powershell
git clone https://github.com/SSujitX/ReinstallSafe
cd ReinstallSafe
```

Repository: [github.com/SSujitX/ReinstallSafe](https://github.com/SSujitX/ReinstallSafe)

### Run the app

```powershell
# Recommended: uv
uv sync
uv run main.py
```

Or with pip:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Build a standalone `.exe` (no Python needed on target PC)

```powershell
uv run build.py
```

Output: `dist/ReinstallSafe.exe` — copy this and your backup drive to the PC after reinstall.

---

## How to use: backup → reinstall → restore

### 1. Backup (before Windows setup)

1. Open **Backup**.
2. Choose destination — external drive recommended (`D:\Backups`, `E:\`, etc.).
3. Select categories or use **One-Click Full Backup**.
4. Pick **user folders** and **browsers** in the detail panels.
5. Add **custom folders** if you have projects outside Documents.
6. Wait for completion → **Verify Backup**.

### 2. Reinstall Windows

Use Windows Settings → Recovery, installation media, or OEM recovery — ReinstallSafe does not reinstall Windows for you.

### 3. Restore (after Windows setup)

1. Install ReinstallSafe on the new Windows (or run `ReinstallSafe.exe`).
2. Open **Restore** → **Select Backup Folder** → pick your `ReinstallSafe_Backup_*` folder.
3. Review the summary (date, PC name, categories).
4. Choose:
   - **Safe Restore** — files, custom folders, browsers, Wi‑Fi, fonts (recommended first)
   - **Full Restore** — everything including AppData, drivers, registry
   - **Custom Restore** — pick exactly what you want
5. Close browsers when prompted before browser restore.
6. Reinstall remaining apps manually; use `apps/installed-programs.csv` as a checklist.

---

## Safe Restore vs Full Restore

| | Safe Restore | Full Restore |
|---|-------------|--------------|
| User files | ✅ | ✅ |
| Custom folders | ✅ | ✅ |
| Browser profiles | ✅ | ✅ |
| Wi‑Fi passwords | ✅ | ✅ |
| Fonts | ✅ | ✅ |
| AppData settings | ❌ | ✅ |
| Drivers | ❌ | ✅ |
| Registry | ❌ | ✅ |
| Windows settings | ❌ | ✅ |
| winget apps | ❌ | ✅ |
| Overwrites existing files | Warns first | Warns first |

**Safe Restore** is the best first step after a clean install. Use **Full Restore** when you also need AppData, drivers, registry, and automatic winget reinstall.

---

## Important limitations

ReinstallSafe is honest about what a **file-based backup tool** can and cannot do:

- **Not a system image** — cannot restore Windows itself, boot partition, or licensed OEM recovery partitions.
- **Browser passwords/cookies** — often encrypted per-PC; use **browser sync** before reinstall.
- **Not every app reinstalls** — only **winget** packages auto-install; Steam, Adobe, custom `.exe` installs are manual.
- **AppData is Roaming only** — many modern apps store data in `%LOCALAPPDATA%`, which is not fully backed up.
- **Printers** — names saved, not drivers or ports.
- **Game saves** — common folders only; Steam/Epic/Xbox cloud saves are not scanned.
- **Administrator recommended** — driver export/import and some registry operations work best elevated.

ReinstallSafe **never deletes your original files** during backup. Restore **merges/overwrites** matching paths — you confirm before risky operations.

---

## FAQ

### Should I back up to C: drive?

Only if you have enough space and are **not** wiping C:. For reinstall safety, use an **external USB drive**.

### Does ReinstallSafe backup Chrome extensions?

Yes — browser **profile folders** are copied (extensions, bookmarks, settings on disk). Saved **passwords** may not work after a clean install unless you use sync.

### Does it backup Chrome Beta and multiple browsers?

Yes — Chrome, Chrome Beta, Chrome Dev, Canary, Edge channels, Brave, Firefox, Opera, and many more are detected automatically if installed.

### Can I pick which folders to backup (Desktop only, etc.)?

Yes — the **User Folders to Include** panel lets you choose Desktop, Documents, Downloads, Pictures, Videos, and Music individually.

### Where is my default backup folder saved?

**Settings → Default Backup Destination**. Browse to pick a folder — it saves automatically and pre-fills the Backup page.

### What if winget fails to reinstall some apps?

Check `logs/failed-apps.txt` in your backup folder. Install those programs manually from their websites.

### Do I need admin rights?

Recommended for drivers and some registry/AppData operations. The app warns at startup if not elevated but still runs other categories.

---

## Build from source

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| OS | Windows 10 / 11 |
| Package manager | [uv](https://docs.astral.sh/uv/) (recommended) |

**Tech stack (for developers):** PyQt6 UI, background workers, Windows tools (`robocopy`, `winget`, `pnputil`, `netsh`, `reg`), JSON manifest, PyInstaller for `.exe` builds.

```powershell
uv sync
uv run main.py
uv run build.py   # → dist/ReinstallSafe.exe
```

Drop `assets/icon.ico` before building for a custom application icon.

---

## Project structure

```
ReinstallSafe/
├── main.py
├── build.py
├── app/
│   ├── main_window.py       # Shell + navigation
│   ├── pages/               # Backup, Restore, Logs, Settings
│   ├── core/                # Backup/restore logic (no UI)
│   │   ├── backup_manager.py
│   │   ├── restore_manager.py
│   │   ├── browsers.py      # 65+ browser definitions
│   │   ├── custom_folders.py
│   │   ├── category_info.py # UI expectations + preflight notes
│   │   └── ...
│   ├── workers/             # Background QThread jobs
│   └── utils/
├── assets/icon.ico
└── backup_manifest.json     # Written inside each backup folder
```

---

## Backup folder layout

```
ReinstallSafe_Backup_YYYY-MM-DD_HH-MM-SS/
├── user_files/
├── custom_folders/          # includes folder_map.json (original paths)
├── browsers/
├── apps/                    # winget-apps.json, installed-programs.csv
├── wifi/
├── fonts/
├── registry/
├── windows_settings/
├── appdata/
├── drivers/
├── games/
├── email/
├── printers/
├── logs/
└── backup_manifest.json
```

---

**ReinstallSafe** — back up before Windows setup. Restore when you're ready.

<div align="center">

## Star History

<a href="https://www.star-history.com/?repos=SSujitX%2FReinstallSafe&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=SSujitX/ReinstallSafe&type=date&theme=dark&legend=top-left&sealed_token=1JCUlwnX3meYMwe7L7fxxKjV21YgpEdm069eXYmAgFEMm0eENeNOv5-Gc0MUM4A6o_igSiZLr1xcETMgqt6zZ3IKNV7zh08SbPoeB5FFNGRB-IW3RwYt49_NRdQruGJLUSEBzEklhmKPE6aakCwt7lOJ1EnNIMB9aWvGm57jrCVVT4YVof2d5_xWZCYl" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=SSujitX/ReinstallSafe&type=date&legend=top-left&sealed_token=1JCUlwnX3meYMwe7L7fxxKjV21YgpEdm069eXYmAgFEMm0eENeNOv5-Gc0MUM4A6o_igSiZLr1xcETMgqt6zZ3IKNV7zh08SbPoeB5FFNGRB-IW3RwYt49_NRdQruGJLUSEBzEklhmKPE6aakCwt7lOJ1EnNIMB9aWvGm57jrCVVT4YVof2d5_xWZCYl" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=SSujitX/ReinstallSafe&type=date&legend=top-left&sealed_token=1JCUlwnX3meYMwe7L7fxxKjV21YgpEdm069eXYmAgFEMm0eENeNOv5-Gc0MUM4A6o_igSiZLr1xcETMgqt6zZ3IKNV7zh08SbPoeB5FFNGRB-IW3RwYt49_NRdQruGJLUSEBzEklhmKPE6aakCwt7lOJ1EnNIMB9aWvGm57jrCVVT4YVof2d5_xWZCYl" />
 </picture>
</a>

<a href="https://visitorbadge.io/status?path=https%3A%2F%2Fgithub.com%2FSSujitX%2FReinstallSafe"><img src="https://api.visitorbadge.io/api/visitors?path=https%3A%2F%2Fgithub.com%2FSSujitX%2FReinstallSafe&countColor=%23263759" /></a>

</div>