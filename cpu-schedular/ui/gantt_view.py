# =============================================================================
# TEAM CONTRACT — READ BEFORE MODIFYING
# -----------------------------------------------------------------------------
# THIS WIDGET ONLY DRAWS TIMELINE SEGMENTS; IT DOES NOT SCHEDULE PROCESSES.
#
# DATA FLOW (actual codebase):
#   - Batch: main_window passes merged timeline blocks from static_run result.
#   - Live:  main_window replays snapshot["timeline"] each tick via add_block().
#
# ENGINE / SNAPSHOT RULES (simulation.py):
#   - Timeline entries are { "pid": str, "start": int, "end": int }.
#   - Idle CPU uses pid == "IDLE" in those blocks.
#   - Live mode advances in whole time units; tick_seconds defaults to 1s real time.
#
# IMPORTANT FOR TEAMMATES:
#   - Do NOT call paintEvent() manually — use update() after mutating blocks.
#   - Do not mutate _blocks from outside except via reset() / add_block().
#   - Scheduling logic stays in engine; this file only visualizes (pid, start, end).
#
# IF YOU CHANGE TIMELINE SHAPE IN MODELS/SIMULATION → UPDATE main_window + THIS FILE.
#
# =============================================================================


# =============================================================================
# gantt_view.py
# -----------------------------------------------------------------------------
# This file is responsible for the Gantt Chart visualization of the CPU
# scheduling simulation.
#
# The Gantt chart shows:
#   - Which process is running at each time unit
#   - The execution timeline visually (like a horizontal bar chart)
#
# Each block in the chart represents:
#   (Process ID, Start Time, End Time)
#
# -----------------------------------------------------------------------------
# HOW IT CONNECTS TO THE REST OF THE PROJECT:
#
#   - The Simulation engine calls:
#         gantt.add_block(pid, start, end)
#
#   - This happens every tick (1 second in live mode)
#
#   - The GanttChart DOES NOT decide scheduling logic.
#     It ONLY displays what the engine tells it.
#
#   - The Main Window (main_window.py) connects:
#         engine.tick() → gantt.add_block(...)
#
# -----------------------------------------------------------------------------
# DESIGN NOTES:
#
#   - If the SAME process continues running:
#         → we EXTEND the previous block (no new block created)
#
#   - If a DIFFERENT process starts:
#         → we create a NEW block
#
#   - This keeps the chart clean and readable.
#
# =============================================================================

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QRect


# =============================================================================
# GanttChart Widget
# =============================================================================

class GanttChart(QWidget):
    """
    A custom widget that draws the CPU execution timeline.

    Internally stores a list of blocks:
        [(pid, start_time, end_time)]

    Example:
        [("P1", 0, 2), ("P2", 2, 4), ("P1", 4, 5)]

    Each block is drawn as a colored rectangle.
    """

    def __init__(self, parent=None):
        """
        Constructor: initializes internal storage and visual settings.
        """
        super().__init__(parent)

        # List of execution segments (the Gantt data)
        self.gantt = []

        # Width of ONE time unit (controls horizontal scaling)
        self.unit_width = 40

        # Height of each block
        self.block_height = 40

    # -------------------------------------------------------------------------
    def add_block(self, pid: str, start: int, end: int):
        """
        Adds a new execution block OR extends the previous one.

        Args:
            pid   : Process ID (e.g., "P1" or "IDLE")
            start : Start time of execution
            end   : End time of execution

        Behavior:
            - If the last block has the SAME pid → extend it
            - Otherwise → create a new block

        IMPORTANT:
            This function assumes time is continuous and increasing.
        """

        # If last block exists AND same process → extend it
        if self.gantt and self.gantt[-1][0] == pid:
            last_pid, last_start, _ = self.gantt[-1]
            self.gantt[-1] = (last_pid, last_start, end)

        else:
            # Create a new block
            self.gantt.append((pid, start, end))

        # Trigger repaint of the widget
        self.update()

    # -------------------------------------------------------------------------
    def reset(self):
        """
        Clears the entire Gantt chart.

        Used when user presses "Reset".
        """
        self.gantt.clear()
        self.update()

    # -------------------------------------------------------------------------
    def paintEvent(self, event):
        """
        Automatically called by Qt when the widget needs to redraw.

        This function:
            - Loops over all stored blocks
            - Converts time → pixel position
            - Draws rectangles + labels
        """
        painter = QPainter(self)

        # Vertical position of the chart
        y = 50

        # Loop through all execution segments
        for pid, start, end in self.gantt:

            # Convert time → pixel position
            x = start * self.unit_width
            width = (end - start) * self.unit_width

            # Generate consistent color per process
            color = QColor(hash(pid) % 255, 150, 200)

            # Draw filled rectangle
            painter.fillRect(QRect(x, y, width, self.block_height), color)

            # Draw border
            painter.drawRect(QRect(x, y, width, self.block_height))

            # Draw process label inside block
            painter.drawText(x + 5, y + 25, str(pid))