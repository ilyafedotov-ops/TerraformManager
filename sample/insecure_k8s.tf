# On‑prem default via Kubernetes provider
provider "kubernetes" {
  host                   = var.kube_host
  token                  = var.kube_token
  cluster_ca_certificate = base64decode(var.kube_ca)
}

variable "kube_host" {}
variable "kube_token" {}
variable "kube_ca" {}

resource "kubernetes_namespace" "ns" {
  metadata { name = "demo" }
}

resource "kubernetes_deployment" "bad_deploy" {
  metadata {
    name      = "insecure-app"
    namespace = kubernetes_namespace.ns.metadata[0].name
    labels = { app = "insecure" }
  }
  spec {
    replicas = 1
    selector { match_labels = { app = "insecure" } }
    template {
      metadata { labels = { app = "insecure" } }
      spec {
        container {
          name  = "app"
          image = "nginx:latest" # latest tag (bad)
          port { container_port = 80 }
          # missing security_context and resources limits/requests
        }
      }
    }
  }
}
