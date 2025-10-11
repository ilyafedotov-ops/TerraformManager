from backend.policies import syntax, aws, azure, k8s

ALL_CHECKS = (
    syntax.CHECKS
    + aws.CHECKS
    + azure.CHECKS
    + k8s.CHECKS
)

__all__ = ["ALL_CHECKS"]
