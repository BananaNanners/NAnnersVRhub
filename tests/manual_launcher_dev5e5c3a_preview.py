# SPDX-License-Identifier: GPL-3.0-only
"""Full Hub legacy recognition acceptance preview, isolated writable state."""
from PySide6.QtWidgets import QLabel
from tests.manual_launcher_dev5e5c2a_preview import SteamVRPreview, old


class RecognitionPreview(SteamVRPreview):
    report_version = '0.5.5-dev5E5-C3a'

    def identify_preview(self):
        super().identify_preview()
        self.setWindowTitle('NAnnersVRhub Dev5E5-C3a - Existing Installation Recognition')
        brand = self.findChild(QLabel, 'brandTitle')
        if brand:
            brand.setText('NAnnersVRhub - Dev5E5-C3a Preview')
        self.downloads.recognition_changed.connect(self.log_recognition)
        print('C3a recognition acceptance ready; live installation disabled', flush=True)

    def log_recognition(self):
        result = self.downloads.recognition_result
        if result is not None:
            print('C3a explicit recognition', result['status'], result.get('counts'), result.get('sampled_at'), flush=True)


if __name__ == '__main__':
    old.full.FullHubPreview = RecognitionPreview
    raise SystemExit(old.full.main())
