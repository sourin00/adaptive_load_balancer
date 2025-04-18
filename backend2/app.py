import socket

from flask import Flask, request, jsonify
import psutil

app = Flask(__name__)


@app.route('/')
def hello():
    server_name = socket.gethostname()
    algo = request.args.get('algo')
    return {
        'message': 'API is running',
        'serverName': server_name,
        'algo': algo,
        'region': 'Hello from Europe'
    }


@app.route('/metrics')
def metrics():
    # Get the system metrics
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    network_info = psutil.net_io_counters()

    # Return the metrics as a JSON response
    return jsonify({
        'cpu_usage': cpu_usage,
        'memory_usage': memory_info.percent,
        'net_usage': network_info.bytes_sent + network_info.bytes_recv,
        'active_connections': len(psutil.net_connections(kind='inet')),  # Count active connections
        'response_time': 0.05  # Dummy response time for simulation (can be dynamically calculated)
    })

@app.route('/health')
def health():
    try:
        if psutil.cpu_percent() > 95 or psutil.virtual_memory().percent > 90:
            return jsonify({'status': 'unhealthy'}), 503
        else:
            return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
