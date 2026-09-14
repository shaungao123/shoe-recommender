data "digitalocean_kubernetes_versions" "current" {}

locals {
  # Use the pinned version if var.kubernetes_version is set, else the latest DO offers.
  kubernetes_version = coalesce(
    var.kubernetes_version,
    data.digitalocean_kubernetes_versions.current.latest_version,
  )
}

resource "digitalocean_kubernetes_cluster" "main" {
  name    = var.cluster_name
  region  = var.region
  version = local.kubernetes_version

  # Upgrade deliberately, not during a maintenance window mid-debugging.
  auto_upgrade = false

  # Adds a temporary extra node during upgrades so pods reschedule before the
  # old node drains — avoids downtime with only one replica per app.
  surge_upgrade = true

  node_pool {
    name       = "worker-pool"
    size       = var.node_size
    node_count = var.node_count
  }
}
