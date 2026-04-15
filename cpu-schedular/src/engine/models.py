"""
Shared data models for the CPU scheduler engine.

This module centralizes the "shape" of data exchanged between:
- algorithm modules (fcfs/sjf/priority/round_robin),
- simulation runtime,
- and UI callbacks.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, NotRequired, Optional, Tuple, TypedDict


# =============================================================================
# Input Models
# =============================================================================


class ProcessInput(TypedDict):
    """
    Raw process object accepted by engine APIs.

    Required:
    - pid, arrival, burst

    Optional:
    - priority: smaller value => higher priority (required by priority algorithms at runtime)
    """

    pid: str
    arrival: int
    burst: int
    priority: NotRequired[Optional[int]]


# =============================================================================
# Timeline Models
# =============================================================================


# Internal gantt representation used by algorithm modules.
GanttTuple = Tuple[str, int, int]  # (pid, start, end)


class TimelineBlock(TypedDict):
    """
    UI-friendly gantt block.
    Example: {"pid": "P1", "start": 3, "end": 7}
    """

    pid: str
    start: int
    end: int


# =============================================================================
# Metrics / Result Models
# =============================================================================


class BasicProcessStats(TypedDict):
    """
    Minimal per-process metrics returned by some algorithm modules.
    """

    pid: str
    waiting: int
    turnaround: int


class ProcessStats(TypedDict, total=False):
    """
    Full per-process metrics shape used by simulation outputs.
    """

    pid: str
    arrival: int
    burst: int
    priority: Optional[int]
    completion: int
    waiting: int
    turnaround: int


class StaticRunResult(TypedDict):
    """
    Standard static_run output contract.
    """

    mode: str
    algorithm: str
    timeline: List[TimelineBlock]
    process_stats: List[ProcessStats]
    avg_waiting_time: float
    avg_turnaround_time: float
    total_time: int


class LiveTickProcessState(TypedDict, total=False):
    """
    Per-process snapshot row emitted on each live tick callback.
    """

    pid: str
    arrival: int
    burst: int
    priority: Optional[int]
    remaining: int
    completion: Optional[int]
    state: str


class LiveTickSnapshot(TypedDict):
    """
    on_tick callback payload contract.
    """

    mode: str
    algorithm: str
    current_time: int
    timeline: List[TimelineBlock]
    processes: List[LiveTickProcessState]


class LiveFinalResult(TypedDict):
    """
    on_finish callback payload contract.
    """

    mode: str
    algorithm: str
    timeline: List[TimelineBlock]
    process_stats: List[ProcessStats]
    avg_waiting_time: float
    avg_turnaround_time: float
    total_time: int


# Common return type for static algorithm functions:
# (gantt_log, per-process basic/full stats, avg_waiting, avg_turnaround)
AlgorithmRunTuple = Tuple[List[GanttTuple], List[Dict[str, Any]], float, float]


# =============================================================================
# Optional Runtime Dataclass
# =============================================================================


@dataclass
class RuntimeProcess:
    """
    Optional strongly-typed runtime process object.

    Note:
    Current engine implementation uses dictionaries for flexibility.
    This dataclass is provided to support gradual migration to typed runtime
    objects without breaking existing modules.
    """

    pid: str
    arrival: int
    burst: int
    priority: Optional[int] = None
    remaining: Optional[int] = None
    completion: Optional[int] = None
