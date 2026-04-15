# =============================================================================
# burst_table.py
# -----------------------------------------------------------------------------
# This file is responsible for TWO visual components in the GUI:
#
#   1. BurstTable  — A live updating table that shows every process,
#                    original burst time, remaining time, current state.
#
#   2. MetricsView — A small card that shows the running averages for waiting time
#                    and turnaround time (it keeps getting updated during simulation
#                    and gives final result at the end).


#
# Both are PySide6 widgets. A widget can contain other widgets.
#
# HOW IT CONNECTS TO THE REST OF THE PROJECT:
#   - The Simulation engine calls `table.update_state(snapshot)` every tick (second).
#   - `snapshot` is just a list of dictionaries — one per process — that the
#     engine already builds. You don't need to touch the engine yourself.
#   - When all processes finish, the engine calls
#     `metrics.set_final(avg_waiting, avg_turnaround)`.
# =============================================================================

from PySide6.QtWidgets import (
    QWidget,          # Base class for all visual elements
    QVBoxLayout,      # Stacks vertically
    QHBoxLayout,      # Stacks horizontally
    QTableWidget,     # The actual  table
    QTableWidgetItem, # A single cell inside the table
    QLabel,           # A text display widget
    QHeaderView,      # Controls how column headers behave
    QFrame,           # A box/panel widget (used for the metrics card)
    QSizePolicy,      # Controls how a widget grows/shrinks
)
from PySide6.QtCore import Qt          # Constants alignment
from PySide6.QtGui import QColor, QFont  # For cell background colors and fonts


# =============================================================================
# PART 1 — BurstTable
# =============================================================================

class BurstTable(QWidget):
    """
    A live table that shows each process's status during the simulation.

    Columns:
      PID | Original Burst | Remaining Burst | State

    State can be: "Ready", "Running", or "Finished"

    """

    # These are the column names shown in the table header
    COLUMNS = ["PID", "Original Burst", "Remaining Burst", "State"]

    # Color mapping for each state background using RGB
    STATE_COLORS = {
        "Running":  QColor(102, 102, 255),
        "Ready":    QColor(255, 102, 102),
        "Finished": QColor(192, 192, 192),
    }

    def __init__(self, parent=None):
        """
        __init__  constructor that runs when you create a new table.
        It builds the visual layout (title label + table).
        """
        super().__init__(parent)

        # --- Outer layout: stacks the title label on top of the table ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # No padding around edges
        layout.setSpacing(12)

        # --- Title label ---
        title = QLabel("Remaining Burst Time")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        # --- The table itself ---
        self.table = QTableWidget()                          #creates the actual table
        self.table.setColumnCount(len(self.COLUMNS))         # 4 columns
        self.table.setHorizontalHeaderLabels(self.COLUMNS)   # Set header text
        self.table.setRowCount(0)                            # Start with 0 rows
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        #^Makes cells read-only so the user can't accidentally edit them (authorization)

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        #^Clicking a cell highlights the whole row


        # Make columns stretch to fill the available width evenly
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)



        layout.addWidget(self.table)

        # --- Internal store: maps PID to row index so we can update quickly and don't rebuild table every tick ---
        self._pid_to_row: dict[str, int] = {}

    # -------------------------------------------------------------------------
    def update_state(self, snapshot: list[dict]):
        """
        Called by the engine every tick to update the table.

        Args:
            snapshot: A list of dicts, one per process. Each dict must have:
                      "pid"       (str)  — process identifier,"P1"
                      "burst"     (int)  — original burst time
                      "remaining" (int)  — how much is left (0 if finished)
                      "state"     (str)  — "Ready", "Running", or "Finished"


          - New processes get a new row added.
          - Existing processes just get their cells updated in-place.
        """
        for process in snapshot:
            pid       = str(process["pid"])
            burst     = int(process["burst"])
            remaining = int(process["remaining"])
            state     = str(process["state"])

            if pid not in self._pid_to_row:
                # This process hasn't appeared before >> add a new row
                row = self.table.rowCount()       # Current last index
                self.table.insertRow(row)         # Append a blank row
                self._pid_to_row[pid] = row       # Remember its position

            row = self._pid_to_row[pid]

            # Update the four cells in this row. Table doesn't reset
            self._set_cell(row, 0, pid)
            self._set_cell(row, 1, str(burst))
            self._set_cell(row, 2, str(remaining))
            self._set_cell(row, 3, state, color=self.STATE_COLORS.get(state))   #add state and assign it to its color

    # -------------------------------------------------------------------------
    def reset(self):
        """
        Clears the entire table and the internal row-tracking dictionary.
        Needed for when the user presses Reset to start a fresh simulation.
        """
        self.table.setRowCount(0)       # Remove all rows visually
        self._pid_to_row.clear()        # Forget all row-position mappings

    # -------------------------------------------------------------------------
    def _set_cell(self, row: int, col: int, text: str, color: QColor = None):
        """
       creates or updates a table cell. puts text inside. Add color if needed

        Args:
            row:   Row index (first row = 0)
            col:   Column index (PID = 0, Original = 1, Remaining = 2, State = 3)
            text:  The text to display inside the cell
            color: Optional background color
        """
        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignCenter  # Center text inside each cell
        )
        if color: #if cause it's not in all cases it's optional
            item.setBackground(color)    # Apply background color if provided
        self.table.setItem(row, col, item)


# =============================================================================
# PART 2 — MetricsView
# =============================================================================

class MetricsView(QWidget):
    """
    A small Dashboard displays two averages:
      • Average Waiting Time
      • Average Turnaround Time

    These update live as processes finish,
    and show the final values when all processes are done.

    HOW TO USE (from main_window.py):
        self.metrics = MetricsView()
        layout.addWidget(self.metrics)

        # During the run, update with averages of completed processes so far:
        self.metrics.update(avg_waiting=3.5, avg_turnaround=7.0)

        # When the simulation ends, call set_final to lock in final values:
        self.metrics.set_final(avg_waiting=4.2, avg_turnaround=8.1)

        # To reset (e.g. user presses Reset):
        self.metrics.reset()
    """

    def __init__(self, parent=None): #it's optional for this widget to have a parent "Stand-alone"
        """
        Builds two labeled value displays side by side.
        """
        super().__init__(parent)

        # --- Outer frame gives a visible border around the metrics panel ---
        outer = QVBoxLayout(self)                       # Creates outer vertical layout
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)   # Draws a border
        frame.setFrameShadow(QFrame.Shadow.Raised)
        outer.addWidget(frame)

        # --- Inner layout inside the frame ---
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.setSpacing(8)

        # --- Title ---
        title = QLabel("Averages")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)

        # --- Two metric boxes side by side ---
        row_layout = QHBoxLayout()
        row_layout.setSpacing(16)

        # Create one display box for each metric
        self._waiting_box    = self._make_metric_box("Avg Waiting Time",      "—")
        self._turnaround_box = self._make_metric_box("Avg Turnaround Time",   "—")

        row_layout.addWidget(self._waiting_box)
        row_layout.addWidget(self._turnaround_box)
        inner.addLayout(row_layout)

        # --- Status label (shows "Live" during run, "Final" when done) ---
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: grey; font-size: 10px;")
        inner.addWidget(self._status_label)

        # Store references to the value labels so we can update them later
        # (These are set inside _make_metric_box below)
        self._waiting_value_label: QLabel = self._waiting_box.findChild(
            QLabel, "value_label"
        )
        self._turnaround_value_label: QLabel = self._turnaround_box.findChild(
            QLabel, "value_label"
        )

    # -------------------------------------------------------------------------
    def update(self, avg_waiting: float, avg_turnaround: float):
        """
        Updates the displayed averages during the simulation.
        This is meant to be called whenever a process finishes (partial average).

        Args:
            avg_waiting:     Current average waiting time of finished processes
            avg_turnaround:  Current average turnaround time of finished processes
        """
        self._waiting_value_label.setText(f"{avg_waiting:.2f}")
        # ^^^ :.2f formats the number to 2 decimal places, 4.2 >> "4.20"
        self._turnaround_value_label.setText(f"{avg_turnaround:.2f}")
        self._status_label.setText("(live — completed processes)")

    # -------------------------------------------------------------------------
    def set_final(self, avg_waiting: float, avg_turnaround: float):
        """
        Shows the final averages when the simulation ends.
        Changes the status label to "Final" to signal the run is complete.

        Args:
            avg_waiting:     Final average waiting time across all processes
            avg_turnaround:  Final average turnaround time across all processes
        """
        self._waiting_value_label.setText(f"{avg_waiting:.2f}")
        self._turnaround_value_label.setText(f"{avg_turnaround:.2f}")
        self._status_label.setText("✓ Final result")
        self._status_label.setStyleSheet("color: green; font-size: 10px;")

    # -------------------------------------------------------------------------
    def reset(self):
        """
        Resets both metric values back to dashes and clears the status label.
        Call this when the user presses Reset.
        """
        self._waiting_value_label.setText("—")
        self._turnaround_value_label.setText("—")
        self._status_label.setText("")
        self._status_label.setStyleSheet("color: grey; font-size: 10px;")

    # -------------------------------------------------------------------------
    def _make_metric_box(self, label_text: str, initial_value: str) -> QFrame:
        """
        Helper: builds a small card that shows a metric name + its value.

        Args:
            label_text:    The metric name to display ("Avg Waiting Time")
            initial_value: Starting display value (use "—" before any data)

        Returns:
            A QFrame widget containing two QLabels stacked vertically.
        """
        box = QFrame()
        box.setFrameShape(QFrame.Shape.Box)
        box.setFrameShadow(QFrame.Shadow.Sunken)
        box.setSizePolicy(
            QSizePolicy.Policy.Expanding,   # Grow horizontally
            QSizePolicy.Policy.Fixed        # Don't grow vertically
        )

        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setSpacing(4)
        box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top: small label describing the metric
        name_label = QLabel(label_text)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: grey; font-size: 10px;")

        # Bottom: big bold number
        value_label = QLabel(initial_value)
        value_label.setObjectName("value_label")
        # ^ObjectName lets us find this label later with findChild()
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))

        box_layout.addWidget(name_label)
        box_layout.addWidget(value_label)

        return box


# =============================================================================
# QUICK DEMO — only runs if you execute THIS file directly in PyCharm
# (not when imported by main_window.py)
# =============================================================================

if __name__ == "__main__":
    """
    This block to test widgets in isolation WITHOUT needing
    the rest of the project to be ready. May be deleted later

    """
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # --- Build a small test window ---
    window = QWidget()
    window.setWindowTitle("BurstTable + MetricsView — standalone test")
    window.resize(600, 400)
    main_layout = QVBoxLayout(window)
    main_layout.setSpacing(16)
    main_layout.setContentsMargins(16, 16, 16, 16)

    # Create the two widgets
    burst_table  = BurstTable()
    metrics_view = MetricsView()

    main_layout.addWidget(burst_table)
    main_layout.addWidget(metrics_view)

    # Feed in fake data to simulate a tick from the engine
    fake_snapshot = [
        {"pid": "P1", "burst": 8,  "remaining": 3,  "state": "Running"},
        {"pid": "P2", "burst": 5,  "remaining": 5,  "state": "Ready"},
        {"pid": "P3", "burst": 4,  "remaining": 0,  "state": "Finished"},
        {"pid": "P4", "burst": 10, "remaining": 10, "state": "Ready"},
    ]
    burst_table.update_state(fake_snapshot)

    # Show partial metrics (as if P3 just finished)
    metrics_view.update(avg_waiting=2.0, avg_turnaround=6.0)

    window.show()
    sys.exit(app.exec())