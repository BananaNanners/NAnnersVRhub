# NAnnersVRhub 0.5.5 — Dev5D1-B Launch Tools refinement

**Status:** Implemented and verified offline; KDE desktop acceptance pending.

**Parent checkpoint:** Dev5D1-B `53676de` (unchanged).
**Worktree:** `~/Projects/NAnnersVRhub-0.5.5-dev5d1b-launch-tools`
**Branch:** `dev/0.5.5-button-consolidation-launch-tools`

## Approved change

Move the existing **Copy launch options** and **Run UEVR injector** buttons
out of Compatibility's collapsed advanced tools into a compact **LAUNCH TOOLS**
secondary row directly beneath **Launch game** and **Preflight** on Overview.

The original QPushButtons, click handlers and backend code remain unchanged.

## Context-sensitive visibility

- Steam games with a Steam app ID: **Copy launch options** is visible.
- Games whose recipe `method` is `uevr`: **Run UEVR injector** is visible.
- Steam + UEVR (Fatekeeper): both appear.
- Heroic/Epic + UEVR (Hogwarts Legacy): injector only.
- Steam without UEVR (Cyberpunk 2077): Copy only.
- Heroic/GOG without UEVR (DOOM 2016): hide the entire row.
- Switching games updates both buttons and the row's visibility.

An action being visible is not a claim that its prerequisites are installed or
that VR gameplay was verified. The original operation can still report missing
prerequisites. **The desktop preview disables both launch actions.**

Other advanced tools, including the handler-owned **Launch game tool**, stay
accessible from Compatibility. The seven tabs and original yellow-and-blue
branding remain unchanged.

## Safety and preservation

- No changes to the Hub's installation, archive verification, mod removal,
  backup, rollback, or game/injector launch backend functions.
- The previously approved Dev5C2/Dev5C3 file-recovery rules and the closed
  live UEVR **profile installation/restore** gate remain unchanged.
- No live game, injector or UEVR profile operation was executed during testing.
- All nine saved game archive scans remain available.
- The released Hub and all previously approved dev worktrees remain untouched.
- The read-only preview uses a separate test state and disables live game,
  installer, injector, updater and download actions.

## Verification

- Full suite: **921 run; 920 passed; 1 skipped**.
- Native Qt isolated preview: **139/139 passed**.
- Focused tests verify copy/injector original signals, placement, game-specific
  visibility, transitions between games, and intact Compatibility diagnostics.
- The smaller-screen initial geometry check passes after keeping the normal,
  compact Dev5D1b brand title; the preview's window title remains descriptive.

## KDE acceptance checklist

- [ ] Preview opens in a comfortable, non-maximized window at ~1630 × 1060.
- [ ] **Overview** shows Launch game + Preflight, then the **Launch Tools** row.
- [ ] Fatekeeper shows **Copy launch options** and **Run UEVR injector**.
- [ ] Hogwarts Legacy shows **Run UEVR injector** only.
- [ ] Cyberpunk 2077 shows **Copy launch options** only.
- [ ] DOOM (2016) hides the entire Launch Tools row.
- [ ] Switching between these games updates the row without stale buttons.
- [ ] Compatibility retains all reports, dated evidence and diagnostic tools.
- [ ] The preview keeps launch/injection buttons disabled; no game files change.
- [ ] The seven tabs, game artwork, saved scans and narrow-width scrolling remain correct.
- [ ] User explicitly approves the layout before moving to Dev5D1-C.

**UI acceptance does not enable live UEVR profile install/restore.**
