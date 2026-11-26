# SPDX-License-Identifier: GPL-3.0-only
"""Shared desktop review window; UI restrictions are not backend authorization."""
from PySide6.QtWidgets import QPushButton
from .gui import HubWindow
from . import fatekeeper_commit


class ReadOnlyPreview(HubWindow):
    """Use normal read-only handlers, preserving their own enabled state."""
    def __init__(self):
        if fatekeeper_commit.live_install_authorized():
            raise RuntimeError("Preview requires the closed production gate.")
        super().__init__(read_only_preview=True)
        self.downloads.advanced_availability_changed.connect(self.apply_preview_policy)
        self.downloads.scan_idle.connect(self.apply_preview_policy)
        self.downloads.download_idle.connect(self.apply_preview_policy)
        self.apply_preview_policy()

    def show_details(self):
        super().show_details()
        self.apply_preview_policy()

    def apply_preview_policy(self):
        d = self.downloads
        allowed = {self.sidebar.games_button, self.sidebar.system_button,
                   self.library_toggle, self.more_tools_toggle,
                   self.install_tools_toggle, self.update_tools_toggle,
                   d.folder_menu_button, d.scan, d.install_review_button,
                   d.inspect, d.integrity_button, d.set_global, d.set_game,
                   d.clear_game, d.reset_global, d.manual_review_button,
                   d.comparison_toggle, d.safety_button, self.mod_updates.refresh_button,
                   self.compat_refresh_btn, self.compat_copy_btn,
                   self.scan_btn, self.copy_scan_btn}
        for button in self.mod_updates.findChildren(QPushButton) + d.table.findChildren(QPushButton):
            if button.objectName() == "modSourceButton" or button.text() == "Open source":
                allowed.add(button)
        for button in self.findChildren(QPushButton):
            if button not in allowed:
                button.setEnabled(False)
        self.development_tools_action.setEnabled(False)
        self.hub_update_btn.setEnabled(False)
        self.allow_guided_installs = False
        d.allow_transfers = False
        d._sync_folder_actions()

    def _run(self, *args, **kwargs):
        # No mutation through the generic action dispatcher in this preview.
        return

    def mark_current(self):
        return

    def set_nexus_key(self):
        return

    def uninstall(self):
        return

    def uninstall_profile(self):
        return

    def refresh_system_live(self):
        # Bootstrap on first dashboard visit; thereafter use the existing
        # five-second read-only refresh. No runtime is started or selected.
        if self.auto_live.isChecked():
            if self.scan_report is None:
                if self.tabs.currentIndex() == 0:
                    self.scan_setup()
            else:
                super().refresh_system_live()

    def show_system_report(self, report):
        super().show_system_report(report)
        self.save_scan_btn.setEnabled(False)

    def save_system_report(self):
        # Arbitrary report file writes remain outside preview scope.
        return

    def set_development_tools_enabled(self, checked):
        super().set_development_tools_enabled(False)
