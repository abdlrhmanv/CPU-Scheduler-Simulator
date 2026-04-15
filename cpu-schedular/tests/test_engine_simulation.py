# =============================================================================
# TEAM CONTRACT — READ BEFORE MODIFYING
# -----------------------------------------------------------------------------
# THESE TESTS LOCK THE BATCH API: `simulation.static_run(...)`.
#
# BEFORE MERGING ENGINE CHANGES:
#   - Run:  cd cpu-schedular && pytest tests/test_engine_simulation.py -q
#   - If timelines or averages change, update EXPECTED values with team agreement.
#
# IMPORTANT FOR TEAMMATES:
#   - Keep fixtures tiny and hand-verifiable; document assumptions in test docstrings.
#   - Use ProcessInput casts/helpers so type checkers stay happy.
#
# =============================================================================


"""
Unit tests for engine batch scheduling via simulation.static_run.

Fixtures use small integer traces with hand-verified expected metrics.
Run from repo: cd cpu-schedular && pytest -q
"""
# Module docstring: what is tested and how to run pytest from the correct folder.

from __future__ import annotations
# Postpone evaluation of annotations (consistent with the rest of the project).

from typing import Any, Dict, List, cast
# Any/Dict for loose per-process stat rows; List/cast for ProcessInput typing.

import pytest
# approx() for float averages; raises() for validation tests.

from engine.models import ProcessInput
# TypedDict for process dicts passed into static_run (matches engine contract).

from engine.simulation import static_run
# Single entry point for batch (instant) scheduling used by the UI.


def _two_same_arrival() -> List[ProcessInput]:
    """Two processes arriving together: P1 longer burst, P2 shorter (classic tie-break tests)."""
    return cast(
        List[ProcessInput],
        [
            {"pid": "P1", "arrival": 0, "burst": 3, "priority": None},
            {"pid": "P2", "arrival": 0, "burst": 2, "priority": None},
        ],
    )


def _as_processes(xs: List[dict[str, Any]]) -> List[ProcessInput]:
    """Narrow plain dict literals to ProcessInput for static_run (pyright/basedpyright)."""
    return cast(List[ProcessInput], xs)


def test_static_fcfs_order_and_averages() -> None:
    """FCFS: sort by (arrival, pid) — P1 before P2."""
    procs = _two_same_arrival()  # Shared tiny workload.
    r = static_run(procs, "fcfs")  # Batch run; no config needed.
    assert r["mode"] == "static"  # Result envelope from simulation.static_run.
    assert r["algorithm"] == "fcfs"  # Normalized algorithm key.
    assert r["timeline"] == [  # Merged Gantt blocks (pid, start, end).
        {"pid": "P1", "start": 0, "end": 3},
        {"pid": "P2", "start": 3, "end": 5},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.5)  # Hand-calculated mean WT.
    assert r["avg_turnaround_time"] == pytest.approx(4.0)  # Hand-calculated mean TAT.
    assert r["total_time"] == 5  # Makespan = last timeline end.


def test_static_sjf_np_shortest_job_first() -> None:
    """Non-preemptive SJF picks P2 (burst 2) before P1 (burst 3)."""
    procs = _two_same_arrival()
    r = static_run(procs, "sjf_np")
    assert r["algorithm"] == "sjf_np"
    assert r["timeline"] == [
        {"pid": "P2", "start": 0, "end": 2},
        {"pid": "P1", "start": 2, "end": 5},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.0)
    assert r["avg_turnaround_time"] == pytest.approx(3.5)


def test_static_sjf_preemptive_srtf() -> None:
    """SRTF matches shortest remaining at each tick."""
    procs = _two_same_arrival()
    r = static_run(procs, "sjf_p")
    assert r["algorithm"] == "sjf_p"
    assert r["timeline"] == [
        {"pid": "P2", "start": 0, "end": 2},
        {"pid": "P1", "start": 2, "end": 5},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.0)


def test_static_round_robin_quantum_2() -> None:
    """RR q=2: alternate 2-unit slices until done."""
    procs = _two_same_arrival()
    r = static_run(procs, "rr", {"quantum": 2})  # Config passes time slice to RR.
    assert r["algorithm"] == "rr"
    assert r["timeline"] == [
        {"pid": "P1", "start": 0, "end": 2},
        {"pid": "P2", "start": 2, "end": 4},
        {"pid": "P1", "start": 4, "end": 5},
    ]
    assert r["avg_waiting_time"] == pytest.approx(2.0)
    assert r["avg_turnaround_time"] == pytest.approx(4.5)


def test_static_priority_non_preemptive() -> None:
    """Smaller priority number runs first."""
    procs = _as_processes(
        [
            {"pid": "A", "arrival": 0, "burst": 2, "priority": 1},
            {"pid": "B", "arrival": 0, "burst": 2, "priority": 0},
        ]
    )
    r = static_run(procs, "priority_np")
    assert r["algorithm"] == "priority_np"
    assert r["timeline"] == [
        {"pid": "B", "start": 0, "end": 2},
        {"pid": "A", "start": 2, "end": 4},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.0)


def test_static_priority_preemptive_runs() -> None:
    """Preemptive priority with quantum should complete without error."""
    procs = _as_processes(
        [
            {"pid": "A", "arrival": 0, "burst": 2, "priority": 1},
            {"pid": "B", "arrival": 0, "burst": 2, "priority": 0},
        ]
    )
    r = static_run(procs, "priority_p", {"quantum": 2})  # Same-priority RR uses quantum.
    assert r["algorithm"] == "priority_p"
    assert r["total_time"] == 4
    by_pid = {cast(Dict[str, Any], s)["pid"]: cast(Dict[str, Any], s) for s in r["process_stats"]}
    assert by_pid["A"]["completion"] == 4
    assert by_pid["B"]["completion"] == 2


def test_process_stats_turnaround_identity() -> None:
    """Turnaround = completion - arrival for every process."""
    procs = _two_same_arrival()
    r = static_run(procs, "fcfs")
    for s in r["process_stats"]:  # One enriched stat row per process.
        sp = cast(Dict[str, Any], s)  # ProcessStats has optional keys for checker.
        assert sp["turnaround"] == sp["completion"] - sp["arrival"]
        assert sp["waiting"] == sp["turnaround"] - sp["burst"]


def test_validation_empty_input() -> None:
    """static_run must reject an empty process list."""
    with pytest.raises(ValueError, match="non-empty"):
        static_run(cast(List[ProcessInput], []), "fcfs")  # Empty list typed as ProcessInput[].


def test_validation_duplicate_pid() -> None:
    """Duplicate PIDs are invalid across the workload."""
    procs = _as_processes(
        [
            {"pid": "P1", "arrival": 0, "burst": 1, "priority": None},
            {"pid": "P1", "arrival": 1, "burst": 1, "priority": None},
        ]
    )
    with pytest.raises(ValueError, match="duplicate"):
        static_run(procs, "fcfs")


def test_unsupported_algorithm() -> None:
    """Unknown algorithm string should raise a clear error."""
    with pytest.raises(ValueError, match="Unsupported"):
        static_run(_two_same_arrival(), "unknown_algo")


def test_timeline_end_matches_total_time() -> None:
    """Merged timeline last end equals total_time."""
    procs = _as_processes(
        [
            {"pid": "P1", "arrival": 0, "burst": 1, "priority": None},
            {"pid": "P2", "arrival": 5, "burst": 1, "priority": None},
        ]
    )
    r = static_run(procs, "fcfs")
    assert r["timeline"][-1]["end"] == r["total_time"]  # Idle gap may precede P2; end still matches.
