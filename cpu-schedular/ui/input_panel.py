# =============================================================================
# TEAM CONTRACT — READ BEFORE MODIFYING
# -----------------------------------------------------------------------------
# THIS FILE DEFINES USER INPUT; IT DOES NOT RUN THE SCHEDULER.
#
# OUTPUT CONTRACT (to engine via main_window):
#   - `collect_processes()` MUST return dicts compatible with `ProcessInput`
#     (pid, arrival, burst; optional priority when algorithm requires it).
#   - `algorithm_key()` strings MUST match `simulation.static_run` / `start_live`
#     dispatch keys (fcfs, sjf_np, sjf_p, priority_np, priority_p, rr).
#
# UI RULES:
#   - Show quantum spinbox only for RR and preemptive priority.
#   - Show priority column only for priority algorithms.
#   - Raise ValueError with clear messages on bad table data (caught by main_window).
#
# IMPORTANT FOR TEAMMATES:
#   - Do not embed scheduling logic here — only validation and field visibility.
#
# IF YOU ADD A NEW ALGORITHM TO THE COMBO → ADD IT TO ALGORITHMS AND simulation.py.
#
# =============================================================================


"""
Conditional process input: algorithm choice, batch/live mode, quantum when needed,
and a small table (PID, Arrival, Burst, Priority) with priority column hidden unless required.
"""
# Module-level docstring: describes the widget’s role in the CPU scheduler GUI.

from __future__ import annotations
# Postpone evaluation of type hints (e.g. forward refs) across Python 3.7+ style.

from typing import List
# Used for ALGORITHMS type annotation: list of (label, key) tuples.

from PySide6.QtWidgets import (
    QAbstractItemView,  # Enums for selection behavior and edit triggers on QTableWidget.
    QComboBox,  # Dropdown for algorithm and batch/live mode.
    QHBoxLayout,  # Horizontal row layout for controls.
    QHeaderView,  # Column resize modes for the process table.
    QLabel,  # Static text labels (Algorithm, Mode, Quantum, section title).
    QPushButton,  # Add row / Remove selected buttons.
    QSpinBox,  # Integer quantum for RR and preemptive priority.
    QTableWidget,  # Editable grid for PID, Arrival, Burst, Priority.
    QTableWidgetItem,  # One cell in the table.
    QVBoxLayout,  # Vertical stack: rows + table + buttons.
    QWidget,  # Base class for this custom panel.
)

# (display label, engine key)
ALGORITHMS: List[tuple[str, str]] = [
    # User-visible name and internal key passed to engine.static_run / start_live.
    ("FCFS", "fcfs"),
    ("SJF (non-preemptive)", "sjf_np"),
    ("SJF / SRTF (preemptive)", "sjf_p"),
    ("Priority (non-preemptive)", "priority_np"),
    ("Priority (preemptive)", "priority_p"),
    ("Round Robin", "rr"),
]


class InputPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)  # Initialize QWidget with optional parent for Qt hierarchy.
        layout = QVBoxLayout(self)  # Main vertical layout attached to this widget.

        row1 = QHBoxLayout()  # First row: algorithm + mode selectors.
        row1.addWidget(QLabel("Algorithm:"))  # Label before algorithm combo.
        self._algo = QComboBox()  # Dropdown populated from ALGORITHMS.
        for label, key in ALGORITHMS:  # Fill combo: visible text = label, data = engine key.
            self._algo.addItem(label, key)  # Store key in Qt user role (currentData()).
        row1.addWidget(self._algo)  # Place combo after “Algorithm:” label.
        row1.addWidget(QLabel("Mode:"))  # Label before batch/live combo.
        self._mode = QComboBox()  # Batch = instant simulation; live = real-time ticks.
        self._mode.addItem("Batch (instant)", "batch")  # User data key "batch".
        self._mode.addItem("Live (1s per unit)", "live")  # User data key "live".
        row1.addWidget(self._mode)  # Add mode combo to the first row.
        layout.addLayout(row1)  # Insert horizontal row into vertical main layout.

        row2 = QHBoxLayout()  # Second row: quantum spinbox (shown only for RR / priority_p).
        self._lbl_quantum = QLabel("Quantum:")  # Label toggled with spinbox visibility.
        self._quantum = QSpinBox()  # Integer input for time slice / quantum.
        self._quantum.setRange(1, 100)  # Reasonable bounds for assignment demos.
        self._quantum.setValue(2)  # Default quantum (must match team decision / engine).
        row2.addWidget(self._lbl_quantum)  # Left side: label.
        row2.addWidget(self._quantum)  # Next to label: spinbox.
        row2.addStretch()  # Push quantum controls left; absorb extra horizontal space.
        layout.addLayout(row2)  # Add quantum row below algorithm row.

        self._table = QTableWidget(0, 4)  # Start with zero rows, four columns.
        self._table.setHorizontalHeaderLabels(["PID", "Arrival", "Burst", "Priority"])  # Column titles.
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)  # Equal-ish widths.
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)  # Click selects whole row.
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)  # Cells editable by user.

        btn_row = QHBoxLayout()  # Row for table manipulation buttons.
        self._btn_add = QPushButton("Add row")  # Append empty process row.
        self._btn_remove = QPushButton("Remove selected")  # Delete highlighted rows.
        self._btn_add.clicked.connect(self._add_row)  # Qt signal → slot to insert row.
        self._btn_remove.clicked.connect(self._remove_selected)  # Qt signal → slot to delete rows.
        btn_row.addWidget(self._btn_add)  # Left button.
        btn_row.addWidget(self._btn_remove)  # Right button.
        btn_row.addStretch()  # Align buttons to the left.

        layout.addWidget(QLabel("Processes (required: PID, Arrival, Burst):"))  # Hint above grid.
        layout.addWidget(self._table)  # Expandable table occupies vertical space.
        layout.addLayout(btn_row)  # Buttons below the table.

        self._algo.currentIndexChanged.connect(self._sync_visibility)  # Re-run when algorithm changes.
        self._sync_visibility()  # Initial hide/show of priority column and quantum row.

        # Seed two example rows
        self._add_row()  # First default process row.
        self._add_row()  # Second default process row.

    def _algorithm_key(self) -> str:
        return self._algo.currentData()  # Engine key for selected algorithm (from addItem data).

    def _sync_visibility(self) -> None:
        algo = self._algorithm_key()  # Current scheduler key string.
        need_priority = algo in ("priority_np", "priority_p")  # Show column 3 only for priority modes.
        need_quantum = algo in ("rr", "priority_p")  # RR and preemptive priority need quantum in engine cfg.
        self._table.setColumnHidden(3, not need_priority)  # Hide priority column if not used.
        self._lbl_quantum.setVisible(need_quantum)  # Show label only when quantum applies.
        self._quantum.setVisible(need_quantum)  # Show spinbox together with label.

    def _add_row(self) -> None:
        r = self._table.rowCount()  # Next row index (append at end).
        self._table.insertRow(r)  # Create empty row at index r.
        for c, text in enumerate(["", "0", "1", "0"]):  # Defaults: empty PID, arrival 0, burst 1, priority 0.
            self._table.setItem(r, c, QTableWidgetItem(text))  # Place default text in each cell.

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self._table.selectedIndexes()}, reverse=True)  # Unique rows, delete bottom-up.
        for r in rows:  # Remove each selected row; reverse order keeps indices valid.
            self._table.removeRow(r)  # Delete row r from the model/view.
        if self._table.rowCount() == 0:  # Avoid empty table with no way to add data.
            self._add_row()  # Ensure at least one row remains for user input.

    def algorithm_key(self) -> str:
        return self._algorithm_key()  # Public alias for main window / tests.

    def mode_key(self) -> str:
        return self._mode.currentData()  # "batch" or "live" from combo user data.

    def quantum_value(self) -> int:
        return int(self._quantum.value())  # Integer quantum for config dict passed to engine.

    def collect_processes(self) -> list[dict]:
        """Build list of process dicts for the engine. Raises ValueError on bad input."""
        algo = self._algorithm_key()  # Need to know if priority column is required.
        need_priority = algo in ("priority_np", "priority_p")  # Same rule as _sync_visibility.
        out: list[dict] = []  # Accumulator for valid process dicts.
        seen: set[str] = set()  # Track PIDs to detect duplicates.

        for r in range(self._table.rowCount()):  # Iterate every table row.
            def cell(col: int) -> str:
                it = self._table.item(r, col)  # QTableWidgetItem at (row, col) or None.
                return (it.text() if it else "").strip()  # Text content stripped of whitespace.

            pid = cell(0)  # First column: process identifier string.
            if not pid:  # Skip blank rows (user left PID empty).
                continue
            if pid in seen:  # Duplicate PID invalid for simulation.
                raise ValueError(f"Duplicate PID in table: {pid}")
            seen.add(pid)  # Register PID as used.

            try:
                arrival = int(cell(1))  # Second column: arrival time (integer).
                burst = int(cell(2))  # Third column: total CPU burst.
            except ValueError as e:  # Non-numeric arrival/burst.
                raise ValueError(f"Row {r + 1}: Arrival and Burst must be integers.") from e

            if arrival < 0 or burst <= 0:  # Domain rules: arrival ≥ 0, burst positive.
                raise ValueError(f"Row {r + 1}: invalid arrival/burst.")

            pr = None  # Optional priority; None when algorithm ignores priority.
            if need_priority:  # Must read and validate priority column.
                try:
                    pr = int(cell(3))  # Fourth column: priority (lower number = higher priority in engine).
                except ValueError as e:
                    raise ValueError(f"Row {r + 1}: Priority must be an integer.") from e
                if pr < 0:  # Non-negative priority as per engine contract.
                    raise ValueError(f"Row {r + 1}: Priority must be >= 0.")

            out.append(
                {
                    "pid": pid,  # String process id.
                    "arrival": arrival,  # Integer arrival time.
                    "burst": burst,  # Integer total burst.
                    "priority": pr,  # int or None depending on algorithm.
                }
            )

        if not out:  # No valid rows after skipping empties.
            raise ValueError("Add at least one process with a non-empty PID.")
        return out  # List of dicts ready for static_run or start_live.
