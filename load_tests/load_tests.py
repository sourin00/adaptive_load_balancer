from locust import HttpUser, task, between


class LoadBalancerUser(HttpUser):
    wait_time = between(1, 3)  # Simulate user think time between requests (1 to 3 seconds)

    # List of load balancing algorithms to test
    algorithms = ['least_connections', 'ip_hash', 'round_robin', 'weighted_round_robin']

    @task(1)  # Equal weight for all algorithms, so each runs equally
    def test_round_robin(self):
        algo = 'round_robin'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_weighted_round_robin(self):
        algo = 'weighted_round_robin'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_least_connections(self):
        algo = 'least_connections'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_ip_hash(self):
        algo = 'ip_hash'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_power_of_two(self):
        algo = 'power_of_two'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_geo_aware(self):
        algo = 'geo_aware'
        self.client.get(f'/?algo={algo}')

    @task(1)
    def test_adaptive(self):
        self.client.get(f'/')