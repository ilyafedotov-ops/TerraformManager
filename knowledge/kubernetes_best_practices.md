# Kubernetes Best Practices (Terraform `kubernetes` provider)

- Avoid container image tag `:latest`.
- Run as non-root (`security_context { run_as_non_root = true }`).
- Read-only root filesystem when possible; set resource `limits` and `requests`.
- Enforce `seccomp_profile { type = "RuntimeDefault" }` and AppArmor `runtime/default` annotations to harden syscall surfaces.
- Consider NetworkPolicies and restrictive PodSecurity standards.
