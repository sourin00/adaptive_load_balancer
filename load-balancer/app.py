import hashlib
import random
import threading
import time

import redis
import docker
import requests
from flask import Flask, request
from prometheus_api_client import PrometheusConnect
from prometheus_client import start_http_server, Counter, Histogram, generate_latest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

import geoip2.database
import os

import pprint

pp = pprint.PrettyPrinter(indent=2)

app = Flask(__name__)

# Redis setup
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

# Prometheus setup
prom = PrometheusConnect(url="http://prometheus:9090", disable_ssl=True)

# Prometheus metrics
REQUEST_COUNT = Counter('load_balancer_requests_total', 'Total requests')
RESPONSE_TIME = Histogram('load_balancer_response_duration_seconds', 'Response durations', ['algo'])
ALGO_REQUEST_COUNT = Counter('load_balancer_algo_requests_total', 'Requests per algorithm', ['algo'])

# Server pool
servers = [
    {'name': 'backend1', 'url': "http://34.142.176.64", 'weight': 2, 'connections': 0, 'response_time': 0.05},
    {'name': 'backend2', 'url': "http://34.140.174.234", 'weight': 3, 'connections': 0, 'response_time': 0.04},
    {'name': 'backend3', 'url': "http://34.173.210.96", 'weight': 1, 'connections': 0, 'response_time': 0.06}
]

executor = ThreadPoolExecutor(max_workers=50)  # Configurable pool


@app.route('/')
def load_balancer():
    start_time = time.time()
    REQUEST_COUNT.inc()

    algo = request.args.get('algo')
    redis_client.set("last_used_algo", algo)

    # Reset index for round-robin family if algo changes
    if algo in ['round_robin', 'weighted_round_robin']:
        if redis_client.get("last_used_algo") not in ['round_robin', 'weighted_round_robin']:
            redis_client.set("next_server_index", 0)

    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    selected_server_info = select_server(algo, client_ip)
    if not selected_server_info:
        return {'error': 'No backend available'}, 503

    ALGO_REQUEST_COUNT.labels(algo=algo).inc()

    # Mark connection increment early (for accurate concurrency tracking)
    if algo in ['least_connections', 'power_of_two']:
        selected_server_info['connections'] += 1

    try:
        future = executor.submit(requests.get, f"{selected_server_info['url']}?algo={algo}", timeout=2.5)
        response = future.result(timeout=3.0)  # max wait time
        return response.content, response.status_code
    except FuturesTimeout:
        return {'error': 'Backend timeout'}, 504
    except Exception as e:
        return {'error': str(e)}, 500
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
    total_weight = sum(s.get('effective_weight', s['weight']) for s in servers)
    for s in servers:
        s.setdefault('current_weight', 0)
        s['current_weight'] += s.get('effective_weight', s['weight'])
    selected = max(servers, key=lambda s: s['current_weight'])
    selected['current_weight'] -= total_weight
    return selected


def power_of_two_choice():
    candidates = random.sample(servers, 2)
    return min(candidates, key=lambda s: s['connections'])


def hash_ip(ip):
    return int(hashlib.md5(ip.encode()).hexdigest(), 16)


def geo_aware_routing(ip):
    try:
        db_path = os.path.join(os.path.dirname(__file__), "GeoLite2-Country.mmdb")
        print("GeoLite2-Country.mmdb path collected")
        reader = geoip2.database.Reader(db_path)
        print("GeoIP DB loaded....")
        # For dev/testing, override with a test IP:
        if ip.startswith("172.") or ip == "127.0.0.1":
            ip = "8.8.8.8"  # Example: US IP
        print("detecting country from ip address: ", ip)
        response = reader.country(ip)
        country_code = response.country.iso_code

        eu_countries = {"FR", "DE", "IT", "ES", "NL", "BE", "PL", "SE", "FI", "IE", "DK", "PT", "AT"}
        apac_countries = {"IN", "CN", "JP", "KR", "AU", "SG", "TH", "VN", "MY", "PH", "ID"}

        if country_code in apac_countries:
            return servers[0]  # backend1
        elif country_code in eu_countries:
            return servers[1]  # backend2
        else:
            return servers[2]  # backend3
    except Exception as e:
        print(f"GeoIP lookup failed for {ip}: {e}")
        return servers[2]  # fallback


# --- Metric Polling ---

def update_server_effective_weight(server):
    cpu = normalize(server.get('cpu', 0), 100)
    mem = normalize(server.get('mem', 0), 4e9)
    conns = normalize(server.get('connections', 0), 100)
    resp = normalize(server.get('response_time', 0), 1.0)

    # Score reflects capacity headroom
    capacity_score = (1 - cpu) * 0.4 + (1 - mem) * 0.2 + (1 - conns) * 0.2 + (1 - resp) * 0.2

    # Map score (0.0 to 1.0) to weight (1 to 5)
    server['effective_weight'] = max(1, min(5, int(round(capacity_score * 5))))


def update_server_metrics_using_api():
    """Fetch the real-time metrics for each server by calling the /metrics API endpoint."""
    for server_info in servers:
        try:
            # Query the /metrics API on each backend server to get the latest metrics
            response = requests.get(f"{server_info['url']}/metrics")
            metrics_obj = response.json()

            # Update server dictionary with real-time values
            server_info.update({
                'cpu': metrics_obj['cpu_usage'],
                'mem': metrics_obj['memory_usage'],
                'net_usage': metrics_obj['net_usage'],
                'response_time': metrics_obj['response_time'],
                'connections': metrics_obj['active_connections']
            })

            #Update dynamic weight
            update_server_effective_weight(server_info)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching metrics for {server_info['server']}: {e}")
    print("🔄 Updated Server Metrics using api:")
    pp.pprint(servers)


def calculate_cpu_percent(stats):
    try:
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        cpu_count = len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [])) or 1
        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * cpu_count * 100.0
    except Exception as e:
        print("❌ Error calculating CPU:", e)
    return 0.0


def update_server_metrics_using_docker_sdk():
    client = docker.from_env()
    try:
        for s in servers:
            try:
                container = client.containers.get(s['name'])
                pp.pprint("Container ID: " + container.id)
                stats = container.stats(stream=False)

                cpu = calculate_cpu_percent(stats)
                mem = stats['memory_stats']['usage']

                s['cpu'] = round(cpu, 2)
                s['mem'] = mem
            except Exception as e:
                print(f"❌ Error getting stats for {s['name']}: {e}")

        print("🔄 Updated Server Metrics using docker SDK:")
        pp.pprint(servers)

    except Exception as e:
        print("❌ Top-level updater error:", e)


def background_metrics_updater(interval=5):
    while True:
        update_server_metrics_using_api()
        time.sleep(interval)


def normalize(value, max_value=100.0):
    try:
        return min(float(value) / max_value, 1.0)
    except:
        return 0.0


def calculate_server_score(server, weights=None):
    if weights is None:
        weights = {
            'cpu': 0.4,
            'mem': 0.2,
            'connections': 0.2,
            'response_time': 0.2
        }

    cpu = normalize(server.get('cpu', 0), 100)
    mem = normalize(server.get('mem', 0), 4e9)  # assuming 4GB upper cap
    conns = normalize(server.get('connections', 0), 100)
    resp = normalize(server.get('response_time', 0), 1.0)

    score = (1 - cpu) * weights['cpu'] + \
            (1 - mem) * weights['mem'] + \
            (1 - conns) * weights['connections'] + \
            (1 - resp) * weights['response_time']

    return round(score, 3)


def select_best_server():

    # Check Redis for a recent cached decision
    last_decision = redis_client.get("cached_best_server_index")
    if last_decision:
        return servers[int(last_decision)]

    best_score = -1
    best_server = None

    for s in servers:
        score = calculate_server_score(s)
        if score > best_score:
            best_score = score
            best_server = s

    redis_client.setex("cached_best_server_index", 5, servers.index(best_server))  # Cache for 5 seconds
    return best_server


def select_server(algo, client_ip):
    try:
        if algo == 'adaptive':
            return select_best_server()
        elif algo == 'least_connections':
            return min(servers, key=lambda s: s['connections'])
        elif algo == 'ip_hash':
            return servers[hash_ip(client_ip) % len(servers)]
        elif algo == 'round_robin':
            return get_server_round_robin()
        elif algo == 'weighted_round_robin':
            return smooth_weighted_round_robin()
        elif algo == 'power_of_two':
            return power_of_two_choice()
        elif algo == 'least_response_time':
            return min(servers, key=lambda s: s['response_time'])
        elif algo == 'geo_aware':
            return geo_aware_routing(client_ip)
    except Exception as e:
        print(f"❌ Error selecting server using {algo}: {e}")
        return None


def health_check_loop(interval=10):
    while True:
        for s in servers:
            try:
                resp = requests.get(f"{s['url']}/health", timeout=2)
                s['healthy'] = (resp.status_code == 200)
            except:
                s['healthy'] = False
        time.sleep(interval)


if __name__ == "__main__":
    threading.Thread(target=background_metrics_updater, daemon=True).start()
    threading.Thread(target=health_check_loop, daemon=True).start()
    start_http_server(8000)
    app.run(host='0.0.0.0', port=5000, threaded=True)
