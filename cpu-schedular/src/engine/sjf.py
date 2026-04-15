def sjf_non_preemptive(processes):

    """
    processes: list of dicts, each with:
        - pid      : process name/id
        - arrival  : arrival time
        - burst    : burst time
    returns: (gantt_log, results)
        - gantt_log : list of (pid, start_time, end_time)
        - results   : list of dicts with pid, waiting, turnaround
    """

    # make a copy so we don't modify the original list (procs=processes point to the same data)
    procs = [p.copy() for p in processes]
    n = len(procs)
    done = [False] * n
    gantt_log = []
    t = 0  # current time
    completed = 0

    while completed < n:
        # get all processes that have arrived and are not done yet
        available = [
            procs[i] for i in range(n)
            if not done[i] and procs[i]["arrival"] <= t
        ]

        if not available:
            t += 1  # CPU is idle, jump forward
            continue

        # pick the one with the shortest burst time
        chosen = min(available, key=lambda p: p["burst"])
        idx = procs.index(chosen)

        # run it to completion
        start = t
        end = t + chosen["burst"]
        gantt_log.append((chosen["pid"], start, end))

        chosen["start"]      = start
        chosen["finish"]     = end
        chosen["turnaround"] = end - chosen["arrival"]
        chosen["waiting"]    = chosen["turnaround"] - chosen["burst"]

        t = end
        done[idx] = True
        completed += 1

    results = [{
        "pid":        p["pid"],
        "waiting":    p["waiting"],
        "turnaround": p["turnaround"]
    } for p in procs]

    avg_waiting    = sum(r["waiting"]    for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n

    return gantt_log, results, avg_waiting, avg_turnaround


def sjf_preemptive(processes):
    """
    Preemptive SJF = Shortest Remaining Time First (SRTF).
    Same input format as above.
    """

    procs = [p.copy() for p in processes]
    for p in procs:
        p["remaining"]  = p["burst"]
        p["finish"]     = 0
        p["waiting"]    = 0
        p["turnaround"] = 0

    n = len(procs)
    done = [False] * n
    gantt_log = []
    t = 0
    completed = 0

    while completed < n:
        available = [
            procs[i] for i in range(n)
            if not done[i] and procs[i]["arrival"] <= t
        ]

        if not available:
            t += 1
            continue

        # pick the process with the shortest REMAINING time
        chosen = min(available, key=lambda p: p["remaining"])

        # run for 1 unit of time
        chosen["remaining"] -= 1
        t += 1

        # add to gantt (merge with previous block if same process)
        if gantt_log and gantt_log[-1][0] == chosen["pid"]:
            gantt_log[-1] = (chosen["pid"], gantt_log[-1][1], t)
        else:
            gantt_log.append((chosen["pid"], t - 1, t))

        # check if process finished
        if chosen["remaining"] == 0:
            chosen["finish"]     = t
            chosen["turnaround"] = t - chosen["arrival"]
            chosen["waiting"]    = chosen["turnaround"] - chosen["burst"]
            idx = procs.index(chosen)
            done[idx] = True
            completed += 1

    results = [{
        "pid":        p["pid"],
        "waiting":    p["waiting"],
        "turnaround": p["turnaround"]
    } for p in procs]

    avg_waiting    = sum(r["waiting"]    for r in results) / n
    avg_turnaround = sum(r["turnaround"] for r in results) / n

    return gantt_log, results, avg_waiting, avg_turnaround