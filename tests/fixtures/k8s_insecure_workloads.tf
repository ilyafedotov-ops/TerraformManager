resource "kubernetes_namespace" "insecure" {
  metadata {
    name = "insecure"
  }
}

resource "kubernetes_stateful_set" "db" {
  metadata {
    name      = "db"
    namespace = kubernetes_namespace.insecure.metadata[0].name
  }
  spec {
    service_name = "db"
    selector {
      match_labels = { app = "db" }
    }
    template {
      metadata {
        labels = { app = "db" }
      }
      spec {
        container {
          name  = "db"
          image = "postgres:15"
          # missing security_context + resources
        }
      }
    }
  }
}

resource "kubernetes_daemonset" "agent" {
  metadata {
    name      = "agent"
    namespace = kubernetes_namespace.insecure.metadata[0].name
  }
  spec {
    selector {
      match_labels = { app = "agent" }
    }
    template {
      metadata {
        labels = { app = "agent" }
        # missing AppArmor annotation
      }
      spec {
        container {
          name  = "agent"
          image = "busybox:1.36"
          security_context {
            run_as_non_root = false
          }
        }
      }
    }
  }
}
