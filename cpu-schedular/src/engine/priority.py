# deque -> efficient O(1) queue operations for ready queues.
from collections import deque
# deepcopy -> lets us mutate runtime fields without touching caller input.
from copy import deepcopy
# typing imports -> clearer function contracts and maintainability.
from typing import Any, Deque, Dict, List, cast

from .models import AlgorithmRunTuple, GanttTuple, ProcessInput


def _require_priority(p: Dict[str, Any]) -> int:
    """Priority algorithms need an integer priority on every process."""
    pr = p.get("priority")
    if pr is None:
        raise ValueError("priority is required for priority scheduling")
    return pr


# =============================================================================
# priority.py
# -----------------------------------------------------------------------------
# Pure Priority scheduling engine module (no GUI code).
#
# Priority rule:
#   - Smaller priority number = higher priority.
#
# Exposes:
#   - priority_non_preemptive(processes, quantum=2)
#   - priority_preemptive(processes, quantum=2)
#
# Note:
#   - In non-preemptive mode, quantum is kept for API compatibility only.
#   - In preemptive mode, processes with the same priority are rotated RR-style
#     using the provided quantum.
# =============================================================================


def priority_non_preemptive(processes: List[ProcessInput], quantum: int = 2) -> AlgorithmRunTuple:
    """
    Priority non-preemptive scheduler.
    Chooses highest priority among arrived jobs, then runs selected process
    to completion. Ties are broken deterministically by arrival then PID.
    """
    # Non-preemptive mode does not use quantum, kept only to preserve API.
    _ = quantum

    # Copy input list so metric/runtime fields don't leak to caller data.
    # Mutable dicts (extra keys) are typed loosely so the checker allows runtime fields.
    procs: List[Dict[str, Any]] = cast(List[Dict[str, Any]], deepcopy(processes))
    # Total process count.
    n = len(procs)
    # Guard against invalid empty run.
    if n == 0:
        raise ValueError("processes must be non-empty")

    # done[i] = process at index i has completed.
    done = [False] * n
    # Timeline blocks -> (pid, start, end).
    gantt_log: List[GanttTuple] = []
    # Current simulation clock.
    t = 0
    # Completed process counter.
    completed = 0

    # Run until all processes are finished.
    while completed < n:
        # Build ready set: arrived and not done processes.
        available = [
            (i, procs[i])
            for i in range(n)
            if (not done[i]) and procs[i]["arrival"] <= t
        ]

        if not available:
            # CPU idle for one unit until a process arrives.
            t += 1
            continue

        # Highest priority first (smaller number), then earliest arrival, then PID.
        idx, chosen = min(
            available,
            key=lambda item: (
                _require_priority(item[1]),
                item[1]["arrival"],
                str(item[1]["pid"]),
            ),
        )

        # Selected process starts at current time.
        start = t
        # Non-preemptive: run selected process to completion.
        end = t + chosen["burst"]
        # Add one execution block to Gantt.
        gantt_log.append((chosen["pid"], start, end))

        # Store completion and derived metrics.
        chosen["finish"] = end
        chosen["turnaround"] = end - chosen["arrival"]
        chosen["waiting"] = chosen["turnaround"] - chosen["burst"]

        # Move time to process finish.
        t = end
        # Mark selected index as done.
        done[idx] = True
        # Increment completed count.
        completed += 1

    # Build final compact results for caller/UI.
    results = [
        {
            "pid": p["pid"],
            "waiting": p["waiting"],
            "turnaround": p["turnaround"],
        }
        for p in procs
    ]

    # Compute overall averages required by assignment outputs.
    avg_waiting = sum(r["waiting"] for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n
    # Return timeline + per-process metrics + averages.
    return gantt_log, results, avg_waiting, avg_turnaround


def priority_preemptive(processes: List[ProcessInput], quantum: int = 2) -> AlgorithmRunTuple:
    """
    Priority preemptive scheduler.
    - At each tick, highest-priority ready queue runs.
    - For equal priority, uses Round Robin with given quantum.
    """
    # Validate RR time slice used within same-priority queue.
    if not isinstance(quantum, int) or quantum <= 0:
        raise ValueError("quantum must be an integer > 0")

    # Copy input to safely mutate runtime fields.
    procs: List[Dict[str, Any]] = cast(List[Dict[str, Any]], deepcopy(processes))
    # Total process count.
    n = len(procs)
    # Guard against invalid empty run.
    if n == 0:
        raise ValueError("processes must be non-empty")

    # Initialize runtime fields for each process.
    for p in procs:
        # Remaining starts equal to full burst.
        p["remaining"] = p["burst"]
        # Finish is unknown until process completes.
        p["finish"] = None
        # Metrics placeholders.
        p["waiting"] = 0
        p["turnaround"] = 0

    # Sort arrivals once, then advance with pointer.
    arrivals = sorted(
        range(n),
        key=lambda i: (
            procs[i]["arrival"],
            _require_priority(procs[i]),
            str(procs[i]["pid"]),
            i,
        ),
    )
    # Points to next process in sorted-arrivals list not enqueued yet.
    next_arrival_ptr = 0

    # priority_value -> deque of process indices
    ready_queues: Dict[int, Deque[int]] = {}
    # Remaining RR slice for each active process index.
    slice_left: Dict[int, int] = {}

    # Timeline blocks -> (pid, start, end).
    gantt_log: List[GanttTuple] = []
    # Current simulation clock.
    t = 0
    # Completed process counter.
    completed = 0

    def enqueue_arrived(now: int) -> None:
        # We update outer pointer from inner helper.
        nonlocal next_arrival_ptr
        # Enqueue every process whose arrival <= current time.
        while next_arrival_ptr < n and procs[arrivals[next_arrival_ptr]]["arrival"] <= now:
            idx = arrivals[next_arrival_ptr]
            pr = _require_priority(procs[idx])
            # Put process in queue for its priority level.
            ready_queues.setdefault(pr, deque()).append(idx)
            # New/returned process gets fresh same-priority quantum budget.
            slice_left[idx] = quantum
            next_arrival_ptr += 1

    # Prime ready queues with arrivals at t=0.
    enqueue_arrived(t)

    # Run tick-by-tick until all processes complete.
    while completed < n:
        # Remove empty queues before selecting highest priority.
        empty_keys = [pr for pr, q in ready_queues.items() if not q]
        for pr in empty_keys:
            del ready_queues[pr]

        if not ready_queues:
            # CPU idle until next arrival.
            # Safe because completed < n means at least one arrival remains.
            next_t = procs[arrivals[next_arrival_ptr]]["arrival"]
            if t < next_t:
                # Record explicit idle block for visualization.
                gantt_log.append(("IDLE", t, next_t))
            # Jump to next arrival instant.
            t = next_t
            # Enqueue all processes that have now arrived.
            enqueue_arrived(t)
            continue

        # Select highest-priority non-empty queue (smaller number is higher).
        highest_priority = min(ready_queues.keys())
        queue = ready_queues[highest_priority]
        # RR within this priority: run queue head.
        idx = queue[0]
        chosen = procs[idx]

        # Execute one tick.
        chosen["remaining"] -= 1
        slice_left[idx] -= 1
        t += 1

        # Update Gantt, merging contiguous blocks of same PID.
        if gantt_log and gantt_log[-1][0] == chosen["pid"]:
            # Extend previous contiguous block.
            gantt_log[-1] = (chosen["pid"], gantt_log[-1][1], t)
        else:
            # Start a new one-tick block.
            gantt_log.append((chosen["pid"], t - 1, t))

        # Add processes that arrived at this new time.
        enqueue_arrived(t)

        if chosen["remaining"] == 0:
            # Finished process leaves queue permanently.
            queue.popleft()
            chosen["finish"] = t
            chosen["turnaround"] = t - chosen["arrival"]
            chosen["waiting"] = chosen["turnaround"] - chosen["burst"]
            completed += 1
            del slice_left[idx]
        elif slice_left[idx] == 0:
            # Quantum expired -> RR rotation inside same priority.
            queue.popleft()
            queue.append(idx)
            # Reset quantum budget for its next turn.
            slice_left[idx] = quantum

    # Build final compact results list.
    results = [
        {
            "pid": p["pid"],
            "waiting": p["waiting"],
            "turnaround": p["turnaround"],
        }
        for p in procs
    ]

    # Compute overall averages.
    avg_waiting = sum(r["waiting"] for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n
    # Return timeline + per-process metrics + averages.
    return gantt_log, results, avg_waiting, avg_turnaround