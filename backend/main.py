from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from engine import run_simulation, compare_algorithms, rerun_reroute_analysis

app = FastAPI(title="Energy-Aware Mesh Routing Research Simulator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:80",
        "http://127.0.0.1:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimRequest(BaseModel):
    nodes: int = Field(28, ge=5, le=150)
    gateway: int = Field(0, ge=0)
    rounds: int = Field(80, ge=1, le=1000)
    seed: int = 7
    k: int = Field(2, ge=1, le=4)
    traffic_per_round: int = Field(18, ge=1, le=500)
    failure_round: int = Field(25, ge=0, le=999)
    failure_count: int = Field(1, ge=0, le=20)
    threshold: float = Field(25.0, ge=1, le=90)
    tx_cost: float = Field(0.65, gt=0, le=100)
    rx_cost: float = Field(0.18, gt=0, le=100)
    initial_energy: float = Field(100.0, gt=0, le=100000)
    # Multi-objective routing weights (active when use_weighted_route=True)
    use_weighted_route: bool = False
    energy_weight: float = Field(1.0, ge=0, le=100)
    depletion_weight: float = Field(1.0, ge=0, le=100)
    redundancy_weight: float = Field(1.0, ge=0, le=100)
    # Rigorous k-edge-connectivity enforcement
    rigorous_k: bool = False

class CompareRequest(SimRequest):
    seeds: int = Field(5, ge=1, le=30)

class RerouteAnalysisRequest(SimRequest):
    source_node: int | None = Field(None, ge=0)
    failed_node_id: int | None = Field(None, ge=0)
    repair: bool = True

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "mesh-routing-research-simulator"}

@app.post("/api/simulate")
def simulate(req: SimRequest, algorithm: str = "incremental"):
    try:
        if req.gateway >= req.nodes:
            raise ValueError("gateway must be less than node count")
        # Validate algorithm name
        allowed = {"shortest", "energy", "global_energy", "incremental"}
        if algorithm not in allowed:
            raise ValueError(f"unsupported algorithm '{algorithm}'. Supported: shortest, energy, global_energy, incremental")
        # Map global_energy to energy mode (same cost function)
        engine_algo = "energy" if algorithm == "global_energy" else algorithm
        return run_simulation(req.model_dump(), engine_algo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc

@app.post("/api/reroute")
def reroute_analysis(req: RerouteAnalysisRequest):
    try:
        if req.gateway >= req.nodes:
            raise ValueError("gateway must be less than node count")
        payload = req.model_dump()
        source_node = payload.pop("source_node", None)
        failed_node_id = payload.pop("failed_node_id", None)
        repair = payload.pop("repair", True)
        return rerun_reroute_analysis(
            payload, source_node=source_node, failed_node_id=failed_node_id, repair=repair
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rerouting analysis failed: {exc}") from exc

@app.post("/api/compare")
def compare(req: CompareRequest):
    try:
        if req.gateway >= req.nodes:
            raise ValueError("gateway must be less than node count")
        payload = req.model_dump()
        seeds = payload.pop("seeds")
        return compare_algorithms(payload, seeds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {exc}") from exc
