# NAnnersVRhub development

Follow the NAnners Development Foundation and Product Direction guidance.
For every GUI milestone, review the interactive KDE development build with the
player before requesting acceptance. Report each item below as PASS, FAIL, or
PENDING, with the exact checkpoint and observed process.

## Player-first language, setup guides and controller bindings

- Write visible labels, buttons, statuses, tooltips, warnings and confirmations
  in clear everyday language. Explain what happened and what the player should
  do next. Avoid internal terminology unless necessary; explain essential
  names such as UEVR, Proton, OpenXR and WiVRn in context.
- Keep technical details in existing diagnostics, Logs and development tools.
  Never hide material safety consequences or weaken informed consent.
- Keep setup guides accurate, short and ordered by the player's actual
  workflow: named source-page links, required downloads, installation,
  game-specific settings, headset connection and launch. Avoid redundant
  steps and manual file placement where the Hub already handles it.
- Make controller bindings readable and organized by gameplay action. Clearly
  distinguish documented defaults, preset-dependent mappings and actual
  player-tested controls; do not infer working controls from telemetry.
  Include known conflicts and workarounds without inventing mappings.
- Review player-facing wording and guide accuracy during acceptance.
  Reuse existing interface and controls; no unnecessary tabs or selectors.
  Preserve approved behavior, safety gates and historical evidence.

## Mandatory KDE acceptance checklist

- [ ] Previous development preview identified, or verified absent.
- [ ] Previous preview safely closed or reused.
- [ ] Exactly one current development preview running.
- [ ] Stable NAnnersVRhub unaffected.
- [ ] Current Git checkpoint and running preview process verified.
- [ ] Interactive KDE preview left open for player acceptance.

## Preview replacement procedure

1. Identify candidate development processes using the KDE window PID and
   corroborate it with the process start identity, launcher, worktree, and
   isolated preview state. Record the Git commit at launch. A window title,
   PID alone, or the worktree's current HEAD does not establish what a
   running process loaded. Keep unidentified windows and the stable Hub
   outside the lifecycle operation.
2. Reuse and activate the existing preview if it is running the required
   checkpoint. If source and runtime match and only documentation changed,
   record both the running code checkpoint and the newer documentation
   commit. For a changed runtime checkpoint, shut down the previous preview
   before launching a replacement.
3. Check for unsaved work, confirmation dialogs, and active install,
   rollback, or recovery work. Use a normal KDE close request directed only
   to the identified development window so its close handlers can run. If
   there is unsaved work, an active operation, or any uncertainty about
   identity or whether closing is safe, pause and keep the preview open.
   Never use broad process-killing commands or force-close a preview.
4. Verify a replaced preview's process has exited before launching the next.
   Keep preview state, recovery files, and logs in place. Launch from the
   verified worktree with isolated preview state. For scripted launches,
   serialize the check, close, and launch sequence so concurrent requests
   cannot open duplicates.
5. Verify the visible KDE window, its PID, and the launched checkpoint after
   the operation. Leave exactly one current preview open for the player.
   If closing is blocked, report the pending check and keep the existing
   preview open. Automated tests and screenshots do not substitute for
   interactive player acceptance.
