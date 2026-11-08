# SPDX-FileCopyrightText: 2026 Carlos Garcia (BananaNanners) and NAnnersVRhub contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in development window for all bundled game save adapters."""
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtWidgets import (QFileDialog, QComboBox, QLabel, QPushButton, QDialog, QVBoxLayout,
                               QHBoxLayout, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
                               QDialogButtonBox, QInputDialog, QSplitter, QMessageBox, QLineEdit, QWidget, QPlainTextEdit, QScrollArea, QLayout, QFrame)
from .doom_save_gui import DoomSavesDialog, summary, save_state
from .game_saves import GameSaves, enabled, compare_files
from .display_time import local_time
from .theme import BG
from .recovery_window_size import RecoveryWindowSize, DEFAULT_PERCENT


class GameSavesDialog(DoomSavesDialog):
    def __init__(self, recipe, parent=None, *, auto_scan=True, development_enabled=None):
        if not (enabled() if development_enabled is None else development_enabled):
            raise RuntimeError("Enable development save recovery before opening this window.")
        backend = GameSaves(recipe, development_enabled=development_enabled)
        super().__init__(recipe, parent, auto_scan=False, backend=backend)
        self.setWindowTitle(f"Development save recovery — {recipe['name']}")
        self.note.setText("Development tool: select the active target, then a source save folder. Backups are kept before replacement. Dates do not establish progress. No automatic newest-save selection or cloud synchronization. Close games and launchers before restoring.")
        self.custom_targets = set()
        self._pending_source_selection = None
        self.history_dialog = None
        self.comparison_dialog = None
        self.undo_dialog = None
        self._pending_history_source = None
        self.targets_label = QLabel("Active target (select the correct account, slot, world or character collection):")
        self.targets_label.setWordWrap(True)
        self.target_combo = QComboBox()
        self.target_combo.setMinimumContentsLength(30)
        self.target_combo.currentIndexChanged.connect(self.target_changed)
        self.target_choose = QPushButton("Choose active target folder…")
        self.target_choose.clicked.connect(self.choose_target)
        self.layout().insertWidget(1, self.targets_label)
        self.layout().insertWidget(2, self.target_combo)
        target_actions = QHBoxLayout()
        target_actions.addWidget(self.target_choose, 1)
        self.forget_locations_button = QPushButton("Forget remembered folders…")
        self.forget_locations_button.clicked.connect(self.forget_locations)
        self.forget_locations_button.setToolTip("Forget custom folder paths for this game only. Save files and backups are kept.")
        target_actions.addWidget(self.forget_locations_button)
        self.layout().insertLayout(3, target_actions)
        self.backup_current_button = QPushButton("Back up current saves…")
        self.history_button = QPushButton("Backup history…")
        self.backup_current_button.setEnabled(False)
        self.backup_current_button.clicked.connect(self.request_backup)
        self.history_button.clicked.connect(self.show_history)
        backup_actions = QHBoxLayout()
        backup_actions.addWidget(self.backup_current_button)
        backup_actions.addWidget(self.history_button)
        self.undo_button = QPushButton("Undo last restore…")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.show_undo)
        backup_actions.addWidget(self.undo_button)
        self.layout().insertLayout(4, backup_actions)
        self.compare_button = QPushButton("View file comparison…")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self.show_comparison)
        self.layout().insertWidget(self.layout().indexOf(self.restore_button), self.compare_button)
        # Give the save list priority instead of splitting scarce vertical space
        # equally with an empty details editor. Both panes remain scrollable.
        layout = self.layout()
        position = layout.indexOf(self.table)
        layout.removeWidget(self.table)
        layout.removeWidget(self.details)
        self.save_splitter = QSplitter(Qt.Vertical, self)
        self.save_splitter.setObjectName("saveRecoverySplitter")
        self.save_splitter.setChildrenCollapsible(False)
        self.save_splitter.setHandleWidth(8)
        self.table.setMinimumHeight(self.table.horizontalHeader().sizeHint().height()
                                    + 4 * self.table.verticalHeader().defaultSectionSize()
                                    + 2 * self.table.frameWidth()
                                    + self.table.horizontalScrollBar().sizeHint().height())
        self.details.setMinimumHeight(64)
        self.save_splitter.addWidget(self.table)
        self.save_splitter.addWidget(self.details)
        self.save_splitter.setStretchFactor(0, 5)
        self.save_splitter.setStretchFactor(1, 1)
        self.save_splitter.setSizes([500, 100])
        self.save_splitter.setToolTip("Drag the divider to resize the save list and details.")
        layout.insertWidget(position, self.save_splitter, 1)
        available = self.screen().availableGeometry()
        self.resize(max(1, int(available.width() * DEFAULT_PERCENT / 100)),
                    max(1, int(available.height() * DEFAULT_PERCENT / 100)))
        self.choose_button.setText("Browse for another source folder")
        self.choose_button.setToolTip("Add a source that is not listed. The browser starts at the selected row's folder when available.")
        self.source_help = QLabel("Click a row below to select a source. Browse only if your folder is not listed. Folders must contain this game's saves.")
        self.source_help.setWordWrap(True)
        layout.insertWidget(layout.indexOf(self.save_splitter), self.source_help)
        self.source_title = QLabel("Selected source:")
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.source_path.setPlaceholderText("None — click a save row other than the current target")
        self.remember_source_button = QPushButton("Remember selected source")
        self.remember_source_button.setEnabled(False)
        self.remember_source_button.clicked.connect(self.remember_selected_source)
        self.source_bar = QWidget()
        source_layout = QHBoxLayout(self.source_bar)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_title)
        source_layout.addWidget(self.source_path, 1)
        source_layout.addWidget(self.remember_source_button)
        detail_pane = QWidget()
        detail_layout = QVBoxLayout(detail_pane)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.source_bar)
        self.summary_splitter = QSplitter(Qt.Horizontal)
        self.summary_splitter.setObjectName("saveSourceTargetSplitter")
        self.summary_splitter.setChildrenCollapsible(False)
        self.summary_splitter.setHandleWidth(8)
        self.summary_splitter.setStyleSheet("QSplitter#saveSourceTargetSplitter::handle:horizontal { background: #31414a; margin: 3px 2px; } QSplitter#saveSourceTargetSplitter::handle:horizontal:hover { background: #FFD21A; }")
        self.summary_splitter.setToolTip("Drag the divider to resize the source and target panels.")
        source_panel = QWidget()
        source_panel_layout = QVBoxLayout(source_panel)
        source_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.source_heading = QLabel("SELECTED SOURCE")
        self.source_heading.setStyleSheet("font-weight: bold;")
        source_panel_layout.addWidget(self.source_heading)
        self.details.setMinimumHeight(96)
        source_panel_layout.addWidget(self.details, 1)
        target_panel = QWidget()
        target_panel_layout = QVBoxLayout(target_panel)
        target_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.target_heading = QLabel("ACTIVE TARGET")
        self.target_heading.setStyleSheet("font-weight: bold;")
        target_panel_layout.addWidget(self.target_heading)
        self.target_details = QPlainTextEdit()
        self.target_details.setReadOnly(True)
        self.target_details.setMinimumHeight(96)
        self.target_details.setPlainText("Select an active target to review its saves here.")
        target_panel_layout.addWidget(self.target_details, 1)
        source_panel.setMinimumWidth(180)
        target_panel.setMinimumWidth(180)
        self.summary_splitter.addWidget(source_panel)
        self.summary_splitter.addWidget(target_panel)
        self.summary_splitter.setStretchFactor(0, 1)
        self.summary_splitter.setStretchFactor(1, 1)
        self.summary_splitter.setSizes([500, 500])
        detail_layout.addWidget(self.summary_splitter, 1)
        self.save_splitter.addWidget(detail_pane)
        self.save_splitter.setStretchFactor(0, 3)
        self.save_splitter.setStretchFactor(1, 2)
        self.save_splitter.setSizes([300, 300])
        # Dialogs remain explicit in button wording; no decorative trailing dots.
        for button in self.findChildren(QPushButton):
            button.setText(button.text().removesuffix("…").removesuffix("..."))
        self._requested_target_path = None
        self.target_feedback = QPlainTextEdit()
        self.target_feedback.setReadOnly(True)
        self.target_feedback.setMinimumHeight(72)
        self.target_feedback.setMaximumHeight(104)
        self.target_feedback.setObjectName("targetChangeFeedback")
        self.dismiss_target_feedback = QPushButton("Dismiss")
        self.dismiss_target_feedback.clicked.connect(self.clear_target_feedback)
        self.target_feedback_box = QWidget()
        feedback_layout = QHBoxLayout(self.target_feedback_box)
        feedback_layout.setContentsMargins(0, 0, 0, 0)
        feedback_layout.addWidget(self.target_feedback, 1)
        feedback_layout.addWidget(self.dismiss_target_feedback)
        layout.insertWidget(4, self.target_feedback_box)
        self.target_feedback_box.hide()
        # Dynamic feedback must not force controls into the splitters' minimum
        # sizes. Scroll the form when space is tight and keep Close accessible.
        self.recovery_body = QWidget()
        self.recovery_body.setObjectName("saveRecoveryBody")
        self.recovery_body.setStyleSheet("QWidget#saveRecoveryBody { background-color: " + BG + "; }")
        body_layout = QVBoxLayout(self.recovery_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        while layout.count() > 1:
            stretch = layout.stretch(0)
            item = layout.takeAt(0)
            if item.widget() is not None:
                # Move the existing item with its widget so Qt invalidates the
                # same item's size cache when wrapped text changes later.
                item.widget().setParent(self.recovery_body)
                body_layout.addItem(item)
                body_layout.setStretch(body_layout.count() - 1, stretch)
            elif item.layout() is not None:
                child_layout = item.layout()
                child_layout.setParent(None)
                body_layout.addLayout(child_layout, stretch)
            else:
                body_layout.addItem(item)
        self.recovery_scroll = QScrollArea(self)
        self.recovery_scroll.setObjectName("saveRecoveryScroll")
        self.recovery_scroll.setFrameShape(QFrame.NoFrame)
        self.recovery_scroll.setWidgetResizable(True)
        self.recovery_scroll.viewport().setObjectName("saveRecoveryViewport")
        self.recovery_scroll.viewport().setStyleSheet("QWidget#saveRecoveryViewport { background-color: " + BG + "; }")
        self.recovery_scroll.setWidget(self.recovery_body)
        layout.insertWidget(0, self.recovery_scroll, 1)
        close_item = layout.takeAt(layout.count() - 1)
        footer = QHBoxLayout()
        self.window_size_controls = RecoveryWindowSize(self)
        footer.addWidget(self.window_size_controls, 1)
        footer.addItem(close_item)
        layout.addLayout(footer)
        self._label_fit_pending = False
        self._label_fit_timer = QTimer(self)
        self._label_fit_timer.setSingleShot(True)
        self._label_fit_timer.timeout.connect(self.fit_wrapped_labels)
        self._wrapped_labels = (self.note, self.targets_label, self.status, self.source_help, self.result)
        self._label_measure = QLabel(self)
        self._label_measure.setWordWrap(True)
        self._label_measure.hide()
        for label in self._wrapped_labels:
            policy = label.sizePolicy()
            policy.setHeightForWidth(False)
            label.setSizePolicy(policy)
        for watched in (self.recovery_body, self.recovery_scroll.viewport(), *self._wrapped_labels):
            watched.installEventFilter(self)
        self.queue_label_fit()
        if auto_scan:
            self.scan()

    def eventFilter(self, watched, event):
        if hasattr(self, "_wrapped_labels") and event.type() in {QEvent.Resize, QEvent.LayoutRequest, QEvent.FontChange, QEvent.StyleChange}:
            self.queue_label_fit()
        return super().eventFilter(watched, event)

    def queue_label_fit(self):
        if not self._label_fit_pending:
            self._label_fit_pending = True
            self._label_fit_timer.start(0)

    def fit_wrapped_labels(self):
        self._label_fit_pending = False
        changed = False
        for label in self._wrapped_labels:
            width = label.width()
            if width <= 0:
                continue
            self._label_measure.setFont(label.font())
            self._label_measure.setTextFormat(label.textFormat())
            self._label_measure.setContentsMargins(label.contentsMargins())
            self._label_measure.setText(label.text())
            height = max(label.fontMetrics().height(), self._label_measure.heightForWidth(width)) if label.text() else 0
            if label.minimumHeight() != height or label.maximumHeight() != height:
                label.setFixedHeight(height)
                changed = True
        if changed:
            self.recovery_body.layout().invalidate()
            self.recovery_body.layout().activate()
            self.recovery_body.updateGeometry()

    def _controls(self):
        super()._controls()
        if hasattr(self, "target_combo"):
            self.target_combo.setEnabled(self.worker is None)
            self.target_choose.setEnabled(self.worker is None)
            self.forget_locations_button.setEnabled(self.worker is None and bool((self.report or {}).get("remembered_targets") or (self.report or {}).get("remembered_sources")))
        if hasattr(self, "backup_current_button"):
            current = self.current_save_row()
            self.backup_current_button.setEnabled(self.worker is None and current is not None)
            self.history_button.setEnabled(self.worker is None)
        if hasattr(self, "undo_button"):
            self.undo_button.setEnabled(self.worker is None and bool((self.report or {}).get("undo_plan")))
            self.undo_button.setToolTip((self.report or {}).get("undo_reason") or "Preview undo for the selected target; nothing changes until confirmation.")
        if hasattr(self, "compare_button"):
            self.compare_button.setEnabled(self.worker is None and self.plan is not None)
        if hasattr(self, "source_path"):
            self.update_source_controls()

    def clear_target_feedback(self):
        self.target_feedback.clear()
        self.target_feedback_box.hide()

    def show_target_feedback(self, text):
        self.target_feedback.setPlainText(text)
        self.target_feedback.verticalScrollBar().setValue(0)
        self.target_feedback_box.show()

    def begin_target_choice(self, path):
        self._requested_target_path = path
        self.clear_target_feedback()
        self.show_target_feedback("Checking selected target. The current target is unchanged until validation passes.")

    def selected_save_row(self):
        if not self.report or not self.table.selectedItems():
            return None
        index = self.table.currentRow()
        if not 0 <= index < len(self.report["rows"]):
            return None
        row = self.report["rows"][index]
        return None if row.get("group_header") else row

    def update_source_controls(self):
        row = self.selected_save_row()
        source = row if row and not row["current"] else None
        path = source["root"] if source else ""
        if self.source_path.text() != path:
            self.source_path.setText(path)
            self.source_path.setCursorPosition(0)
        self.source_path.setToolTip(path)
        self.source_title.setText("Selected source:" if not source or source["usable"] else "Folder blocked:")
        remembered = path in (self.report or {}).get("remembered_sources", [])
        self.remember_source_button.setText("Source remembered" if remembered else "Remember selected source")
        self.remember_source_button.setEnabled(self.worker is None and bool(source and source["usable"]) and not remembered)
        self.remember_source_button.setToolTip("Store this source folder path for this game. Save files are not copied or restored.")
        # Keep the selected-source indicator separate from restore eligibility.
        # Matching, incompatible or invalid sets still use the existing guards.
        for index, item_row in enumerate((self.report or {}).get("rows", [])):
            if item_row.get("group_header"):
                continue
            item = self.table.item(index, 5)
            if item is not None:
                state = save_state(item_row)
                if item_row is source and item_row["usable"]:
                    state = "Selected source"
                item.setText(state)
        if self.report:
            parts = self.status.text().split("\n", 1)
            parts[0] = parts[0].replace("No source selected.", "Source selected." if source else "No source selected.")
            if not source:
                parts[0] = parts[0].replace("Source selected.", "No source selected.")
            self.status.setText("\n".join(parts))

    def remember_selected_source(self):
        row = self.selected_save_row()
        if self.worker is None and row and row["usable"] and not row["current"]:
            path = row["root"]
            self._start("remember_source", lambda: self.backend.remember_folder("sources", path), self.remembered_source)

    def scanned(self, report):
        self.custom_targets.update(report.get("remembered_targets", []))
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("Select an active target…", None)
        current = 0
        for row in report["rows"]:
            if row["label"] not in {"Active save location", "Current Heroic save"}:
                continue
            self.target_combo.addItem((row["location_role"] + " — " if row.get("location_role") else "") + row["root"], row["root"])
            if row["root"] == report["target"]:
                current = self.target_combo.count() - 1
        self.target_combo.setCurrentIndex(current)
        self.target_combo.blockSignals(False)
        # Keep source rows intact for the shared selection/restore logic. Visual
        # section rows are nonselectable and mapped explicitly into the report.
        plain, groups = [], {}
        for row in report["rows"]:
            if row.get("recovery_group"):
                groups.setdefault(row["recovery_group"], []).append(row)
            else:
                plain.append(row)
        plain.sort(key=lambda row: 0 if row["label"] in {"Active save location", "Current Heroic save"} else 1)
        ordered = list(plain)
        sections = []
        if plain and groups:
            sections.append((0, "Save locations", "Active locations and other explicitly available sources."))
        group_list = sorted(groups.values(), key=lambda rows: (rows[0].get("recovery_created_at") or "", rows[0]["recovery_group"]), reverse=True)
        for number, rows in enumerate(group_list, 1):
            row = rows[0]
            stamp = local_time(row["recovery_created_at"]) if row.get("recovery_created_at") else "Date unavailable"
            title = f"{row['recovery_operation']} — {stamp} · Backup set {number}"
            sections.append((len(ordered), title, row["recovery_group"]))
            ordered.extend(rows)
        sorted_report = dict(report, rows=ordered)
        self.table.clearSpans()
        super().scanned(sorted_report)
        display_rows = list(ordered)
        for offset, (position, title, tooltip) in enumerate(sections):
            index = position + offset
            self.table.insertRow(index)
            self.table.setSpan(index, 0, 1, self.table.columnCount())
            item = QTableWidgetItem(title)
            item.setFlags(Qt.ItemIsEnabled)
            font = item.font(); font.setBold(True); item.setFont(font)
            item.setToolTip(tooltip)
            self.table.setItem(index, 0, item)
            display_rows.insert(index, dict(group_header=True, current=False, usable=False))
        self.report = dict(report, rows=display_rows)
        location_count, backup_count = len(plain), sum(len(rows) for rows in group_list)
        self.status.setText(f"Found {location_count} save locations and {len(group_list)} recovery backup sets ({backup_count} saved copies). No source selected."
                            + ("\n" + "\n".join(report["notes"]) if report["notes"] else "")
                            + ("\nRestore blocked: " + " | ".join(dict.fromkeys(row.get("error", "Unknown scan error") for row in ordered if not row["usable"]))
                               if any(not row["usable"] for row in ordered) else ""))
        selected, self._pending_source_selection = self._pending_source_selection, None
        if selected:
            for index, row in enumerate(display_rows):
                if row.get("root") == selected and not row.get("current"):
                    self.table.selectRow(index)
                    self.table.scrollToItem(self.table.item(index, 0))
                    self.selection_changed()
                    break
        self.refresh_side_panels()
        self._controls()

    def target_changed(self, index):
        if self.worker is not None:
            return
        path = self.target_combo.itemData(index)
        if not path:
            self.clear_target_feedback()
            self.backend.target = None
            self.backend.manual_target = False
            self.scan()
            return
        self.begin_target_choice(path)
        self._start("select_target", lambda: self.backend.validate_target_folder(path), self.selected_target)

    def choose_target(self):
        if self.worker is not None:
            return
        initial = Path(self.backend.target) if self.backend.target else Path.home()
        while not initial.is_dir() and initial != initial.parent:
            initial = initial.parent
        path = QFileDialog.getExistingDirectory(self, "Choose this game's active save-only target", str(initial))
        if path:
            self.begin_target_choice(path)
            self._start("remember_target", lambda: self.backend.remember_folder("targets", path), self.remembered_target)

    def selected_target(self, path):
        self.backend.target = path
        self.backend.manual_target = path in self.custom_targets
        self.show_target_feedback("Target changed. No saves were moved.\nTarget: " + path)

    def remembered_target(self, path):
        self.custom_targets.add(path)
        self.selected_target(path)

    def remembered_source(self, path):
        if path not in self.extra_roots:
            self.extra_roots.append(path)
        self._pending_source_selection = path
        self.result.setText("Source folder remembered for this game. Save files were not changed.")

    def confirm_forget_locations(self):
        return QMessageBox.question(self, "Forget remembered folders?",
                                    "Forget custom source and target paths for this game? Save files and backups are kept. The current custom target will be deselected.",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def forget_locations(self):
        if self.worker is None and self.confirm_forget_locations():
            self._start("forget_locations", self.backend.forget_folders, self.forgot_locations)

    def forgot_locations(self, _result):
        remembered = set((self.report or {}).get("remembered_targets", []) + (self.report or {}).get("remembered_sources", []))
        self.extra_roots = [p for p in self.extra_roots if p not in remembered]
        self.custom_targets.difference_update(remembered)
        if self.backend.target in remembered:
            self.backend.target = None
            self.backend.manual_target = False
        self.plan = None
        self.result.setText("Remembered folders forgotten for this game. Save files and backups were kept.")

    def selection_changed(self):
        index = self.table.currentRow()
        if self.report and 0 <= index < len(self.report["rows"]) and self.report["rows"][index].get("group_header"):
            self.plan = None
            self.details.setPlainText("Choose a save set below this heading. Backups are grouped by operation; folder paths remain in each row's tooltip and selected-save details.")
            self.refresh_side_panels()
            self._controls()
            return
        super().selection_changed()
        if self.plan is not None:
            source, target = self.plan["source"], self.plan["target"]
            if (source.get("component"), source.get("account")) != (target.get("component"), target.get("account")):
                self.plan = None
                self.details.setPlainText("Save type or account differs; restore blocked. Account conversion is not supported.")
                self._controls()
        if self.plan is not None:
            difference = compare_files(self.plan["source"]["files"], self.plan["target"]["files"])
            self.details.appendPlainText("\nFILE COMPARISON — EFFECT ON TARGET\n" + comparison_summary(difference)
                                        + "\nRemoved means absent from the restored folder; the original target is retained in backup."
                                        + "\nUse View file comparison for every relative path. Counts compare file hashes, not gameplay progress.")

        self.refresh_side_panels()

    def refresh_side_panels(self):
        if not hasattr(self, "target_details"):
            return
        target = next((row for row in (self.report or {}).get("rows", []) if row.get("current")), None)
        if target and target["usable"]:
            self.target_details.setPlainText(summary(target))
        elif target:
            self.target_details.setPlainText("Target blocked: " + target.get("error", "Save set is not valid.")
                                            + "\nLocation: " + target["root"]
                                            + ("\nObserved folder date: " + local_time(target["file_modified_at"]) + " (not validated save data)"
                                               if target.get("file_modified_at") else "\nDate unavailable"))
        else:
            self.target_details.setPlainText("No active target selected. Choose the game's save folder above.")
        row = self.selected_save_row()
        self.source_heading.setText("SELECTED SOURCE — RESTORE BLOCKED" if row and not row.get("current") and not row["usable"] else "SELECTED SOURCE")
        if row and row.get("current") and row["usable"]:
            self.details.setPlainText("ACTIVE SAVE TARGET selected. Choose a different save row as the source. The target's details are shown on the right.")
        elif row and not row.get("current") and row["usable"]:
            notes = self.details.toPlainText().replace(summary(row), "")
            if target and target["usable"]:
                notes = notes.replace(summary(target), "")
            headings = {"ACTIVE SAVE TARGET TO REPLACE", "ACTIVE SAVE TARGET", "SELECTED SOURCE", "SOURCE"}
            notes = "\n".join(line for line in notes.splitlines() if line not in headings)
            self.details.setPlainText(summary(row) + ("\n\n" + notes.strip() if notes.strip() else ""))
        # Invalid folders and scan diagnostics remain visible in the source panel.
        self.details.verticalScrollBar().setValue(0)
        self.target_details.verticalScrollBar().setValue(0)

    def show_comparison(self):
        if self.worker is None and self.plan is not None:
            self.comparison_dialog = FileComparisonDialog(self.plan, self)
            self.comparison_dialog.show()

    def choose(self):
        if self.worker is not None:
            return
        row = self.selected_save_row()
        initial = Path(row["root"]) if row else Path.home()
        while not initial.is_dir() and initial != initial.parent:
            initial = initial.parent
        path = QFileDialog.getExistingDirectory(self, "Browse for another source folder containing this game's saves", str(initial))
        if path:
            self._start("remember_source", lambda: self.backend.remember_folder("sources", path), self.remembered_source)

    def confirm_restore(self, plan):
        from PySide6.QtWidgets import QMessageBox
        question = QMessageBox(self)
        question.setObjectName("doomSaveConfirmation")
        undoing = bool(plan.get("undo_record"))
        question.setWindowTitle("Undo last restore?" if undoing else "Development: replace selected save target?")
        question.setIcon(QMessageBox.Question)
        question.setTextFormat(Qt.PlainText)
        difference = compare_files(plan["source"]["files"], plan["target"]["files"])
        undo_note = ("UNDO of restore recorded: " + local_time(plan.get("restore_created_at"))
                     + ("\nCurrent saves changed since that restore. Undo replaces those changes; a fresh backup is kept." if plan.get("current_changed_since_restore") else "")
                     + "\n\n") if undoing else ""
        question.setText(undo_note + f"Game: {self.recipe['name']}\nClose games, injectors, MO2, Steam and Heroic. Disable cloud sync.\n\nSOURCE\n"
                         + summary(plan["source"]) + "\n\nREPLACE TARGET\n" + summary(plan["target"])
                         + "\n\nFILE COMPARISON — EFFECT ON TARGET\n" + comparison_summary(difference)
                         + "\nThis replaces the entire target folder. Target-only files will be absent from the restored folder; originals remain backed up."
                         + "\n\nBoth complete folders will be backed up and verified. Save compatibility and progress are not verified. Continue?")
        question.setDetailedText(comparison_details(difference))
        question.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        question.setDefaultButton(QMessageBox.No)
        if undoing:
            question.button(QMessageBox.Yes).setText("Back up and undo")
        return question.exec() == QMessageBox.Yes

    def restored(self, result):
        super().restored(result)
        self.result.setText(self.result.text().replace("Launch DOOM normally and check Continue.", "Launch the selected game and verify your progress."))

    def show_undo(self):
        plan = (self.report or {}).get("undo_plan")
        if self.worker is None and plan is not None:
            self.undo_dialog = UndoPreviewDialog(plan, self)
            self.undo_dialog.undo_requested.connect(self.request_undo)
            self.undo_dialog.show()

    def request_undo(self, plan):
        if self.worker is not None:
            return
        from copy import deepcopy
        plan = deepcopy(plan)
        if not self.confirm_restore(plan):
            return
        self.status.setText("Backing up current saves, verifying originals and undoing the last restore…")
        self._start("undo", lambda: self.backend.undo(plan), self.undone)

    def undone(self, result):
        self.last_backup = result["backup"]
        self.backup_button.setEnabled(True)
        self.result.setText(f"Undo completed; {result['file_count']} files verified.\n"
                            + "The saves that existed before undo are retained in a fresh recovery backup.\n"
                            + "Backup: " + result["backup"]
                            + ("\n" + result["warning"] if result.get("warning") else ""))

    def current_save_row(self):
        return next((row for row in (self.report or {}).get("rows", []) if row["current"] and row["usable"]), None)

    def backup_note(self, row):
        dialog = QInputDialog(self)
        dialog.setObjectName("doomSaveConfirmation")
        dialog.setWindowTitle("Back up current saves")
        dialog.setLabelText("Close the game, injectors, MO2, Steam and Heroic first.\n\n"
                            + summary(row) + "\n\nOptional note (one line, up to 300 characters):")
        dialog.setOkButtonText("Create verified backup")
        if dialog.exec() != QDialog.Accepted:
            return None
        return dialog.textValue()

    def request_backup(self):
        if self.worker is not None:
            return
        row = self.current_save_row()
        if row is None:
            return
        note = self.backup_note(row)
        if note is None:
            return
        from copy import deepcopy
        expected = deepcopy(row)
        self.status.setText("Creating and verifying a backup of the selected current saves…")
        self._start("backup", lambda: self.backend.backup_current(expected, note), self.backed_up)

    def backed_up(self, result):
        self.last_backup = result["backup"]
        self.backup_button.setEnabled(True)
        self.result.setText(f"Backed up {result['file_count']} files; SHA-256 verification passed. Active saves were not replaced.\n"
                            + f"Created: {local_time(result['created_at'])}\nBackup: {result['backup']}"
                            + ("\nNote: " + result["note"] if result["note"] else ""))

    def failed(self, message):
        super().failed(message)
        if self.action == "backup":
            self.result.setText("Backup stopped.\n" + message)
        elif self.action == "undo":
            self.result.setText("Undo stopped.\n" + message)
        elif self.action in {"remember_target", "select_target"}:
            self.show_target_feedback("Target change blocked. Target unchanged; no saves were moved.\n"
                                      + message + "\nChosen folder: " + str(self._requested_target_path))

    def finished_work(self):
        action = self.action
        super().finished_work()
        if action in {"backup", "undo", "remember_target", "select_target", "remember_source", "forget_locations"}:
            self.scan()
        elif self._pending_history_source is not None and self.worker is None:
            path, self._pending_history_source = self._pending_history_source, None
            self.use_history_source(path)

    def show_history(self):
        if self.worker is None:
            self.status.setText("Reading backup history…")
            self._start("history", self.backend.backup_history, self.history_loaded)

    def history_loaded(self, rows):
        self.history_dialog = BackupHistoryDialog(self.recipe, rows, self)
        self.history_dialog.source_selected.connect(self.use_history_source)
        self.history_dialog.show()
        self.status.setText("Backup history read. Recorded backups are verified before restore.")

    def use_history_source(self, path):
        if self.worker is not None:
            self._pending_history_source = path
            return
        if path not in self.extra_roots:
            self.extra_roots.append(path)
        self.scan()


class BackupHistoryDialog(QDialog):
    source_selected = Signal(str)

    def __init__(self, recipe, rows, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.setObjectName("doomSaveRecoveryDialog")
        self.setWindowTitle("Save backup history — " + recipe["name"])
        self.setWindowModality(Qt.WindowModal)
        self.resize(1050, 460)
        layout = QVBoxLayout(self)
        note = QLabel("Up to 128 recent snapshot records for this game. Recorded status is historical; files are verified when used as a restore source. Backups are not deleted automatically.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(len(rows), 6)
        self.table.setHorizontalHeaderLabels(["Game", "Backup created", "Hub version", "Files", "Note", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        for index, row in enumerate(rows):
            status = "Recorded complete — verify before restore" if row["status"] == "complete" else ("Restore blocked — backup verification needed" if row["status"] == "review required" else "Restore blocked — backup incomplete")
            values = [row["game_name"], local_time(row.get("created_at")), row["hub_version"], row["file_count"], row["note"], status]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(row["folder"] + ("\nNote: " + row["note"] if row.get("note") else "")
                                + ("\n" + row["error"] if row.get("error") else ""))
                self.table.setItem(index, column, item)
        self.table.clearSelection()
        layout.addWidget(self.table)
        self.use_button = QPushButton("Show selected backup as a source")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.use_selected)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.use_button)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

    def selection_changed(self):
        index = self.table.currentRow()
        self.use_button.setEnabled(bool(self.table.selectedItems()) and 0 <= index < len(self.rows)
                                   and self.rows[index]["status"] == "complete")

    def use_selected(self):
        index = self.table.currentRow()
        if self.use_button.isEnabled() and 0 <= index < len(self.rows):
            self.source_selected.emit(self.rows[index]["save_path"])
            self.accept()


def comparison_summary(difference):
    return (f"Added: {len(difference['added'])} | Changed: {len(difference['changed'])} | "
            f"Removed: {len(difference['removed'])} | Unchanged: {len(difference['unchanged'])}")


def comparison_details(difference):
    return "\n\n".join(kind.upper() + f" ({len(difference[kind])})\n"
                          + ("\n".join(difference[kind]) or "None")
                          for kind in ("added", "changed", "removed", "unchanged"))


class FileComparisonDialog(QDialog):
    def __init__(self, plan, parent=None):
        super().__init__(parent)
        self.setObjectName("doomSaveRecoveryDialog")
        self.setWindowTitle("Save file comparison — effect on target")
        self.setWindowModality(Qt.WindowModal)
        self.resize(1000, 550)
        difference = compare_files(plan["source"]["files"], plan["target"]["files"])
        layout = QVBoxLayout(self)
        counts = QLabel(comparison_summary(difference))
        counts.setWordWrap(True)
        layout.addWidget(counts)
        explanation = QLabel("Whole-folder replacement: added files come from the source; changed files have different content hashes; removed files exist only in the target. Original target files are backed up. Hashes do not measure gameplay progress. Files are checked again before restore.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        paths = QLabel("SOURCE: " + plan["source"]["root"] + "\nTARGET: " + plan["target"]["root"])
        paths.setTextFormat(Qt.PlainText)
        paths.setWordWrap(True)
        paths.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(paths)
        self.table = QTableWidget(sum(len(values) for values in difference.values()), 2)
        self.table.setHorizontalHeaderLabels(["Effect on target", "Relative file path"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        index = 0
        for kind in ("added", "changed", "removed", "unchanged"):
            for path in difference[kind]:
                self.table.setItem(index, 0, QTableWidgetItem(kind.capitalize()))
                item = QTableWidgetItem(path)
                item.setToolTip(path)
                self.table.setItem(index, 1, item)
                index += 1
        layout.addWidget(self.table)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)


class UndoPreviewDialog(FileComparisonDialog):
    undo_requested = Signal(object)

    def __init__(self, plan, parent=None):
        from copy import deepcopy
        super().__init__(plan, parent)
        self.plan = deepcopy(plan)
        self.setWindowTitle("Preview undo — last restore for selected target")
        message = "Restore recorded: " + local_time(plan.get("restore_created_at")) + ". Undo returns this target to its verified pre-restore save set."
        if plan.get("current_changed_since_restore"):
            message += " Current saves changed since that restore; undo replaces those changes. A fresh backup is kept before undo."
        else:
            message += " Current saves are backed up before undo."
        label = QLabel(message)
        label.setWordWrap(True)
        self.layout().insertWidget(0, label)
        self.proceed_button = QPushButton("Review confirmation to undo")
        self.proceed_button.clicked.connect(self.proceed)
        self.layout().insertWidget(self.layout().count() - 1, self.proceed_button)

    def proceed(self):
        self.accept()
        self.undo_requested.emit(self.plan)
