variable "do_token" {
  description = "DigitalOcean PAT with write scope. Supply via $env:TF_VAR_do_token — never commit it."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DO region. nyc3 is the closest to the Supabase project in us-east-2 (~20ms)."
  type        = string
  default     = "nyc3"
}

variable "cluster_name" {
  description = "DOKS cluster name. Changing this REPLACES the cluster."
  type        = string
  default     = "shoe-recommender"
}

variable "kubernetes_version" {
  description = <<-EOT
    DOKS version slug, e.g. "1.34.1-do.0". Leave null on the first apply to take the
    latest available, then copy the `kubernetes_version` output here to pin it. Pinning
    stops an unrelated `terraform plan` from proposing a surprise control-plane upgrade.
  EOT
  type        = string
  default     = "1.36.3-do.4"
}

variable "node_size" {
  description = "Droplet slug for worker nodes. s-1vcpu-2gb is ~$12/mo each, ~1.4Gi allocatable."
  type        = string
  default     = "s-1vcpu-2gb"
}

variable "node_count" {
  description = <<-EOT
    Worker nodes. One keeps the bill at ~$12/mo but means no fault tolerance at all:
    the node is a single point of failure, and node maintenance is a full outage.
    Bump to 2 (~$24/mo) for real multi-node scheduling and the ability to drain a node.
  EOT
  type        = number
  default     = 1
}
