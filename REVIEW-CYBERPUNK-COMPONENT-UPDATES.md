# NAnnersVRhub Cyberpunk 2077 per-component update detection — dev review

## Finding

The released 0.5.4 Cyberpunk recipe declares 15 `[[components]]` but only one `[[updates]]` entry (CyberpunkVR Port, Nexus #30093). Its update checker compared Nexus update times to game-wide installation time, so other dependencies were not queried and recently installed old archives could appear current.

## Proposed isolated development fix

Branch: `dev/cyberpunk-component-updates` in separate git worktree `~/Projects/NAnnersVRhub-Update-Detection-Dev`.

- Enable `track_component_updates = true` for the Cyberpunk recipe, generating one Nexus check per component; existing explicit port check is deduplicated. Other recipes retain their existing legacy logic.
- Read `state[recipe_id]["components"][mod_id]`, including the recorded original Nexus archive name. Compare strictly numeric release versions against versions extracted from recognized archive patterns. Do **not** infer currency from a recent installation date.
- Reject nonexistent or damaged components, unknown tag/archive patterns, and locally newer/incompatible formats without incorrectly claiming "Up to date."
- Leave installed game/mod files and Nexus API key unchanged. No mod archives were moved or deleted.
- Protect `Mark as up to date` for component-version recipes; it cannot override an outdated recorded archive.
- No daemon, new auto-installer, background monitoring, or default Nexus key change added.

## Confirmed live read-only Nexus results (November 20, 2026)

Five updates detected using the user's preconfigured Nexus API key without displaying it:

| Nexus mod ID | Component | Recorded installed | Latest reported by Nexus | Result |
|---|---|---|---|---|
| 107 | Cyber Engine Tweaks | 1.37.1 | 1.38.1 | Update |
| 4198 | ArchiveXL | 1.27.3 | 1.28.8 | Update |
| 4575 | Input Loader | 0.2.3 | 0.2.6 | Update |
| 7780 | Codeware | 1.20.5 | 1.21.4 | Update |
| 21936 | Visual Holsters | 1.2 | 1.4 | Update |
| 2380 | RED4ext | 1.31.1 | 1.31.1 | Current version |
| 1511 | redscript | 0.5.32 | 0.5.32 | Current version |
| 4197 | TweakXL | 1.12.2 | 1.12.2 | Current version |
| 22251 | Visible Bullets | 2.31 in archive filename | 2.5 | Unknown: likely versioning ambiguity; review manually |
| 30093 | Cyberpunk VR Port | no installed component record | not requested | Not installed per hub record |

Other installed dependencies matched the Nexus-reported version at the time of this check. Same-version file revisions and Nexus update-time changes may still require human review.

## Validation

- 15 target IDs, no duplicates, including the VR Port entry.
- **602 unit tests passed, 1 skipped**, under `QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -q`.
- New per-component tests cover old archive installed recently, missing/deleted files, unknown installed/version tags, skipped API requests for missing mods, name formats, normalization, missing key, legacy behavior, and mark-current state immutability.
- `git diff --check` passed.
- The original `~/Projects/NAnnersVRhub` release worktree and user's installed application remain unchanged.

## Pending before public release

User desktop UI acceptance test (including Check for updates after updating archives); consider controlled cache/backoff if 14+ sequential Nexus API calls make first startup too slow or hit rate limits. Test the effect on network-offline start, rates, and detail-panel readability. Nothing has been merged into the released main branch yet.
## November 20 GUI acceptance preflight

The real `HubWindow` update worker and details/table were tested with the experimental read-only runner `tests/manual_component_update_preview.py` against an **isolated copy** of the user's Hub state, using the existing Nexus key by reference (not copied or printed). The runner disables installs, uninstalls, game launches, application self-updates, and development actions. It also skips unrelated VR system scanning.

**Automated offscreen GUI verification: PASS, 9/9 checks.** The UI presented all 15 Cyberpunk update entries, the correct summary, individual latest-versus-installed comparisons, and no API errors. All prohibited action buttons were disabled.

One dependency changed between the original read-only API check and GUI test: **ArchiveXL was updated from 1.27.3 to 1.28.8**, and the real GUI correctly reported it as current. The remaining four updates were Cyber Engine Tweaks (107), Input Loader (4575), Codeware (7780), and Visual Holsters (21936). This is a positive dynamic version-tracking test; hardcoding the old expected update count would be wrong.

The read-only interactive test window was opened successfully on the KDE Wayland desktop, showing 15 entries and the four updates. **User visual acceptance remains pending.** Nothing was installed, removed or launched in the Steam games. Release 0.5.4 remains untouched.
