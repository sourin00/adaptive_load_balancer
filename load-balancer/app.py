import hashlib
import time

import requests
from flask import Flask, request
from prometheus_client import start_http_server, Counter, Histogram, generate_latest

app = Flask(__name__)

# Metrics for Prometheus
REQUEST_COUNT = Counter('load_balancer_requests_total', 'Total number of requests handled by the load balancer')
RESPONSE_TIME = Histogram('load_balancer_response_duration_seconds', 'Histogram of response durations by algorithm', ['algo'])
ALGO_REQUEST_COUNT = Counter('load_balancer_algo_requests_total', 'Total number of requests per algorithm', ['algo'])

# List of backend servers with default values for resource usage
servers = [
    {'server': "http://backend1:5000", 'weight': 2, 'connections': 0, 'response_time': 0.05, 'cpu_usage': 10, 'mem_usage': 20, 'net_usage': 30},
    {'server': "http://backend2:5000", 'weight': 3, 'connections': 0, 'response_time': 0.04, 'cpu_usage': 15, 'mem_usage': 25, 'net_usage': 35},
    {'server': "http://backend3:5000", 'weight': 1, 'connections': 0, 'response_time': 0.06, 'cpu_usage': 20, 'mem_usage': 30, 'net_usage': 40}
]

# Track the last used algorithm
last_used_algo = None

@app.route('/')
def load_balancer():
    global last_used_algo, next_server_index

    # Start the timer for response time tracking
    start_time = time.time()

    REQUEST_COUNT.inc()

    algo = request.args.get('algo')
    if not algo:
        # Intelligent algorithm selection
        algo = select_best_algorithm()

    # Check if we need to reset the next_server_index
    if algo in ['round_robin', 'weighted_round_robin'] and last_used_algo not in ['round_robin', 'weighted_round_robin']:
        next_server_index = 0  # Reset the round-robin index to 0

    # Select load balancing algorithm based on the query parameter
    if algo == 'least_connections':
        selected_server = handle_request_least_connections()
    elif algo == 'ip_hash':
        selected_server = handle_request_ip_hash()
    elif algo == 'round_robin':
        selected_server = handle_request_round_robin()
    elif algo == 'weighted_round_robin':
        selected_server = handle_request_weighted_round_robin()
    else:
        return {'error': 'Invalid algorithm specified'}, 400

    # Increment algorithm-specific counter
    ALGO_REQUEST_COUNT.labels(algo=algo).inc()

    # Update the last used algorithm
    last_used_algo = algo

    try:
        # Simulate request to the backend
        response = requests.get(f"{selected_server}{request.path}?algo={algo}")
        return response.content, response.status_code
    except requests.exceptions.RequestException as e:
        return str(e), 500
    finally:
        # Measure the response duration
        response_duration = time.time() - start_time
        RESPONSE_TIME.labels(algo=algo).observe(response_duration)


# Round-robin implementation
next_server_index = 0

def handle_request_round_robin():
    global next_server_index
    server_info = servers[next_server_index]
    current_server = server_info['server']
    next_server_index = (next_server_index + 1) % len(servers)
    return current_server

def handle_request_weighted_round_robin():
    global next_server_index
    current_server = ""

    # Weighted round robin: each server's weight determines how many times it is selected
    total_weight = sum(server['weight'] for server in servers)
    current_weight = 0
    for i, server_info in enumerate(servers):
        current_weight += server_info['weight']
        if current_weight > total_weight * (next_server_index / len(servers)):
            current_server = server_info['server']
            break

    next_server_index = (next_server_index + 1) % len(servers)
    return current_server

def handle_request_least_connections():
    # Find the server with the least number of connections
    server_info = min(servers, key=lambda server: server['connections'])
    server_info['connections'] += 1
    return server_info['server']

def handle_request_ip_hash():
    # Get the client's IP address
    client_ip = request.remote_addr
    # Hash the IP and use modulo to choose a backend server
    hashed_ip = int(hashlib.md5(client_ip.encode('utf-8')).hexdigest(), 16)
    server_index = hashed_ip % len(servers)
    return servers[server_index]['server']

@app.route('/metrics')
def metrics():
    # Expose Prometheus metrics
    return generate_latest()


# Calculate dynamic weight based on server performance
def calculate_dynamic_weight(server):
    # Server performance (CPU, memory, network utilization) is factored in the weight
    performance_factor = (server['cpu_usage'] + server['mem_usage'] + server['net_usage']) / 3
    dynamic_weight = server['weight'] / performance_factor
    return dynamic_weight

# Calculate the composite load (CTL) of the server
def calculate_composite_load(server):
    # Composite load is a combination of response time and connections
    response_time_factor = server['response_time']
    connection_factor = server['connections']
    composite_load = 0.7 * response_time_factor + 0.3 * connection_factor
    return composite_load

# Calculate server's final weight based on dynamic load and performance
def calculate_server_weight(server):
    dynamic_weight = calculate_dynamic_weight(server)
    composite_load = calculate_composite_load(server)
    final_weight = dynamic_weight / composite_load
    return final_weight


# Intelligent algorithm selection based on load and performance
def select_best_algorithm():
    # Calculate composite load for each server
    server_weights = [(server, calculate_server_weight(server)) for server in servers]
    server_weights.sort(key=lambda x: x[1])  # Sort by calculated server weight

    # If server is highly loaded (high response time or many connections), use least_connections
    if server_weights[0][1] > 1.5:  # Example threshold: you can adjust this
        return 'least_connections'

    # If server has a balanced load, use weighted round robin or round robin
    if server_weights[0][1] < 0.7:
        return 'weighted_round_robin'

    # Fallback to round robin if the load is relatively balanced
    return 'round_robin'

if __name__ == "__main__":
    # Start the Prometheus client HTTP server
    start_http_server(8000)  # Prometheus metrics server on port 8000
    app.run(host='0.0.0.0', port=5000)
