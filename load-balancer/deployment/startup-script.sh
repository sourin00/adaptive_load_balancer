#!/bin/bash

exec > >(tee /var/log/startup.log | logger -t startup-script) 2>&1
echo "=== Starting VM setup ==="

apt-get update
apt-get install -y docker.io curl unzip wget

systemctl enable docker
systemctl start docker

# Pull and start Redis container
docker run --restart=always -d --name redis -p 6379:6379 redis:7

# Pull and start Prometheus container with default config
cat <<EOF > prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'load_balancer'
    static_configs:
      - targets: ['localhost:8000']
EOF

docker run --restart=always -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Pull and start your load balancer
docker pull sourin00/load-balancer:latest

docker run --restart=always -d -p 5000:5000 \
  --name load-balancer \
  --link redis \
  sourin00/load-balancer:latest

echo "=== Setup complete ==="
