# Adaptive Load Balancer

This project implements an adaptive load balancer using various techniques, deployed with Docker Compose and Kubernetes options. It includes multiple backend services, monitoring with Prometheus and Grafana, and load testing capabilities with Locust.

## Features

* **Multiple Load Balancing Algorithms:** Supports various algorithms including:
    * Round Robin
    * Weighted Round Robin
    * Least Connections
    * IP Hash
    * Power of Two Choices
    * Adaptive (Geo-aware and metrics-based)
* **Geo-aware Routing:** Directs traffic based on the client's geographical location (APAC, EU, US) using the MaxMind GeoLite2 database.
* **Dynamic Server Weighting:** Adjusts server weights based on real-time metrics like CPU usage, memory usage, active connections, and response time for the adaptive algorithm.
* **Backend Services:** Includes six simple Flask backend services, each potentially representing a different region or capacity.
* **Monitoring Stack:** Integrated monitoring using:
    * **Prometheus:** For metrics collection from the load balancer, backend services (via exporters), cAdvisor, and Node Exporter.
    * **Grafana:** For visualizing metrics with pre-configured dashboards.
    * **cAdvisor:** For container metrics.
    * **Node Exporter:** For host system metrics.
    * **InfluxDB:** As a remote write target for Prometheus metrics.
* **Load Testing:** Uses Locust for simulating user traffic and testing load balancer performance under different algorithms.
* **Caching:** Utilizes Redis for caching load balancing decisions and storing state for algorithms like Round Robin.
* **Deployment Options:**
    * Docker Compose for local development and testing.
    * Kubernetes deployment files for backend services.
    * GCP startup script for deploying the load balancer and Redis on a VM.

## Technologies Used

* Python (Flask, requests, psutil, prometheus_client, prometheus_api_client, docker, geoip2)
* Docker & Docker Compose
* Kubernetes
* Prometheus
* Grafana
* cAdvisor
* Node Exporter
* InfluxDB
* Redis
* Locust
* MaxMind GeoLite2 Database

## Setup and Usage

### Prerequisites

* Docker
* Docker Compose
* Kubernetes Cluster (Optional, for k8s deployment)
* `GeoLite2-Country.mmdb` file from MaxMind placed in the `load-balancer/` directory.

### Docker Compose (Local Development/Testing)

1.  **Clone the repository (or ensure you have the code).**
2.  **Place the `GeoLite2-Country.mmdb` file** in the `load-balancer/` directory. You need to download this from the MaxMind website.
3.  **Build and run the services:**
    ```bash
    docker-compose up --build -d
    ```
4.  **Access services:**
    * Load Balancer: `http://localhost:5000`
    * Grafana: `http://localhost:3000` (login: admin/admin)
    * Prometheus: `http://localhost:9090`
    * Locust UI: `http://localhost:8089`
    * cAdvisor: `http://localhost:8080`
    * Backend Services: `http://localhost:5001` - `http://localhost:5006`

### Load Balancer Endpoint

* Access `http://localhost:5000` in your browser or using `curl`.
* To specify a load balancing algorithm, use the `algo` query parameter:
    * `http://localhost:5000/?algo=round_robin`
    * `http://localhost:5000/?algo=least_connections`
    * `http://localhost:5000/?algo=adaptive` (Default)

### Monitoring

* **Grafana:** Access `http://localhost:3000`. Pre-configured dashboards for the load balancer, cAdvisor, Node Exporter, and Locust should be available.
* **Prometheus:** Access `http://localhost:9090` to query metrics directly.

### Load Testing

1.  Access the **Locust UI** at `http://localhost:8089`.
2.  Enter the number of users and spawn rate.
3.  Use `http://load-balancer:5000` as the host.
4.  Start swarming. Locust will run the tasks defined in `load_tests/load_tests.py`, hitting the load balancer with requests for different algorithms.
5.  Monitor Locust metrics via the provided Grafana dashboard.

### Kubernetes Deployment (Backend Services)

The `k8s/` directory contains sample deployment and service files for the backend services.

1.  Ensure your `kubectl` is configured for your cluster.
2.  Apply the deployment files:
    ```bash
    kubectl apply -f k8s/
    ```
3.  This will create deployments and LoadBalancer services for each backend. You'll need to update the `servers` list in `load-balancer/app.py` with the external IPs assigned by Kubernetes/your cloud provider if deploying the load balancer separately.

### GCP VM Deployment (Load Balancer + Redis)

The `load-balancer/deployment/startup-script.sh` provides a basic setup for running the load balancer and Redis on a Google Cloud VM.

1.  Create a GCP VM instance.
2.  Use the content of `startup-script.sh` as the startup script for the VM.
3.  Ensure the VM has Docker installed or the script handles the installation.
4.  The script pulls the `sourin00/load-balancer:latest` image (you might need to build and push your own image) and runs it along with Redis.
5.  Configure firewall rules to allow access to ports 5000 (load balancer) and 9090 (Prometheus, if run on the same VM).

## License

* The GeoLite2 database usage is governed by the MaxMind GeoLite2 End User License Agreement.
* The GeoLite2 database incorporates GeoNames geographical data, licensed under CC BY 4.0.