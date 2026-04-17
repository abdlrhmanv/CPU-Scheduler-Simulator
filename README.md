# CPU Scheduler Simulator

**CSE335s (UG2023) — Operating Systems · course project — desktop GUI for CPU scheduling algorithms.**

A Python + PySide6 application that runs **FCFS**, **SJF (non-preemptive / preemptive)**, **Priority (non-preemptive / preemptive)**, and **Round Robin**, in **batch** (instant) or **live** (1 time unit ≈ 1 second) mode, with **Gantt chart**, **remaining-burst table**, **average waiting / turnaround** metrics, **pause / resume**, and **dynamic add process** during live runs.

---

## About

This repository contains our team’s CPU scheduling simulator: a clear separation between the **scheduling engine** (`src/engine`) and the **Qt desktop UI** (`ui`). The engine exposes a small API (`static_run`, live session with `start_live` / `stop_live` / `pause` / `resume` / `add_process`) consumed by the main window.

**Course:** **CSE335s (UG2023) — Operating Systems** · Ain Shams University — Computer and Systems Engineering.

---

## Repository structure

```text
Project/
├── README.md
├── requirements.txt
├── pyrightconfig.json              # IDE / basedpyright paths (optional)
└── cpu-schedular/
    ├── main.py                     # Application entry (run from this folder)
    ├── pytest.ini
    ├── src/
    │   └── engine/                 # Pure scheduling logic (no GUI)
    │       ├── models.py           # Shared TypedDicts / contracts
    │       ├── simulation.py       # Static + live orchestration
    │       ├── fcfs.py
    │       ├── sjf.py
    │       ├── priority.py
    │       └── round_robin.py
    ├── ui/
    │   ├── main_window.py          # Layout, controls, engine wiring
    │   ├── input_panel.py          # Algorithm, mode, quantum, process table
    │   ├── gantt_view.py           # Gantt timeline
    │   └── burst_table.py          # Burst table + metrics panel
    ├── tests/
    │   └── test_engine_simulation.py
    └── build/
        └── pyinstaller.spec        # Packaging (fill when building exe)
```

---

## Features

| Area | Description |
|------|-------------|
| Algorithms | FCFS, SJF (NP/P), Priority (NP/P), Round Robin |
| Modes | Batch (instant full run) · Live (tick-based, pause/resume) |
| UI | Conditional inputs (e.g. quantum, priority column when needed) |
| Visualization | Gantt chart + remaining burst table + avg WT / TAT |
| Live | Add process at current time, reset/stop |

---

## Team & ownership

| Member | Student ID | Main contribution |
|--------|------------|---------------------|
| **Abdlrhman Hisham Ismail** | 2300343 | `models.py`, `simulation.py`, tests, `input_panel.py`, `main_window.py`, `main.py` |
| **Mena Moheb AbdElshaheed** | 2300700 | FCFS (`fcfs.py`) |
| **Mina Hany Eid** | 2300434 | Round Robin (`round_robin.py`) |
| **Mark Amir Ayad** | 2300453 | Priority (`priority.py`) |
| **Abdallah Ragaae Ahmed** | 2301025 | SJF (`sjf.py`) |
| **Mariam Maged** | — | Gantt view (`gantt_view.py`) |
| **Asmaa Salah** | — | Burst table + metrics (`burst_table.py`) |

---

## Tech stack

| Category | Tools |
|----------|--------|
| Language | Python 3.11+ |
| GUI | PySide6 (Qt6) |
| Testing | pytest |
| Packaging | PyInstaller (optional; see `build/pyinstaller.spec`) |

---

## Getting started

### 1. Clone and enter the project

```bash
git clone https://github.com/abdlrhmanv/CPU-Scheduler-Simulator
cd Project
```

### 2. Virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (cmd/PowerShell)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

From the **`cpu-schedular`** directory (required for imports and `ui` / `engine` paths):

```bash
cd cpu-schedular
python main.py
```

### 5. Run tests

```bash
cd cpu-schedular
pytest
```

**Linux note:** If Qt fails to start in some terminals (Wayland / IDE), the entry point defaults to the X11 platform on Linux; see comments in `main.py`.

---

## Contact

| | |
|--|--|
| **Email (readme / coordination)** | [abdlrhmanv@icloud.com](mailto:abdlrhmanv@icloud.com) |
| **GitHub** | [@abdlrhmanv](https://github.com/abdlrhmanv) |

Happy to discuss OS, scheduling, or this codebase — adjust links as needed for your team.

---

## License & course use

Provided for educational use in **CSE335s (UG2023) — Operating Systems**. Adapt usage and attribution per your instructor’s requirements.

---

Made with care by the CPU Scheduler team — **Abdlrhman Hisham Ismail**, **Mina Moheb**, **Mina Hany Eid**, **Mark Amir**, **Abdallah Ragaae**, **Mariam Maged**, **Asmaa Salah**.
