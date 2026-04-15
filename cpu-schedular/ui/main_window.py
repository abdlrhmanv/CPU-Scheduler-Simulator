"""
Main window: input panel, controls, Gantt chart, burst table, metrics.
Uses engine.simulation static_run / start_live / pause / resume / stop_live / add_process.
Worker thread callbacks are bridged to the GUI thread via Qt signals.
"""
# Module docstring: summarizes responsibilities and threading model (signals for live ticks).

from __future__ import annotations
# Deferred annotation evaluation for forward references and cleaner class bodies.

from typing import Any, Dict, List, Optional, Tuple, cast
# Any: loose typing for snapshot dicts from engine; Dict/List for structured data.

from PySide6.QtCore import QObject, Signal
# QObject: base for tick bridge carrying cross-thread signals; Signal: Qt typed signal declarations.

from PySide6.QtWidgets import (
    QDialog,  # Modal dialog for “Add process” form in live mode.
    QFormLayout,  # Label–field rows in the add-process dialog.
    QHBoxLayout,  # Horizontal layouts for toolbar and Gantt vs right column.
    QLineEdit,  # Text fields for PID, burst, priority in dialog.
    QMainWindow,  # Standard main window with menu area and central widget.
    QMessageBox,  # Modal warnings/errors for validation and engine exceptions.
    QPushButton,  # Start, Pause, Resume, Add process, Reset, dialog OK/Cancel.
    QVBoxLayout,  # Vertical stack for central layout and right column.
    QWidget,  # Container for central widget and child layouts.
)

from engine import simulation as sim
from engine.models import ProcessInput
# Engine API: static_run (batch), start_live/stop_live/pause/resume/add_process (live).

from .burst_table import BurstTable, MetricsView
# BurstTable: remaining-burst grid; MetricsView: average WT/TAT display.

from .gantt_view import GanttChart
# Custom widget painting Gantt timeline blocks.

from .input_panel import InputPanel
# Algorithm/mode/quantum/process table widget.


class TickBridge(QObject):
    """Thread-safe bridge: engine callbacks may emit from background thread."""

    tick = Signal(object)  # Emitted each live tick with snapshot dict (any type for flexibility).
    finish = Signal(object)  # Emitted when live simulation ends with final result dict.


def _burst_rows_from_snapshot(snap: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map engine live snapshot to BurstTable.update_state rows (Ready/Running/Finished/Waiting)."""
    t = int(snap["current_time"])  # Simulation clock at this tick.
    running_pid: Optional[str] = None  # PID on CPU at end of timeline at time t, if any.
    tl = snap.get("timeline") or []  # List of Gantt segments; may be empty early on.
    if tl:  # Inspect last block to see who is running at current time.
        b = tl[-1]  # Last segment (most recent CPU assignment).
        if b["end"] == t and b["pid"] != "IDLE":  # Segment ends “now” and is not idle gap.
            running_pid = str(b["pid"])  # That process is running at snapshot time.
    rows: List[Dict[str, Any]] = []  # Rows for BurstTable.update_state.
    for p in snap["processes"]:  # Each process state from engine snapshot.
        pid = str(p["pid"])  # Normalize PID to string for comparison/display.
        if int(p["remaining"]) == 0:  # No burst left → finished.
            st = "Finished"
        elif running_pid is not None and pid == running_pid:  # Matches CPU holder.
            st = "Running"
        elif int(p["arrival"]) <= t:  # Arrived but not necessarily on CPU → ready queue.
            st = "Ready"
        else:  # Not yet arrived.
            st = "Waiting"
        rows.append(
            {
                "pid": pid,  # Process id.
                "burst": int(p["burst"]),  # Original total burst (for display).
                "remaining": int(p["remaining"]),  # Remaining CPU time.
                "state": st,  # One of Finished / Running / Ready / Waiting.
            }
        )
    return rows  # List of dicts consumed by BurstTable.


def _partial_metrics(snap: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Average waiting / turnaround over finished processes only (live)."""
    wts: List[int] = []  # Waiting times for completed processes at this tick.
    tats: List[int] = []  # Turnaround times for same subset.
    for p in snap["processes"]:  # Scan all processes in snapshot.
        if int(p["remaining"]) != 0:  # Skip not-yet-finished.
            continue
        c = p.get("completion")  # Completion time; may be missing if engine omits it.
        if c is None:  # Cannot compute metrics without completion stamp.
            continue
        ta = int(c) - int(p["arrival"])  # Turnaround = completion − arrival.
        wt = ta - int(p["burst"])  # Waiting = turnaround − burst (non-preemptive-style identity).
        wts.append(wt)  # Collect for averaging.
        tats.append(ta)
    if not wts:  # No finished processes yet → no partial averages.
        return None, None
    return sum(wts) / len(wts), sum(tats) / len(tats)  # Simple arithmetic means.


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()  # Construct QMainWindow base.
        self.setWindowTitle("CPU Scheduler")  # Window title bar text.
        self.resize(1000, 720)  # Initial pixel size (width × height).

        self._bridge = TickBridge()  # QObject living in GUI thread; receives cross-thread emits.
        self._bridge.tick.connect(self._slot_tick)  # Route live snapshots to UI update slot.
        self._bridge.finish.connect(self._slot_finish)  # Route completion to final metrics + button state.

        self._input = InputPanel()  # Top: algorithm, mode, table, quantum.
        self._gantt = GanttChart()  # Middle-left: timeline visualization.
        self._burst = BurstTable()  # Middle-right top: process states and bursts.
        self._metrics = MetricsView()  # Middle-right bottom: avg WT / TAT.

        central = QWidget()  # Central widget holds all custom child widgets.
        layout = QVBoxLayout(central)  # Vertical: toolbar, input, then Gantt+side.

        bar = QHBoxLayout()  # Control buttons row.
        self._btn_start = QPushButton("Start")  # Begin batch or live run from table data.
        self._btn_pause = QPushButton("Pause")  # Pause live simulation (engine thread).
        self._btn_resume = QPushButton("Resume")  # Resume after pause.
        self._btn_add = QPushButton("Add process (live)")  # Dynamic arrival in live mode only.
        self._btn_reset = QPushButton("Reset")  # Stop live and clear views.
        self._btn_pause.setEnabled(False)  # Disabled until live run starts.
        self._btn_resume.setEnabled(False)  # Disabled until paused (optional UX).
        self._btn_add.setEnabled(False)  # Only meaningful during live simulation.

        self._btn_start.clicked.connect(self._on_start)  # Validates input and dispatches batch/live.
        self._btn_pause.clicked.connect(sim.pause)  # Direct engine call (thread-safe in sim module).
        self._btn_resume.clicked.connect(sim.resume)  # Resume live loop.
        self._btn_add.clicked.connect(self._on_add_process)  # Opens dialog then sim.add_process.
        self._btn_reset.clicked.connect(self._on_reset)  # stop_live + clear UI.

        for b in (
            self._btn_start,
            self._btn_pause,
            self._btn_resume,
            self._btn_add,
            self._btn_reset,
        ):
            bar.addWidget(b)  # Add each control button left-to-right.
        bar.addStretch()  # Push button group to the left.
        layout.addLayout(bar)  # Toolbar at top of central layout.

        layout.addWidget(self._input)  # Full-width input panel below toolbar.

        mid = QHBoxLayout()  # Split: Gantt (wide) vs burst+metrics (narrower).
        mid.addWidget(self._gantt, stretch=2)  # Gantt gets 2/(2+1) of horizontal space.
        right = QVBoxLayout()  # Stack burst table above metrics in right column.
        right.addWidget(self._burst)  # Upper right.
        right.addWidget(self._metrics)  # Lower right.
        mid.addLayout(right, stretch=1)  # Right column gets stretch=1.
        layout.addLayout(mid, stretch=1)  # Middle row expands vertically.

        self.setCentralWidget(central)  # Attach composed widget to QMainWindow.

    def _on_start(self) -> None:
        try:
            procs = cast(List[ProcessInput], self._input.collect_processes())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid input", str(e))  # Show validation message.
            return  # Abort start.

        algo = self._input.algorithm_key()  # Scheduler key string for engine.
        mode = self._input.mode_key()  # "batch" or "live".
        cfg = {"quantum": self._input.quantum_value(), "tick_seconds": 1.0}  # Engine config: slice + live tick length.

        self._gantt.reset()  # Clear previous Gantt drawing.
        self._burst.reset()  # Clear burst table state.
        self._metrics.reset()  # Clear metric labels.

        if mode == "batch":  # Instant full run, no timer.
            try:
                result = sim.static_run(procs, algo, cfg)  # Synchronous; returns timeline + averages.
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))  # Engine/runtime error.
                return
            for b in result["timeline"]:  # Each Gantt segment from static result.
                self._gantt.add_block(b["pid"], b["start"], b["end"])  # Paint one bar.
            rows = [
                {
                    "pid": str(sp.get("pid", "")),
                    "burst": int(sp.get("burst", 0)),
                    "remaining": 0,
                    "state": "Finished",
                }
                for sp in (cast(Dict[str, Any], s) for s in result["process_stats"])
            ]
            self._burst.update_state(rows)  # Fill burst table with final states.
            self._metrics.set_final(
                result["avg_waiting_time"],
                result["avg_turnaround_time"],
            )  # Show definitive averages.
            return  # Batch path done; do not start live thread.

        try:
            sim.start_live(
                procs,
                algo,
                config=cfg,
                on_tick=lambda s: self._bridge.tick.emit(s),  # Forward snapshots to GUI thread via signal.
                on_finish=lambda r: self._bridge.finish.emit(r),  # Forward final result dict.
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))  # Failed to start worker.
            return

        self._btn_pause.setEnabled(True)  # Live controls become active.
        self._btn_resume.setEnabled(True)  # User can pause/resume immediately.
        self._btn_add.setEnabled(True)  # Allow dynamic process add.
        self._btn_start.setEnabled(False)  # Prevent double-start until reset/finish.

    def _slot_tick(self, snap: object) -> None:
        if not isinstance(snap, dict):  # Defensive: ignore malformed callbacks.
            return
        self._gantt.reset()  # Rebuild Gantt from full prefix each tick (simplest consistency).
        for b in snap.get("timeline") or []:  # Every segment so far in live run.
            self._gantt.add_block(b["pid"], b["start"], b["end"])  # Append visual blocks.
        self._burst.update_state(_burst_rows_from_snapshot(snap))  # Map snapshot to table rows.
        aw, at = _partial_metrics(snap)  # Running averages over finished processes only.
        if aw is not None and at is not None:  # Update only when at least one finished.
            self._metrics.update_metrics(aw, at)  # Show partial averages during live run.

    def _slot_finish(self, result: object) -> None:
        if not isinstance(result, dict):  # Ignore bad finish payloads.
            return
        self._metrics.set_final(
            float(result["avg_waiting_time"]),
            float(result["avg_turnaround_time"]),
        )  # Final averages from completed simulation.
        self._btn_pause.setEnabled(False)  # Live session over.
        self._btn_resume.setEnabled(False)
        self._btn_add.setEnabled(False)  # No more adds after finish.
        self._btn_start.setEnabled(True)  # Allow new run.

    def _on_reset(self) -> None:
        sim.stop_live()  # Signal engine to stop worker thread / timers.
        self._gantt.reset()  # Clear chart.
        self._burst.reset()  # Clear table.
        self._metrics.reset()  # Clear metrics.
        self._btn_start.setEnabled(True)  # Ready to start again.
        self._btn_pause.setEnabled(False)  # Reset live-only buttons.
        self._btn_resume.setEnabled(False)
        self._btn_add.setEnabled(False)

    def _on_add_process(self) -> None:
        d = QDialog(self)  # Modal dialog; blocks main window until closed.
        d.setWindowTitle("Add process")  # Dialog title.
        form = QFormLayout(d)  # Two-column label + field layout.
        e_pid = QLineEdit()  # User types new PID.
        e_burst = QLineEdit()  # User types burst length.
        e_pr = QLineEdit()  # Priority field; used only for priority algorithms.
        form.addRow("PID:", e_pid)  # First row.
        form.addRow("Burst:", e_burst)  # Second row.
        algo = self._input.algorithm_key()  # Current scheduler from main panel.
        need_p = algo in ("priority_np", "priority_p")  # Whether priority is required.
        if need_p:
            form.addRow("Priority (smaller = higher):", e_pr)  # Explain convention to user.
        row = QHBoxLayout()  # Button row inside form.
        ok = QPushButton("Add")  # Accept dialog.
        cancel = QPushButton("Cancel")  # Reject dialog.
        row.addWidget(ok)  # OK left.
        row.addWidget(cancel)  # Cancel right.
        form.addRow(row)  # Span row for buttons (Qt places under last fields).
        ok.clicked.connect(d.accept)  # QDialog.Accepted on OK.
        cancel.clicked.connect(d.reject)  # QDialog.Rejected on Cancel.

        if d.exec() != QDialog.DialogCode.Accepted:  # User cancelled.
            return

        pid = e_pid.text().strip()  # Normalize PID string.
        if not pid:  # Empty PID invalid.
            QMessageBox.warning(self, "Invalid", "PID is required.")
            return
        try:
            burst = int(e_burst.text())  # Parse burst integer.
            if burst <= 0:  # Must be positive.
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid", "Burst must be a positive integer.")
            return

        proc: Dict[str, Any] = {"pid": pid, "burst": burst}  # arrival defaults in engine.add_process.
        if need_p:  # Attach priority if algorithm needs it.
            try:
                proc["priority"] = int(e_pr.text())  # Parse priority.
            except ValueError:
                QMessageBox.warning(self, "Invalid", "Priority must be an integer.")
                return

        try:
            sim.add_process(proc)  # Engine adds at “current” simulation time in live mode.
        except Exception as e:
            QMessageBox.warning(self, "Cannot add process", str(e))  # Duplicate PID, wrong mode, etc.
