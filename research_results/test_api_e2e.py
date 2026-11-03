import urllib.request
import urllib.error
import json

base_url = 'http://localhost:8000/api'

payload_default = {
    'nodes': 28, 'gateway': 0, 'rounds': 80, 'seed': 7, 'k': 2,
    'traffic_per_round': 18, 'failure_round': 25, 'failure_count': 1,
    'threshold': 25.0, 'tx_cost': 0.65, 'rx_cost': 0.18, 'initial_energy': 100.0
}

# Test algorithms
for algo in ['incremental', 'energy', 'shortest', 'global_energy']:
    req = urllib.request.Request(
        f'{base_url}/simulate?algorithm={algo}',
        data=json.dumps(payload_default).encode(),
        headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            cors = resp.headers.get('Access-Control-Allow-Origin')
            pdr = data['metrics']['packet_delivery_ratio']
            energy = data['metrics']['energy_consumed']
            recomputes = data['metrics']['routing_recomputations']
            print(f"ALGO {algo:14s}: 200 OK | CORS={cors} | PDR={pdr:.4f} | Energy={energy:.2f} | Recomputes={recomputes}")
    except Exception as e:
        print(f"ALGO {algo:14s}: FAILED: {e}")

# Test node failures & route recovery
payload_fail = dict(payload_default, failure_round=10, failure_count=3)
req = urllib.request.Request(
    f'{base_url}/simulate?algorithm=incremental',
    data=json.dumps(payload_fail).encode(),
    headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    loc_up = data['metrics']['local_route_updates']
    n_failed = len([e for e in data.get('events', []) if e.get('type') == 'node_failure'])
    print(f"FAILURE TEST   : 200 OK | local_updates={loc_up} | failure_events={n_failed}")

# Test unreachable destination (partition)
payload_partition = dict(payload_default, nodes=10, failure_round=1, failure_count=5)
req = urllib.request.Request(
    f'{base_url}/simulate?algorithm=incremental',
    data=json.dumps(payload_partition).encode(),
    headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    pdr = data['metrics']['packet_delivery_ratio']
    conn = data['metrics']['final_connected']
    print(f"PARTITION TEST : 200 OK | PDR={pdr:.4f} | final_connected={conn}")

# Test invalid inputs
test_invalids = [
    ('invalid_algorithm', dict(payload_default), 'algorithm=invalid_xyz', 400),
    ('gateway_ge_nodes', dict(payload_default, gateway=28, nodes=28), 'algorithm=incremental', 400),
    ('nodes_too_few', dict(payload_default, nodes=3), 'algorithm=incremental', 422),
    ('rounds_negative', dict(payload_default, rounds=0), 'algorithm=incremental', 422),
]
for name, p, q, expected_code in test_invalids:
    req = urllib.request.Request(
        f'{base_url}/simulate?{q}',
        data=json.dumps(p).encode(),
        headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'}
    )
    try:
        urllib.request.urlopen(req)
        print(f"INVALID TEST {name:18s}: UNEXPECTED SUCCESS")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:70]
        print(f"INVALID TEST {name:18s}: Expected {expected_code}, Got {e.code} | {body}")

# Test compare endpoint
comp_payload = dict(payload_default, seeds=2)
req = urllib.request.Request(
    f'{base_url}/compare',
    data=json.dumps(comp_payload).encode(),
    headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:5173'}
)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    n_sum = len(data.get('summaries', []))
    n_runs = len(data.get('runs', []))
    print(f"COMPARE TEST   : 200 OK | Summaries={n_sum} | Runs={n_runs}")
