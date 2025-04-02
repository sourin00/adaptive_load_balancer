import hashlib
import random
import threading
import time

import redis
import requests
from flask import Flask, request
from prometheus_api_client import PrometheusConnect
from prometheus_client import start_http_server, Counter, Histogram, generate_latest

app = Flask(__name__)

# Redis setup
redis_client = redis.StrictRedis(host='redis', port=6379, decode_responses=True)

# Prometheus setup
prom = PrometheusConnect(url="http://prometheus:9090", disable_ssl=True)

# Prometheus metrics
REQUEST_COUNT = Counter('load_balancer_requests_total', 'Total requests')
RESPONSE_TIME = Histogram('load_balancer_response_duration_seconds', 'Response durations', ['algo'])
ALGO_REQUEST_COUNT = Counter('load_balancer_algo_requests_total', 'Requests per algorithm', ['algo'])

# Server pool
servers = [
    {'name': 'backend1', 'url': "http://backend1:5000", 'weight': 2, 'connections': 0, 'response_time': 0.05},
    {'name': 'backend2', 'url': "http://backend2:5000", 'weight': 3, 'connections': 0, 'response_time': 0.04},
    {'name': 'backend3', 'url': "http://backend3:5000", 'weight': 1, 'connections': 0, 'response_time': 0.06}
]


@app.route('/')
def load_balancer():
    start_time = time.time()
    REQUEST_COUNT.inc()

    algo = request.args.get('algo')
    if not algo:
        algo = select_best_algorithm()

    last_used_algo = redis_client.get("last_used_algo")
    if algo in ['round_robin', 'weighted_round_robin'] and last_used_algo not in ['round_robin', 'weighted_round_robin']:
        redis_client.set("next_server_index", 0)

    redis_client.set("last_used_algo", algo)
    selected_server_info = None

    if algo == 'least_connections':
        selected_server_info = min(servers, key=lambda s: s['connections'])
        selected_server_info['connections'] += 1
    elif algo == 'ip_hash':
        selected_server_info = servers[hash_ip(request.remote_addr) % len(servers)]
    elif algo == 'round_robin':
        selected_server_info = get_server_round_robin()
    elif algo == 'weighted_round_robin':
        selected_server_info = smooth_weighted_round_robin()
    elif algo == 'power_of_two':
        selected_server_info = power_of_two_choice()
        selected_server_info['connections'] += 1
    elif algo == 'least_response_time':
        selected_server_info = min(servers, key=lambda s: s['response_time'])
    elif algo == 'geo_aware':
        selected_server_info = geo_aware_routing(request.remote_addr)
    else:
        return {'error': 'Invalid algorithm specified'}, 400

    ALGO_REQUEST_COUNT.labels(algo=algo).inc()

    try:
        response = requests.get(f"{selected_server_info['url']}?algo={algo}")
        return response.content, response.status_code
    except Exception as e:
        return str(e), 500
    finally:
        if algo in ['least_connections', 'power_of_two']:
            selected_server_info['connections'] -= 1
        selected_server_info['response_time'] = time.time() - start_time
        RESPONSE_TIME.labels(algo=algo).observe(selected_server_info['response_time'])


@app.route('/metrics')
def metrics():
    return generate_latest()


# Redis-based round-robin
def get_server_round_robin():
    try:
        index = int(redis_client.incr("next_server_index")) % len(servers)
    except Exception:
        index = 0
        redis_client.set("next_server_index", 1)
    return servers[index]


# Weighted round robin (smooth)
def smooth_weighted_round_robin():
    total_weight = sum(s['weight'] for s in servers)
    for s in servers:
        s.setdefault('current_weight', 0)
        s['current_weight'] += s['weight']
    selected = max(servers, key=lambda s: s['current_weight'])
    selected['current_weight'] -= total_weight
    return selected


def power_of_two_choice():
    candidates = random.sample(servers, 2)
    return min(candidates, key=lambda s: s['connections'])


def hash_ip(ip):
    return int(hashlib.md5(ip.encode()).hexdigest(), 16)


def geo_aware_routing(ip):
    # Placeholder: In production, use MaxMind GeoIP or similar
    # Example: send APAC IPs to backend1, EU to backend2, others to backend3
    hash_val = hash_ip(ip)
    if hash_val % 3 == 0:
        return servers[0]
    elif hash_val % 3 == 1:
        return servers[1]
    return servers[2]


# --- Metric Polling ---

def get_prometheus_metric(query):
    try:
        result = prom.custom_query(query)
        if result and 'value' in result[0]:
            return float(result[0]['value'][1])
    except Exception:
        pass
    return 0.0


def background_metrics_updater(interval=10):
    while True:
        try:
            for s in servers:
                cpu = get_prometheus_metric(f'rate(container_cpu_usage_seconds_total{{container="{s["name"]}"}}[1m])')
                mem = get_prometheus_metric(f'container_memory_usage_bytes{{container="{s["name"]}"}}')
                s['cpu'] = cpu
                s['mem'] = mem
        except Exception as e:
            print("Error updating metrics:", e)
        time.sleep(interval)


def calculate_server_weight(server):
    cpu = server.get('cpu', 1)
    mem = server.get('mem', 1)
    load = server.get('connections', 1)
    return server['weight'] / (0.6 * cpu + 0.2 * mem + 0.2 * load + 1e-5)


def select_best_algorithm():
    weighted = [(s, calculate_server_weight(s)) for s in servers]
    weighted.sort(key=lambda x: x[1], reverse=True)

    if weighted[0][1] < 0.7:
        return 'weighted_round_robin'
    elif weighted[0][1] > 2.0:
        return 'least_connections'
    else:
        return 'power_of_two'


if __name__ == "__main__":
    threading.Thread(target=background_metrics_updater, daemon=True).start()
    start_http_server(8000)
    app.run(host='0.0.0.0', port=5000)
