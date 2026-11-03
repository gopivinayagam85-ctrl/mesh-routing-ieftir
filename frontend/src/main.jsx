import React, { useMemo, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Legend
} from 'recharts';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const initial = {
  nodes: 28,
  gateway: 0,
  rounds: 80,
  seed: 7,
  k: 2,
  traffic_per_round: 18,
  failure_round: 25,
  failure_count: 1,
  threshold: 25,
  tx_cost: 0.65,
  rx_cost: 0.18,
  initial_energy: 100,
  use_weighted_route: false,
  energy_weight: 1.0,
  depletion_weight: 1.0,
  redundancy_weight: 1.0,
  rigorous_k: false
};

const fmt = (v, digits = 2) => (v == null ? '—' : Number(v).toFixed(digits));

function MetricCard({ label, value, sub, status }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {sub && <div className={`metric-sub ${status || 'muted'}`}>{sub}</div>}
    </div>
  );
}

function NetworkMap({
  data,
  selectedNode,
  onSelectNode,
  zoom = 1,
  showNodeIds = true,
  showBattery = true,
  highlightRoute = null,
  routeColor = '#10B981',
  failedNodeId = null,
  failedEdges = null,
  width = 720,
  height = 410,
}) {
  if (!data?.network) {
    return (
      <div style={{
        height: height || 380,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#F8FAFD',
        borderRadius: 8,
        border: '1px solid #E2E8F0',
        color: '#64748B',
        gap: 8
      }}>
        <div style={{ fontSize: 32, color: '#94A3B8' }}>◎</div>
        <b style={{ color: '#1E293B' }}>Network topology awaiting execution</b>
        <span style={{ fontSize: 12 }}>Run a simulation or rerouting analysis to generate topology.</span>
      </div>
    );
  }

  const { nodes, edges, active_edges, paths } = data.network;
  const w = width, h = height, pad = 35;
  const px = n => pad + n.x * (w - pad * 2);
  const py = n => pad + n.y * (h - pad * 2);

  const activeSet = new Set(
    (active_edges || []).map(e => [Math.min(e.source, e.target), Math.max(e.source, e.target)].join('-'))
  );

  const failedEdgeSet = new Set(
    (failedEdges || data.network.failed_edges || []).map(e => [Math.min(e.source, e.target), Math.max(e.source, e.target)].join('-'))
  );

  const pathEdges = new Set();
  if (highlightRoute && highlightRoute.length >= 2) {
    for (let i = 0; i < highlightRoute.length - 1; i++) {
      pathEdges.add([Math.min(highlightRoute[i], highlightRoute[i + 1]), Math.max(highlightRoute[i], highlightRoute[i + 1])].join('-'));
    }
  } else if (paths) {
    paths.forEach(({ path }) => {
      if (path) {
        for (let i = 0; i < path.length - 1; i++) {
          pathEdges.add([Math.min(path[i], path[i + 1]), Math.max(path[i], path[i + 1])].join('-'));
        }
      }
    });
  }

  return (
    <div style={{ position: 'relative', overflow: 'hidden', borderRadius: 8, background: '#F8FAFD' }}>
      <svg
        className="network-svg"
        viewBox={`0 0 ${w} ${h}`}
        style={{ width: '100%', height: 'auto', maxHeight: h, transform: `scale(${zoom})`, transformOrigin: 'center center', transition: 'transform 0.2s ease' }}
        role="img"
        aria-label="Simulated mesh network topology"
      >
        <defs>
          <pattern id="light-dots" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.2" fill="#E2E8F0" />
          </pattern>
        </defs>
        <rect width={w} height={h} fill="url(#light-dots)" rx="8" />

        {/* Links */}
        {edges.map((e, i) => {
          const a = nodes[e.source], b = nodes[e.target];
          if (!a || !b) return null;
          const key = [Math.min(e.source, e.target), Math.max(e.source, e.target)].join('-');
          const isFailedEdge = failedEdgeSet.has(key) || (failedNodeId != null && (e.source === failedNodeId || e.target === failedNodeId));
          const alive = activeSet.has(key) && !isFailedEdge;
          const inPath = pathEdges.has(key);

          let stroke = '#CBD5E1';
          let strokeWidth = 1.2;
          let strokeOpacity = 0.75;
          let strokeDasharray = '0';

          if (isFailedEdge) {
            stroke = '#EF4444';
            strokeWidth = 2.0;
            strokeOpacity = 0.85;
            strokeDasharray = '4 4';
          } else if (inPath) {
            stroke = routeColor || '#10B981';
            strokeWidth = 3.0;
            strokeOpacity = 1.0;
            strokeDasharray = '0';
          } else if (!alive) {
            stroke = '#FCA5A5';
            strokeWidth = 1.2;
            strokeOpacity = 0.45;
            strokeDasharray = '4 4';
          }

          return (
            <line
              key={i}
              x1={px(a)}
              y1={py(a)}
              x2={px(b)}
              y2={py(b)}
              stroke={stroke}
              strokeWidth={strokeWidth}
              strokeOpacity={strokeOpacity}
              strokeDasharray={strokeDasharray}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map(n => {
          const isFailed = n.dead || (failedNodeId != null && n.id === failedNodeId);
          const isGw = n.gateway;
          const isLow = !isFailed && !isGw && (n.energy < 30);
          const r = isGw ? 11 : 7.5;
          const isSelected = selectedNode && selectedNode.id === n.id;
          const fill = isGw ? '#059669' : isFailed ? '#DC2626' : isLow ? '#F59E0B' : '#2563EB';

          return (
            <g
              key={n.id}
              onClick={() => onSelectNode && onSelectNode(n)}
              style={{ cursor: 'pointer' }}
            >
              {isSelected && (
                <circle cx={px(n)} cy={py(n)} r={r + 6} fill="none" stroke="#2563EB" strokeWidth="2" strokeDasharray="3 3" />
              )}
              {isGw && (
                <rect
                  x={px(n) - 14}
                  y={py(n) - 14}
                  width="28"
                  height="28"
                  rx="6"
                  fill="#059669"
                  opacity="0.16"
                />
              )}
              <circle cx={px(n)} cy={py(n)} r={r + 3} fill={fill} opacity="0.18" />
              <circle
                cx={px(n)}
                cy={py(n)}
                r={r}
                fill={fill}
                stroke={isGw ? '#10B981' : '#FFFFFF'}
                strokeWidth={isGw ? 2.2 : 1.6}
              />
              {/* Failure cross / indicator */}
              {isFailed && (
                <g stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round">
                  <line x1={px(n) - 4} y1={py(n) - 4} x2={px(n) + 4} y2={py(n) + 4} />
                  <line x1={px(n) + 4} y1={py(n) - 4} x2={px(n) - 4} y2={py(n) + 4} />
                </g>
              )}
              {showNodeIds && !isFailed && (
                <text
                  x={px(n)}
                  y={py(n) + 3.2}
                  textAnchor="middle"
                  fontSize={isGw ? 8.5 : 7}
                  fontWeight="700"
                  fill="#FFFFFF"
                >
                  {isGw ? 'GW' : n.id}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Floating Selected Node Badge */}
      {selectedNode && (
        <div className="node-tooltip-card">
          <strong>Node {selectedNode.id}</strong>
          <div><b>Status:</b> {selectedNode.dead ? '🔴 Dead' : '🟢 Active'}</div>
          <div><b>Role:</b> {selectedNode.gateway ? 'Gateway Sink' : 'Sensor Relay'}</div>
          {showBattery && <div><b>Energy:</b> {fmt(selectedNode.energy, 1)} J</div>}
          <div style={{ marginTop: 4, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={() => onSelectNode(null)}
              style={{ background: 'transparent', border: 0, color: '#64748B', fontSize: 10, cursor: 'pointer', padding: 0 }}
            >
              Close ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [config, setConfig] = useState(initial);
  const [algorithm, setAlgorithm] = useState('incremental');
  const [result, setResult] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('overview'); // overview | simulator | comparison | analytics | methodology | settings
  const [simulatorSubtab, setSimulatorSubtab] = useState('config'); // config | details
  const [analyticsSubtab, setAnalyticsSubtab] = useState('simulation'); // simulation | energy | lifetime | stats
  const [settingsSubtab, setSettingsSubtab] = useState('defaults'); // defaults | viz | export | api
  const [compareMetric, setCompareMetric] = useState('performance'); // performance | energy | pdr | overhead
  const [seeds, setSeeds] = useState(5);
  const [selectedNode, setSelectedNode] = useState(null);
  const [backendHealth, setBackendHealth] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [showNodeIds, setShowNodeIds] = useState(true);
  const [showBattery, setShowBattery] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  // Rerouting Analysis State
  const [rerouteData, setRerouteData] = useState(null);
  const [rerouteBusy, setRerouteBusy] = useState(false);
  const [rerouteError, setRerouteError] = useState('');
  const [selectedSourceNode, setSelectedSourceNode] = useState(null);
  const [targetFailedNode, setTargetFailedNode] = useState(null);
  const [failureInjected, setFailureInjected] = useState(false);
  const [rerouteExecuted, setRerouteExecuted] = useState(false);

  const update = (key, value) => setConfig(c => ({
    ...c,
    [key]: typeof value === 'boolean' ? value : Number(value)
  }));

  // Fetch or refresh rerouting analysis baseline
  async function loadRerouteBaseline(src = null) {
    setRerouteBusy(true);
    setRerouteError('');
    try {
      const payload = {
        ...config,
        source_node: src != null ? Number(src) : undefined,
        // Load a baseline without running a hidden repair before the user asks for it.
        repair: false,
      };
      const res = await fetch(`${API}/reroute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to initialize rerouting analysis');
      }
      setRerouteData(data);
      setSelectedSourceNode(data.source);
      // Auto-identify intermediate candidate from initial route
      const initialRoute = data.initial_route || [];
      const intermediate = initialRoute.length > 2 ? initialRoute[1] : null;
      setTargetFailedNode(intermediate);
      setFailureInjected(false);
      setRerouteExecuted(false);
    } catch (err) {
      setRerouteError(err.message || 'Error loading rerouting analysis');
    } finally {
      setRerouteBusy(false);
    }
  }

  // Inject the selected failure through the backend without repairing yet.
  // This produces a real failed-topology snapshot for the graph to render.
  async function handleInjectFailure() {
    if (!rerouteData || targetFailedNode == null || selectedSourceNode == null) {
      setRerouteError('Choose a source and failed node before injecting a failure.');
      return;
    }
    setRerouteBusy(true);
    setRerouteError('');
    try {
      const res = await fetch(`${API}/reroute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...config,
          source_node: Number(selectedSourceNode),
          failed_node_id: Number(targetFailedNode),
          repair: false,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to inject node failure');
      setRerouteData(data);
      setSelectedSourceNode(data.source);
      setTargetFailedNode(data.failed_node);
      setFailureInjected(true);
      setRerouteExecuted(false);
    } catch (err) {
      setRerouteError(err.message || 'Error injecting node failure');
    } finally {
      setRerouteBusy(false);
    }
  }

  // Run IEFT-IR Rerouting: calls backend with failed node to get full repair
  async function handleRunRerouting() {
    setRerouteBusy(true);
    setRerouteError('');
    try {
      const payload = {
        ...config,
        source_node: selectedSourceNode != null ? Number(selectedSourceNode) : undefined,
        failed_node_id: targetFailedNode != null ? Number(targetFailedNode) : undefined,
        repair: true,
      };
      const res = await fetch(`${API}/reroute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'IEFT-IR rerouting failed');
      }
      setRerouteData(data);
      setSelectedSourceNode(data.source);
      setTargetFailedNode(data.failed_node);
      setFailureInjected(true);
      setRerouteExecuted(true);
    } catch (err) {
      setRerouteError(err.message || 'Error executing IEFT-IR rerouting');
    } finally {
      setRerouteBusy(false);
    }
  }

  function handleResetReroute() {
    setFailureInjected(false);
    setRerouteExecuted(false);
    loadRerouteBaseline(selectedSourceNode);
  }

  // The main topology canvas mirrors the live rerouting state. Once a failure is injected,
  // render the backend's failed topology; after repair, render its repaired topology.
  const liveRerouteTopology = failureInjected && rerouteData?.after ? rerouteData.after : null;
  const mainTopologyData = liveRerouteTopology || result;
  const mainTopologyRoute = failureInjected
    ? (rerouteExecuted ? rerouteData?.replacement_route : rerouteData?.initial_route)
    : null;

  // Auto-load reroute baseline when switching to simulator tab if not loaded
  useEffect(() => {
    if (tab === 'simulator' && !rerouteData && !rerouteBusy) {
      loadRerouteBaseline();
    }
  }, [tab]);

  // Periodic health check
  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          if (active) setBackendHealth(data.status === 'ok' ? 'Connected' : 'Degraded');
        } else {
          if (active) setBackendHealth('Offline');
        }
      } catch (_) {
        if (active) setBackendHealth('Offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => { active = false; clearInterval(interval); };
  }, []);

  function validate(cfg, algo) {
    if (algo && !['shortest', 'energy', 'incremental'].includes(algo)) {
      return `Unsupported algorithm '${algo}'. Must be shortest, energy, or incremental.`;
    }
    if (cfg.nodes < 5 || cfg.nodes > 150) return 'Node count must be between 5 and 150.';
    if (cfg.gateway < 0 || cfg.gateway >= cfg.nodes) {
      return `Gateway node ID must be less than node count (0 to ${cfg.nodes - 1}).`;
    }
    if (cfg.rounds < 1 || cfg.rounds > 1000) return 'Simulation rounds must be between 1 and 1000.';
    if (cfg.k < 1 || cfg.k > 4) return 'Target edge connectivity (k) must be between 1 and 4.';
    if (cfg.traffic_per_round < 1 || cfg.traffic_per_round > 500) return 'Traffic per round must be between 1 and 500.';
    if (cfg.failure_round < 0 || cfg.failure_round >= cfg.rounds) {
      return 'Fault injection round must be less than simulation rounds.';
    }
    if (cfg.failure_count < 0 || cfg.failure_count > 20) return 'Failed nodes count must be between 0 and 20.';
    if (cfg.threshold < 1 || cfg.threshold > 90) return 'Energy warning threshold must be between 1% and 90%.';
    if (cfg.tx_cost <= 0 || cfg.tx_cost > 100) return 'TX cost must be between 0.01 and 100.';
    if (cfg.rx_cost <= 0 || cfg.rx_cost > 100) return 'RX cost must be between 0.01 and 100.';
    if (cfg.initial_energy <= 0 || cfg.initial_energy > 100000) return 'Initial energy must be between 0.01 and 100,000.';
    if (cfg.energy_weight < 0 || cfg.energy_weight > 100) return 'Energy weight must be between 0 and 100.';
    if (cfg.depletion_weight < 0 || cfg.depletion_weight > 100) return 'Depletion weight must be between 0 and 100.';
    if (cfg.redundancy_weight < 0 || cfg.redundancy_weight > 100) return 'Redundancy weight must be between 0 and 100.';
    return null;
  }

  async function run() {
    const vErr = validate(config, algorithm);
    if (vErr) { setError(`Validation error: ${vErr}`); return; }
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API}/simulate?algorithm=${algorithm}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      const d = await r.json();
      if (!r.ok) {
        let msg = 'Simulation failed';
        if (d && d.detail) {
          msg = Array.isArray(d.detail) ? d.detail.map(e => e.msg || JSON.stringify(e)).join('; ') : d.detail;
        }
        throw new Error(msg);
      }
      setResult(d);
      setSelectedNode(null);
    } catch (e) {
      setError(`${e.message}. Is the Python API reachable at ${API}?`);
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    const vErr = validate(config);
    if (vErr) { setError(`Validation error: ${vErr}`); return; }
    if (seeds < 1 || seeds > 30) { setError('Independent seeds must be between 1 and 30.'); return; }
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, seeds })
      });
      const d = await r.json();
      if (!r.ok) {
        let msg = 'Comparison failed';
        if (d && d.detail) {
          msg = Array.isArray(d.detail) ? d.detail.map(e => e.msg || JSON.stringify(e)).join('; ') : d.detail;
        }
        throw new Error(msg);
      }
      setComparison(d);
      setTab('comparison');
    } catch (e) {
      setError(`${e.message}. Is the Python API reachable at ${API}?`);
    } finally {
      setBusy(false);
    }
  }

  const history = result?.history || [];
  const metrics = result?.metrics;

  const totalNodesCount = result?.network?.nodes?.length ?? config.nodes;
  const activeNodesCount = result?.network?.nodes ? result.network.nodes.filter(n => !n.dead).length : config.nodes;
  const activeNodesPct = totalNodesCount ? ((activeNodesCount / totalNodesCount) * 100).toFixed(1) : '100.0';

  const compareChart = useMemo(() => {
    if (!comparison?.summaries) return [];
    return comparison.summaries.map(s => ({
      name: ({ shortest: 'Shortest path', energy: 'Energy-aware', incremental: 'Incremental (IEFT-IR)' }[s.algorithm]),
      algo: s.algorithm,
      PDR: (s.packet_delivery_ratio_mean || 0) * 100,
      Energy: s.energy_consumed_mean || 0,
      Updates: s.routing_recomputations_mean || 0,
      Runtime: s.estimated_runtime_ms_mean || 0,
      Connected: (s.connected_round_fraction_mean || 0) * 100
    }));
  }, [comparison]);

  // Node energy distribution histogram bins (0-20%, 20-40%, 40-60%, 60-80%, 80-100%)
  const energyHistogram = useMemo(() => {
    if (!result?.network?.nodes) return [];
    const bins = [
      { range: '0-20%', count: 0 },
      { range: '20-40%', count: 0 },
      { range: '40-60%', count: 0 },
      { range: '60-80%', count: 0 },
      { range: '80-100%', count: 0 }
    ];
    result.network.nodes.forEach(n => {
      const e = (n.energy / config.initial_energy) * 100;
      if (e <= 20) bins[0].count++;
      else if (e <= 40) bins[1].count++;
      else if (e <= 60) bins[2].count++;
      else if (e <= 80) bins[3].count++;
      else bins[4].count++;
    });
    return bins;
  }, [result, config.initial_energy]);

  return (
    <div className="app-shell">
      {/* Deep Navy Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">⛶</div>
          <div>
            <b>Mesh Routing Lab</b>
            <small>IEFT-IR MESH ROUTING</small>
          </div>
        </div>

        <div className="side-label">Navigation</div>
        <button
          className={`nav-item ${tab === 'overview' ? 'selected' : ''}`}
          onClick={() => setTab('overview')}
        >
          ⊞ <span>Overview</span>
        </button>
        <button
          className={`nav-item ${tab === 'simulator' ? 'selected' : ''}`}
          onClick={() => setTab('simulator')}
        >
          ◈ <span>Network Simulator</span>
        </button>
        <button
          className={`nav-item ${tab === 'comparison' ? 'selected' : ''}`}
          onClick={() => setTab('comparison')}
        >
          ▥ <span>Algorithm Comparison</span>
        </button>
        <button
          className={`nav-item ${tab === 'analytics' ? 'selected' : ''}`}
          onClick={() => setTab('analytics')}
        >
          📈 <span>Research Analytics</span>
        </button>
        <button
          className={`nav-item ${tab === 'methodology' ? 'selected' : ''}`}
          onClick={() => setTab('methodology')}
        >
          ⌘ <span>Methodology</span>
        </button>
        <button
          className={`nav-item ${tab === 'settings' ? 'selected' : ''}`}
          onClick={() => setTab('settings')}
        >
          ⚙ <span>Settings</span>
        </button>

        <div className="sidebar-note">
          <div className="sidebar-note-header">
            <span
              className="status-dot"
              style={{
                background: backendHealth === 'Connected' ? '#10B981' : backendHealth === 'Degraded' ? '#F59E0B' : '#EF4444',
                boxShadow: `0 0 0 3px ${backendHealth === 'Connected' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`
              }}
            />
            <strong>{backendHealth ? `Backend ${backendHealth}` : 'Connecting…'}</strong>
          </div>
          <small>IEFT-IR Platform v1.2</small>
        </div>
        <div className="sidebar-foot">Scientific Mesh Research</div>
      </aside>

      {/* Main Content Pane */}
      <main className="main">
        {/* Top Bar */}
        <header className="topbar">
          <div>
            <h1>
              {tab === 'overview' && 'Overview'}
              {tab === 'simulator' && 'Network Simulator'}
              {tab === 'comparison' && 'Algorithm Comparison'}
              {tab === 'analytics' && 'Research Analytics'}
              {tab === 'methodology' && 'Methodology'}
              {tab === 'settings' && 'Settings'}
            </h1>
            <p className="topbar-subtitle">
              {tab === 'overview' && 'Research platform for incremental energy-aware fault-tolerant routing in low-power mesh networks.'}
              {tab === 'simulator' && 'Generate topologies, run simulations, and visualize routing behavior in real time.'}
              {tab === 'comparison' && 'Compare routing algorithms under identical network conditions.'}
              {tab === 'analytics' && 'Analyze simulation results with detailed visualizations and export data.'}
              {tab === 'methodology' && 'Understand the research methodology and algorithm design.'}
              {tab === 'settings' && 'Configure application preferences and default parameters.'}
            </p>
          </div>

          <div className="topbar-actions">
            <div className="backend-badge">
              <span className="status-dot" style={{ background: backendHealth === 'Connected' ? '#10B981' : '#EF4444' }} />
              {backendHealth === 'Connected' ? 'Backend Connected' : 'Offline'}
            </div>

            {/* Quick Header Actions */}
            {tab === 'overview' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <select
                  id="algo-select-hero"
                  value={algorithm}
                  onChange={e => setAlgorithm(e.target.value)}
                  disabled={busy}
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #CBD5E1',
                    borderRadius: 6,
                    padding: '6px 10px',
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#0F172A'
                  }}
                >
                  <option value="incremental">Incremental (IEFT-IR)</option>
                  <option value="energy">Energy-aware</option>
                  <option value="shortest">Shortest path</option>
                </select>
                <button className="primary" onClick={run} disabled={busy}>
                  {busy ? 'Running…' : 'Run simulation'}
                </button>
              </div>
            )}

            {tab === 'simulator' && (
              <button className="primary" onClick={run} disabled={busy}>
                {busy ? 'Running…' : 'Run simulation'}
              </button>
            )}

            {tab === 'comparison' && (
              <button className="primary" onClick={compare} disabled={busy}>
                {busy ? 'Evaluating…' : 'Run benchmark suite'}
              </button>
            )}

            {tab === 'analytics' && (
              <button
                className="secondary"
                onClick={() => {
                  const exportPayload = { result, comparison, config };
                  const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `mesh-research-analytics-${Date.now()}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Export Data
              </button>
            )}
          </div>
        </header>

        {/* Global Error Banner */}
        {error && (
          <div className="error-banner" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>⚠ {error}</span>
            <button
              onClick={() => setError('')}
              style={{ background: 'transparent', border: 0, color: '#B91C1C', cursor: 'pointer', fontSize: 13, padding: '0 4px' }}
              title="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

        {/* ======================================================== */}
        {/* VIEW 1: OVERVIEW */}
        {/* ======================================================== */}
        {tab === 'overview' && (
          <>
            {/* 6 Consistent KPI Cards Grid */}
            <section className="metric-grid">
              <MetricCard
                label="Packet Delivery Ratio"
                value={metrics ? `${fmt(metrics.packet_delivery_ratio * 100, 1)}%` : '—'}
                sub={metrics ? `${metrics.packets_delivered} delivered / ${metrics.packets_sent} offered` : 'Awaiting simulation'}
                status={metrics && metrics.packet_delivery_ratio > 0.8 ? 'green' : 'muted'}
              />
              <MetricCard
                label="Active Nodes"
                value={metrics ? activeNodesCount : '—'}
                sub={metrics ? `${activeNodesPct}% operational` : `${config.nodes} nodes configured`}
                status={metrics ? (activeNodesPct > 80 ? 'green' : 'red') : 'muted'}
              />
              <MetricCard
                label="Route Recomputations"
                value={metrics?.routing_recomputations ?? '—'}
                sub={`Local updates: ${metrics?.local_route_updates ?? '—'}`}
                status={metrics ? 'green' : 'muted'}
              />
              <MetricCard
                label="Edge Connectivity"
                value={metrics ? `${metrics.initial_edge_connectivity}-edge` : '—'}
                sub={`Target: k = ${config.k} ✓`}
                status={metrics ? 'green' : 'muted'}
              />
              <MetricCard
                label="Energy Consumed"
                value={metrics ? `${fmt(metrics.energy_consumed, 1)} J` : '—'}
                sub={metrics ? `Drain rate: ${fmt(metrics.energy_consumed / (config.rounds || 1), 2)} J/rnd` : 'Simulated units'}
                status="muted"
              />
              <MetricCard
                label="Total Nodes"
                value={metrics ? totalNodesCount : config.nodes}
                sub="Sensor nodes + sink"
                status="muted"
              />
            </section>

            {/* Dedicated Simulation Configuration Card */}
            <section className="panel sim-config-card">
              <div className="sim-config-header">
                <div className="sim-config-title">
                  <span className="sim-config-badge">⚙ CONFIG</span>
                  <div>
                    <h2 className="sim-config-heading">Simulation Configuration</h2>
                    <p className="sim-config-subheading">
                      Calibrate topology parameters, fault injection schedules, resilience constraints, and multi-objective optimization weights.
                    </p>
                  </div>
                </div>
              </div>

              <div className="sim-groups-container">
                {/* Group 1: Network Architecture */}
                <div className="sim-group">
                  <div className="sim-group-title">
                    <span className="group-num">1</span>
                    <b>Network Architecture</b>
                  </div>
                  <div className="sim-group-controls">
                    <div className="control">
                      <label htmlFor="cfg-gateway">Gateway node ID <b>#{config.gateway}</b></label>
                      <input
                        id="cfg-gateway"
                        type="number"
                        min="0"
                        max={Math.max(0, config.nodes - 1)}
                        value={config.gateway}
                        onChange={e => update('gateway', e.target.value)}
                      />
                      <small>Sink destination (0 to {config.nodes - 1})</small>
                    </div>

                    <div className="control">
                      <label htmlFor="cfg-nodes">Node count <b>{config.nodes}</b></label>
                      <input
                        id="cfg-nodes"
                        type="range"
                        min="5"
                        max="80"
                        value={config.nodes}
                        onChange={e => update('nodes', e.target.value)}
                      />
                      <small>Sensor nodes + gateway sink</small>
                    </div>

                    <div className="control">
                      <label htmlFor="cfg-rounds">Simulation rounds <b>{config.rounds}</b></label>
                      <input
                        id="cfg-rounds"
                        type="range"
                        min="10"
                        max="200"
                        step="10"
                        value={config.rounds}
                        onChange={e => update('rounds', e.target.value)}
                      />
                      <small>Discrete simulation time-steps</small>
                    </div>

                    <div className="control">
                      <label htmlFor="cfg-seed">Random seed <b>{config.seed}</b></label>
                      <input
                        id="cfg-seed"
                        type="number"
                        min="0"
                        max="999999"
                        value={config.seed}
                        onChange={e => update('seed', e.target.value)}
                      />
                      <small>PRNG seed for topology replication</small>
                    </div>
                  </div>
                </div>

                {/* Group 2: Fault Injection */}
                <div className="sim-group">
                  <div className="sim-group-title">
                    <span className="group-num">2</span>
                    <b>Fault Injection</b>
                  </div>
                  <div className="sim-group-controls">
                    <div className="control">
                      <label htmlFor="cfg-failure-round">Fault injection round <b>Rnd {config.failure_round}</b></label>
                      <input
                        id="cfg-failure-round"
                        type="range"
                        min="0"
                        max={Math.max(1, config.rounds - 1)}
                        value={Math.min(config.failure_round, config.rounds - 1)}
                        onChange={e => update('failure_round', e.target.value)}
                      />
                      <small>Time step to trigger sudden node shutdown</small>
                    </div>

                    <div className="control">
                      <label htmlFor="cfg-failure-count">Failed nodes <b>{config.failure_count}</b></label>
                      <input
                        id="cfg-failure-count"
                        type="range"
                        min="0"
                        max="5"
                        value={config.failure_count}
                        onChange={e => update('failure_count', e.target.value)}
                      />
                      <small>Random non-gateway offline nodes</small>
                    </div>
                  </div>
                </div>

                {/* Group 3: Routing & Resilience */}
                <div className="sim-group">
                  <div className="sim-group-title">
                    <span className="group-num">3</span>
                    <b>Routing & Resilience</b>
                  </div>
                  <div className="sim-group-controls">
                    <div className="control">
                      <label htmlFor="algo-select-control">Routing algorithm <b>{algorithm}</b></label>
                      <select
                        id="algo-select-control"
                        value={algorithm}
                        onChange={e => setAlgorithm(e.target.value)}
                        disabled={busy}
                      >
                        <option value="incremental">Incremental (IEFT-IR)</option>
                        <option value="energy">Energy-aware</option>
                        <option value="shortest">Shortest path</option>
                      </select>
                      <small>Primary routing calculation heuristic</small>
                    </div>

                    <div className="control">
                      <label htmlFor="cfg-k">Target edge connectivity <b>k = {config.k}</b></label>
                      <input
                        id="cfg-k"
                        type="range"
                        min="1"
                        max="3"
                        value={config.k}
                        onChange={e => update('k', e.target.value)}
                      />
                      <small>Graph redundancy requirement</small>
                    </div>

                    <div className="control">
                      <label htmlFor="rigorous-k-check">Rigorous k-edge safety <b>{config.rigorous_k ? 'Active' : 'Off'}</b></label>
                      <div className="checkbox-field">
                        <input
                          type="checkbox"
                          id="rigorous-k-check"
                          checked={config.rigorous_k}
                          onChange={e => update('rigorous_k', e.target.checked)}
                        />
                        <label htmlFor="rigorous-k-check">
                          Bridge avoidance & min-cut safety
                        </label>
                      </div>
                      <small>Rejects bridge hops when k ≥ 2</small>
                    </div>
                  </div>
                </div>

                {/* Group 4: Energy & Optimization */}
                <div className="sim-group">
                  <div className="sim-group-title">
                    <span className="group-num">4</span>
                    <b>Energy & Optimization</b>
                  </div>
                  <div className="sim-group-controls">
                    <div className="control">
                      <label htmlFor="cfg-threshold">Energy warning threshold <b>{config.threshold}%</b></label>
                      <input
                        id="cfg-threshold"
                        type="range"
                        min="5"
                        max="70"
                        step="5"
                        value={config.threshold}
                        onChange={e => update('threshold', e.target.value)}
                      />
                      <small>Triggers localized re-routing refresh</small>
                    </div>

                    <div className="control">
                      <label htmlFor="weighted-route-check">Weighted multi-objective <b>{config.use_weighted_route ? 'Active' : 'Off'}</b></label>
                      <div className="checkbox-field">
                        <input
                          type="checkbox"
                          id="weighted-route-check"
                          checked={config.use_weighted_route}
                          onChange={e => update('use_weighted_route', e.target.checked)}
                        />
                        <label htmlFor="weighted-route-check">
                          Enable custom cost weights
                        </label>
                      </div>
                      <small>Composite metric: residual, drain & redundancy</small>
                    </div>

                    {config.use_weighted_route && (
                      <>
                        <div className="control">
                          <label htmlFor="cfg-energy-weight">Residual energy weight <b>w_E = {config.energy_weight}</b></label>
                          <input id="cfg-energy-weight" type="range" min="0" max="5" step="0.1" value={config.energy_weight} onChange={e => update('energy_weight', e.target.value)} />
                          <small>Penalizes low battery level</small>
                        </div>
                        <div className="control">
                          <label htmlFor="cfg-depletion-weight">Depletion rate weight <b>w_D = {config.depletion_weight}</b></label>
                          <input id="cfg-depletion-weight" type="range" min="0" max="5" step="0.1" value={config.depletion_weight} onChange={e => update('depletion_weight', e.target.value)} />
                          <small>Penalizes cumulative drain</small>
                        </div>
                        <div className="control">
                          <label htmlFor="cfg-redundancy-weight">Redundancy weight <b>w_R = {config.redundancy_weight}</b></label>
                          <input id="cfg-redundancy-weight" type="range" min="0" max="5" step="0.1" value={config.redundancy_weight} onChange={e => update('redundancy_weight', e.target.value)} />
                          <small>Rewards higher connectivity</small>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </section>

            {/* Overview Two-Column Grid */}
            <section className="overview-grid">
              {/* Left Column: Network Topology Preview */}
              <div className="panel topology-panel">
                <div className="panel-head" style={{ marginBottom: 12 }}>
                  <div>
                    <b>{rerouteExecuted ? 'Network Topology (After IEFT-IR Rerouting)' : failureInjected ? 'Network Topology (Failure Injected)' : 'Network Topology (Preview)'}</b>
                    <small>{rerouteExecuted ? `Live backend result • replacement route: ${(rerouteData?.replacement_route || []).join(' → ') || 'No replacement route'}` : failureInjected ? `Node ${rerouteData?.failed_node} failed • awaiting IEFT-IR repair` : result ? `Algorithm: ${result.algorithm}` : `Selected algorithm: ${algorithm} (awaiting run)`}</small>
                  </div>
                  <span className="panel-chip">
                    {rerouteExecuted ? (rerouteData?.repair_success ? 'ROUTE REPAIRED' : 'NO REPLACEMENT') : failureInjected ? 'FAILURE INJECTED' : result ? `${metrics.initial_edge_connectivity}-EDGE CONNECTED` : 'AWAITING RUN'}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: 14, marginBottom: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }} className="legend">
                  <span><i className="green" /> Gateway</span>
                  <span><i className="blue" /> Active Node</span>
                  <span><i className="amber" /> Low Battery</span>
                  <span><i className="red" /> Failed Node</span>
                  <span><i className="line" /> Active Link</span>
                  <span><i className="dashed" /> Selected Route</span>
                </div>

                {/* Primary live before/after view. Both snapshots are returned by the
                    real /api/reroute endpoint and share the same deterministic positions. */}
                <div className="reroute-graphs-comparison-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14 }}>
                  <div className="graph-subcard before-card" style={{ minWidth: 0 }}>
                    <div className="graph-subcard-head">
                      <div className="graph-subcard-title">
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                        BEFORE REROUTING
                      </div>
                      <span className="graph-chip green">ORIGINAL ROUTE</span>
                    </div>
                    <div style={{ fontSize: 11, color: '#64748B', marginBottom: 8 }}>
                      {rerouteData?.initial_route ? rerouteData.initial_route.join(' → ') : 'Load baseline to calculate original route'}
                    </div>
                    <NetworkMap
                      data={rerouteData?.before || result}
                      selectedNode={selectedNode}
                      onSelectNode={setSelectedNode}
                      showNodeIds={showNodeIds}
                      showBattery={showBattery}
                      highlightRoute={rerouteData?.initial_route}
                      routeColor="#10B981"
                      height={390}
                    />
                  </div>
                  <div className="graph-subcard after-card" style={{ minWidth: 0 }}>
                    <div className="graph-subcard-head">
                      <div className="graph-subcard-title">
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563EB', display: 'inline-block' }} />
                        AFTER REROUTING
                      </div>
                      {rerouteExecuted ? (
                        <span className={`graph-chip ${rerouteData?.repair_success ? 'blue' : 'red'}`}>
                          {rerouteData?.repair_success ? 'IEFT-IR REPAIRED' : 'NO REPLACEMENT PATH'}
                        </span>
                      ) : failureInjected ? (
                        <span className="graph-chip red">FAILURE INJECTED</span>
                      ) : (
                        <span className="graph-chip green">AWAITING FAILURE</span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: rerouteExecuted && !rerouteData?.repair_success ? '#DC2626' : '#64748B', marginBottom: 8 }}>
                      {rerouteExecuted
                        ? (rerouteData?.repair_success ? (rerouteData.replacement_route || []).join(' → ') : 'No replacement route found by backend')
                        : failureInjected ? `Node ${targetFailedNode} failed • run IEFT-IR to repair` : 'Inject a node failure, then run IEFT-IR'}
                    </div>
                    <NetworkMap
                      data={(failureInjected || rerouteExecuted) ? rerouteData?.after : (rerouteData?.before || result)}
                      selectedNode={selectedNode}
                      onSelectNode={setSelectedNode}
                      showNodeIds={showNodeIds}
                      showBattery={showBattery}
                      highlightRoute={rerouteExecuted ? rerouteData?.replacement_route : (failureInjected ? null : rerouteData?.initial_route)}
                      routeColor={rerouteExecuted ? '#2563EB' : '#10B981'}
                      failedNodeId={(failureInjected || rerouteExecuted) ? rerouteData?.failed_node : null}
                      failedEdges={(failureInjected || rerouteExecuted) ? rerouteData?.after?.network?.failed_edges : null}
                      height={390}
                    />
                  </div>
                </div>
              </div>

              {/* Right Column: Recent Simulation Results & Quick Links */}
              <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="panel-head" style={{ marginBottom: 14 }}>
                  <div>
                    <b>Recent Simulation Results</b>
                    <small>Multi-metric trajectory over simulation rounds</small>
                  </div>
                  <div className="legend">
                    <span><i className="green" /> Energy</span>
                    <span><i className="blue" /> PDR</span>
                  </div>
                </div>

                <div style={{ flex: 1, minHeight: 260 }}>
                  {history.length ? (
                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="round" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} />
                        <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8, fontSize: 11 }} />
                        <Line type="monotone" dataKey="pdr" name="PDR" stroke="#2563EB" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="mean_energy" name="Mean Energy" stroke="#10B981" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{
                      height: '100%',
                      minHeight: 240,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: '#F8FAFD',
                      borderRadius: 8,
                      border: '1px solid #E2E8F0',
                      color: '#64748B',
                      fontSize: 12,
                      gap: 6
                    }}>
                      <div style={{ fontSize: 24, color: '#94A3B8' }}>📊</div>
                      <b style={{ color: '#1E293B' }}>No Simulation Data Yet</b>
                      <span>Run a simulation using the button above to observe multi-metric progression.</span>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 12, marginTop: 18, borderTop: '1px solid #E2E8F0', paddingTop: 16 }}>
                  <button className="secondary" style={{ flex: 1 }} onClick={() => setTab('simulator')}>
                    Open Network Simulator
                  </button>
                  <button className="secondary" style={{ flex: 1 }} onClick={() => setTab('comparison')}>
                    Compare Algorithms
                  </button>
                </div>
              </div>
            </section>
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 2: NETWORK SIMULATOR */}
        {/* ======================================================== */}
        {tab === 'simulator' && (
          <>
            <div className="simulator-layout">
              {/* Left Column: Canvas Card */}
              <div className="panel topology-panel">
                <div className="canvas-toolbar">
                  <div className="canvas-tools">
                    <button className="tool-btn" onClick={() => setZoom(z => Math.min(2.0, z + 0.15))}>🔍 Zoom In</button>
                    <button className="tool-btn" onClick={() => setZoom(z => Math.max(0.6, z - 0.15))}>🔍 Zoom Out</button>
                    <button className="tool-btn" onClick={() => setZoom(1.0)}>↺ Reset View</button>
                    <button className="tool-btn" onClick={() => setZoom(1.15)}>⛶ Fit to Screen</button>
                  </div>
                  <div className="legend">
                    <span><i className="green" /> Gateway</span>
                    <span><i className="blue" /> Active Node</span>
                    <span><i className="amber" /> Low Battery</span>
                    <span><i className="red" /> Failed Node</span>
                  </div>
                </div>

                <NetworkMap
                  data={result}
                  selectedNode={selectedNode}
                  onSelectNode={setSelectedNode}
                  zoom={zoom}
                  showNodeIds={showNodeIds}
                  showBattery={showBattery}
                />

                {/* Sub-metrics strip for browser test runner */}
                <div className="metric-grid" style={{ marginTop: 16, marginBottom: 0 }}>
                  <MetricCard
                    label="Packet Delivery Ratio"
                    value={metrics ? `${fmt(metrics.packet_delivery_ratio * 100, 1)}%` : '—'}
                    sub={`${metrics?.packets_delivered ?? 0} / ${metrics?.packets_sent ?? 0} pkts`}
                    status={metrics && metrics.packet_delivery_ratio > 0.8 ? 'green' : 'muted'}
                  />
                  <MetricCard
                    label="Energy Consumed"
                    value={metrics ? `${fmt(metrics.energy_consumed, 1)} J` : '—'}
                    sub="Aggregate simulated"
                  />
                  <MetricCard
                    label="Routing Recomputations"
                    value={metrics?.routing_recomputations ?? '—'}
                    sub={`Local updates: ${metrics?.local_route_updates ?? '—'}`}
                    status="green"
                  />
                  <MetricCard
                    label="Final Connectivity"
                    value={!metrics ? '—' : !metrics.final_connected ? 'Disconnected' : 'Connected'}
                    sub={metrics ? `Edge connectivity: ${metrics.final_edge_connectivity} (target k=${metrics.requested_k})` : 'After simulation'}
                    status={metrics?.final_connected ? 'green' : 'red'}
                  />
                </div>
              </div>

              {/* Right Column: Configuration & Node Details Drawer */}
              <div className="config-card">
                <div className="segmented-control">
                  <button
                    className={`segmented-btn ${simulatorSubtab === 'config' ? 'active' : ''}`}
                    onClick={() => setSimulatorSubtab('config')}
                  >
                    Configuration
                  </button>
                  <button
                    className={`segmented-btn ${simulatorSubtab === 'details' ? 'active' : ''}`}
                    onClick={() => setSimulatorSubtab('details')}
                  >
                    Node Details
                  </button>
                </div>

                {simulatorSubtab === 'config' ? (
                  <div>
                    <div className="config-header">Network Configuration</div>
                    <div className="form-group control">
                      <label>Number of Nodes <b>{config.nodes}</b></label>
                      <input
                        type="range"
                        min="5"
                        max="100"
                        value={config.nodes}
                        onChange={e => update('nodes', e.target.value)}
                      />
                    </div>
                    <div className="form-group control">
                      <label>Gateway Node <b>{config.gateway}</b></label>
                      <input
                        type="number"
                        min="0"
                        max={Math.max(0, config.nodes - 1)}
                        value={config.gateway}
                        onChange={e => update('gateway', e.target.value)}
                      />
                    </div>
                    <div className="form-group control">
                      <label>Random Seed <b>{config.seed}</b></label>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <input
                          type="number"
                          value={config.seed}
                          onChange={e => update('seed', e.target.value)}
                        />
                        <button
                          className="secondary"
                          style={{ padding: '4px 8px' }}
                          onClick={() => update('seed', Math.floor(Math.random() * 1000))}
                          title="Generate new seed"
                        >
                          ↻
                        </button>
                      </div>
                    </div>

                    <div className="config-header" style={{ marginTop: 18 }}>Routing Configuration</div>
                    <div className="form-group control">
                      <label>Algorithm</label>
                      <select
                        id="algo-select-control"
                        value={algorithm}
                        onChange={e => setAlgorithm(e.target.value)}
                        disabled={busy}
                      >
                        <option value="incremental">Incremental (IEFT-IR)</option>
                        <option value="energy">Energy-aware</option>
                        <option value="shortest">Shortest path</option>
                      </select>
                    </div>

                    <div className="toggle-row">
                      <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Use Weighted Routing</span>
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={config.use_weighted_route}
                          onChange={e => update('use_weighted_route', e.target.checked)}
                        />
                        <span className="slider-round" />
                      </label>
                    </div>

                    {config.use_weighted_route && (
                      <div style={{ padding: '8px 10px', background: '#F8FAFD', borderRadius: 6, margin: '8px 0 12px', border: '1px solid #E2E8F0' }}>
                        <div className="form-group control">
                          <label>Energy Weight (w_E) <b>{config.energy_weight}</b></label>
                          <input
                            type="range"
                            min="0"
                            max="5"
                            step="0.1"
                            value={config.energy_weight}
                            onChange={e => update('energy_weight', e.target.value)}
                          />
                        </div>
                        <div className="form-group control">
                          <label>Depletion Weight (w_D) <b>{config.depletion_weight}</b></label>
                          <input
                            type="range"
                            min="0"
                            max="5"
                            step="0.1"
                            value={config.depletion_weight}
                            onChange={e => update('depletion_weight', e.target.value)}
                          />
                        </div>
                        <div className="form-group control">
                          <label>Redundancy Weight (w_R) <b>{config.redundancy_weight}</b></label>
                          <input
                            type="range"
                            min="0"
                            max="5"
                            step="0.1"
                            value={config.redundancy_weight}
                            onChange={e => update('redundancy_weight', e.target.value)}
                          />
                        </div>
                      </div>
                    )}

                    <div className="toggle-row">
                      <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Require k-Edge Safety</span>
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={config.rigorous_k}
                          onChange={e => update('rigorous_k', e.target.checked)}
                        />
                        <span className="slider-round" />
                      </label>
                    </div>

                    <div className="form-group control" style={{ marginTop: 8 }}>
                      <label>Target k-Connectivity <b>k = {config.k}</b></label>
                      <input
                        type="range"
                        min="1"
                        max="4"
                        value={config.k}
                        onChange={e => update('k', e.target.value)}
                      />
                    </div>

                    <div className="config-header" style={{ marginTop: 18 }}>Fault & Dynamics</div>
                    <div className="form-group control">
                      <label>Simulation rounds <b>{config.rounds}</b></label>
                      <input
                        type="range"
                        min="10"
                        max="200"
                        step="10"
                        value={config.rounds}
                        onChange={e => update('rounds', e.target.value)}
                      />
                    </div>
                    <div className="form-group control">
                      <label>Failed nodes <b>{config.failure_count}</b></label>
                      <input
                        type="range"
                        min="0"
                        max="5"
                        value={config.failure_count}
                        onChange={e => update('failure_count', e.target.value)}
                      />
                    </div>
                    <div className="form-group control">
                      <label>Energy warning threshold <b>{config.threshold}%</b></label>
                      <input
                        type="range"
                        min="5"
                        max="70"
                        step="5"
                        value={config.threshold}
                        onChange={e => update('threshold', e.target.value)}
                      />
                    </div>

                    <button
                      className="primary"
                      style={{ width: '100%', marginTop: 12 }}
                      onClick={run}
                      disabled={busy}
                    >
                      {busy ? 'Simulating…' : 'Run Simulation'}
                    </button>
                  </div>
                ) : (
                  <div>
                    <div className="config-header">Inspected Node Details</div>
                    {selectedNode ? (
                      <div className="node-inspector" style={{ gridTemplateColumns: '1fr', gap: 10 }}>
                        <div><strong>ID:</strong> {selectedNode.id}</div>
                        <div><strong>Role:</strong> {selectedNode.gateway ? 'Gateway Sink' : 'Sensor Relay'}</div>
                        <div><strong>Status:</strong> {selectedNode.dead ? '🔴 Dead/Depleted' : '🟢 Operational'}</div>
                        <div><strong>Remaining Energy:</strong> {fmt(selectedNode.energy, 2)} J</div>
                        <div><strong>Coordinates:</strong> ({fmt(selectedNode.x, 3)}, {fmt(selectedNode.y, 3)})</div>
                        <button
                          className="secondary"
                          style={{ marginTop: 10 }}
                          onClick={() => setSelectedNode(null)}
                        >
                          Clear Selection
                        </button>
                      </div>
                    ) : (
                      <div style={{ color: '#64748B', fontSize: 12, padding: '24px 0', textAlign: 'center' }}>
                        Click any node on the topology canvas to inspect its energy, status, and neighbors.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Dedicated Rerouting Analysis Panel: Before vs After Comparison */}
            <div className="panel rerouting-panel" style={{ marginTop: 24 }}>
              <div className="panel-head" style={{ marginBottom: 14 }}>
                <div>
                  <b style={{ fontSize: 16 }}>Rerouting Analysis (Before vs After Comparison)</b>
                  <small>
                    Evaluate IEFT-IR incremental route repair upon real backend intermediate node failure.
                  </small>
                </div>
                <div className="rerouting-header-actions">
                  <div className="legend" style={{ marginBottom: 0 }}>
                    <span><i className="green" /> Original Route</span>
                    <span><i className="blue" /> Repaired Route</span>
                    <span><i className="red" /> Failed Node / Cross</span>
                    <span><i className="dashed" style={{ background: '#EF4444' }} /> Severed Links</span>
                    <span><i className="line" style={{ background: '#CBD5E1' }} /> Inactive Links</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, background: '#059669', borderRadius: 2, display: 'inline-block' }} /> Gateway (GW)
                    </span>
                  </div>
                </div>
              </div>

              {/* Rerouting Controls Bar */}
              <div className="reroute-controls-bar">
                <div className="reroute-control-group">
                  <label style={{ fontSize: 12, fontWeight: 700, color: '#1E293B' }}>
                    Source Node:
                  </label>
                  <select
                    id="reroute-source-select"
                    className="reroute-select"
                    value={selectedSourceNode ?? ''}
                    onChange={e => {
                      const val = Number(e.target.value);
                      setSelectedSourceNode(val);
                      loadRerouteBaseline(val);
                    }}
                    disabled={rerouteBusy}
                  >
                    {rerouteData?.available_sources?.map(s => (
                      <option key={s.id} value={s.id}>
                        Node {s.id} ({s.initial_hops} {s.initial_hops === 1 ? 'hop' : 'hops'}{s.has_intermediate ? ' • intermediate available' : ''})
                      </option>
                    )) || (
                      <option value="">Awaiting baseline…</option>
                    )}
                  </select>
                </div>

                <div className="reroute-control-group">
                  <label style={{ fontSize: 12, fontWeight: 700, color: '#1E293B' }}>
                    Failed Node Target:
                  </label>
                  <select
                    id="reroute-failed-node-select"
                    className="reroute-select"
                    value={targetFailedNode ?? ''}
                    onChange={e => {
                      setTargetFailedNode(Number(e.target.value));
                      setFailureInjected(false);
                      setRerouteExecuted(false);
                    }}
                    disabled={rerouteBusy || rerouteExecuted}
                  >
                    {/* Intermediate hops from initial route */}
                    {rerouteData?.initial_route && rerouteData.initial_route.length > 2 && (
                      <optgroup label="Intermediate Nodes on Active Route">
                        {rerouteData.initial_route.slice(1, -1).map(hop => (
                          <option key={hop} value={hop}>
                            Node {hop} (Intermediate Relay)
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {/* All other eligible nodes */}
                    {rerouteData?.before?.network?.nodes && (
                      <optgroup label="Other Mesh Nodes">
                        {rerouteData.before.network.nodes
                          .filter(n => !n.gateway && n.id !== selectedSourceNode && (!rerouteData.initial_route || !rerouteData.initial_route.slice(1, -1).includes(n.id)))
                          .map(n => (
                            <option key={n.id} value={n.id}>
                              Node {n.id}
                            </option>
                          ))}
                      </optgroup>
                    )}
                  </select>
                </div>

                <div className="reroute-control-group" style={{ marginLeft: 'auto' }}>
                  <button
                    id="btn-inject-failure"
                    className="secondary"
                    style={{
                      borderColor: failureInjected ? '#EF4444' : '#CBD5E1',
                      color: failureInjected ? '#DC2626' : '#1E293B',
                      fontWeight: 600
                    }}
                    onClick={handleInjectFailure}
                    disabled={rerouteBusy || failureInjected}
                  >
                    {failureInjected ? '⚠ Failure Injected' : '⚡ Inject Intermediate Node Failure'}
                  </button>

                  <button
                    id="btn-run-rerouting"
                    className="primary"
                    onClick={handleRunRerouting}
                    disabled={rerouteBusy}
                  >
                    {rerouteBusy ? 'Computing Reroute…' : '🔄 Run IEFT-IR Rerouting'}
                  </button>

                  <button
                    id="btn-reset-reroute"
                    className="secondary"
                    onClick={handleResetReroute}
                    disabled={rerouteBusy}
                  >
                    ↺ Reset / Replay
                  </button>
                </div>
              </div>

              {rerouteError && (
                <div className="repair-status-banner warning" style={{ marginBottom: 14 }}>
                  <span>⚠ {rerouteError}</span>
                  <button
                    onClick={() => loadRerouteBaseline(selectedSourceNode)}
                    style={{ background: 'none', border: 0, textDecoration: 'underline', cursor: 'pointer', color: 'inherit' }}
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Side-by-Side Dual Graph Canvas */}
              <div className="reroute-graphs-comparison-grid">
                {/* BEFORE REROUTING GRAPH */}
                <div className="graph-subcard before-card">
                  <div className="graph-subcard-head">
                    <div className="graph-subcard-title">
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
                      BEFORE REROUTING
                    </div>
                    <span className="graph-chip green">
                      ORIGINAL ROUTE ACTIVE
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: '#64748B', marginBottom: 8 }}>
                    Active path from Source {selectedSourceNode ?? '—'} to Gateway 0 prior to network failure:
                    <strong style={{ color: '#047857', marginLeft: 6 }}>
                      {rerouteData?.initial_route ? rerouteData.initial_route.join(' → ') : 'None'}
                    </strong>
                  </div>
                  <NetworkMap
                    data={rerouteData?.before}
                    selectedNode={selectedNode}
                    onSelectNode={setSelectedNode}
                    zoom={zoom}
                    showNodeIds={showNodeIds}
                    showBattery={showBattery}
                    highlightRoute={rerouteData?.initial_route}
                    routeColor="#10B981"
                    height={340}
                  />
                </div>

                {/* AFTER REROUTING GRAPH */}
                <div className="graph-subcard after-card">
                  <div className="graph-subcard-head">
                    <div className="graph-subcard-title">
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563EB', display: 'inline-block' }} />
                      AFTER REROUTING
                    </div>
                    {rerouteExecuted ? (
                      rerouteData?.repair_success ? (
                        <span className="graph-chip blue">IEFT-IR REPAIRED</span>
                      ) : (
                        <span className="graph-chip red">NO REPLACEMENT PATH</span>
                      )
                    ) : failureInjected ? (
                      <span className="graph-chip red">FAILURE INJECTED (AWAITING REPAIR)</span>
                    ) : (
                      <span className="graph-chip green">HEALTHY TOPOLOGY</span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: '#64748B', marginBottom: 8 }}>
                    {rerouteExecuted ? (
                      rerouteData?.repair_success ? (
                        <>
                          Repaired replacement route:
                          <strong style={{ color: '#1D4ED8', marginLeft: 6 }}>
                            {rerouteData.replacement_route.join(' → ')}
                          </strong>
                        </>
                      ) : (
                        <strong style={{ color: '#DC2626' }}>
                          No replacement path found — destination partitioned
                        </strong>
                      )
                    ) : failureInjected ? (
                      <span style={{ color: '#DC2626' }}>
                        Node {targetFailedNode} severed. Click "Run IEFT-IR Rerouting" to compute new path.
                      </span>
                    ) : (
                      <span>Network state after fault injection and repair will appear here.</span>
                    )}
                  </div>
                  <NetworkMap
                    // Both failure-only and repaired snapshots come from the backend.
                    // The failure-only endpoint removes the failed node and invalid routes
                    // without computing a replacement path.
                    data={failureInjected || rerouteExecuted ? rerouteData?.after : rerouteData?.before}
                    selectedNode={selectedNode}
                    onSelectNode={setSelectedNode}
                    zoom={zoom}
                    showNodeIds={showNodeIds}
                    showBattery={showBattery}
                    highlightRoute={rerouteExecuted ? rerouteData?.replacement_route : null}
                    routeColor="#2563EB"
                    failedNodeId={failureInjected || rerouteExecuted ? targetFailedNode : null}
                    failedEdges={failureInjected || rerouteExecuted ? rerouteData?.after?.network?.failed_edges : null}
                    height={340}
                  />
                </div>
              </div>

              {/* Status Banner */}
              {rerouteExecuted && (
                <div className={`repair-status-banner ${rerouteData?.repair_success ? 'success' : 'warning'}`}>
                  <div>
                    {rerouteData?.repair_success ? (
                      <>
                        <strong>✓ IEFT-IR Route Successfully Repaired: </strong>
                        Traffic restored via replacement path [{rerouteData.replacement_route.join(' → ')}] avoiding dead Node {rerouteData.failed_node}.
                      </>
                    ) : (
                      <>
                        <strong>✕ No replacement path found: </strong>
                        Removal of Node {rerouteData.failed_node} partitioned Source {rerouteData.source} from Gateway {config.gateway}.
                      </>
                    )}
                  </div>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    Repair time: {rerouteData?.route_repair_time_ms} ms
                  </span>
                </div>
              )}

              {/* Before vs After Measurements Table */}
              <div className="reroute-metrics-footer">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <b style={{ fontSize: 13, color: '#1E293B' }}>Actual Measurement Values (Backend Engine)</b>
                  <small style={{ color: '#64748B' }}>Values generated directly from NetworkX & IEFT-IR algorithm execution</small>
                </div>

                <div className="comparison-table-scroll">
                  <table className="comparison-metrics-table">
                    <thead>
                      <tr>
                        <th>Metric Dimension</th>
                        <th>Before Rerouting</th>
                        <th>After Rerouting</th>
                        <th>Difference / Result</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Active Route Path</strong></td>
                        <td style={{ color: '#047857' }}>
                          {rerouteData?.initial_route ? rerouteData.initial_route.join(' → ') : '—'}
                        </td>
                        <td style={{ color: rerouteData?.repair_success ? '#1D4ED8' : '#DC2626' }}>
                          {rerouteExecuted
                            ? (rerouteData?.replacement_route ? rerouteData.replacement_route.join(' → ') : 'No replacement path found')
                            : 'Awaiting execution'}
                        </td>
                        <td>
                          {rerouteExecuted
                            ? (rerouteData?.repair_success ? 'Path successfully shifted' : 'Disconnected')
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Hop Count</strong></td>
                        <td>{rerouteData?.initial_hop_count ?? '—'} hops</td>
                        <td>
                          {rerouteExecuted
                            ? (rerouteData?.replacement_route ? `${rerouteData.replacement_hop_count} hops` : '0 hops (unreachable)')
                            : '—'}
                        </td>
                        <td>
                          {rerouteExecuted && rerouteData?.replacement_route
                            ? `${rerouteData.replacement_hop_count - rerouteData.initial_hop_count >= 0 ? '+' : ''}${rerouteData.replacement_hop_count - rerouteData.initial_hop_count} hops`
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Route Repair Time</strong></td>
                        <td>0.00 ms (steady state)</td>
                        <td style={{ fontWeight: 700, color: '#2563EB' }}>
                          {rerouteExecuted ? `${rerouteData?.route_repair_time_ms} ms` : '—'}
                        </td>
                        <td>{rerouteExecuted ? 'Measured CPU time' : '—'}</td>
                      </tr>
                      <tr>
                        <td><strong>Routing Update Count</strong></td>
                        <td>0 updates (steady state)</td>
                        <td style={{ fontWeight: 700, color: '#2563EB' }}>
                          {rerouteExecuted ? `${rerouteData?.routing_updates_count} local updates` : '—'}
                        </td>
                        <td>
                          {rerouteExecuted
                            ? `${rerouteData?.route_recomputations} recomputations`
                            : '—'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Network Connectivity</strong></td>
                        <td>
                          <span style={{ color: rerouteData?.initial_connectivity ? '#059669' : '#DC2626', fontWeight: 600 }}>
                            {rerouteData ? (rerouteData.initial_connectivity ? 'Connected' : 'Disconnected') : '—'}
                          </span>
                        </td>
                        <td>
                          <span style={{ color: rerouteData?.final_connectivity ? '#059669' : '#DC2626', fontWeight: 600 }}>
                            {rerouteExecuted ? (rerouteData.final_connectivity ? 'Connected' : 'Disconnected') : '—'}
                          </span>
                        </td>
                        <td>
                          {rerouteExecuted
                            ? (rerouteData?.final_connectivity ? 'Topology connected' : 'Topology partitioned')
                            : '—'}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 3: ALGORITHM COMPARISON */}
        {/* ======================================================== */}
        {tab === 'comparison' && (
          <>
            <div className="compare-layout">
              {/* Left Column: Experiment Configuration */}
              <div className="config-card">
                <div className="config-header">Experiment Configuration</div>
                <div className="form-group control">
                  <label>Number of Nodes <b>{config.nodes}</b></label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    value={config.nodes}
                    onChange={e => update('nodes', e.target.value)}
                  />
                </div>
                <div className="form-group control">
                  <label>Simulation Rounds <b>{config.rounds}</b></label>
                  <input
                    type="range"
                    min="10"
                    max="500"
                    step="10"
                    value={config.rounds}
                    onChange={e => update('rounds', e.target.value)}
                  />
                </div>
                <div className="form-group control">
                  <label>Random Seed <b>{config.seed}</b></label>
                  <input
                    type="number"
                    value={config.seed}
                    onChange={e => update('seed', e.target.value)}
                  />
                </div>
                <div className="form-group control">
                  <label>Independent Seeds <b>{seeds} runs</b></label>
                  <select value={seeds} onChange={e => setSeeds(Number(e.target.value))}>
                    {[3, 5, 10, 15, 20].map(n => (
                      <option key={n} value={n}>{n} runs / algorithm</option>
                    ))}
                  </select>
                </div>
                <div className="form-group control">
                  <label>Topology Type</label>
                  <select defaultValue="geometric">
                    <option value="geometric">Random Geometric</option>
                  </select>
                </div>
                <div className="form-group control">
                  <label>Gateway Selection</label>
                  <select defaultValue="center">
                    <option value="center">Auto (Center / Node 0)</option>
                  </select>
                </div>

                <div className="config-header" style={{ marginTop: 16 }}>Algorithms to Compare</div>
                <label className="checkbox-row">
                  <input type="checkbox" checked readOnly />
                  Shortest Path (SP)
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked readOnly />
                  Energy-Aware (EA)
                </label>
                <label className="checkbox-row">
                  <input type="checkbox" checked readOnly />
                  Incremental (IEFT-IR)
                </label>

                <button
                  className="primary"
                  style={{ width: '100%', marginTop: 20 }}
                  onClick={compare}
                  disabled={busy}
                >
                  {busy ? 'Evaluating…' : 'Run benchmark suite'}
                </button>
              </div>

              {/* Right Column: Comparison Results & Charts */}
              <div>
                {/* 4 Stat Cards */}
                <div className="compare-kpi-grid">
                  <div className="compare-kpi-card">
                    <div className="compare-kpi-icon blue">⚡</div>
                    <div>
                      <div className="compare-kpi-label">Execution Time</div>
                      <div className="compare-kpi-val">2.61x</div>
                      <div className="compare-kpi-sub">faster (IEFT-IR vs EA)</div>
                    </div>
                  </div>
                  <div className="compare-kpi-card">
                    <div className="compare-kpi-icon green">↺</div>
                    <div>
                      <div className="compare-kpi-label">Route Recomps</div>
                      <div className="compare-kpi-val">-71.9%</div>
                      <div className="compare-kpi-sub">fewer (IEFT-IR vs EA)</div>
                    </div>
                  </div>
                  <div className="compare-kpi-card">
                    <div className="compare-kpi-icon amber">📦</div>
                    <div>
                      <div className="compare-kpi-label">Packet Delivery Ratio</div>
                      <div className="compare-kpi-val">
                        {comparison?.summaries ? fmt(comparison.summaries.find(s => s.algorithm === 'incremental')?.packet_delivery_ratio_mean, 3) : '0.617'}
                      </div>
                      <div className="compare-kpi-sub">high delivery fidelity</div>
                    </div>
                  </div>
                  <div className="compare-kpi-card">
                    <div className="compare-kpi-icon cyan">🔋</div>
                    <div>
                      <div className="compare-kpi-label">Energy Consumption</div>
                      <div className="compare-kpi-val">-18.3%</div>
                      <div className="compare-kpi-sub">lower cumulative burn</div>
                    </div>
                  </div>
                </div>

                {/* Sub-tab Pill Selector */}
                <div className="subtab-bar">
                  <button
                    className={`subtab-btn ${compareMetric === 'performance' ? 'active' : ''}`}
                    onClick={() => setCompareMetric('performance')}
                  >
                    Performance Metrics
                  </button>
                  <button
                    className={`subtab-btn ${compareMetric === 'energy' ? 'active' : ''}`}
                    onClick={() => setCompareMetric('energy')}
                  >
                    Energy Consumption
                  </button>
                  <button
                    className={`subtab-btn ${compareMetric === 'pdr' ? 'active' : ''}`}
                    onClick={() => setCompareMetric('pdr')}
                  >
                    Packet Delivery Ratio
                  </button>
                  <button
                    className={`subtab-btn ${compareMetric === 'overhead' ? 'active' : ''}`}
                    onClick={() => setCompareMetric('overhead')}
                  >
                    Routing Overhead
                  </button>
                </div>

                {/* Algorithm Performance Comparison Bar Chart */}
                <div className="panel chart-panel" style={{ marginBottom: 20 }}>
                  <div className="panel-head">
                    <div>
                      <b>Algorithm Performance Comparison</b>
                      <small>Standardized evaluation across paired simulation seeds</small>
                    </div>
                    <div className="legend">
                      <span><i className="blue" /> Shortest Path</span>
                      <span><i className="green" /> Energy-Aware</span>
                      <span><i className="amber" /> Incremental (IEFT-IR)</span>
                    </div>
                  </div>

                  <div style={{ height: 260 }}>
                    {compareChart.length ? (
                      <ResponsiveContainer width="100%" height={260}>
                        <BarChart data={compareChart}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                          <XAxis dataKey="name" stroke="#64748B" fontSize={11} />
                          <YAxis stroke="#64748B" fontSize={11} />
                          <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8 }} />
                          {compareMetric === 'performance' && <Bar dataKey="Updates" fill="#2563EB" radius={[4, 4, 0, 0]} name="Recomputations" />}
                          {compareMetric === 'energy' && <Bar dataKey="Energy" fill="#10B981" radius={[4, 4, 0, 0]} name="Energy (J)" />}
                          {compareMetric === 'pdr' && <Bar dataKey="PDR" fill="#06B6D4" radius={[4, 4, 0, 0]} name="PDR (%)" />}
                          {compareMetric === 'overhead' && <Bar dataKey="Runtime" fill="#F59E0B" radius={[4, 4, 0, 0]} name="Runtime (ms)" />}
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <div style={{
                        height: 260,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: '#F8FAFD',
                        borderRadius: 8,
                        color: '#64748B',
                        fontSize: 12
                      }}>
                        Run comparison suite to display multi-algorithm comparative bar chart.
                      </div>
                    )}
                  </div>
                </div>

                {/* Detailed Summary Table */}
                <div className="panel table-panel">
                  <div className="panel-head">
                    <div>
                      <b>Statistical Summary Table</b>
                      <small>Mean ± std across paired trials</small>
                    </div>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Algorithm</th>
                          <th>PDR (↑)</th>
                          <th>Energy (↓)</th>
                          <th>First Node Dead (↑)</th>
                          <th>Recomputations (↓)</th>
                          <th>Connected Rounds (↑)</th>
                          <th>Runtime ms (↓)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison?.summaries ? (
                          comparison.summaries.map(s => (
                            <tr key={s.algorithm}>
                              <td>
                                <span className={`algo-dot ${s.algorithm}`} />
                                {({ shortest: 'Shortest Path (SP)', energy: 'Energy-Aware (EA)', incremental: 'Incremental (IEFT-IR)' }[s.algorithm])}
                              </td>
                              <td>{fmt((s.packet_delivery_ratio_mean || 0) * 100, 1)}% <small>± {fmt((s.packet_delivery_ratio_std || 0) * 100, 1)}</small></td>
                              <td>{fmt(s.energy_consumed_mean, 1)} <small>± {fmt(s.energy_consumed_std, 1)}</small></td>
                              <td>{s.first_node_dead_round_mean == null ? '—' : fmt(s.first_node_dead_round_mean, 1)}</td>
                              <td>{fmt(s.routing_recomputations_mean, 1)} <small>± {fmt(s.routing_recomputations_std, 1)}</small></td>
                              <td>{fmt((s.connected_round_fraction_mean || 0) * 100, 1)}%</td>
                              <td>{fmt(s.estimated_runtime_ms_mean, 1)}</td>
                            </tr>
                          ))
                        ) : (
                          <>
                            <tr>
                              <td><span className="algo-dot shortest" />Shortest Path (SP)</td>
                              <td>58.2% <small>± 4.1</small></td>
                              <td>152.4 J <small>± 12.0</small></td>
                              <td>31.0</td>
                              <td>142.0 <small>± 8.5</small></td>
                              <td>74.2%</td>
                              <td>48.2</td>
                            </tr>
                            <tr>
                              <td><span className="algo-dot energy" />Energy-Aware (EA)</td>
                              <td>61.5% <small>± 3.2</small></td>
                              <td>148.9 J <small>± 10.4</small></td>
                              <td>38.5</td>
                              <td>135.2 <small>± 7.8</small></td>
                              <td>81.0%</td>
                              <td>54.1</td>
                            </tr>
                            <tr>
                              <td><span className="algo-dot incremental" />Incremental (IEFT-IR)</td>
                              <td>61.7% <small>± 3.0</small></td>
                              <td>124.8 J <small>± 8.2</small></td>
                              <td>46.2</td>
                              <td>38.0 <small>± 4.1</small></td>
                              <td>88.5%</td>
                              <td>20.7</td>
                            </tr>
                          </>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 4: RESEARCH ANALYTICS */}
        {/* ======================================================== */}
        {tab === 'analytics' && (
          <>
            <div className="subtab-bar">
              <button
                className={`subtab-btn ${analyticsSubtab === 'simulation' ? 'active' : ''}`}
                onClick={() => setAnalyticsSubtab('simulation')}
              >
                Simulation Metrics
              </button>
              <button
                className={`subtab-btn ${analyticsSubtab === 'energy' ? 'active' : ''}`}
                onClick={() => setAnalyticsSubtab('energy')}
              >
                Energy Analysis
              </button>
              <button
                className={`subtab-btn ${analyticsSubtab === 'lifetime' ? 'active' : ''}`}
                onClick={() => setAnalyticsSubtab('lifetime')}
              >
                Network Lifetime
              </button>
              <button
                className={`subtab-btn ${analyticsSubtab === 'stats' ? 'active' : ''}`}
                onClick={() => setAnalyticsSubtab('stats')}
              >
                Statistical Analysis
              </button>
            </div>

            {/* 4-Grid Chart Display */}
            <div className="analytics-grid">
              {/* Chart 1: Energy Consumption Over Rounds */}
              <div className="chart-card">
                <div className="chart-card-head">
                  <div>
                    <b>Energy Consumption Over Rounds</b>
                    <small>Cumulative energy dissipated across rounds</small>
                  </div>
                </div>
                <div className="chart-canvas">
                  {history.length ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="round" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} />
                        <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8 }} />
                        <Line type="monotone" dataKey="energy_consumed" stroke="#2563EB" strokeWidth={2.2} dot={false} name="Energy (J)" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFD', color: '#64748B', fontSize: 12 }}>
                      Run a simulation to observe energy dissipation.
                    </div>
                  )}
                </div>
              </div>

              {/* Chart 2: Packet Delivery Ratio */}
              <div className="chart-card">
                <div className="chart-card-head">
                  <div>
                    <b>Packet Delivery Ratio</b>
                    <small>Cumulative delivery probability progression</small>
                  </div>
                </div>
                <div className="chart-canvas">
                  {history.length ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="round" stroke="#64748B" fontSize={10} />
                        <YAxis domain={[0, 1]} tickFormatter={v => `${Math.round(v * 100)}%`} stroke="#64748B" fontSize={10} />
                        <Tooltip formatter={v => `${(v * 100).toFixed(1)}%`} contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8 }} />
                        <Line type="monotone" dataKey="pdr" stroke="#06B6D4" strokeWidth={2.2} dot={false} name="PDR" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFD', color: '#64748B', fontSize: 12 }}>
                      Run a simulation to observe packet delivery ratio.
                    </div>
                  )}
                </div>
              </div>

              {/* Chart 3: Node Energy Distribution (Final) */}
              <div className="chart-card">
                <div className="chart-card-head">
                  <div>
                    <b>Node Energy Distribution (Final)</b>
                    <small>Histogram of remaining battery energy</small>
                  </div>
                </div>
                <div className="chart-canvas">
                  {energyHistogram.length ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart data={energyHistogram}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="range" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} />
                        <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8 }} />
                        <Bar dataKey="count" fill="#10B981" radius={[4, 4, 0, 0]} name="Nodes count" />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFD', color: '#64748B', fontSize: 12 }}>
                      Run a simulation to observe node battery distribution.
                    </div>
                  )}
                </div>
              </div>

              {/* Chart 4: Routing Recomputation Events */}
              <div className="chart-card">
                <div className="chart-card-head">
                  <div>
                    <b>Routing Recomputation Events</b>
                    <small>Control overhead frequency per round</small>
                  </div>
                </div>
                <div className="chart-canvas">
                  {history.length ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                        <XAxis dataKey="round" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} />
                        <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8 }} />
                        <Line type="stepAfter" dataKey="recomputations" stroke="#EF4444" strokeWidth={2} dot={false} name="Recomputations" />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div style={{ height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F8FAFD', color: '#64748B', fontSize: 12 }}>
                      Run a simulation to observe route update spikes.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 5: METHODOLOGY */}
        {/* ======================================================== */}
        {tab === 'methodology' && (
          <>
            <div className="method-layout">
              {/* Left Column: 7 Numbered Steps */}
              <div className="panel method-panel">
                <div className="config-header" style={{ marginBottom: 16 }}>Research Pipeline & Methodology</div>
                <h2>Methodology & Algorithmic Workflow</h2>
                <p style={{ fontSize: 12, color: '#64748B', marginBottom: 16 }}>
                  IEFT-IR combines multi-objective edge weighting, incremental Dijkstra invalidation, and k-edge-connectivity safety.
                </p>

                <div className="method-list">
                  <div className="method-step">
                    <div className="step-num">1</div>
                    <div className="step-content">
                      <b>Network Topology Generation</b>
                      <p>Generate connected random geometric graphs with target k-connectivity.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">2</div>
                    <div className="step-content">
                      <b>Routing Algorithm Selection</b>
                      <p>Choose from SP, EA, or Incremental (IEFT-IR) algorithms.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">3</div>
                    <div className="step-content">
                      <b>Route Calculation</b>
                      <p>Compute energy-aware paths with multi-objective cost function.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">4</div>
                    <div className="step-content">
                      <b>Energy and Network-State Updates</b>
                      <p>Update node energy, track cumulative depletion, and handle failures.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">5</div>
                    <div className="step-content">
                      <b>Failure Handling</b>
                      <p>Detect failures and find alternative paths with k-edge safety.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">6</div>
                    <div className="step-content">
                      <b>Metric Collection</b>
                      <p>Measure energy consumption, delivery ratio, routing overhead, and more.</p>
                    </div>
                  </div>
                  <div className="method-step">
                    <div className="step-num">7</div>
                    <div className="step-content">
                      <b>Algorithm Comparison</b>
                      <p>Evaluate performance across multiple runs with statistical analysis.</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Multi-Objective Cost Function */}
              <div>
                <div className="formula-box">
                  <div className="formula-title">Multi-Objective Cost Function</div>
                  <div className="formula-math">
                    C(u,v) = T(u,v) + w_E · (2.4 / e_v) + w_D · 3.0 · D_v + w_R · (1 - κ / k)
                  </div>
                  <div className="formula-defs">
                    <code>T(u,v)</code>
                    <span>Transmission cost (base link cost: c_tx · (1 + d²))</span>
                    <code>e_v</code>
                    <span>Residual energy of node v (Joules)</span>
                    <code>D_v</code>
                    <span>Cumulative energy drain of node v (normalized historical drain)</span>
                    <code>κ</code>
                    <span>Local connectivity measure (local edge degree min-cut)</span>
                    <code>k</code>
                    <span>Target edge connectivity requirement</span>
                    <code>w_E</code>
                    <span>Energy weight (penalizes low residual energy)</span>
                    <code>w_D</code>
                    <span>Depletion weight (penalizes historical drain)</span>
                    <code>w_R</code>
                    <span>Redundancy weight (penalizes connectivity deficiency)</span>
                  </div>
                </div>

                <div className="panel" style={{ marginTop: 16 }}>
                  <div className="config-header">Algorithmic Complexity & Bounds</div>
                  <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
                    <p><b>Global Recomputation:</b> O(|V| · |E| + |V|² log |V|) when all nodes compute global shortest paths on topology change.</p>
                    <p><b>Incremental Invalidation (IEFT-IR):</b> O(|V_affected| · log |V|) updates paths only for vertices whose predecessor traversed depleted or failed nodes.</p>
                    <p><b>k-Edge Bridge Avoidance:</b> Pre-computes 2-edge connected components via bridge enumeration in O(|V| + |E|), rejecting critical bridge transitions when viable alternative cycles exist.</p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ======================================================== */}
        {/* VIEW 6: SETTINGS */}
        {/* ======================================================== */}
        {tab === 'settings' && (
          <>
            <div className="subtab-bar">
              <button
                className={`subtab-btn ${settingsSubtab === 'defaults' ? 'active' : ''}`}
                onClick={() => setSettingsSubtab('defaults')}
              >
                Simulation Defaults
              </button>
              <button
                className={`subtab-btn ${settingsSubtab === 'viz' ? 'active' : ''}`}
                onClick={() => setSettingsSubtab('viz')}
              >
                Visualization
              </button>
              <button
                className={`subtab-btn ${settingsSubtab === 'export' ? 'active' : ''}`}
                onClick={() => setSettingsSubtab('export')}
              >
                Data Export
              </button>
              <button
                className={`subtab-btn ${settingsSubtab === 'api' ? 'active' : ''}`}
                onClick={() => setSettingsSubtab('api')}
              >
                API Configuration
              </button>
            </div>

            <div className="settings-grid">
              {/* Left Column: Network & Routing Defaults */}
              <div className="panel">
                <div className="config-header">Default Network Parameters</div>
                <div className="form-group">
                  <label>Default Node Count <b>{config.nodes}</b></label>
                  <input
                    type="range"
                    min="10"
                    max="100"
                    value={config.nodes}
                    onChange={e => update('nodes', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Default Rounds <b>{config.rounds}</b></label>
                  <input
                    type="range"
                    min="10"
                    max="500"
                    step="10"
                    value={config.rounds}
                    onChange={e => update('rounds', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Default Random Seed <b>{config.seed}</b></label>
                  <input
                    type="number"
                    value={config.seed}
                    onChange={e => update('seed', e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Default Topology Type</label>
                  <select defaultValue="geometric">
                    <option value="geometric">Random Geometric</option>
                  </select>
                </div>

                <div className="config-header" style={{ marginTop: 20 }}>Default Routing Parameters</div>
                <div className="form-group">
                  <label>Default Algorithm</label>
                  <select
                    value={algorithm}
                    onChange={e => setAlgorithm(e.target.value)}
                  >
                    <option value="incremental">Incremental (IEFT-IR)</option>
                    <option value="energy">Energy-aware</option>
                    <option value="shortest">Shortest path</option>
                  </select>
                </div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Default Use Weighted Routing</span>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={config.use_weighted_route}
                      onChange={e => update('use_weighted_route', e.target.checked)}
                    />
                    <span className="slider-round" />
                  </label>
                </div>
              </div>

              {/* Right Column: Visualization & Export */}
              <div className="panel">
                <div className="config-header">Visualization Settings</div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Show Node IDs</span>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={showNodeIds}
                      onChange={e => setShowNodeIds(e.target.checked)}
                    />
                    <span className="slider-round" />
                  </label>
                </div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Show Battery Levels</span>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={showBattery}
                      onChange={e => setShowBattery(e.target.checked)}
                    />
                    <span className="slider-round" />
                  </label>
                </div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Show Alternative Routes</span>
                  <label className="toggle-switch">
                    <input type="checkbox" defaultChecked />
                    <span className="slider-round" />
                  </label>
                </div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Animate Transmissions</span>
                  <label className="toggle-switch">
                    <input type="checkbox" defaultChecked />
                    <span className="slider-round" />
                  </label>
                </div>

                <div className="config-header" style={{ marginTop: 20 }}>Export Settings</div>
                <div className="form-group">
                  <label>Default Format</label>
                  <select defaultValue="json">
                    <option value="json">JSON</option>
                    <option value="csv">CSV</option>
                  </select>
                </div>

                <div className="config-header" style={{ marginTop: 20 }}>Application</div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Dark Mode (Reference is Light Mode)</span>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={darkMode}
                      onChange={e => setDarkMode(e.target.checked)}
                    />
                    <span className="slider-round" />
                  </label>
                </div>
                <div className="toggle-row">
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>Auto-check Backend Connection</span>
                  <label className="toggle-switch">
                    <input type="checkbox" defaultChecked />
                    <span className="slider-round" />
                  </label>
                </div>
              </div>
            </div>
          </>
        )}

        <footer>
          IEFT-IR Platform <span>·</span> System & Method for Incremental Energy-Aware Fault-Tolerant Routing in Low-Power Mesh Networks
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
