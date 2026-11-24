# SPDX-License-Identifier: GPL-3.0-only
"""Full Hub SteamVR telemetry acceptance preview; isolated state."""
from PySide6.QtWidgets import QLabel
from tests import manual_launcher_dev5e2_install_preview as old


class SteamVRPreview(old.FatekeeperInstallPreview):
    report_version = "0.5.5-dev5E5-C2a"

    def identify_preview(self):
        super().identify_preview()
        self.setWindowTitle("NAnnersVRhub Dev5E5-C2a - SteamVR Headset Detection")
        brand = self.findChild(QLabel, "brandTitle")
        if brand:
            brand.setText("NAnnersVRhub - Dev5E5-C2a Preview")

    def show_system_report(self, report):
        super().show_system_report(report)
        live = report["live"]
        key = (report["runtime"], live.get("activity"), live.get("headset_connected"), live.get("headset_name"))
        if key != getattr(self, "_last_telemetry", None):
            self._last_telemetry = key
            print("C2a runtime transition", live["sampled_at"], key, live["headset_source"], flush=True)


if __name__ == "__main__":
    old.full.FullHubPreview = SteamVRPreview
    raise SystemExit(old.full.main())
