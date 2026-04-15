# deepcopy -> protects caller input from in-place mutations during simulation
from copy import deepcopy
# typing imports -> clearer contracts for inputs/outputs
from typing import List

from .models import AlgorithmRunTuple, GanttTuple, ProcessInput


# =============================================================================
# sjf.py
# -----------------------------------------------------------------------------
# Pure SJF engine module (no GUI code).
#
# Exposes:
#   - sjf_non_preemptive(processes)
#   - sjf_preemptive(processes)   # SRTF
#
# Input format:
#   processes = [{"pid": "P1", "arrival": 0, "burst": 5, ...}, ...]
# =============================================================================


def sjf_non_preemptive(processes: List[ProcessInput]) -> AlgorithmRunTuple:

    """
    processes: list of dicts, each with:
        - pid      : process name/id
        - arrival  : arrival time
        - burst    : burst time
    returns: (gantt_log, results)
        - gantt_log : list of (pid, start_time, end_time)
        - results   : list of dicts with pid, waiting, turnaround
    """

    # Make a deep copy so original process list remains unchanged.
    procs = deepcopy(processes)
    # Number of processes.
    n = len(procs)
    # done[i] tells whether process i has finished execution.
    done = [False] * n
    # Gantt blocks as (pid, start, end).
    gantt_log: List[GanttTuple] = []
    # Current simulation time.
    t = 0
    # Counter for finished processes.
    completed = 0

    # Continue until every process is completed.
    while completed < n:
        # collect (index, process) for arrived & unfinished processes
        available = [
            (i, procs[i]) for i in range(n)
            if (not done[i]) and procs[i]["arrival"] <= t
        ]

        # If nothing is ready, CPU stays idle for one time unit.
        if not available:
            t += 1  # CPU is idle, jump forward
            continue

        # pick shortest burst, then earliest arrival, then lower PID for stability
        idx, chosen = min(
            available,
            key=lambda item: (item[1]["burst"], item[1]["arrival"], str(item[1]["pid"]))
        )

        # Non-preemptive SJF: once selected, run chosen process to completion.
        start = t
        end = t + chosen["burst"]
        # Add one block to the timeline for this full run.
        gantt_log.append((chosen["pid"], start, end))

        # Keep optional internal timing fields in process object.
        chosen["start"]      = start
        chosen["finish"]     = end
        # Turnaround = finish - arrival.
        chosen["turnaround"] = end - chosen["arrival"]
        # Waiting = turnaround - burst.
        chosen["waiting"]    = chosen["turnaround"] - chosen["burst"]

        # Move global time to completion point.
        t = end
        # Mark that process index as completed.
        done[idx] = True
        # Increment completed counter.
        completed += 1

    # Build normalized lightweight results list.
    results = [
        {
            "pid": p["pid"],
            "waiting": p["waiting"],
            "turnaround": p["turnaround"],
        }
        for p in procs
    ]

    # Compute overall averages required by project output.
    avg_waiting    = sum(r["waiting"]    for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n

    # Return timeline + per-process metrics + averages.
    return gantt_log, results, avg_waiting, avg_turnaround


def sjf_preemptive(processes: List[ProcessInput]) -> AlgorithmRunTuple:
    """
    Preemptive SJF = Shortest Remaining Time First (SRTF).
    Same input format as above.
    """

    # Deep copy input so we can update remaining time safely.
    procs = deepcopy(processes)
    # Initialize runtime fields for each process.
    for p in procs:
        # In SRTF, remaining starts equal to full burst.
        p["remaining"]  = p["burst"]
        # Placeholder finish time (set when remaining reaches zero).
        p["finish"]     = 0
        # Placeholder metrics initialized to zero.
        p["waiting"]    = 0
        p["turnaround"] = 0

    # Number of processes.
    n = len(procs)
    # done[i] indicates process i has fully completed.
    done = [False] * n
    # Gantt blocks as (pid, start, end).
    gantt_log: List[GanttTuple] = []
    # Current simulation time.
    t = 0
    # Number of fully completed processes.
    completed = 0

    # Loop until all processes finish.
    while completed < n:
        # Ready set at current time: arrived and not completed.
        available = [
            (i, procs[i]) for i in range(n)
            if (not done[i]) and procs[i]["arrival"] <= t
        ]

        # If no ready process, CPU idles for one unit.
        if not available:
            t += 1
            continue

        # pick the process with the shortest REMAINING time
        idx, chosen = min(
            available,
            key=lambda item: (item[1]["remaining"], item[1]["arrival"], str(item[1]["pid"]))
        )

        # Preemptive SJF/SRTF: execute only one time unit, then re-evaluate.
        chosen["remaining"] -= 1
        # Advance time by exactly one unit.
        t += 1

        # add to gantt (merge with previous block if same process)
        if gantt_log and gantt_log[-1][0] == chosen["pid"]:
            # Extend previous block to avoid fragmented timeline.
            gantt_log[-1] = (chosen["pid"], gantt_log[-1][1], t)
        else:
            # Start a new block for this tick.
            gantt_log.append((chosen["pid"], t - 1, t))

        # check if process finished
        if chosen["remaining"] == 0:
            # Completion happens at current time t.
            chosen["finish"]     = t
            # Turnaround = finish - arrival.
            chosen["turnaround"] = t - chosen["arrival"]
            # Waiting = turnaround - original burst.
            chosen["waiting"]    = chosen["turnaround"] - chosen["burst"]
            # Mark process done and increase completed count.
            done[idx] = True
            completed += 1

    # Build compact result list expected by simulation.py.
    results = [
        {
            "pid": p["pid"],
            "waiting": p["waiting"],
            "turnaround": p["turnaround"],
        }
        for p in procs
    ]

    # Compute averages required by outputs.
    avg_waiting    = sum(r["waiting"]    for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n

    # Return timeline + process metrics + averages.
    return gantt_log, results, avg_waiting, avg_turnaround