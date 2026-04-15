# deque -> efficient O(1) queue operations from both ends (perfect for RR ready queue)
from collections import deque
# deepcopy -> keeps caller's data intact while we mutate runtime fields
from copy import deepcopy
# typing imports -> clearer signatures and easier static analysis
from typing import Any, Deque, Dict, List, cast

from .models import AlgorithmRunTuple, GanttTuple, ProcessInput


# =============================================================================
# round_robin.py
# -----------------------------------------------------------------------------
# Pure Round Robin engine module (no GUI, no global runtime state).
#
# Input format:
#   processes = [{"pid": "P1", "arrival": 0, "burst": 5, "priority": None}, ...]
#   quantum   = integer time slice (> 0)
#
# Output:
#   (gantt_log, results, avg_waiting, avg_turnaround)
# =============================================================================


def run_round_robin_static(processes: List[ProcessInput], quantum: int) -> AlgorithmRunTuple:
    """
    Execute Round Robin in static mode (instant computation).

    Returns:
      - gantt_log: list[(pid, start, end)]
      - results: list[dict] with pid, waiting, turnaround
      - avg_waiting: float
      - avg_turnaround: float
    """
    # Validate quantum: RR requires a positive integer time slice.
    if not isinstance(quantum, int) or quantum <= 0:
        raise ValueError("quantum must be an integer > 0")

    # Copy input processes so we can safely add runtime fields (not on ProcessInput TypedDict).
    procs: List[Dict[str, Any]] = cast(List[Dict[str, Any]], deepcopy(processes))
    # Total number of processes.
    n = len(procs)
    # Empty process list is invalid for scheduler execution.
    if n == 0:
        raise ValueError("processes must be non-empty")

    # Prepare runtime fields.
    for p in procs:
        # Remaining CPU time starts equal to original burst.
        p["remaining"] = p["burst"]
        # Completion time is unknown until process fully finishes.
        p["completion"] = None

    # Deterministic process order for stable behavior with same arrival.
    # enumerate keeps original index so we can refer back to procs list.
    indexed = list(enumerate(procs))
    # Stable tie-breaking:
    #   1) earlier arrival
    #   2) lexicographically smaller PID
    #   3) original index
    indexed.sort(key=lambda item: (item[1]["arrival"], str(item[1]["pid"]), item[0]))

    # Ready queue stores process indices (not process dicts) for safe updates.
    ready_queue: Deque[int] = deque()
    # Gantt timeline blocks -> (pid, start_time, end_time).
    gantt_log: List[GanttTuple] = []
    # Current simulation time.
    t = 0
    # Points to next process in indexed list that has not been enqueued yet.
    next_arrival_ptr = 0
    # Number of completed processes.
    completed = 0

    def enqueue_arrived(now: int) -> None:
        # We update outer pointer variable from inner helper function.
        nonlocal next_arrival_ptr
        # Push every process that has arrival <= current time into ready queue.
        while next_arrival_ptr < n and indexed[next_arrival_ptr][1]["arrival"] <= now:
            # Store original process index.
            ready_queue.append(indexed[next_arrival_ptr][0])
            # Move pointer to the next not-yet-considered arrival.
            next_arrival_ptr += 1

    # Prime queue with arrivals at time 0.
    enqueue_arrived(t)

    # Main RR loop: stop only when all processes are completed.
    while completed < n:
        if not ready_queue:
            # CPU idle until next process arrival.
            # next_arrival_ptr is safe here because completed < n means some process remains.
            next_arrival_time = indexed[next_arrival_ptr][1]["arrival"]
            if t < next_arrival_time:
                # Record explicit idle interval in Gantt chart.
                gantt_log.append(("IDLE", t, next_arrival_time))
            # Jump time to first future arrival.
            t = next_arrival_time
            # Enqueue whatever has now arrived at this new time.
            enqueue_arrived(t)
            continue

        # Take next process in RR order.
        idx = ready_queue.popleft()
        # Direct reference to process runtime dict.
        proc = procs[idx]

        # Process can run at most quantum, or less if it will finish earlier.
        run_time = min(quantum, proc["remaining"])
        # Start/end window for this CPU slice.
        start = t
        end = t + run_time
        # Consume CPU time from remaining burst.
        proc["remaining"] -= run_time
        # Advance global simulation clock.
        t = end

        # Merge with previous block if same PID is contiguous.
        if gantt_log and gantt_log[-1][0] == proc["pid"] and gantt_log[-1][2] == start:
            # Extend previous block instead of adding a tiny fragment.
            gantt_log[-1] = (proc["pid"], gantt_log[-1][1], end)
        else:
            # Create a new timeline block for this run slice.
            gantt_log.append((proc["pid"], start, end))

        # Enqueue newly arrived processes during this time slice.
        enqueue_arrived(t)

        # If process finished, record completion and update count.
        if proc["remaining"] == 0:
            proc["completion"] = t
            completed += 1
        else:
            # Not finished -> goes back to end of queue.
            ready_queue.append(idx)

    # Build final per-process metrics in the same shape used by other engines.
    results = []
    for p in procs:
        # Turnaround = completion - arrival.
        turnaround = p["completion"] - p["arrival"]
        # Waiting = turnaround - burst.
        waiting = turnaround - p["burst"]
        results.append(
            {
                "pid": p["pid"],
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )

    # Global averages required in assignment outputs.
    avg_waiting = sum(r["waiting"] for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n
    # Return timeline + detailed results + averages.
    return gantt_log, results, avg_waiting, avg_turnaround