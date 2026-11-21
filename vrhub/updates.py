# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Update checking: GitHub releases (no login) and Nexus Mods (needs a free personal API key)."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
APP = {"Application-Name": "NAnnersVRhub", "Application-Version": "0.3", "User-Agent": "NAnnersVRhub/0.3"}
_UNSET = object()


def _ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


# ---- GitHub ---------------------------------------------------------------
# Reuse a successful result briefly when the user refreshes multiple times.
# This is process-only memory: no user tokens, files or system state are written.
GITHUB_CACHE_SECONDS = 15 * 60
_github_recent: dict[str, tuple[float, dict]] = {}
_github_retry_after = 0.0


def _github_retry_message() -> str:
    if _github_retry_after > time.time():
        local = datetime.fromtimestamp(_github_retry_after).astimezone().strftime("%H:%M")
        return f"GitHub API rate limit reached; retry after {local} local time."
    return "GitHub API rate limit reached; retry later."


def fetch_latest(repo: str, timeout: int = 8) -> dict:
    """Read the latest GitHub release, coalescing frequent user refreshes.

    Never turn an expired cached result into a false "current" claim. When
    rate-limited, yield a clear error instead of making further API calls.
    """
    global _github_retry_after
    now = time.monotonic()
    cached = _github_recent.get(repo)
    if cached and now - cached[0] < GITHUB_CACHE_SECONDS:
        return {**cached[1], "cached": True}
    if time.time() < _github_retry_after:
        raise OSError(_github_retry_message())

    req = urllib.request.Request(
        GITHUB_API.format(repo=repo),
        headers={"Accept": "application/vnd.github+json", **APP})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        headers = exc.headers or {}
        rate_limited = (exc.code == 429 or
                        (exc.code == 403 and (
                            str(headers.get("X-RateLimit-Remaining", "")) == "0"
                            or "rate limit" in str(exc).lower())))
        if rate_limited:
            reset = headers.get("X-RateLimit-Reset")
            try:
                reset_time = float(reset)
            except (TypeError, ValueError, OverflowError):
                reset_time = time.time() + 60
            _github_retry_after = max(time.time() + 60, reset_time)
            raise OSError(_github_retry_message()) from None
        raise OSError(f"GitHub returned HTTP {exc.code}; try again later.") from None
    latest = {
        "tag": str(data["tag_name"]),
        "published": str(data["published_at"]),
        "url": str(data["html_url"]),
    }
    _github_recent[repo] = (time.monotonic(), latest)
    return {**latest, "cached": False}


# ---- Nexus Mods -----------------------------------------------------------
def nexus_base() -> str:
    return os.environ.get("VRHUB_NEXUS_BASE", "https://api.nexusmods.com/v1")


def key_path() -> Path:
    if os.environ.get("VRHUB_NEXUS_KEY_FILE"):
        return Path(os.environ["VRHUB_NEXUS_KEY_FILE"])
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return cfg / "vrhub" / "nexus_key"


def get_key() -> str | None:
    """NEXUS_API_KEY environment variable wins, then the saved key file."""
    env = os.environ.get("NEXUS_API_KEY", "").strip()
    if env:
        return env
    p = key_path()
    return p.read_text().strip() or None if p.is_file() else None


def set_key(key: str) -> None:
    p = key_path()
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # private to your user
    with os.fdopen(fd, "w") as f:
        f.write(key.strip() + "\n")
    os.chmod(p, 0o600)


def clear_key() -> None:
    key_path().unlink(missing_ok=True)


def _nexus_get(path: str, key: str, timeout: int = 8) -> dict:
    req = urllib.request.Request(f"{nexus_base()}/{path}", headers={"apikey": key, "Accept": "application/json", **APP})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # friendlier messages (never include the key)
        msg = {401: "Nexus rejected the API key", 403: "Nexus rejected the API key",
               404: "Nexus doesn't know that mod", 429: "Nexus rate limit reached, try again later"}
        raise OSError(msg.get(e.code, f"Nexus returned HTTP {e.code}")) from None


def validate_key(key: str) -> str:
    """Return the account name for a valid key (this call doesn't count against rate limits)."""
    return str(_nexus_get("users/validate.json", key)["name"])


def fetch_mod_info(game: str, mod_id: int, key: str) -> dict:
    """Name and latest version of a Nexus mod (used to label the component checklist)."""
    d = _nexus_get(f"games/{game}/mods/{mod_id}.json", key)
    return {"name": str(d["name"]), "version": str(d.get("version", ""))}


def fetch_nexus(game: str, mod_id: int, key: str) -> dict:
    d = _nexus_get(f"games/{game}/mods/{mod_id}.json", key)
    if d.get("updated_timestamp") is not None:
        published = datetime.fromtimestamp(int(d["updated_timestamp"]), timezone.utc).isoformat()
    else:
        published = d["updated_time"]
    return {"tag": str(d["version"]), "published": published,
            "url": f"https://www.nexusmods.com/{game}/mods/{mod_id}"}


# ---- per-component Nexus update checking ----------------------------------
def _release_version(tag: str) -> tuple[int, ...] | None:
    # Unknown/non-numeric tags are not silently treated as matching versions.
    match = re.fullmatch(r"[vV]?(\d+(?:\.\d+){0,3})", str(tag).strip())
    return tuple(int(v) for v in match.group(1).split(".")) if match else None


def _installed_archive_version(filename: str, mod_id: int) -> tuple[int, ...] | None:
    """Extract Nexus's usual 'mod-id-version-timestamp' or 'id 1.2.3' form.

    Never infer a version from install time. Non-matching filenames remain
    unknown rather than being reported as current.
    """
    if not isinstance(filename, str) or not filename:
        return None
    pattern = r"(?<![0-9A-Za-z])" + re.escape(str(mod_id)) + (
        r"(?![0-9A-Za-z])[ _-]+[vV]?(\d{1,4}(?:[._-]\d{1,4}){0,3})(?=$|[ ._-])"
    )
    match = re.search(pattern, filename)
    return tuple(int(v) for v in re.split(r"[._-]", match.group(1))) if match else None


def _ordered_numeric(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    width = max(len(a), len(b))
    aa, bb = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return (aa > bb) - (aa < bb)


def _update_targets(recipe: dict, state: dict) -> list[dict]:
    """Explicit update targets plus opt-in Nexus targets for all components."""
    result = list(recipe.get("updates", []))
    if not recipe.get("track_component_updates"):
        return result
    tracked = {(u.get("nexus_game"), u.get("nexus_mod")) for u in result}
    names = state.get("_names", {})
    for comp in recipe.get("components", []):
        mod_id = comp["nexus_mod"]
        key = (recipe["nexus_game"], mod_id)
        if key in tracked:
            continue
        label = names.get(str(mod_id), {}).get("name") or comp["name"]
        result.append({"name": label, "nexus_game": recipe["nexus_game"], "nexus_mod": mod_id})
        tracked.add(key)
    return result


# ---- shared checking logic ------------------------------------------------
def check_recipe(recipe: dict, state: dict, fetch=None, nexus_fetch=None, nexus_key=_UNSET) -> list[dict]:
    fetch = fetch or fetch_latest
    nexus_fetch = nexus_fetch or fetch_nexus
    out = []
    for u in _update_targets(recipe, state):
        if "github" in u:
            page = f"https://github.com/{u['github']}/releases"
        elif "nexus_game" in u:
            page = f"https://www.nexusmods.com/{u['nexus_game']}/mods/{u['nexus_mod']}"
        else:
            page = u.get("manual", "")
        item = {"name": u["name"], "page": page}
        if isinstance(u.get("nexus_mod"), int):
            item["mod_id"] = u["nexus_mod"]
        component_ids = {c["nexus_mod"] for c in recipe.get("components", [])}
        is_component = bool(recipe.get("track_component_updates") and
                            u.get("nexus_game") == recipe.get("nexus_game") and
                            u.get("nexus_mod") in component_ids)
        component = None
        if is_component:
            component = state.get(recipe["id"], {}).get("components", {}).get(str(u["nexus_mod"]))
            if not isinstance(component, dict):
                item.update(status="not_installed", detail="Not installed through the hub; open Nexus for releases.")
                out.append(item)
                continue
            archive_version = _installed_archive_version(
                component.get("archive", ""), u["nexus_mod"])
            if archive_version is not None:
                item["installed_version"] = ".".join(map(str, archive_version))
            files = component.get("files", [])
            if not isinstance(files, list) or not files or any(
                    not isinstance(p, str) or not Path(p).is_file() for p in files):
                item.update(status="unknown", detail="Recorded files are missing or unverified; inspect the mod install.")
                out.append(item)
                continue
        source = "the update source"
        try:
            if "github" in u:
                source = "GitHub"
                latest = fetch(u["github"])
            elif "nexus_game" in u:
                source = "Nexus"
                key = get_key() if nexus_key is _UNSET else nexus_key
                if not key:
                    item.update(status="no_key", detail="Add a free Nexus API key to check this automatically "
                                                        "(use the 'Nexus API key…' button).")
                    out.append(item)
                    continue
                latest = nexus_fetch(u["nexus_game"], u["nexus_mod"], key)
            else:
                item.update(status="manual", detail="Can't be checked automatically. "
                                                    "Open the mod page and compare versions yourself.")
                out.append(item)
                continue
            tag, published = latest["tag"], latest["published"]
            published_ts = _ts(published)
        except (OSError, ValueError, KeyError, TypeError) as e:  # network errors, bad JSON, odd replies
            item.update(status="error", detail=f"Couldn't check {source}: {e}")
            out.append(item)
            continue
        day = published[:10]
        item["latest_version"] = str(tag)
        item["page"] = latest.get("url", item["page"])
        if latest.get("cached"):
            item["cached"] = True
        if is_component:
            installed = _installed_archive_version(component.get("archive", ""), u["nexus_mod"])
            available = _release_version(tag)
            if installed is None or available is None:
                item.update(status="unknown", detail=f"Latest Nexus version: {tag} ({day}); "
                            f"couldn't reliably compare the installed archive version.")
            else:
                old = ".".join(str(x) for x in installed)
                change = _ordered_numeric(installed, available)
                if change < 0:
                    item.update(status="update", detail=f"Update available: {old} → {tag} (updated {day})")
                elif change == 0:
                    item.update(status="current", detail=f"Version matches Nexus: {tag} ({day}); "
                                "file revisions may need manual review.")
                else:
                    item.update(status="unknown", detail=f"Installed archive {old} is newer than "
                                f"reported Nexus version {tag}; verify manually.")
            out.append(item)
            continue
        if u.get("upstream_reference") is True:
            # A community-bundled injector is not necessarily a tagged upstream
            # release. Installation timestamps cannot establish that identity.
            item.update(status="unknown", detail=(
                f"Latest upstream UEVR release: {tag} ({day}). "
                "Installed upstream version not established; review compatibility "
                "with the matched game profile before updating."))
            out.append(item)
            continue
        tracked = [state[k] for k in u.get("tracks", [recipe["id"]]) if k in state]
        stamps = [t.get("installed_at") for t in tracked]
        if not tracked:
            item.update(status="not_installed", detail=f"Latest release: {tag} ({day})")
        elif any(s is None for s in stamps):
            item.update(status="unknown", detail=f"Latest release is {tag} ({day}). This install has no date "
                                                 "recorded; if it's already the latest, click 'Mark as up to date'.")
        elif any(s < published_ts for s in stamps):
            item.update(status="update", detail=f"Update available: {tag} (updated {day})")
        else:
            item.update(status="current", detail=f"Up to date (latest: {tag}, {day})")
        if item.get("cached"):
            item["detail"] += "; cached GitHub result reused (up to 15 minutes old)"
        out.append(item)
    return out


def check_all(recipes: dict, state: dict, fetch=None, **kw) -> dict[str, list[dict]]:
    return {rid: check_recipe(r, state, fetch, **kw) for rid, r in recipes.items()}


def summarize(items: list[dict] | None) -> str:
    if not items:
        return "—"
    found = {i["status"] for i in items}
    for status, label in (("update", "Update available"), ("error", "Couldn't check"),
                          ("unknown", "Unknown"), ("no_key", "Needs Nexus key"),
                          ("manual", "Check manually"), ("not_installed", "Not installed"),
                          ("current", "Up to date")):
        if status in found:
            return label
    return "—"
