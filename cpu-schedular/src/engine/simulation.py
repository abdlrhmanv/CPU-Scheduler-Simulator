# deepcopy -> protects caller-owned data from in-place mutation.
from copy import deepcopy
# threading -> live simulation runs on a background worker thread.
import threading
# time -> used for real-time tick delay in live mode.
import time
# typing -> keeps function contracts explicit and easier to maintain.
from typing import Any, Dict, List, Optional, cast

# FCFS static engine function.
from .fcfs import run_fcfs_static
# Shared type contracts for engine/runtime payloads.
from .models import (
    LiveFinalResult,
    LiveTickSnapshot,
    ProcessInput,
    ProcessStats,
    StaticRunResult,
    TimelineBlock,
)
# Priority static engine functions (NP + P).
from .priority import priority_non_preemptive, priority_preemptive
# Round Robin static engine function.
from .round_robin import run_round_robin_static
# SJF static engine functions (NP + P/SRTF).
from .sjf import sjf_non_preemptive, sjf_preemptive


# =============================================================================
# simulation.py
# -----------------------------------------------------------------------------
# This file is the "runtime brain" for the scheduler project.
#
# It provides TWO modes:
#   1) static_run(...) -> compute full result instantly (no real-time delay).
#   2) start_live(...) -> run second-by-second simulation with pause/resume
#                         and dynamic add_process() while running.
#
# HOW IT CONNECTS TO THE REST OF THE PROJECT:
#   - UI sends input processes + selected algorithm to this file.
#   - In static mode, UI calls static_run() once and draws final outputs.
#   - In live mode, UI calls start_live(...):
#       * on_tick(snapshot) is fired every tick for live table/chart refresh.
#       * on_finish(result) is fired once when all processes are done.
# =============================================================================


# -------------------------
# Validation / Normalization
# -------------------------
def _validate_and_normalize_processes(processes: List[ProcessInput]) -> List[ProcessInput]:
    """
    Validate the initial list of processes and normalize data shape/types.
    Raises ValueError early if any required field is invalid.
    """
    if not isinstance(processes, list) or len(processes) == 0:
        raise ValueError("processes must be a non-empty list")

    normalized: List[ProcessInput] = []
    seen_pids = set()

    for i, p in enumerate(processes):
        if not isinstance(p, dict):
            raise ValueError(f"process at index {i} must be a dict")

        pid = p.get("pid")
        arrival = p.get("arrival")
        burst = p.get("burst")
        priority = p.get("priority")

        if pid is None or pid == "":
            raise ValueError(f"process at index {i} has invalid PID")
        pid = str(pid)

        if pid in seen_pids:
            raise ValueError(f"duplicate pid: {pid}")
        seen_pids.add(pid)

        if not isinstance(arrival, int) or arrival < 0:
            raise ValueError(f"process {pid}: arrival must be int >= 0")
        if not isinstance(burst, int) or burst <= 0:
            raise ValueError(f"process {pid}: burst must be int > 0")
        if priority is not None and (not isinstance(priority, int) or priority < 0):
            raise ValueError(f"process {pid}: priority must be int >= 0")

        normalized.append(
            {
                "pid": pid,
                "arrival": arrival,
                "burst": burst,
                "priority": priority,
            }
        )

    return normalized


def _validate_single_process(process: ProcessInput, *, allow_missing_arrival: bool = False) -> ProcessInput:
    """
    Validate one process object (used by add_process in live mode).
    If allow_missing_arrival=True, caller can omit arrival and we auto-assign it.
    """
    if not isinstance(process, dict):
        raise ValueError("process must be a dict")

    pid = process.get("pid")
    arrival = process.get("arrival")
    burst = process.get("burst")
    priority = process.get("priority")

    if pid is None or pid == "":
        raise ValueError("process has invalid PID")
    pid = str(pid)

    if not allow_missing_arrival:
        if not isinstance(arrival, int) or arrival < 0:
            raise ValueError(f"process {pid}: arrival must be int >= 0")

    if not isinstance(burst, int) or burst <= 0:
        raise ValueError(f"process {pid}: burst must be int > 0")
    if priority is not None and (not isinstance(priority, int) or priority < 0):
        raise ValueError(f"process {pid}: priority must be int >= 0")

    return {
        "pid": pid,
        "arrival": arrival if isinstance(arrival, int) else 0,
        "burst": burst,
        "priority": priority,
    }


# -------------------------
# Shared Helpers
# -------------------------
def _merge_gantt(gantt_log: List[tuple[str, int, int]]) -> List[TimelineBlock]:
    """
    Merge adjacent timeline blocks for cleaner chart rendering.
    Example:
      [("P1",0,1), ("P1",1,2)] -> [{"pid":"P1","start":0,"end":2}]
    """
    merged: List[TimelineBlock] = []
    for pid, start, end in gantt_log:
        if merged and merged[-1]["pid"] == pid and merged[-1]["end"] == start:
            merged[-1]["end"] = end
        else:
            merged.append({"pid": pid, "start": start, "end": end})
    return merged


def _compute_enriched_stats(
    processes: List[ProcessInput],
    basic_results: List[Dict[str, Any]],
) -> List[ProcessStats]:
    """
    Convert SJF basic results into the common output shape used by this module.
    basic_results from sjf.py -> {"pid", "waiting", "turnaround"}
    """
    by_pid = {r["pid"]: r for r in basic_results}
    stats: List[ProcessStats] = []

    for p in processes:
        pid = p["pid"]
        waiting = by_pid[pid]["waiting"]
        turnaround = by_pid[pid]["turnaround"]
        completion = p["arrival"] + turnaround

        stats.append(
            {
                "pid": pid,
                "arrival": p["arrival"],
                "burst": p["burst"],
                "priority": p.get("priority"),
                "completion": completion,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )
    return stats


# -------------------------
# Static Mode API
# -------------------------
def static_run(
    processes: List[ProcessInput],
    algorithm: str,
    config: Optional[Dict[str, Any]] = None,
) -> StaticRunResult:
    """
    Unified static scheduler entry point.
    algorithm:
      - "fcfs"
      - "sjf_np" | "sjf_p" | "sjf_preemptive" | "srtf"
      - "priority_np" | "priority_p"
      - "rr" | "round_robin"
    """
    # Normalize optional config dict so `.get(...)` is always safe.
    config = config or {}
    # Validate and normalize input process objects once at entry.
    procs = _validate_and_normalize_processes(processes)
    # Normalize algorithm selector to case-insensitive canonical form.
    algo = (algorithm or "").strip().lower()

    if algo == "fcfs":
        # FCFS already returns enriched process stats.
        gantt_log, stats, avg_w, avg_t = run_fcfs_static(procs)
    elif algo == "sjf_np":
        # SJF module returns basic stats -> enrich to common output shape.
        gantt_log, basic_results, avg_w, avg_t = sjf_non_preemptive(deepcopy(procs))
        stats = _compute_enriched_stats(procs, basic_results)
    elif algo in {"sjf_p", "sjf_preemptive", "srtf"}:
        # Preemptive SJF (SRTF) static path.
        gantt_log, basic_results, avg_w, avg_t = sjf_preemptive(deepcopy(procs))
        stats = _compute_enriched_stats(procs, basic_results)
    elif algo in {"priority_np", "priority_non_preemptive"}:
        # Priority non-preemptive static path.
        gantt_log, basic_results, avg_w, avg_t = priority_non_preemptive(deepcopy(procs))
        stats = _compute_enriched_stats(procs, basic_results)
    elif algo in {"priority_p", "priority_preemptive"}:
        # Shared quantum option for priority-preemptive same-priority RR.
        quantum = int(config.get("quantum", 2))
        gantt_log, basic_results, avg_w, avg_t = priority_preemptive(deepcopy(procs), quantum=quantum)
        stats = _compute_enriched_stats(procs, basic_results)
    elif algo in {"rr", "round_robin"}:
        # Round Robin requires a quantum from config (default=2).
        quantum = int(config.get("quantum", 2))
        gantt_log, basic_results, avg_w, avg_t = run_round_robin_static(deepcopy(procs), quantum=quantum)
        stats = _compute_enriched_stats(procs, basic_results)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    # merge tiny adjacent blocks for a cleaner UI timeline
    timeline = _merge_gantt(gantt_log)
    total_time = max((b["end"] for b in timeline), default=0)

    return cast(
        StaticRunResult,
        {
            "mode": "static",
            "algorithm": algo,
            "timeline": timeline,
            "process_stats": sorted(stats, key=lambda x: str(x.get("pid", ""))),
            "avg_waiting_time": avg_w,
            "avg_turnaround_time": avg_t,
            "total_time": total_time,
        },
    )


# -------------------------
# Live Mode Runtime State
# -------------------------
# Shared mutable state for the active live session.
# We keep it module-level so pause/resume/add_process can control the same run.
_live_lock = threading.Lock()
_live_thread: Optional[threading.Thread] = None
_live_state: Dict[str, Any] = {
    # Runtime lifecycle flags.
    "running": False,
    "paused": False,
    # Selected algorithm for current live run.
    "algorithm": None,
    # Real-world seconds per simulation tick.
    "tick_seconds": 1.0,
    # Simulation time unit counter.
    "current_time": 0,
    # Runtime process list (mutable).
    "processes": [],
    # Raw gantt timeline as (pid,start,end) blocks.
    "gantt_log": [],
    "current_pid": None,  # used by non-preemptive behavior
    "current_idx": None,  # used by RR/priority live scheduling
    # Quantum used by RR-style schedulers in live mode.
    "rr_quantum": 2,
    # Per-process remaining slice budget for RR behavior.
    "rr_slice_left": {},
    # RR ready queue (stores process indices).
    "rr_queue": [],
    # Priority queues: priority_value -> list of process indices.
    "priority_queues": {},
    # UI callbacks.
    "on_tick": None,
    "on_finish": None,
}


def _build_tick_snapshot() -> LiveTickSnapshot:
    """
    Build the payload sent to on_tick callback every second.
    """
    # Snapshot reads from the latest shared runtime state.
    procs = _live_state["processes"]
    return {
        "mode": "live",
        "algorithm": _live_state["algorithm"],
        "current_time": _live_state["current_time"],
        # Merge timeline for cleaner chart drawing in UI.
        "timeline": _merge_gantt(_live_state["gantt_log"]),
        "processes": [
            {
                "pid": p["pid"],
                "arrival": p["arrival"],
                "burst": p["burst"],
                "priority": p.get("priority"),
                "remaining": p["remaining"],
                "completion": p.get("completion"),
                "state": (
                    "done"
                    if p["remaining"] == 0
                    # arrived but not finished -> ready
                    else ("ready" if p["arrival"] <= _live_state["current_time"] else "not_arrived")
                ),
            }
            # Keep deterministic process row ordering in table view.
            for p in sorted(procs, key=lambda x: x["pid"])
        ],
    }


def _finalize_live_result() -> LiveFinalResult:
    """
    Build final live-mode result payload after all processes finish.
    """
    # Freeze final mutable runtime state before computing metrics.
    procs = deepcopy(_live_state["processes"])

    stats = []
    for p in procs:
        completion = p["completion"]
        turnaround = completion - p["arrival"]
        waiting = turnaround - p["burst"]
        stats.append(
            {
                "pid": p["pid"],
                "arrival": p["arrival"],
                "burst": p["burst"],
                "priority": p.get("priority"),
                "completion": completion,
                "waiting": waiting,
                "turnaround": turnaround,
            }
        )

    # Final global averages (safe even if list is unexpectedly empty).
    avg_w = sum(x["waiting"] for x in stats) / len(stats) if stats else 0.0
    avg_t = sum(x["turnaround"] for x in stats) / len(stats) if stats else 0.0

    return {
        "mode": "live",
        "algorithm": _live_state["algorithm"],
        "timeline": _merge_gantt(_live_state["gantt_log"]),
        "process_stats": sorted(stats, key=lambda x: str(x.get("pid", ""))),
        "avg_waiting_time": avg_w,
        "avg_turnaround_time": avg_t,
        "total_time": _live_state["current_time"],
    }


def _pick_next_process_idx(now: int, algo: str) -> Optional[int]:
    """
    Select the next process index according to selected live algorithm.
    Returns None if CPU should be idle this tick.
    """
    procs = _live_state["processes"]

    ready_indices = [
        i
        for i, p in enumerate(procs)
        if p["arrival"] <= now and p["remaining"] > 0
    ]
    if not ready_indices:
        return None

    # FCFS/SJF-NP/Priority-NP should continue current if still running.
    if algo in {"fcfs", "sjf_np", "priority_np", "priority_non_preemptive"} and _live_state["current_pid"] is not None:
        current_idx = next(
            (i for i, p in enumerate(procs) if p["pid"] == _live_state["current_pid"]),
            None,
        )
        if current_idx is not None and procs[current_idx]["remaining"] > 0:
            return current_idx

    if algo == "fcfs":
        # earliest arrival, then insertion order
        return min(ready_indices, key=lambda i: (procs[i]["arrival"], procs[i]["_order"]))
    if algo == "sjf_np":
        # shortest burst among ready when choosing a new process
        return min(ready_indices, key=lambda i: (procs[i]["burst"], procs[i]["arrival"], procs[i]["_order"]))
    if algo in {"sjf_p", "sjf_preemptive", "srtf"}:
        # shortest remaining each tick
        return min(ready_indices, key=lambda i: (procs[i]["remaining"], procs[i]["arrival"], procs[i]["_order"]))
    if algo in {"priority_np", "priority_non_preemptive"}:
        # smaller priority value means higher priority
        return min(
            ready_indices,
            key=lambda i: (procs[i].get("priority", 0), procs[i]["arrival"], procs[i]["_order"]),
        )

    raise ValueError(f"Unsupported live algorithm: {algo}")


def _rr_enqueue_arrivals(now: int) -> None:
    """Enqueue ready processes for RR that are not already queued/running."""
    procs = _live_state["processes"]
    queue: List[int] = _live_state["rr_queue"]
    current_idx = _live_state["current_idx"]
    # Add each arrived process exactly once to RR queue unless currently running.
    for i, p in enumerate(procs):
        if p["arrival"] <= now and p["remaining"] > 0 and i != current_idx and i not in queue:
            queue.append(i)
            _live_state["rr_slice_left"].setdefault(i, _live_state["rr_quantum"])


def _priority_enqueue_arrivals(now: int) -> None:
    """Enqueue ready processes into per-priority queues if not already present."""
    procs = _live_state["processes"]
    current_idx = _live_state["current_idx"]
    pr_queues: Dict[int, List[int]] = _live_state["priority_queues"]
    # Place each arrived process into its priority-level queue exactly once.
    for i, p in enumerate(procs):
        if p["arrival"] > now or p["remaining"] <= 0 or i == current_idx:
            continue
        pr = p.get("priority", 0)
        queue = pr_queues.setdefault(pr, [])
        if i not in queue:
            queue.append(i)
            _live_state["rr_slice_left"].setdefault(i, _live_state["rr_quantum"])


def _priority_highest_queue_key() -> Optional[int]:
    """Return highest priority key among non-empty queues."""
    pr_queues: Dict[int, List[int]] = _live_state["priority_queues"]
    # Filter only non-empty priority queues.
    non_empty = [pr for pr, q in pr_queues.items() if q]
    if not non_empty:
        return None
    return min(non_empty)


def _live_loop():
    """
    Background thread loop for live simulation.
    One iteration ~= one time unit, then sleeps tick_seconds.
    """
    # Keep looping until run stops or finishes.
    while True:
        with _live_lock:
            if not _live_state["running"]:
                return

            if _live_state["paused"]:
                # stay in paused state without consuming CPU time units
                pass
            else:
                # Read current state for this scheduling decision.
                now = _live_state["current_time"]
                algo = _live_state["algorithm"]
                idx = None

                if algo in {"rr", "round_robin"}:
                    # Ensure all arrived runnable processes are in RR queue.
                    _rr_enqueue_arrivals(now)
                    current_idx = _live_state["current_idx"]
                    # If a process is mid-quantum and still runnable, continue it.
                    if current_idx is not None and _live_state["processes"][current_idx]["remaining"] > 0:
                        idx = current_idx
                    elif _live_state["rr_queue"]:
                        # Otherwise dispatch next process from RR queue head.
                        idx = _live_state["rr_queue"].pop(0)
                        _live_state["current_idx"] = idx
                        _live_state["current_pid"] = _live_state["processes"][idx]["pid"]
                elif algo in {"priority_p", "priority_preemptive"}:
                    # Keep per-priority queues up-to-date with arrivals.
                    _priority_enqueue_arrivals(now)
                    current_idx = _live_state["current_idx"]

                    # Preempt if a higher-priority process is available.
                    if current_idx is not None and _live_state["processes"][current_idx]["remaining"] > 0:
                        current_pr = _live_state["processes"][current_idx].get("priority", 0)
                        top_pr = _priority_highest_queue_key()
                        if top_pr is not None and top_pr < current_pr:
                            _live_state["priority_queues"].setdefault(current_pr, []).insert(0, current_idx)
                            _live_state["current_idx"] = None
                            _live_state["current_pid"] = None

                    current_idx = _live_state["current_idx"]
                    if current_idx is not None and _live_state["processes"][current_idx]["remaining"] > 0:
                        # Continue running current process if no higher-priority preemption.
                        idx = current_idx
                    else:
                        # Dispatch from highest-priority available queue.
                        top_pr = _priority_highest_queue_key()
                        if top_pr is not None:
                            idx = _live_state["priority_queues"][top_pr].pop(0)
                            _live_state["current_idx"] = idx
                            _live_state["current_pid"] = _live_state["processes"][idx]["pid"]
                else:
                    # Use common selector for FCFS/SJF/Priority-NP.
                    idx = _pick_next_process_idx(now, algo)

                if idx is None:
                    # CPU idle for one tick when no ready process exists.
                    _live_state["gantt_log"].append(("IDLE", now, now + 1))
                    _live_state["current_time"] += 1
                    _live_state["current_pid"] = None
                    _live_state["current_idx"] = None
                else:
                    # Execute exactly one simulation time unit.
                    p = _live_state["processes"][idx]
                    start = _live_state["current_time"]
                    end = start + 1

                    p["remaining"] -= 1
                    _live_state["gantt_log"].append((p["pid"], start, end))
                    _live_state["current_time"] = end
                    _live_state["current_pid"] = p["pid"]
                    _live_state["current_idx"] = idx

                    if algo in {"rr", "round_robin", "priority_p", "priority_preemptive"}:
                        # Decrement RR slice budget for current tick.
                        _live_state["rr_slice_left"][idx] = _live_state["rr_slice_left"].get(
                            idx, _live_state["rr_quantum"]
                        ) - 1

                    if p["remaining"] == 0:
                        # record completion instant once process fully finishes
                        p["completion"] = end
                        _live_state["current_pid"] = None
                        _live_state["current_idx"] = None
                        _live_state["rr_slice_left"].pop(idx, None)
                    elif algo in {"rr", "round_robin", "priority_p", "priority_preemptive"}:
                        # For RR-based modes: rotate when quantum expires.
                        if _live_state["rr_slice_left"].get(idx, 0) <= 0:
                            # Reset process slice budget for next dispatch.
                            _live_state["rr_slice_left"][idx] = _live_state["rr_quantum"]
                            if algo in {"rr", "round_robin"}:
                                # RR: push to end of single ready queue.
                                _live_state["rr_queue"].append(idx)
                            else:
                                # Priority-P: push to end of same-priority queue.
                                pr = p.get("priority", 0)
                                _live_state["priority_queues"].setdefault(pr, []).append(idx)
                            _live_state["current_pid"] = None
                            _live_state["current_idx"] = None
                    else:
                        # FCFS/SJF-NP/Priority-NP keep current; SRTF/P modes re-evaluate naturally.
                        if algo in {"sjf_p", "sjf_preemptive", "srtf"}:
                            _live_state["current_pid"] = None
                            _live_state["current_idx"] = None

            # capture callbacks and immutable snapshot while lock is held
            on_tick = _live_state["on_tick"]
            snapshot = _build_tick_snapshot()

            all_done = all(p["remaining"] == 0 for p in _live_state["processes"])
            if all_done and _live_state["running"]:
                # Mark run finished and prepare final callback payload.
                _live_state["running"] = False
                on_finish = _live_state["on_finish"]
                final_result = _finalize_live_result()
            else:
                on_finish = None
                final_result = None

        # Call callbacks outside lock to avoid deadlocks/UI stalls.
        if callable(on_tick):
            on_tick(snapshot)

        if on_finish is not None and callable(on_finish):
            on_finish(final_result)
            return

        time.sleep(_live_state["tick_seconds"])


# -------------------------
# Live Mode API
# -------------------------
def start_live(processes, algorithm, config=None, on_tick=None, on_finish=None):
    """
    Starts live simulation in background thread.
    Each tick = config.get("tick_seconds", 1.0) seconds.
    Currently supported live algorithms:
      - fcfs
      - sjf_np
      - sjf_p / sjf_preemptive / srtf
      - rr / round_robin   (requires config["quantum"], default=2)
      - priority_np / priority_non_preemptive
      - priority_p / priority_preemptive (RR inside equal priority, quantum default=2)
    """
    global _live_thread

    # Normalize config dict and read runtime options.
    config = config or {}
    tick_seconds = float(config.get("tick_seconds", 1.0))
    rr_quantum = int(config.get("quantum", 2))
    if tick_seconds <= 0:
        raise ValueError("tick_seconds must be > 0")
    if rr_quantum <= 0:
        raise ValueError("quantum must be > 0")

    # Validate/normalize inputs and canonicalize algorithm selector.
    procs = _validate_and_normalize_processes(processes)
    algo = (algorithm or "").strip().lower()
    live_supported = {
        "fcfs",
        "sjf_np",
        "sjf_p",
        "sjf_preemptive",
        "srtf",
        "rr",
        "round_robin",
        "priority_np",
        "priority_non_preemptive",
        "priority_p",
        "priority_preemptive",
    }

    if algo not in live_supported:
        raise ValueError(
            f"Unsupported live algorithm: {algorithm}. "
            "Supported live algorithms are: fcfs, sjf_np, sjf_p (srtf), rr, priority_np, priority_p."
        )

    with _live_lock:
        if _live_state["running"]:
            raise RuntimeError("live simulation is already running")

        # Prepare runtime copy and add internal fields used by live engine.
        runtime_procs = []
        for order, p in enumerate(procs):
            runtime_procs.append(
                {
                    "pid": p["pid"],
                    "arrival": p["arrival"],
                    "burst": p["burst"],
                    "priority": p.get("priority"),
                    "remaining": p["burst"],
                    "completion": None,
                    "_order": order,
                }
            )

        _live_state["running"] = True
        _live_state["paused"] = False
        _live_state["algorithm"] = algo
        _live_state["tick_seconds"] = tick_seconds
        # Set RR quantum used by RR and priority-preemptive tie rotation.
        _live_state["rr_quantum"] = rr_quantum
        # Reset all RR/Priority scheduling structures for a fresh run.
        _live_state["rr_slice_left"] = {}
        _live_state["rr_queue"] = []
        _live_state["priority_queues"] = {}
        _live_state["current_time"] = 0
        _live_state["processes"] = runtime_procs
        _live_state["gantt_log"] = []
        _live_state["current_pid"] = None
        _live_state["current_idx"] = None
        _live_state["on_tick"] = on_tick
        _live_state["on_finish"] = on_finish

        # daemon=True so app can exit cleanly without waiting this thread.
        _live_thread = threading.Thread(target=_live_loop, daemon=True)
        _live_thread.start()


def pause():
    """
    Pause live simulation time progression.
    Safe no-op if no live run is active.
    """
    with _live_lock:
        if not _live_state["running"]:
            return
        # Only pauses time progression; state remains intact.
        _live_state["paused"] = True


def resume():
    """
    Resume live simulation from current state/time.
    Safe no-op if no live run is active.
    """
    with _live_lock:
        if not _live_state["running"]:
            return
        # Continue loop from same current_time and scheduler state.
        _live_state["paused"] = False


def stop_live():
    """
    Request the live worker thread to stop (e.g. Reset in UI).
    Safe no-op if no live run is active.
    """
    global _live_thread
    with _live_lock:
        _live_state["running"] = False
        _live_state["paused"] = False
    t = _live_thread
    if t is not None and t.is_alive():
        t.join(timeout=5.0)
    with _live_lock:
        _live_thread = None


def add_process(process):
    """
    Add process during live simulation.
    Arrival time is forced to current live time (as requested).
    """
    # validate input first; arrival will be overridden to current simulation time.
    normalized = _validate_single_process(process, allow_missing_arrival=True)

    with _live_lock:
        if not _live_state["running"]:
            raise RuntimeError("live simulation is not running")

        pid = normalized["pid"]
        if any(p["pid"] == pid for p in _live_state["processes"]):
            raise ValueError(f"duplicate pid: {pid}")

        # Arrival is forced to "now" per project live-mode requirement.
        now = _live_state["current_time"]
        order = len(_live_state["processes"])

        _live_state["processes"].append(
            {
                "pid": pid,
                "arrival": now,  # automatic arrival at current/pause time
                "burst": normalized["burst"],
                "priority": normalized.get("priority"),
                "remaining": normalized["burst"],
                "completion": None,
                "_order": order,
            }
        )