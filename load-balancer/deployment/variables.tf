
variable "project_id" {
  type    = string
  default = "adaptive-load-balancer-2"
}

variable "region" {
  type    = string
  default = "us-central1-a"
}

variable "service_account_email" {
  type        = string
  description = "370073054528-compute@developer.gserviceaccount.com"
}
