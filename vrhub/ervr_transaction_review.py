# SPDX-License-Identifier: GPL-3.0-only
"""ERVR 0.9.2 reviewed payload adapter for the existing fixture-only engine.

Not an installer. No live destination, state path, or production dispatch.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import zipfile
from . import offline_transaction as tx

RELEASE_SHA256 = "098224a1b1b4912430f2f93eb1d8f842703b95c4f24553f30451e792a4ec8eb9"
REPLACE = frozenset("Game/"+n for n in (
    "ERVR/CHANGELOG.md","ERVR/ERVR.dll","ERVR/LICENSE.txt","ERVR/README.md",
    "ERVR/THIRD_PARTY.md","dinput8.dll"))
ADD = frozenset("Game/"+n for n in (
    "ERVR/bhaptics_library.dll","ERVR/bHaptics-THIRD_PARTY_NOTICES.txt",
    "ERVR/LICENSE-bHaptics.txt","ERVR/LICENSE-JsonCpp.txt","ERVR/LICENSE-zlib.txt",
    "ERVR/LICENSE-Zstandard.txt","ERVR/WEAPON_PRESETS.md"))
PRESERVE = frozenset(("Game/dxgi.dll","Game/LICENSE-ReShade.txt"))
CONFIG = frozenset(("Game/ERVR/ERVR.ini","Game/ReShade.ini"))
EXCLUDE = "Game/ERVR Launcher.exe"
OWNED = REPLACE | PRESERVE | CONFIG

def reviewed_payload(archive_bytes):
    if not isinstance(archive_bytes, bytes) or len(archive_bytes)!=7238509 or hashlib.sha256(archive_bytes).hexdigest()!=RELEASE_SHA256:
        raise tx.TransactionBlocked("ERVR release digest or size differs.")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        names = ["Game/"+i.filename for i in z.infolist()]
        if len(names)!=18 or set(names)!=OWNED | ADD | {EXCLUDE}:
            raise tx.TransactionBlocked("ERVR reviewed inventory differs.")
        return {n:z.read(n.removeprefix("Game/")) for n in OWNED | ADD}

LEGACY_SHA256 = "851221c337d2a365df547b34435246486f4e390a77999b1fe712e764ef33a21a"

def _record(fixture, files, *, updated):
    # Actual legacy Hub record shape, but exclusively fixture absolute paths.
    root=tx._assert_fixture(fixture)/"installed"
    stamp=2 if updated else 1
    paths=[str(root/n) for n in sorted(files)]
    return {"installer":"ervr-1","files":paths,"keep":str(root),
            "backup":str(root/"hub/backups/ervr-original"),"originals":["Game/ERVR/ERVR.ini"],
            "retired":[],"original_hashes":{"Game/ERVR/ERVR.ini":
                hashlib.sha256(b"previous backup").hexdigest()},
            "file_hashes":{n:hashlib.sha256(b).hexdigest() for n,b in sorted(files.items())},
            "installed_at":stamp,"packages":{"ervr":{
                "archive":"ERVR-v0.9.2.zip" if updated else "historical-fixture.zip",
                "sha256":RELEASE_SHA256 if updated else LEGACY_SHA256,
                "files":paths,"installed_at":stamp}}}

def _encode(state):
    return (json.dumps(state,sort_keys=True,indent=2)+"\n").encode()

@contextmanager
def rehearsal(archive_bytes):
    """Generate schema-accurate records in a private fixture, never live state."""
    payload=reviewed_payload(archive_bytes)
    old={n:payload[n] if n in PRESERVE else ("synthetic prior "+n).encode() for n in OWNED}
    installed={**old,"Game/eldenring.exe":b"synthetic executable",
               "Game/unrelated.txt":b"foreign mod sentinel",
               "prefix/save.sl2":b"synthetic save",
               "hub/backups/ervr-original/sentinel":b"previous backup",
               "hub/backups/ervr-original/files/Game/ERVR/ERVR.ini":b"previous backup",
               "hub/state.json":b"fixture initialization"}
    incoming={n:payload[n] for n in REPLACE | ADD}
    incoming["hub/state.json"]=b"fixture initialization"
    managed=tuple(sorted(OWNED | {"hub/state.json"}))
    with tx.fixture_sandbox(installed,incoming,managed=managed) as fixture:
        other={"subnautica":{"installer":"submersed-vr-1","fixture":"unchanged"}}
        before={**other,"elden-ring":_record(fixture,old,updated=False)}
        after_files={**old,**{n:payload[n] for n in REPLACE | ADD}}
        after={**other,"elden-ring":_record(fixture,after_files,updated=True)}
        tx._write(fixture,"installed","hub/state.json",_encode(before))
        tx._write(fixture,"incoming","hub/state.json",_encode(after))
        tx._save_inventory(fixture,{n:hashlib.sha256(tx._read(fixture,"installed",n)).hexdigest() for n in managed})
        yield fixture

@contextmanager
def removal_rehearsal(archive_bytes):
    """Independent installed-v0.9.2 fixture; no production destination accepted."""
    payload=reviewed_payload(archive_bytes)
    files={n:payload[n] for n in OWNED|ADD}
    files["Game/ERVR/ERVR.ini"]=b"preserved historical configuration"
    files["Game/ReShade.ini"]=b"preserved reshade configuration"
    original=b"previous backup"
    backup="hub/backups/ervr-original/files/Game/ERVR/ERVR.ini"
    installed={**files,backup:original,"Game/eldenring.exe":b"synthetic executable",
               "Game/unrelated.txt":b"foreign mod sentinel","prefix/save.sl2":b"synthetic save",
               "hub/state.json":b"fixture initialization"}
    incoming={"Game/ERVR/ERVR.ini":original,"hub/state.json":b"fixture initialization"}
    # Save both current configurations in new, distinct recovery files.
    for n in CONFIG:
        incoming["hub/backups/ervr-original/removal-preserved/"+n]=files[n]
    deleted=tuple(sorted((OWNED|ADD)-{"Game/ERVR/ERVR.ini"}))
    managed=tuple(sorted(set(files)|{"hub/state.json"}))
    with tx.fixture_sandbox(installed,incoming,managed=managed,delete=deleted) as fixture:
        other={"subnautica":{"installer":"submersed-vr-1","fixture":"unchanged"}}
        before={**other,"elden-ring":_record(fixture,files,updated=True)}
        tx._write(fixture,"installed","hub/state.json",_encode(before))
        tx._write(fixture,"incoming","hub/state.json",_encode(other))
        tx._save_inventory(fixture,{n:hashlib.sha256(tx._read(fixture,"installed",n)).hexdigest() for n in managed})
        yield fixture
