---
title: Kubernetes Pod Security Standards
provider: kubernetes
service: security
category: [security, pod-security, compliance]
tags: [pss, psa, pod-security-policy, restricted, baseline, privileged]
last_updated: 2025-01-18
difficulty: intermediate
---

# Kubernetes Pod Security Standards (PSS)

Pod Security Standards (PSS) define three security profiles for Kubernetes pods: **Privileged**, **Baseline**, and **Restricted**. These standards are enforced via Pod Security Admission (PSA), which replaced the deprecated PodSecurityPolicy.

## Security Profiles

### Privileged

**Unrestricted** - Allows known privilege escalations. Use only for trusted system components.

- No restrictions on pod capabilities
- Can run as root
- Can use host namespaces (hostNetwork, hostPID, hostIPC)
- Can mount any volume type
- Can use privileged containers

**Use cases:**
- CNI plugins (Calico, Cilium)
- CSI drivers
- Monitoring agents (node-exporter)
- System daemons (kube-proxy)

### Baseline

**Minimally restrictive** - Prevents known privilege escalations while allowing common use cases.

**Restrictions:**
- Cannot use host namespaces (`hostNetwork`, `hostPID`, `hostIPC`)
- Cannot use `hostPath` volumes
- Cannot add dangerous capabilities (`SYS_ADMIN`, `NET_ADMIN`, etc.)
- Cannot run privileged containers
- Limited use of host ports (≥1024)
- AppArmor/Seccomp profiles must be defined or use runtime default

**Allowed:**
- Running as root (UID 0)
- Using most volume types
- Using standard Linux capabilities

**Use cases:**
- Legacy applications that require root
- Applications needing standard capabilities
- Development/staging environments

### Restricted

**Heavily restricted** - Follows current pod hardening best practices.

**All Baseline restrictions PLUS:**
- Must run as non-root user (`runAsNonRoot: true`)
- Must drop all capabilities and only add back `NET_BIND_SERVICE` if needed
- Must use read-only root filesystem or emptyDir/ConfigMap/Secret volumes
- Seccomp profile must be `RuntimeDefault` or `Localhost`
- Cannot escalate privileges (`allowPrivilegeEscalation: false`)
- Must define resource limits

**Use cases:**
- Production workloads
- Multi-tenant clusters
- Compliance-sensitive environments (PCI-DSS, HIPAA)

## Pod Security Admission (PSA)

### Enforcement Modes

PSA operates in three modes per namespace:

1. **enforce** - Rejects pods that violate the policy
2. **audit** - Allows pods but adds audit annotation
3. **warn** - Allows pods but shows warning to user

### Namespace Configuration

**Apply labels to namespaces to enable PSA:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # Enforce restricted profile
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest

    # Audit against restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest

    # Warn against restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```

### Terraform Configuration

```hcl
resource "kubernetes_namespace" "production" {
  metadata {
    name = "production"

    labels = {
      "pod-security.kubernetes.io/enforce"         = "restricted"
      "pod-security.kubernetes.io/enforce-version" = "latest"
      "pod-security.kubernetes.io/audit"           = "restricted"
      "pod-security.kubernetes.io/audit-version"   = "latest"
      "pod-security.kubernetes.io/warn"            = "restricted"
      "pod-security.kubernetes.io/warn-version"    = "latest"
    }
  }
}
```

### Exemptions

**Exempt specific users, namespaces, or RuntimeClasses:**

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
- name: PodSecurity
  configuration:
    apiVersion: pod-security.admission.config.k8s.io/v1
    kind: PodSecurityConfiguration
    defaults:
      enforce: "baseline"
      enforce-version: "latest"
      audit: "restricted"
      audit-version: "latest"
      warn: "restricted"
      warn-version: "latest"
    exemptions:
      usernames: []
      runtimeClasses: []
      namespaces:
        - kube-system
        - kube-public
        - kube-node-lease
```

## Compliant Pod Specifications

### Restricted Profile Example

**Fully compliant with restricted profile:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
  namespace: production
spec:
  # Pod-level security context
  securityContext:
    runAsNonRoot: true
    runAsUser: 10000
    fsGroup: 10000
    fsGroupChangePolicy: "OnRootMismatch"
    seccompProfile:
      type: RuntimeDefault

  containers:
  - name: app
    image: myapp:1.0.0

    # Container-level security context
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 10000
      capabilities:
        drop:
          - ALL
      seccompProfile:
        type: RuntimeDefault

    # Resource limits are required
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "500m"

    # Read-only root FS requires writable mounts
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache

  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

### Baseline Profile Example

**Compliant with baseline but not restricted:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: legacy-app
  namespace: staging
spec:
  securityContext:
    seccompProfile:
      type: RuntimeDefault

  containers:
  - name: app
    image: legacy:1.0.0

    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
        add:
          - NET_BIND_SERVICE  # Allowed in baseline

    # Can run as root (not allowed in restricted)
    # runAsUser not specified - defaults to 0

    resources:
      requests:
        memory: "256Mi"
        cpu: "100m"
      limits:
        memory: "512Mi"
        cpu: "500m"

    volumeMounts:
    - name: data
      mountPath: /data

  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: app-data
```

## Migration Strategy

### Step 1: Audit Current State

**Enable audit mode to identify violations:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: myapp
  labels:
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
    # No enforce label - pods will still be created
```

**Check audit logs:**

```bash
kubectl get events -n myapp --field-selector reason=PodSecurityViolation
```

### Step 2: Fix Violations

**Common fixes for restricted profile:**

1. **Set runAsNonRoot:**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10000
```

2. **Drop all capabilities:**
```yaml
securityContext:
  capabilities:
    drop:
      - ALL
```

3. **Prevent privilege escalation:**
```yaml
securityContext:
  allowPrivilegeEscalation: false
```

4. **Set seccomp profile:**
```yaml
securityContext:
  seccompProfile:
    type: RuntimeDefault
```

5. **Use read-only root filesystem:**
```yaml
securityContext:
  readOnlyRootFilesystem: true
```

6. **Add resource limits:**
```yaml
resources:
  limits:
    memory: "512Mi"
    cpu: "500m"
  requests:
    memory: "256Mi"
    cpu: "100m"
```

### Step 3: Enable Enforcement

**Once violations are fixed, enable enforce mode:**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: myapp
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

## Common Issues and Solutions

### Issue: Application Needs to Write Files

**Problem:** App requires writable filesystem but restricted requires `readOnlyRootFilesystem: true`

**Solution:** Mount emptyDir volumes for writable paths:

```yaml
spec:
  containers:
  - name: app
    securityContext:
      readOnlyRootFilesystem: true
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /var/cache/app
    - name: logs
      mountPath: /var/log/app

  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
  - name: logs
    emptyDir: {}
```

### Issue: Container Image Runs as Root

**Problem:** Dockerfile uses `USER root` or no USER directive

**Solution 1 - Rebuild image:**

```dockerfile
FROM alpine:3.19
RUN addgroup -g 10000 appgroup && \
    adduser -D -u 10000 -G appgroup appuser
USER 10000
```

**Solution 2 - Override in pod spec:**

```yaml
spec:
  securityContext:
    runAsUser: 10000
    runAsGroup: 10000
    fsGroup: 10000
```

### Issue: Application Needs NET_BIND_SERVICE

**Problem:** App binds to privileged port (<1024)

**Solution 1 - Use unprivileged port (≥1024):**
```yaml
# Change app to listen on port 8080 instead of 80
```

**Solution 2 - Use baseline profile:**
```yaml
# Namespace with baseline allows NET_BIND_SERVICE capability
securityContext:
  capabilities:
    add:
      - NET_BIND_SERVICE
```

**Solution 3 - Use Service port mapping:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: app
spec:
  ports:
  - port: 80           # External port
    targetPort: 8080   # Container port
```

## Cluster-Wide Defaults

### Configure Default Policy

**Set cluster-wide defaults in API server configuration:**

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
- name: PodSecurity
  configuration:
    apiVersion: pod-security.admission.config.k8s.io/v1
    kind: PodSecurityConfiguration
    defaults:
      enforce: "baseline"        # Default enforce level
      enforce-version: "latest"
      audit: "restricted"        # Audit against higher standard
      audit-version: "latest"
      warn: "restricted"
      warn-version: "latest"
```

**For managed Kubernetes (EKS, AKS, GKE):**
- Use namespace labels (cluster defaults may not be configurable)
- Create admission webhook for custom enforcement

## Tooling and Validation

### kubectl dry-run

**Test pod compliance before creation:**

```bash
kubectl apply -f pod.yaml --dry-run=server
```

### kubesec

**Static analysis of pod security:**

```bash
docker run -i kubesec/kubesec:v2 scan /dev/stdin < pod.yaml
```

### Polaris

**Cluster-wide security audit:**

```bash
kubectl apply -f https://github.com/FairwindsOps/polaris/releases/latest/download/dashboard.yaml
kubectl port-forward -n polaris svc/polaris-dashboard 8080:80
```

### OPA Gatekeeper

**Custom policy enforcement:**

```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequirenonroot
spec:
  crd:
    spec:
      names:
        kind: K8sRequireNonRoot
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequirenonroot
        violation[{"msg": msg}] {
          not input.review.object.spec.securityContext.runAsNonRoot
          msg := "Pods must specify runAsNonRoot: true"
        }
```

## Best Practices

1. **Start with baseline** - Enforce baseline cluster-wide, restrict sensitive namespaces
2. **Audit before enforcing** - Use audit/warn modes to identify violations
3. **Fix systematically** - Address violations namespace by namespace
4. **Exempt system namespaces** - `kube-system` requires privileged profile
5. **Version your policies** - Pin to specific Kubernetes version for stability
6. **Document exceptions** - Maintain list of exempted workloads with justifications
7. **Test in CI** - Validate pod specs against PSS in CI/CD pipelines
8. **Monitor violations** - Alert on PSS audit events in production

## Compliance Mapping

| Requirement | Profile | Check |
|-------------|---------|-------|
| **CIS Kubernetes Benchmark 5.2.1** | Baseline | Minimize privileged containers |
| **CIS Kubernetes Benchmark 5.2.2** | Baseline | Minimize containers with hostNetwork |
| **CIS Kubernetes Benchmark 5.2.3** | Baseline | Minimize containers with privileged capabilities |
| **CIS Kubernetes Benchmark 5.2.4** | Baseline | Minimize containers with hostPath volumes |
| **CIS Kubernetes Benchmark 5.2.5** | Baseline | Minimize containers with hostPID |
| **CIS Kubernetes Benchmark 5.2.6** | Baseline | Minimize containers with hostIPC |
| **CIS Kubernetes Benchmark 5.2.7** | Restricted | Minimize privileged escalation |
| **CIS Kubernetes Benchmark 5.2.8** | Restricted | Limit use of root containers |
| **CIS Kubernetes Benchmark 5.2.9** | Restricted | Limit NET_RAW capability |
| **NIST SP 800-190** | Restricted | Runtime security |

## Summary Checklist

### For Restricted Profile Compliance:

- [ ] `runAsNonRoot: true` set at pod and container level
- [ ] `allowPrivilegeEscalation: false` set
- [ ] All capabilities dropped (`drop: [ALL]`)
- [ ] Seccomp profile set to `RuntimeDefault`
- [ ] Read-only root filesystem enabled (with emptyDir for writable paths)
- [ ] Resource limits defined for all containers
- [ ] No use of host namespaces (hostNetwork, hostPID, hostIPC)
- [ ] No use of hostPath volumes
- [ ] No privileged containers

### For Namespace Configuration:

- [ ] Production namespaces enforce `restricted`
- [ ] Staging namespaces enforce `baseline`, audit `restricted`
- [ ] System namespaces exempted or set to `privileged`
- [ ] Audit logs monitored for violations
- [ ] Version pinning configured (`enforce-version: latest` or specific version)

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NSA/CISA Kubernetes Hardening Guide](https://media.defense.gov/2022/Aug/29/2003066362/-1/-1/0/CTR_KUBERNETES_HARDENING_GUIDANCE_1.2_20220829.PDF)
