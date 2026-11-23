# SPDX-License-Identifier: GPL-3.0-only
"""Review-only route for official packages outside an approved recipe pin."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from . import download_planner as planner, install_review
from .downloads_gui import GuidedDownloadsPage

def build_review(recipe, rows):
    if recipe.get("method") not in ("bepinex", "ervr") or not isinstance(rows, list):
        raise RuntimeError("Unsupported release review.")
    components = planner.plan_components(recipe)
    if len(rows) != len(components) or not GuidedDownloadsPage._pin_review_set(rows):
        raise RuntimeError("Incomplete review evidence.")
    result = []
    for c, row in zip(components, rows):
        if any(c.get(k) != row.get(k) for k in ("id", "name", "sha256", "hint", "url", "phase")):
            raise RuntimeError("Recipe requirements changed. Rescan.")
        path = Path(row["file"])
        ident = planner.archive_identity(path)
        if not ident or ident["size"] > install_review.MAX_ARCHIVE_BYTES:
            raise RuntimeError("Invalid archive size or identity.")
        review = GuidedDownloadsPage._official_pin_review(row)
        evidence = row["candidates"][0] if review else None
        expected = evidence["sha256"] if review else c["sha256"]
        if review and evidence["identity"] != ident:
            raise RuntimeError("Archive changed. Rescan.")
        actual = planner._pinned_hash(planner.InventoryFile(path, ident["size"]), remaining=[planner.MAX_HASH_BYTES])
        if not expected or actual != expected:
            raise RuntimeError("Archive digest changed. Rescan.")
        install_review._zip_preflight(path)
        if planner.archive_identity(path) != ident:
            raise RuntimeError("Archive changed during review. Rescan.")
        result.append((str(path), row.get("release_expected") if review else "Recipe-pinned SHA-256", actual, c["sha256"], review))
    return tuple(result)

def build_uevr_hash_review(recipe, rows):
    """Only show failures against the currently pinned releases."""
    pins = recipe.get("archive_pins", {})
    if recipe.get("method") != "uevr" or not pins:
        raise RuntimeError("Unsupported checksum review.")
    failures = []
    for row in rows or ():
        role = row.get("id")
        if not GuidedDownloadsPage._verification_blocked(row) or role not in pins:
            continue
        path = Path(row["file"])
        identity = planner.archive_identity(path)
        if not identity or identity["size"] > install_review.MAX_ARCHIVE_BYTES:
            raise RuntimeError("Archive changed or cannot be checked. Rescan.")
        digest = planner._pinned_hash(planner.InventoryFile(path, identity["size"]),
                                      remaining=[planner.MAX_HASH_BYTES])
        if planner.archive_identity(path) != identity or digest == pins[role]:
            raise RuntimeError("Archive verification changed. Rescan.")
        required = recipe["archive_releases"][role]
        source = recipe["archive_display"][role]["url"]
        failures.append((str(path), required["fixed_tag"], required["asset"], source,
                         digest or "Could not verify", pins[role]))
    if not failures:
        raise RuntimeError("No pinned checksum failure remains. Rescan.")
    return tuple(failures)


class ReviewDialog(QDialog):
    def __init__(self, plan, parent=None, *, checksum_failure=False):
        super().__init__(parent)
        self.setWindowTitle("Dependency release review — installation blocked")
        self.resize(880, 420)
        self.setStyleSheet("QDialog {background:#0A0D10;} QLabel {color:#E5E8ED;} QPushButton {padding:9px;}")
        layout = QVBoxLayout(self)
        def add(text, warning=False):
            label = QLabel(text)
            label.setTextFormat(Qt.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if warning:
                label.setStyleSheet("color:#FFD21A;font-weight:700")
            layout.addWidget(label)
        if checksum_failure:
            self.setWindowTitle("Review installation - checksum verification failed")
            add("INSTALLATION BLOCKED - CHECKSUM VERIFICATION FAILED", True)
            for path, version, asset, source, digest, pin in plan:
                add(f"Affected archive: {path}", True)
                add(f"Required: {asset} - {version}")
                add(f"Approved source: {source}")
                add(f"Archive SHA-256: {digest}")
                add(f"Required SHA-256: {pin}")
            add("Download the required archive from the approved source, then rescan.")
        else:
            add("INSTALLATION BLOCKED — NEW RELEASE REQUIRES RECIPE REVIEW", True)
            for path, version, digest, pin, review in plan:
                add(f"{Path(path).name} — {version}", review)
                add(f"SHA-256: {digest}")
                if review:
                    add(f"Current recipe pin: {pin}")
            add("Official release identity is not installation authorization. A separately reviewed recipe and compatibility validation are required before installation. No game, backup or mod files are changed.")
        layout.addStretch()
        buttons = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)
        buttons.addStretch()
        self.apply_button = QPushButton("Install reviewed dependencies")
        self.apply_button.setEnabled(False)
        buttons.addWidget(self.apply_button)
        layout.addLayout(buttons)
