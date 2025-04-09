provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_iam_member" "artifact_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${var.service_account_email}"
}

resource "google_compute_instance_template" "lb_template" {
  name         = "lb-template-v2"
  machine_type = "e2-micro"
  region       = var.region

  tags = ["http-server"]

  metadata_startup_script = file("${path.module}/startup-script.sh")

  disk {
    source_image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
    auto_delete  = true
    boot         = true
  }


  network_interface {
    network = "default"
    access_config {}
  }

  service_account {
    email = var.service_account_email
    scopes = ["cloud-platform"]
  }
}

resource "google_compute_instance_group_manager" "lb_mig" {
  name               = "lb-mig"
  base_instance_name = "lb-instance"
  zone               = var.region
  version {
    instance_template = google_compute_instance_template.lb_template.id
  }
  target_size = 1

  named_port {
    name = "http"
    port = 5000
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.lb_health_check.id
    initial_delay_sec = 60
  }
}

resource "google_compute_health_check" "lb_health_check" {
  name                = "lb-health-check"
  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 2

  http_health_check {
    port         = 5000
    request_path = "/health"
  }
}

resource "google_compute_backend_service" "lb_backend" {
  name                  = "lb-backend-service"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL"
  port_name             = "http"
  timeout_sec           = 10
  health_checks = [google_compute_health_check.lb_health_check.id]

  backend {
    group = google_compute_instance_group_manager.lb_mig.instance_group
  }
}

resource "google_compute_firewall" "allow_http_5000" {
  name    = "allow-http-5000"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["5000"]
  }

  direction = "INGRESS"
  priority  = 1000

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["http-server"]

  description = "Allow HTTP traffic on port 5000"
}

resource "google_compute_url_map" "lb_url_map" {
  name            = "lb-url-map"
  default_service = google_compute_backend_service.lb_backend.id
}

resource "google_compute_target_http_proxy" "lb_http_proxy" {
  name    = "lb-http-proxy"
  url_map = google_compute_url_map.lb_url_map.id
}

resource "google_compute_global_forwarding_rule" "lb_forwarding_rule" {
  name        = "lb-forwarding-rule"
  target      = google_compute_target_http_proxy.lb_http_proxy.id
  port_range  = "80"
  ip_protocol = "TCP"
}
