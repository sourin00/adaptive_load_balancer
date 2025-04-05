provider "google" {
  project = var.project_id
  region  = var.default_region
}

# ---------- VPC ----------
resource "google_compute_network" "vpc_network" {
  name                    = "load-balancer-vpc"
  auto_create_subnetworks = false
}

# ---------- Subnets + Secondary Ranges ----------

# APAC
resource "google_compute_subnetwork" "apac" {
  name          = "subnet-apac"
  ip_cidr_range = "10.0.0.0/16"
  region        = "asia-southeast1"
  network       = google_compute_network.vpc_network.id

  secondary_ip_range {
    range_name    = "pods-range-apac"
    ip_cidr_range = "10.10.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services-range-apac"
    ip_cidr_range = "10.20.0.0/20"
  }
}

# EU
resource "google_compute_subnetwork" "eu" {
  name          = "subnet-eu"
  ip_cidr_range = "10.100.0.0/16"
  region        = "europe-west1"
  network       = google_compute_network.vpc_network.id

  secondary_ip_range {
    range_name    = "pods-range-eu"
    ip_cidr_range = "10.110.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services-range-eu"
    ip_cidr_range = "10.120.0.0/20"
  }
}

# US
resource "google_compute_subnetwork" "us" {
  name          = "subnet-us"
  ip_cidr_range = "10.200.0.0/16"
  region        = "us-central1"
  network       = google_compute_network.vpc_network.id

  secondary_ip_range {
    range_name    = "pods-range-us"
    ip_cidr_range = "10.210.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services-range-us"
    ip_cidr_range = "10.220.0.0/20"
  }
}

# ---------- GKE Clusters ----------

module "gke_apac" {
  source     = "terraform-google-modules/kubernetes-engine/google"
  version    = "~> 19.0"
  project_id = var.project_id
  name       = "cluster-apac"
  region     = "asia-southeast1"
  network    = google_compute_network.vpc_network.name
  subnetwork = google_compute_subnetwork.apac.name

  ip_range_pods     = "pods-range-apac"
  ip_range_services = "services-range-apac"
  initial_node_count = 1

  node_pools = [{
    name         = "default-pool"
    machine_type = "e2-medium"
    min_count    = 1
    max_count    = 3
    auto_upgrade = true
    auto_repair  = true
  }]
}

module "gke_eu" {
  source     = "terraform-google-modules/kubernetes-engine/google"
  version    = "~> 19.0"
  project_id = var.project_id
  name       = "cluster-eu"
  region     = "europe-west1"
  network    = google_compute_network.vpc_network.name
  subnetwork = google_compute_subnetwork.eu.name

  ip_range_pods     = "pods-range-eu"
  ip_range_services = "services-range-eu"
  initial_node_count = 1

  node_pools = [{
    name         = "default-pool"
    machine_type = "e2-medium"
    min_count    = 1
    max_count    = 3
    auto_upgrade = true
    auto_repair  = true
  }]
}

module "gke_us" {
  source     = "terraform-google-modules/kubernetes-engine/google"
  version    = "~> 19.0"
  project_id = var.project_id
  name       = "cluster-us"
  region     = "us-central1"
  network    = google_compute_network.vpc_network.name
  subnetwork = google_compute_subnetwork.us.name

  ip_range_pods     = "pods-range-us"
  ip_range_services = "services-range-us"
  initial_node_count = 1

  node_pools = [{
    name         = "default-pool"
    machine_type = "e2-medium"
    min_count    = 1
    max_count    = 3
    auto_upgrade = true
    auto_repair  = true
  }]
}