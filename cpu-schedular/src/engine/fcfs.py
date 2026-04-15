# deepcopy -> copy nested dict/list structures safely so we do not mutate caller data
from copy import deepcopy
# typing imports -> improve readability and static checking
from typing import List

from .models import AlgorithmRunTuple, GanttTuple, ProcessInput


# =============================================================================
# fcfs.py
# -----------------------------------------------------------------------------
# Pure FCFS engine module (no GUI code).
#
# Input format:
#   processes = [{"pid": "P1", "arrival": 0, "burst": 5, "priority": None}, ...]
#
# Output (run_fcfs_static):
#   - gantt_log: list[(pid, start, end)]
#   - results:   list[dict] with per-process metrics
#   - avg_waiting, avg_turnaround
# =============================================================================


def run_fcfs_static(processes: List[ProcessInput]) -> AlgorithmRunTuple:
    """
    Execute FCFS in static (instant) mode.
    Returns:
      (gantt_log, results, avg_waiting, avg_turnaround)
    """
    # Make a full copy of input so original UI/engine list stays unchanged.
    procs = deepcopy(processes)
    # FCFS order = earliest arrival first, then PID for deterministic ties.
    procs.sort(key=lambda x: (x["arrival"], x["pid"]))

    # Current simulation time.
    t = 0
    # Gantt timeline as tuples: (pid, start_time, end_time).
    gantt_log: List[GanttTuple] = []
    # Per-process final metrics.
    results = []

    # Iterate processes in FCFS order and run each one to completion.
    for p in procs:
        # If CPU time is behind the next arrival, CPU is idle for that gap.
        if t < p["arrival"]:
            # CPU idle until next arrival.
            gantt_log.append(("IDLE", t, p["arrival"]))
            # Jump current time forward to arrival instant.
            t = p["arrival"]

        # Process starts immediately at current simulation time.
        start = t
        # FCFS non-preemptive: process runs for full burst.
        end = t + p["burst"]
        # Add execution block to Gantt timeline.
        gantt_log.append((p["pid"], start, end))
        # Move global time to process finish.
        t = end

        # Turnaround = finish - arrival
        turnaround = end - p["arrival"]
        # Waiting = turnaround - burst
        waiting = turnaround - p["burst"]

        # Store final per-process metrics in unified shape.
        results.append(
            {
                "pid": p["pid"],
                "arrival": p["arrival"],
                "burst": p["burst"],
                "priority": p.get("priority"),
                "completion": end,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )

    # Average waiting over all processes.
    avg_waiting = sum(r["waiting"] for r in results) / len(results)
    # Average turnaround over all processes.
    avg_turnaround = sum(r["turnaround"] for r in results) / len(results)

    # Return everything needed by simulation.py/UI:
    # timeline + per-process stats + global averages.
    return gantt_log, results, avg_waiting, avg_turnaround