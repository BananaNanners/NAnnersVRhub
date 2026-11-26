# SPDX-License-Identifier: GPL-3.0-only
"""Bounded public release metadata. Identity evidence, not install authority."""
from __future__ import annotations
import json
import re
import time
import threading
import urllib.error
import urllib.request
from . import updates

MAX_RESPONSE = 2 * 1024 * 1024
MAX_RELEASES = 30
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
_cache = {}
_lock = threading.Lock()


def fetch_history(repo):
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise ValueError("Invalid release repository")
    with _lock:
        cached = _cache.get(repo)
        if cached and time.monotonic() - cached[0] < updates.GITHUB_CACHE_SECONDS:
            return cached[1]
        if time.time() < updates._github_retry_after:
            raise OSError(updates._github_retry_message())
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases?per_page={MAX_RELEASES}",
            headers={"Accept": "application/vnd.github+json", **updates.APP})
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as exc:
            headers = exc.headers or {}
            if exc.code == 429 or (exc.code == 403 and
                    str(headers.get("X-RateLimit-Remaining", "")) == "0"):
                try:
                    reset = float(headers.get("X-RateLimit-Reset"))
                except (ValueError, TypeError, OverflowError):
                    reset = time.time() + 60
                updates._github_retry_after = max(time.time() + 60, reset)
                raise OSError(updates._github_retry_message()) from None
            raise OSError(f"GitHub HTTP {exc.code}") from None
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Release history response too large")
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) > MAX_RELEASES:
            raise ValueError("Invalid release history")
        _cache[repo] = (time.monotonic(), data)
        return data


KHARVOX_ASSET = re.compile(r"KHARVOX-v[0-9]+(?:\.[0-9]+){0,3}[a-z]?\.zip\Z", re.IGNORECASE)


def kharvox_asset_name(name, *, local=False):
    if not isinstance(name, str):
        return False
    if local:
        name = re.sub(r" \([0-9]+\)(?=\.zip$)", "", name, flags=re.IGNORECASE)
    return KHARVOX_ASSET.fullmatch(name) is not None


def asset_catalog(source, releases):
    """Explicit exact asset or narrowly scoped KHARVOX family; bounded digests.

    The latest expected asset is chosen from the newest release containing
    the configured filename, or the configured fixed bundle tag. Missing
    digest for that release does not promote an older release to 'latest'.
    """
    family = (source.get("repo") == "CactusVRStudios/KHARVOX"
              and source.get("asset_family") == "kharvox-versioned-zip")
    submersed = (source.get("repo") == "Okabintaro/SubmersedVR"
                 and source.get("asset_family") == "submersedvr-versioned-zip")
    ervr = (source.get("repo") == "IlyaMez/EldenringVR"
            and source.get("asset_family") == "ervr-versioned-zip")
    target = None if family or submersed or ervr else source["asset"]
    fixed = source.get("fixed_tag")
    found = []
    for item in releases[:MAX_RELEASES]:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            continue
        tag = item.get("tag_name")
        published = item.get("published_at")
        if not isinstance(tag, str) or not tag or len(tag) > 100:
            continue
        try:
            when = updates._ts(published)
        except (ValueError, TypeError, AttributeError):
            continue
        assets = item.get("assets")
        if not isinstance(assets, list):
            continue
        exact = [a for a in assets if isinstance(a, dict) and (
            kharvox_asset_name(a.get("name")) if family else
            bool(re.fullmatch(r"SubmersedVR_[0-9]+(?:[.][0-9]+){1,3}[.]zip", str(a.get("name", ""))))
            if submersed else (bool(re.fullmatch(r"v[0-9]+[.][0-9]+[.][0-9]+", tag))
                               and a.get("name") == f"ERVR-{tag}.zip")
            if ervr else a.get("name") == target)]
        if len(exact) != 1:
            continue
        a = exact[0]
        digest = a.get("digest")
        sha = digest[7:].lower() if isinstance(digest, str) and digest.startswith("sha256:") else ""
        size = a.get("size")
        found.append({"tag": tag, "when": when,
                      "sha256": sha if SHA.fullmatch(sha) else "",
                      "size": size if type(size) is int and size > 0 else 0})
    found.sort(key=lambda a: (a["when"], a["tag"]), reverse=True)
    expected = next((a for a in found if a["tag"] == fixed), None) if fixed else (found[0] if found else None)
    pinned = next((a for a in found if a["tag"] == source.get("pinned_tag")), None)
    newer = bool(pinned and expected and expected["when"] > pinned["when"]
                 and expected["tag"] != pinned["tag"])
    if ervr and expected and not fixed:
        old = updates._release_version(source.get("pinned_tag", ""))
        new = updates._release_version(expected["tag"])
        newer = old is not None and new is not None and updates._ordered_numeric(old, new) < 0
    return {"assets": found, "expected": expected["tag"] if expected else "",
            "fixed": bool(fixed), "newer_than_pin": newer}


def catalogs_for(recipe, *, fetch=None):
    """Only explicit recipe sources are queried, never candidate filenames."""
    fetch = fetch or fetch_history
    result, errors, histories = {}, {}, {}
    for cid, source in recipe.get("archive_releases", {}).items():
        repo = source["repo"]
        try:
            if repo not in histories:
                try:
                    histories[repo] = fetch(repo)
                except (OSError, ValueError, RuntimeError) as exc:
                    histories[repo] = exc
            if isinstance(histories[repo], Exception):
                raise histories[repo]
            result[cid] = asset_catalog(source, histories[repo])
        except (OSError, ValueError, RuntimeError):
            errors[cid] = "Official release metadata unavailable; archive identity needs review."
    return result, errors
