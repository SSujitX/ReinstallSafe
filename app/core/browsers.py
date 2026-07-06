"""Browser profile detection, backup and restore."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from app.core.robocopy import run_robocopy
from app.utils.paths import appdata_local, appdata_roaming

# Folders that are safe (and large/useless) to skip when copying browser profiles.
CACHE_EXCLUDES = [
    "Cache", "Cache2", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache",
    "Service Worker", "Crashpad", "component_crx_cache", "ScriptCache",
]


@dataclass(frozen=True)
class BrowserDefinition:
    key: str
    label: str
    profile_root: Path
    detect_roots: tuple[Path, ...] = field(default_factory=tuple)

    def active_profile_root(self) -> Path | None:
        for root in self.detect_roots or (self.profile_root,):
            if root.exists():
                return root
        return None


def _browser_definitions() -> list[BrowserDefinition]:
    local = appdata_local()
    roaming = appdata_roaming()

    def c(key: str, label: str, *parts: str) -> BrowserDefinition:
        root = local.joinpath(*parts)
        return BrowserDefinition(key, label, root, (root,))

    def r(key: str, label: str, *parts: str) -> BrowserDefinition:
        root = roaming.joinpath(*parts)
        return BrowserDefinition(key, label, root, (root,))

    def c_multi(key: str, label: str, restore: Path, *detect: Path) -> BrowserDefinition:
        return BrowserDefinition(key, label, restore, detect or (restore,))

    return [
        # --- Google Chrome ---
        c("chrome", "Google Chrome", "Google", "Chrome", "User Data"),
        c("chrome_beta", "Google Chrome Beta", "Google", "Chrome Beta", "User Data"),
        c("chrome_dev", "Google Chrome Dev", "Google", "Chrome Dev", "User Data"),
        c("chrome_canary", "Google Chrome Canary", "Google", "Chrome SxS", "User Data"),

        # --- Microsoft Edge ---
        c("edge", "Microsoft Edge", "Microsoft", "Edge", "User Data"),
        c("edge_beta", "Microsoft Edge Beta", "Microsoft", "Edge Beta", "User Data"),
        c("edge_dev", "Microsoft Edge Dev", "Microsoft", "Edge Dev", "User Data"),
        c("edge_canary", "Microsoft Edge Canary", "Microsoft", "Edge SxS", "User Data"),

        # --- Brave ---
        c("brave", "Brave", "BraveSoftware", "Brave-Browser", "User Data"),
        c("brave_beta", "Brave Beta", "BraveSoftware", "Brave-Browser-Beta", "User Data"),
        c("brave_nightly", "Brave Nightly", "BraveSoftware", "Brave-Browser-Nightly", "User Data"),

        # --- Mozilla / Gecko ---
        r("firefox", "Mozilla Firefox", "Mozilla", "Firefox"),
        r("waterfox", "Waterfox", "Waterfox"),
        r("librewolf", "LibreWolf", "librewolf"),
        r("pale_moon", "Pale Moon", "Moonchild Productions", "Pale Moon"),
        r("basilisk", "Basilisk", "Moonchild Productions", "Basilisk"),
        r("floorp", "Floorp", "Floorp"),
        r("zen", "Zen Browser", "zen"),
        r("seamonkey", "SeaMonkey", "Mozilla", "SeaMonkey"),
        r("kmeleon", "K-Meleon", "K-Meleon"),
        r("falkon", "Falkon", "falkon"),

        # --- Opera ---
        c_multi(
            "opera",
            "Opera",
            local / "Opera Software" / "Opera Stable" / "User Data",
            local / "Opera Software" / "Opera Stable" / "User Data",
            roaming / "Opera Software" / "Opera Stable",
        ),
        c_multi(
            "opera_gx",
            "Opera GX",
            local / "Opera Software" / "Opera GX Stable" / "User Data",
            local / "Opera Software" / "Opera GX Stable" / "User Data",
            roaming / "Opera Software" / "Opera GX Stable",
        ),
        c_multi(
            "opera_beta",
            "Opera Beta",
            local / "Opera Software" / "Opera Beta" / "User Data",
            local / "Opera Software" / "Opera Beta" / "User Data",
            roaming / "Opera Software" / "Opera Beta",
        ),
        c_multi(
            "opera_developer",
            "Opera Developer",
            local / "Opera Software" / "Opera Developer" / "User Data",
            local / "Opera Software" / "Opera Developer" / "User Data",
            roaming / "Opera Software" / "Opera Developer",
        ),
        c("opera_air", "Opera Air", "Opera Software", "Opera Air Stable", "User Data"),

        # --- Other Chromium-based ---
        c("vivaldi", "Vivaldi", "Vivaldi", "User Data"),
        c("chromium", "Chromium", "Chromium", "User Data"),
        c("arc", "Arc", "Arc", "User Data"),
        c("thorium", "Thorium", "Thorium", "User Data"),
        c("supermium", "Supermium", "Supermium", "User Data"),
        c("slimjet", "Slimjet", "Slimjet", "User Data"),
        c("iridium", "Iridium", "Iridium", "User Data"),
        c("torch", "Torch", "Torch", "User Data"),
        c("blisk", "Blisk", "Blisk", "User Data"),
        c("kinza", "Kinza", "Kinza", "User Data"),
        c("sidekick", "Sidekick", "Sidekick", "User Data"),
        c("wavebox", "Wavebox", "Wavebox", "User Data"),
        c("shift", "Shift", "Shift", "User Data"),
        c("ghost", "Ghost Browser", "Ghost Browser", "User Data"),
        c("colibri", "Colibri", "Colibri", "User Data"),
        c("helium", "Helium", "Helium", "User Data"),
        c("duckduckgo", "DuckDuckGo", "DuckDuckGo", "Windows", "Browser", "User Data"),
        c("ccleaner_browser", "CCleaner Browser", "CCleaner Browser", "User Data"),
        c("yandex", "Yandex Browser", "Yandex", "YandexBrowser", "User Data"),
        c("coccoc", "Coc Coc", "CocCoc", "Browser", "User Data"),
        c("cent_browser", "Cent Browser", "CentBrowser", "User Data"),
        c("7star", "7Star", "7Star", "7Star", "User Data"),
        c("sputnik", "Sputnik", "Sputnik", "Sputnik", "User Data"),
        c("ur_browser", "UR Browser", "UR Browser", "User Data"),
        c("orbitum", "Orbitum", "Orbitum", "User Data"),
        c("citrio", "Citrio", "CatalinaGroup", "Citrio", "User Data"),
        c("salamweb", "SalamWeb", "SalamWeb", "User Data"),
        c("qq_browser", "QQ Browser", "Tencent", "QQBrowser", "User Data"),
        c("360chrome", "360 Secure Browser", "360Chrome", "Chrome", "User Data"),
        c("maxthon", "Maxthon", "Maxthon", "User Data"),
        c("epic", "Epic Privacy Browser", "Epic Privacy Browser", "User Data"),

        # --- Security-vendor browsers ---
        c("avast_secure", "Avast Secure Browser", "AVAST Software", "Browser", "User Data"),
        c("avg_secure", "AVG Secure Browser", "AVG", "Browser", "User Data"),
        c("avira_secure", "Avira Secure Browser", "Avira", "Browser", "User Data"),
        c("norton_secure", "Norton Secure Browser", "Norton", "Browser", "User Data"),
        c("comodo_dragon", "Comodo Dragon", "Comodo", "Dragon", "User Data"),
        c("comodo_icedragon", "Comodo IceDragon", "Comodo", "IceDragon", "User Data"),

        # --- Tor / privacy ---
        BrowserDefinition(
            "tor_browser",
            "Tor Browser",
            local / "Tor Browser" / "Browser" / "TorBrowser" / "Data" / "Browser",
            detect_roots=(
                local / "Tor Browser" / "Browser" / "TorBrowser" / "Data" / "Browser",
                roaming / "Tor Browser" / "Browser" / "TorBrowser" / "Data" / "Browser",
            ),
        ),
        r("mullvad_browser", "Mullvad Browser", "Mullvad Browser"),
    ]


def browser_options() -> list[tuple[str, str]]:
    """All known browsers for UI checklists (key, label)."""
    return [(b.key, b.label) for b in _browser_definitions()]


def detect_browsers() -> dict[str, BrowserDefinition]:
    """Return browsers whose profile folder actually exists on this machine."""
    detected: dict[str, BrowserDefinition] = {}
    seen_paths: set[Path] = set()
    for browser in _browser_definitions():
        root = browser.active_profile_root()
        if root is None:
            continue
        resolved = root.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        detected[browser.key] = browser
    return detected


def close_browsers_prompt() -> str:
    """Short reminder listing browsers currently detected on this PC."""
    detected = detect_browsers()
    if not detected:
        return "Please close any browsers you use before continuing."
    names = ", ".join(b.label for b in detected.values())
    return f"Please close these browsers now: {names}."


def backup_browsers(
    selected_keys: list[str],
    destination_root: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    exclude_dirs: Iterable[Path] | None = None,
    on_subprogress: Callable[[float], None] | None = None,
    on_step_begin: Callable[[str], None] | None = None,
    on_step_complete: Callable[[], None] | None = None,
) -> tuple[dict[str, int], dict[str, str], list[str]]:
    """Copy each selected browser's profile folder.

    Returns (key -> copied file count, key -> backed-up source profile path).
    """
    detected = detect_browsers()
    results: dict[str, int] = {}
    profile_paths: dict[str, str] = {}
    failures: list[str] = []
    exclude_args = []
    for name in CACHE_EXCLUDES:
        exclude_args += ["/XD", name]

    for key in selected_keys:
        if cancel_event is not None and cancel_event.is_set():
            break

        browser = detected.get(key)
        if not browser:
            on_line(f"Skipping {key}: not detected on this system.")
            if on_step_complete:
                on_step_complete()
            continue

        source = browser.active_profile_root()
        if source is None:
            on_line(f"Skipping {browser.label}: profile folder not found.")
            if on_step_complete:
                on_step_complete()
            continue

        detail = f"Backing up {browser.label} profile..."
        if on_step_begin:
            on_step_begin(detail)
        on_line(detail)
        profile_paths[key] = str(source.resolve())
        dest = destination_root / browser.key
        result = run_robocopy(
            source,
            dest,
            on_line=on_line,
            cancel_event=cancel_event,
            extra_flags=exclude_args,
            exclude_dirs=exclude_dirs,
            on_subprogress=on_subprogress,
        )
        results[key] = result.copied_files

        if result.cancelled:
            break

        if result.succeeded:
            on_line(f"{browser.label}: {result.copied_files} files backed up.")
        else:
            message = f"{browser.label} backup finished with robocopy code {result.return_code}."
            failures.append(message)
            on_line(f"WARNING: {message}")

        if on_step_complete:
            on_step_complete()

    return results, profile_paths, failures


def _restore_destination(browser: BrowserDefinition, profile_paths: dict[str, str] | None, key: str) -> Path:
    saved = (profile_paths or {}).get(key, "").strip()
    if saved:
        saved_path = Path(saved)
        if saved_path.parent.exists() and _is_safe_browser_destination(saved_path):
            return saved_path
    active = browser.active_profile_root()
    return active if active is not None else browser.profile_root


def restore_browsers(
    selected_keys: list[str],
    backup_browsers_dir: Path,
    on_line: Callable[[str], None],
    cancel_event: threading.Event | None = None,
    profile_paths: dict[str, str] | None = None,
) -> tuple[dict[str, int], bool, list[str]]:
    """Restore browser profiles. Returns (key -> file count, cancelled)."""
    definitions = {b.key: b for b in _browser_definitions()}
    results: dict[str, int] = {}
    cancelled = False
    failures: list[str] = []

    for key in selected_keys:
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break

        browser = definitions.get(key)
        source = backup_browsers_dir / key
        if not browser or not source.exists():
            on_line(f"Skipping {key}: no backed-up profile found.")
            continue

        destination = _restore_destination(browser, profile_paths, key)
        on_line(f"Restoring {browser.label} profile to {destination}...")
        result = run_robocopy(source, destination, on_line=on_line, cancel_event=cancel_event)
        results[key] = result.copied_files

        if result.cancelled:
            cancelled = True
            break

        if result.succeeded:
            on_line(f"{browser.label}: {result.copied_files} files restored.")
        else:
            message = f"{browser.label} restore finished with robocopy code {result.return_code}."
            failures.append(message)
            on_line(f"WARNING: {message}")

    return results, cancelled, failures


def _is_safe_browser_destination(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    roots = [appdata_local(), appdata_roaming()]
    for root in roots:
        try:
            root_resolved = root.resolve()
        except OSError:
            root_resolved = root
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


BROWSER_WARNING = (
    "Browser profiles can be backed up and restored, but cookies, saved logins, and "
    "active sessions may not fully restore because browsers and Windows encrypt sensitive "
    "data. Use browser sync/password export before reinstall."
)
