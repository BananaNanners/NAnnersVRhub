# NAnnersVRhub 0.5.5-dev2 — Resize follow-up and desktop acceptance

**Status:** Code finished for review; **user acceptance pending**. These are checklist items for KDE desktop testing, not claims of user approval.

## What was broken

The Dev2 preview could not be reduced to a normal desktop window. A real Qt geometry probe found **minimumSizeHint 824 × 1063** and an actual minimum window height about 1041. Requesting **1200×750** resulted in **1200×1063**. Maximizing stretched four status cards across all available width, making their spacing difficult to judge. The long Setup guide was exerting a hard minimum on the root layout.

## Changes in this Dev2 follow-up

- Wrapped the **Games** page in a vertically scrollable `QScrollArea`. The sidebar (including **VR System**) and global controls remain outside the scroller.
- Capped dashboard page content at **1420px**, centered on large/maximized screens, without scaling the original banana-yellow/charcoal/cyan brand.
- Status cards change from **4 across** at wider widths to **2 × 2** below a 980px page width.
- Original five main action buttons change to a **2-column** responsive grid below 840px. Their existing click signals, runtime behavior and enabled states are retained.
- The Setup guide and advanced action drawer can expand without forcing the entire application window to grow.
- The read-only KDE preview opens at **1120×720**, not a near-maximized 1450×880, to make window resizing easy to assess.
- No changes to recipe logic, VR readiness criteria, Nexus update tracking, installed mod files, saves, local OpenXR runtime, rollback or hub auto-updates.

## Automated geometry evidence (Qt offscreen)

- Before: requested 920×600 was clamped to ~920×1063.
- After: **1450×880, 1200×750, 1100×700, 980×640, 920×600, 850×560** all obtained their requested window dimensions.
- A **2200×1200** window kept the Games page at **1420px**, with the four cards around 343–344px wide.
- Narrow window **920×600** showed **2 card columns**, **2 action columns**, active vertical scrolling, and **no horizontal scrolling**.
- The real Qt minimum-size hint fell to **772×530**.
- The sidebar's VR System button remained visible at 920×600.
- Eight new automated regression tests assert the actual geometry, scrollability, button layout and expansion safety. Do not substitute `window.resize()` succeeding for checking `window.size()`.

## User's requested future-development review format

**For Dev2 and each subsequent milestone, provide a checkbox-style acceptance list in the chat** so the user can report what passed. Suggested template:

- [ ] Test build opens at a comfortable non-maximized size.
- [ ] Resizing narrower or shorter does not crop off Games / VR System navigation.
- [ ] Dashboard cards remain readable in compact and maximized views.
- [ ] Main content scrolls vertically without requiring the entire window to expand.
- [ ] Game selection updates the correct data; no false VR-ready claims.
- [ ] Setup guide, Compatibility profile, Controller bindings and advanced tools are still accessible.
- [ ] Existing brand colors and visual identity are preserved.
- [ ] No game/mod/save files are changed in the read-only preview.
- [ ] User confirms **PASS** after inspecting the window on KDE.

Automated test pass is not user approval. Keep this checklist visible in Dev3, Dev4, Dev5 and release acceptance notes.

## November 20 final user preference — opening size

User passed every Dev2 desktop check except the small **1120×720** default window. The requested natural launch size is **1630×1060 (width × height)**.

- The real \`HubWindow\` now chooses 1630×1060 on either of the user's existing KDE displays (available logical geometries 2327×1309 and 2259×1271).
- Startup computes a bounded size when the available screen is smaller; maximization and manual window resizing remain unrestricted.
- The read-only KDE preview deliberately uses the exact same default-size logic as the real application, rather than overriding it.
- New unit/Qt tests cover both detected monitor geometries, compact-screen fallbacks, and startup dimensions.
- In Qt's 800×800 simulated offscreen display, full Nexus results may raise the minimum width beyond 800 after switching between very large and compact window sizes. The post-maximize GUI test therefore restores to at least 1120×720, while the separate test still checks the actual screen-aware startup size. This caveat does not affect the 1630×1060 desktop target.

Only the opening dimensions are pending desktop acceptance; all other Dev2 items were reported PASS by the user. The release application, installed games, mods, saves, Proton/OpenXR settings, and Dev1 checkpoint are unchanged.
