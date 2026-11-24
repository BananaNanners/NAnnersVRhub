# SPDX-License-Identifier: GPL-3.0-only
"""Rehearse the reviewed Hogwarts update with exact copied bytes under /tmp."""
import json
from pathlib import Path
import sys
from zipfile import ZipFile

from vrhub import hogwarts_update_pilot as pilot, hub, offline_transaction as tx, profile_safety


def main():
    archive = Path(sys.argv[1])
    recipe = hub.load_recipes()["hogwarts-legacy"]
    plan, rows = pilot.build_review(recipe, archive)
    dest = Path(plan.destination)
    snapshot = profile_safety._snapshot(dest)
    state_path = hub.state_file()
    state_bytes = state_path.read_bytes()
    state_name = "zz-hub/state.json"
    installed = {f"profile/{name}": (dest / name).read_bytes() for name in snapshot["files"]}
    installed[state_name] = state_bytes
    if any(tx._sha(installed[f"profile/{name}"]) != detail["sha256"]
           for name, detail in snapshot["files"].items()):
        raise RuntimeError("The source profile changed while copying it.")
    with ZipFile(archive) as data:
        members = {name: info for info, name in profile_safety._archive_entries(data)}
        payload = {f"profile/{name}": data.read(members[name])
                   for action, name, _ in rows if action in ("Install", "Replace")}
    assert profile_safety._digest(archive) == pilot.ARCHIVE_SHA256
    key = f'{recipe["id"]}:profile'
    state = json.loads(state_bytes)
    owned = tuple(f"profile/{Path(name).relative_to(dest).as_posix()}"
                  for name in state[key]["files"]) + (state_name,)
    for fault in (None, "after_replace:17", "after_inventory"):
        with tx.fixture_sandbox(installed, payload, managed=owned, uevr_payload=True) as first:
            updated_state = json.loads(state_bytes)
            updated_state[key]["files"] = [
                str(first.root / "installed/profile" / name) for name in sorted(members)
            ]
            # The old Hub document stays byte-identical in the fixture backup.
            tx._write(first, "incoming", state_name,
                      (json.dumps(updated_state, indent=2) + "\n").encode())
            root = first.root / "installed"
            for name in snapshot["dirs"]:
                (root / "profile" / name).mkdir(parents=True, exist_ok=True)
            before = profile_safety._snapshot(root)
            inventory = tx._inventory(first)
            backup = first.root / "complete-originals"
            profile_safety._verified_copy(root, backup, before)
            candidate = tx.build_plan(first)
            assert len(candidate.rows) == 90 and not candidate.authorized_live_install
            try:
                tx.execute(first, candidate, fault=fault)
            except tx.SimulatedCrash:
                assert fault
                tx.recover(first)
            else:
                assert fault is None
                assert json.loads((root / state_name).read_bytes()) == updated_state
                for action, name, _ in rows:
                    source = installed if action == "Preserve" else payload
                    assert (root / "profile" / name).read_bytes() == source[f"profile/{name}"]
                tx.rollback(first)
            assert tx._inventory(first) == inventory
            assert profile_safety._snapshot(root) == profile_safety._snapshot(backup) == before
            for name, original in installed.items():
                assert (root / name).read_bytes() == (backup / name).read_bytes() == original
            print(f"PASS {fault or 'commit and explicit rollback'}: 193 profile files, Hub state, inventory and directory layout restored", flush=True)
    assert state_path.read_bytes() == state_bytes
    assert profile_safety._snapshot(dest) == snapshot
    print("PASS source profile and Hub record unchanged", flush=True)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text("Action\tProfile path\tReason\n" +
                                     "".join("\t".join(row) + "\n" for row in rows))


if __name__ == "__main__":
    main()
