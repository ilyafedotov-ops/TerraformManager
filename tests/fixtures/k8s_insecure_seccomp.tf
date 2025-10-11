# Sample: Kubernetes workload missing seccomp/AppArmor annotations

resource "kubernetes_deployment" "insecure" {
  metadata {
    name      = "insecure"
    namespace = "default"
    labels    = { app = "insecure" }
  }
  spec {
    selector { match_labels = { app = "insecure" } }
    template {
      metadata { labels = { app = "insecure" } }
      spec {
        container {
          name  = "app"
          image = "nginx:1.25"
          # Missing seccomp_profile and AppArmor annotations
          security_context {
            run_as_non_root           = true
            read_only_root_filesystem = true
          }
        }
      }
    }
  }
}
