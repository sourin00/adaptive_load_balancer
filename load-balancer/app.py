from flask import Flask, request
import requests
from prometheus_client import start_http_server, Counter, Gauge

app = Flask(__name__)

REQUEST_COUNT = Counter('load_balancer_requests_total', 'Total number of requests handled by the load balancer')
ACTIVE_CONNECTIONS = Gauge('load_balancer_active_connections', 'Number of active connections being handled by the load balancer')

backend_servers = [
    "http://backend1:5000",
    "http://backend2:5000",
    "http://backend3:5000",
]

current_server = 0

@app.route('/')
def load_balancer():
    global current_server

    REQUEST_COUNT.inc()
    ACTIVE_CONNECTIONS.inc()

    # TODO: Add custom algorithm here
    selected_server = backend_servers[current_server]
    current_server = (current_server + 1) % len(backend_servers)

    try:
        response = requests.get(f"{selected_server}{request.path}")
        return response.content, response.status_code
    except requests.exceptions.RequestException as e:
        return str(e), 500
    finally:
        ACTIVE_CONNECTIONS.dec()

if __name__ == "__main__":
    start_http_server(8000)
    app.run(host='0.0.0.0', port=5000)