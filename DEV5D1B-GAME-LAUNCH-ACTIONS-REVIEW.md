# NAnnersVRhub 0.5.5-dev5D1-B — Game-Specific Launch Actions

**Status:** Implemented and verified offline; user KDE desktop acceptance pending.

**Parent checkpoint:** `eb214aa` — approved Launch Tools placement with separate saved scan discrepancy note.
**Worktree:** `~/Projects/NAnnersVRhub-0.5.5-dev5d1b-launch-actions`
**Branch:** `dev/0.5.5-launch-actions`

## Approved scope

Keep Launch Game and Preflight as Overview's primary actions. Group the **existing** per-game launcher buttons and pre-launch bridge check below them in the compact Launch Tools row. Keep bridge logs in Compatibility.

| Game | Main action | Launch Tools |
|---|---|---|
| Cyberpunk 2077 | Game launcher | Copy launch options |
| Fatekeeper | Game launcher | Copy launch options; Run UEVR injector |
| Hogwarts Legacy | Game launcher | Run UEVR injector |
| Skyrim VR (MGO) | Launch Skyrim VR | Copy launch options; Launch MO2 |
| DOOM (2016) | Launch DOOM (flat) | Launch DOOM VR; Test VR bridge |

These labels are derived from the **existing game handlers**. The Skyrim MO2 route retains Jackify's Steam shortcut and Proton setup. DOOM VR retains the existing guarded KHARVOX launcher; Test VR bridge retains its original probe handler, which is **not a live gameplay validation**.

## Compatibility diagnostics

- `bridge_log_btn` stays under Compatibility → More compatibility tools.
- For Skyrim, its label is **Open MO2 bridge log**. The handler resolves `~/.local/share/vrhub/mo2-bridge.log`.
- For DOOM, the handler's existing label is **Open KHARVOX log**. Display stays conditional on a log path being resolvable.
- DOOM's **Open DOOM diagnostics** also stays under Compatibility.
- Copy diagnostics, runtime report, log diagnosis, Compatibility profile and dated gameplay references are unchanged.

## Implementation

- Reparented the original `game_launch_btn` and `doom_probe_btn` from Compatibility advanced tools to `overviewLaunchTools`, next to the original Copy and Injector buttons.
- The existing signal connections and backend functions are unchanged.
- The Launch Tools row becomes visible when any supported per-game action applies, including Skyrim's MO2 or DOOM's KHARVOX route.
- No duplicate buttons, new installer route, or hidden automatic operation introduced.
- Original dark/yellow/blue branding and seven-tab navigation unchanged.

## Safety and preservation

- **No game, mod, ZIP, save, Proton prefix, KHARVOX runner, MO2 data or actual VR profile changed** by this update.
- No game, injector, runner test or KHARVOX process launched during automated tests.
- Mock click tests verify original MO2/DOOM launcher callbacks and DOOM's existing bridge probe callback.
- Installed Hub and all earlier development checkpoints remain unchanged.
- Dev5C2/Dev5C3 recovery protections and the closed live UEVR profile install/restore gate remain unchanged.
- UI preview disables all live launch/injection/test, installer, restore, download and update actions.
- Saved archive scan persistence was identified as a **separate preexisting discrepancy** in the earlier parent checkpoint; no scans are modified or silently reconstructed here.

## Verification

- AST and Git whitespace checks passed.
- Full offline regression: **924 tests run, 923 passed, one skipped**.
- Native isolated Qt preview: **145/145 checks passed**.
- Screenshot reviews include DOOM and Skyrim Overview in the current branding.
- `vrhub/handlers.py`, `vrhub/hub.py`, `vrhub/profile_safety.py`, `vrhub/compatibility.py`, `vrhub/downloads_gui.py` were not modified.

## KDE acceptance checklist

- [ ] Dev5D1-B read-only Game Launch Actions preview opens at a comfortable window size.
- [ ] DOOM: Overview shows **Launch DOOM (flat)** as primary.
- [ ] DOOM: Launch Tools shows **Launch DOOM VR** and **Test VR bridge**.
- [ ] Skyrim: Overview shows **Launch Skyrim VR** as primary.
- [ ] Skyrim: Launch Tools shows **Copy launch options** and **Launch MO2**.
- [ ] Switching to Fatekeeper, Hogwarts, Cyberpunk preserves their previous relevant launch tools.
- [ ] Compatibility still contains bridge-log and diagnostic tools.
- [ ] Where accessible, Skyrim's bridge log says **Open MO2 bridge log**; DOOM's says **Open KHARVOX log**.
- [ ] No duplicate buttons, horizontal page scrolling, missing game artwork, or unrelated tab regressions.
- [ ] Read-only preview keeps launch, injector, Test VR bridge, installation and restore actions disabled.
- [ ] User explicitly accepts the layout before proceeding to Dev5D1-C.

**Acceptance is for the UI only; it does not enable live UEVR profile installation or restoration.**
