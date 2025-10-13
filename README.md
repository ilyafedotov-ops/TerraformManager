# TerraformManager — Wizard + Reviewer (Extended)

This project is a **RAG/LLM‑friendly** GUI + CLI for:
1) **Generate Terraform** via wizard (AWS, Azure, On‑Prem/Kubernetes).
2) **Review** `.tf` files for best practices/security and produce a **fix report** with explanations.
3) **Validate syntax** (HCL parse) and optionally shell out to `terraform fmt` / `terraform validate` when available.
4) **CI pipeline** that runs the reviewer and uploads a JSON artifact.

> On‑Prem **default** is Kubernetes via the Terraform `kubernetes` provider. You can add vSphere, Proxmox, etc.

---

## Quick start (API)

```bash
python -m venv .venv && source .venv/bin/activate      # (Windows) .venv\Scripts\activate
pip install -r requirements.txt
python -m api  # runs uvicorn api.main:app --reload --port 8890
```

- Open http://localhost:8890 for a minimal HTMX UI.
- Save and list reports via `/scan` and `/reports`.
- Store review configs in SQLite with `/configs` endpoints.
- Sync docs from GitHub with `POST /knowledge/sync`.
- Set `TFM_SQL_ECHO=1` (or `SQLALCHEMY_ECHO=1`) to log SQL emitted by the new SQLAlchemy storage layer.

Read `docs/authentication.md` for a full walkthrough of the password + refresh-token flow and environment controls.

To require a token for all endpoints, set `TFM_API_TOKEN=...` and pass either header `X-API-Token: ...` or `Authorization: Bearer ...`. Set a custom port with `TFM_PORT` or `PORT`.

## Web Frontend (SvelteKit)

```bash
cd frontend
pnpm install
pnpm dev -- --open
```

- Defaults to `http://localhost:5173` and proxies API calls to `http://localhost:8890`; export `VITE_API_BASE` to change.
- Authenticated routes live under `(app)/` while guest flows live under `(auth)/`; tokens persist via cookies/local storage helpers.

### Authentication Settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `TFM_API_TOKEN` / `API_TOKEN` | `local-dev` | Legacy single-user password required for login. |
| `TFM_JWT_SECRET` | `dev-secret-change-me` | Symmetric signing key for access tokens. |
| `TFM_REFRESH_SECRET` | falls back to `TFM_JWT_SECRET` | Optional distinct secret for refresh tokens. |
| `TFM_ACCESS_TOKEN_MINUTES` | `30` | Access token lifetime (minutes). |
| `TFM_REFRESH_TOKEN_MINUTES` | `10080` (7 days) | Refresh token lifetime (minutes). |
| `TFM_COOKIE_SECURE` | `false` | Set `true`/`1` in production to emit `Secure` cookies. |
| `TFM_COOKIE_DOMAIN` | unset | Optional domain attribute for cookie scope. |
| `TFM_COOKIE_SAMESITE` | `lax` | SameSite mode for refresh cookies (`lax`, `strict`, `none`). |
| `TFM_AUTH_REFRESH_COOKIE` | `tm_refresh_token` | Cookie name that stores the refresh token. |

Login issues a short-lived access token and a `tm_refresh_token` HttpOnly cookie. Clients must echo the refresh cookie alongside the `X-Refresh-Token-CSRF` header (returned after login/refresh) when calling `/auth/refresh`.

## CLI (for CI or local)

```bash
# Policy scan with formatting, validate, cost, and plan drift awareness
python -m backend.cli scan --path . --out report.json \
  --terraform-fmt \
  --terraform-validate \
  --cost \
  --cost-usage-file infracost-usage.yml \
  --plan-json plan.json

# Capture autofixable diffs alongside the JSON report
python -m backend.cli scan --path . --out report.json --patch-out autofix.patch

# Generate a baseline waiver file (YAML)
python -m backend.cli baseline --path .

# Scaffold pre-commit hooks (fmt/validate/tflint/checkov/infracost/docs)
python -m backend.cli precommit --out .pre-commit-config.yaml

# Generate template documentation (mirrors into docs/ and knowledge/)
python -m backend.cli docs --out docs/generators --knowledge-out knowledge/generated

# Authenticate against running API (stores access/refresh data in tm_auth.json)
python -m backend.cli auth login --email you@example.com --base-url http://localhost:8890
```

To run template smoke tests with `terraform validate`, export `TFM_RUN_TERRAFORM_VALIDATE=1` before executing `python -m unittest` or the new pytest-based smoke test (`TFM_RUN_TERRAFORM_VALIDATE=1 pytest tests/test_terraform_validate_smoke.py`). Terraform must be on `PATH`; tests fall back gracefully if it is absent.

## CI (GitHub Actions)

- Workflow file: `.github/workflows/terraform-review.yml`
- Produces artifact: `terraform_review_report.json`

---

## What’s included

- `frontend/` — SvelteKit dashboard for generator, reviewer, and knowledge workflows (reviewer view now surfaces cost & drift summaries)
- `backend/cli.py` — CLI to scan paths and write a JSON report
- `backend/scanner.py` — Static checks for AWS, Azure, K8s; syntax/HCL parse checker; optional terraform validate hook
- `backend/db/` — SQLAlchemy engine/session helpers plus ORM definitions for configs, reports, and settings
- `backend/rag.py` — Local TF‑IDF retrieval over `knowledge/`
- `backend/validators.py` — Optional helpers for `terraform fmt` / `validate`
- `backend/utils/diff.py` — helper for unified diffs
- `backend/generators/` — Jinja templates:
  - `aws_s3_bucket.tf.j2`
  - `aws_observability_baseline.tf.j2`
  - `aws_alb_waf.tf.j2`
  - `aws_eks_cluster.tf.j2` (optional IMDSv2-required launch template)
  - `aws_ecs_fargate_service.tf.j2`
  - `aws_eks_irsa_service.tf.j2`
  - `aws_rds_baseline.tf.j2`
  - `aws_rds_multi_region.tf.j2`
  - `aws_vpc_networking.tf.j2`
  - `azure_key_vault.tf.j2`
  - `azure_diagnostics_baseline.tf.j2`
  - `azure_storage_account.tf.j2`
  - `azure_vnet_baseline.tf.j2`
    - Auto-suggests diagnostics for VNets/Subnets/NSGs and emits helper outputs for private endpoints/logging.
  - `k8s_deployment.tf.j2` (On‑Prem default)
  - `k8s_namespace_baseline.tf.j2`
  - `k8s_pod_security_baseline.tf.j2`
  - `k8s_psa_namespaces.tf.j2` (supports per-namespace team overrides via `namespace,team` syntax)
  - `k8s_argo_cd_baseline.tf.j2`
  - `k8s_hpa_pdb.tf.j2`
- `knowledge/` — seed Markdown docs (Terraform language + best practices for AWS/Azure/K8s)
- `docs/report_schema.json` — report contract
- `docs/azure_diagnostics.md` — how to auto-generate diagnostics targets and consume outputs
- `sample/` — growing library of examples: S3 (`aws_s3_insecure.tf`), IAM wildcard (`aws_iam_insecure.tf`), VPC flow logs (`aws_vpc_no_flow_logs.tf`), multi-region RDS (`aws_rds_multi_region.tf`), Azure diagnostics (`azure_diagnostics_health_alert.tf`), and Kubernetes seccomp/AppArmor (`k8s_insecure_seccomp.tf`).

> Extend by adding more templates (RDS/EKS/ECS, Azure AKS/Key Vault, K8s/Helm/vSphere) and more review rules.

---

## FastAPI endpoints (summary)

- GET `/health` — liveness
- POST `/scan` — run & save a report
- GET `/reports` — list recent reports
- GET `/reports/{id}` — report JSON
- GET `/reports/{id}/html` — report HTML
- GET `/reports/{id}/csv` — findings as CSV
- DELETE `/reports/{id}` — delete a report
- GET `/ui/reports/{id}/viewer` — inline report viewer with filters
- GET `/ui/reports/{id}/viewer/csv` — filtered CSV export (viewer filters)
- GET `/ui/reports/export-zip?ids=<id1,id2,...>` — bulk export selected reports as a ZIP (HTML + CSV + JSON)
- GET `/` — minimal HTMX UI
- GET `/configs`, POST `/configs`, GET `/configs/{name}` — config storage
- DELETE `/configs/{name}` — delete a config
- POST `/preview/config-application` — JSON preview of waivers/thresholds
- GET `/preview/config-application/html` — HTML preview of waivers/thresholds
- POST `/knowledge/sync` — sync Markdown from GitHub (default HashiCorp Azure Storage policy library)

## Docker

Build and run the API + UI without installing dependencies locally:

```bash
docker build -t terraform-manager:local .
docker run --rm -p 8890:8890 \
  -e TFM_PORT=8890 \
  -e TFM_API_TOKEN=changeme \
  -v "$(pwd)/knowledge:/app/knowledge" \
  -v "$(pwd)/data:/app/data" \
  terraform-manager:local
```

Open http://localhost:8890. To customize port, change `-p` and `TFM_PORT`.

### Docker Compose

```bash
docker compose up --build
```

This mounts `knowledge/` and `data/` for persistence and serves on port 8890.

### AWS ALB logging tips
- When generating the ALB baseline, toggle **Enable ALB access logging** to create a hardened logging bucket automatically.
- If your organization uses a shared log bucket, uncheck **Create and manage log bucket** and supply the shared bucket name/prefix—the template will reference it without trying to manage policies you already own.

### AWS EKS hardening
- The EKS generator now enables control plane logging for `api`, `audit`, `authenticator`, `controllerManager`, and `scheduler`.
- Select **Require IMDSv2 on nodes** to enforce metadata-token requirements via a launch template (recommended for all managed node groups).
- Use the **EKS IRSA Service Module** generator to scaffold namespaces, IRSA roles, and service accounts with least-privilege policies.

### AWS ECS service guidance
- The **ECS Fargate Service** generator emits private networking, IAM roles, and CloudWatch logging defaults rated for production.
- The reviewer flags Fargate services that still assign public IPs so you can route traffic through load balancers or NAT gateways instead.

### Kubernetes GitOps baseline
- The **Argo CD Baseline** generator provisions a restricted namespace, baseline network policies, optional quotas, and installs the official chart with hardened values (admin disabled, PodSecurity defaults, ingress optional).
- Configure the Terraform `kubernetes` and `helm` providers with cluster credentials (host/token/CA) before applying the module.
- Enable ingress when exposing the API externally; otherwise rely on the internal `argocd-server` service.

### Azure diagnostics helpers
- The diagnostics wizard can auto-populate targets for VNets, subnets, NSGs, and storage accounts—provide the subscription ID and resource names to generate the correct resource IDs.
- Generated Terraform emits outputs (`log_analytics_workspace_id`, storage account helpers, diagnostic maps) to streamline private endpoint creation and downstream automation.
- The AKS generator keeps the Azure Policy add-on enabled by default; the reviewer now flags clusters that disable it.
- Control plane diagnostics must include `kube-apiserver`, audit/admin, controller-manager, scheduler, cluster-autoscaler, and guard logs—the reviewer verifies every category is enabled.
- The Review tab now surfaces severity counts and highlights when `tfreview.yaml` severity gates fail so you can react quickly.

### HTML Reporting
- `backend.cli scan` supports `--html-out report.html` to render findings, severities, and thresholds as a self-contained HTML summary.
- Combine with `--patch-out` to ship both a human-friendly report and ready-to-apply diffs in CI artifacts.

---

## Roadmap (suggested)
- Add vSphere VM generator & checks.
- Add more Azure/AWS/K8s rules (CIS aligned).
- Generate `.patch` files for “one‑click fix” with `git apply`.
- GitHub App that comments on PRs using the JSON report.

- Diagnostics fixture for integration: see docs/integration-fixtures.md

- PodSecurity namespace generator usage: see docs/k8s_podsecurity.md
