# SPDX-License-Identifier: GPL-3.0-only
"""Presentation only: translate known diagnostics, never authorize recovery."""


def recovery_guidance(detail):
    if not detail:
        return ""
    if detail.startswith("Fatekeeper recovery pending."):
        return ("Installation interrupted. Open Rollback to review the previous installation "
                "before retrying. The Hub must verify that restoration is safe.")
    return ("Recovery records need review. Keep all backups and recovery files. "
            "Do not retry installation or restore files manually.")


def failure_guidance(detail):
    """Conservative message matching; original diagnostics remain available."""
    if detail.startswith("Recover the existing Fatekeeper transaction before retrying."):
        return recovery_guidance("Fatekeeper recovery pending.")
    if detail.startswith(("Historical backup", "Incomplete or unsafe Fatekeeper historical",
                          "Missing historical", "Unexpected historical",
                          "Conflicting historical", "Missing or unsafe retained original",
                          "Unsafe historical", "Nonterminal historical")):
        return ("Older backups need review. Keep them unchanged and do not retry installation. "
                "Any active recovery must be checked separately in Rollback.")
    if detail.startswith(("Unsafe active Fatekeeper", "Unexpected or missing active Fatekeeper",
                          "Previous Fatekeeper backup verification", "Fatekeeper rollback blocked")):
        return ("The current recovery backup or files could not be verified. "
                "Keep all files and backups unchanged. Manual review is required before restoration or installation.")
    if detail.startswith(("Unresolved production recovery evidence", "Interrupted atomic publication",
                          "Unsafe production staging", "Pending production journal",
                          "Pending initial production journal", "Missing authorized production journal",
                          "Production journal lacks", "Unsafe scoped provenance",
                          "Corrupted scoped provenance", "Invalid scoped provenance")):
        return ("Recovery records need review. Keep all backups and recovery files. "
                "Do not retry installation or restore files manually.")
    if detail.startswith(("Fatekeeper storage identity changed", "Fatekeeper persistent storage identity changed",
                          "Fatekeeper paths changed", "Fatekeeper recovery review changed",
                          "Fatekeeper recovery destination changed", "Archive changed during review")):
        return ("The installation or review changed. Reopen the review to check the current files "
                "and recovery status before retrying.")
    if detail.startswith(("Choose the official UEVR", "Choose Fatekeeper VR Profile")):
        return "The download does not match the approved release. Download the required version and scan again."
    return ("Installation did not complete. Close this review and check recovery status before retrying. "
            "Keep existing files and backups unchanged.")
