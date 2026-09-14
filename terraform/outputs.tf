output "cluster_name" {
  description = "Name to pass to `doctl kubernetes cluster kubeconfig save`."
  value       = digitalocean_kubernetes_cluster.main.name
}

output "cluster_endpoint" {
  description = "Kubernetes API server URL."
  value       = digitalocean_kubernetes_cluster.main.endpoint
}

output "kubernetes_version" {
  description = "Version actually deployed. Copy into var.kubernetes_version to pin it."
  value       = digitalocean_kubernetes_cluster.main.version
}

output "kubeconfig_command" {
  description = "Run this next to point kubectl at the cluster."
  value       = "doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.main.name}"
}
