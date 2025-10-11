# AWS ECS & EKS Service Hardening

## ECS Fargate Networking
- Run Fargate tasks in private subnets and keep `assign_public_ip` disabled; expose traffic through load balancers and NAT gateways instead of direct public addressing.
- Ensure security groups and VPC routing only allow expected ingress/egress paths, and publish application logs to CloudWatch or an observability pipeline.

## EKS IRSA Trust Policies
- Constrain IAM roles assumed via IRSA with `StringEquals` on `<OIDC_HOST>:sub` targeting the namespace and service account that should receive the credentials.
- Require the `sts.amazonaws.com` audience with `StringLike` on `<OIDC_HOST>:aud` so only Kubernetes-issued tokens for STS can assume the role.
- Rotate service account tokens and audit IAM role usage to detect unexpected callers.
