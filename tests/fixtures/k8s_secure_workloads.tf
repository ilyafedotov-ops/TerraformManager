resource "kubernetes_namespace" "secure" {
  metadata {
    name = "secure"
  }
}

resource "kubernetes_stateful_set" "db" {
  metadata {
    name      = "db"
    namespace = kubernetes_namespace.secure.metadata[0].name
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
          security_context {
            run_as_non_root           = true
            read_only_root_filesystem = true
            seccomp_profile {
              type = "RuntimeDefault"
            }
            capabilities { drop = ["ALL"] }
          }
          resources {
            limits   = { cpu = "500m", memory = "512Mi" }
            requests = { cpu = "250m", memory = "256Mi" }
          }
        }
      }
    }
  }
}

resource "kubernetes_daemonset" "agent" {
  metadata {
    name      = "agent"
    namespace = kubernetes_namespace.secure.metadata[0].name
  }
  spec {
    selector {
      match_labels = { app = "agent" }
    }
    template {
      metadata {
        labels = { app = "agent" }
        annotations = {
          "container.apparmor.security.beta.kubernetes.io/agent" = "runtime/default"
        }
      }
      spec {
        container {
          name  = "agent"
          image = "busybox:1.36"
          command = ["sleep", "3600"]
          security_context {
            run_as_non_root           = true
            read_only_root_filesystem = true
            seccomp_profile {
              type = "RuntimeDefault"
            }
            capabilities { drop = ["ALL"] }
          }
          resources {
            limits   = { cpu = "200m", memory = "128Mi" }
            requests = { cpu = "100m", memory = "64Mi" }
          }
        }
      }
    }
  }
}

resource "kubernetes_network_policy" "secure_default_deny" {
  metadata {
    name      = "secure-default-deny"
    namespace = kubernetes_namespace.secure.metadata[0].name
  }
  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}
