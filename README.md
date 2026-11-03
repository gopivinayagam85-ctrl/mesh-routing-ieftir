# Mesh Routing Lab — Research Simulator

A local-first React + FastAPI prototype for experimenting with energy-aware routing in simulated wireless mesh networks.

## Features
- Spatial mesh graph generation with connectivity augmentation toward a requested edge-connectivity target.
- Shortest-path, energy-aware, and localized incremental route-refresh variants.
- Simulated traffic, battery depletion, and configurable node-failure injection.
- Live topology visualization and energy/PDR charts.
- Multi-seed benchmark suite reporting means and standard deviations.
- JSON export and basic unit tests.

## Requirements
- Python 3.10+ (3.11 recommended)
- Node.js 18+ (20 LTS recommended)
- npm

## Run the backend (Windows PowerShell)
Open a terminal in this folder:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend API docs: http://localhost:8000/docs
Health check: http://localhost:8000/api/health

## Run the frontend
Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints, normally http://localhost:5173.

## Run tests
With the backend virtual environment active and terminal in `backend`:

```powershell
python -m unittest -v
```

## Quick API examples
Run one simulation:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/simulate?algorithm=incremental' -Method Post -ContentType 'application/json' -Body '{"nodes":28,"rounds":80,"seed":7,"k":2,"failure_round":25,"failure_count":1}'
```

Compare algorithms across 5 seeds:

```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/compare' -Method Post -ContentType 'application/json' -Body '{"nodes":28,"rounds":80,"seed":7,"k":2,"failure_round":25,"failure_count":1,"seeds":5}'
```

## Algorithm variants
- `shortest`: shortest weighted path using geometric link distance.
- `energy`: global route recomputation using transmission energy, residual energy, and depletion estimates.
- `incremental`: energy-aware route calculation with localized route refreshes when nodes fail or low-energy nodes are used as relays.

## Research integrity / limitations
This is an experimental starting point, not a formally verified implementation of incremental k-edge-connectivity maintenance. The graph generator tries to augment the initial topology to the requested k, but the actual achieved edge connectivity is reported and may be below the target. Connectivity is measured on each round; that validation itself is global and contributes computation not represented by the route-recomputation counter. The energy and radio models are simplified, and routing recomputations are a proxy for control work, not direct packet or CPU measurements. Failure-injection rounds affect node-death metrics. The simulator does not yet model MAC contention, packet loss probabilities, retransmissions, link failures, control-message bytes, CPU time per operation, or formal k-edge connectivity preservation during every incremental update.

Before using results in a paper or patent submission, add link-failure experiments, paired-seed statistical tests, confidence intervals, explicit control-message accounting, and a verified incremental connectivity-maintenance algorithm. Do not claim improvement until results support it.
