"""
Unit tests for engine batch scheduling via simulation.static_run.

Fixtures use small integer traces with hand-verified expected metrics.
Run from repo: cd cpu-schedular && pytest -q
"""

from __future__ import annotations

import pytest

from engine.simulation import static_run


def _two_same_arrival() -> list[dict]:
    return [
        {"pid": "P1", "arrival": 0, "burst": 3, "priority": None},
        {"pid": "P2", "arrival": 0, "burst": 2, "priority": None},
    ]


def test_static_fcfs_order_and_averages() -> None:
    """FCFS: sort by (arrival, pid) — P1 before P2."""
    procs = _two_same_arrival()
    r = static_run(procs, "fcfs")
    assert r["mode"] == "static"
    assert r["algorithm"] == "fcfs"
    assert r["timeline"] == [
        {"pid": "P1", "start": 0, "end": 3},
        {"pid": "P2", "start": 3, "end": 5},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.5)
    assert r["avg_turnaround_time"] == pytest.approx(4.0)
    assert r["total_time"] == 5


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
    r = static_run(procs, "rr", {"quantum": 2})
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
    procs = [
        {"pid": "A", "arrival": 0, "burst": 2, "priority": 1},
        {"pid": "B", "arrival": 0, "burst": 2, "priority": 0},
    ]
    r = static_run(procs, "priority_np")
    assert r["algorithm"] == "priority_np"
    assert r["timeline"] == [
        {"pid": "B", "start": 0, "end": 2},
        {"pid": "A", "start": 2, "end": 4},
    ]
    assert r["avg_waiting_time"] == pytest.approx(1.0)


def test_static_priority_preemptive_runs() -> None:
    """Preemptive priority with quantum should complete without error."""
    procs = [
        {"pid": "A", "arrival": 0, "burst": 2, "priority": 1},
        {"pid": "B", "arrival": 0, "burst": 2, "priority": 0},
    ]
    r = static_run(procs, "priority_p", {"quantum": 2})
    assert r["algorithm"] == "priority_p"
    assert r["total_time"] == 4
    by_pid = {s["pid"]: s for s in r["process_stats"]}
    assert by_pid["A"]["completion"] == 4
    assert by_pid["B"]["completion"] == 2


def test_process_stats_turnaround_identity() -> None:
    """Turnaround = completion - arrival for every process."""
    procs = _two_same_arrival()
    r = static_run(procs, "fcfs")
    for s in r["process_stats"]:
        assert s["turnaround"] == s["completion"] - s["arrival"]
        assert s["waiting"] == s["turnaround"] - s["burst"]


def test_validation_empty_input() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        static_run([], "fcfs")


def test_validation_duplicate_pid() -> None:
    procs = [
        {"pid": "P1", "arrival": 0, "burst": 1, "priority": None},
        {"pid": "P1", "arrival": 1, "burst": 1, "priority": None},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        static_run(procs, "fcfs")


def test_unsupported_algorithm() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        static_run(_two_same_arrival(), "unknown_algo")


def test_timeline_end_matches_total_time() -> None:
    """Merged timeline last end equals total_time."""
    procs = [
        {"pid": "P1", "arrival": 0, "burst": 1, "priority": None},
        {"pid": "P2", "arrival": 5, "burst": 1, "priority": None},
    ]
    r = static_run(procs, "fcfs")
    assert r["timeline"][-1]["end"] == r["total_time"]
