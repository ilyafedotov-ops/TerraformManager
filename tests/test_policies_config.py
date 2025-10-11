import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from backend.policies.config import load_config, apply_config


class ConfigLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._cwd = os.getcwd()

    def tearDown(self) -> None:
        os.chdir(self._cwd)

    def test_load_and_apply_config_with_waivers_and_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "proj"
            project.mkdir()
            (project / "tfreview.yaml").write_text(
                textwrap.dedent(
                    """
                    ignore:
                      - id: AWS-S3-SSE::example
                        reason: "Legacy bucket"
                      - rule: K8S-POD-RESOURCES-LIMITS
                        reason: "Platform-managed workloads"
                    thresholds:
                      fail_on:
                        - CRITICAL
                    """
                ).strip()
            )

            os.chdir(project)
            config = load_config([project])

            self.assertEqual(len(config.waivers), 2)
            self.assertEqual(config.waivers[0].scope, "id")
            self.assertEqual(config.waivers[0].reason, "Legacy bucket")
            self.assertEqual(config.thresholds.fail_on, ["CRITICAL"])

            findings = [
                {
                    "id": "AWS-S3-SSE::example",
                    "rule": "AWS-S3-SSE",
                    "title": "dummy",
                    "severity": "HIGH",
                    "file": "main.tf",
                },
                {
                    "id": "AWS-S3-PUBLIC-ACL::example",
                    "rule": "AWS-S3-PUBLIC-ACL",
                    "title": "dummy",
                    "severity": "CRITICAL",
                    "file": "main.tf",
                },
            ]

            applied = apply_config(findings, config)

            self.assertEqual(len(applied["active"]), 1)
            self.assertEqual(applied["active"][0]["id"], "AWS-S3-PUBLIC-ACL::example")
            self.assertEqual(len(applied["waived"]), 1)
            self.assertEqual(applied["waived"][0]["id"], "AWS-S3-SSE::example")

            severity_counts = applied["severity_counts"]
            self.assertEqual(severity_counts["CRITICAL"], 1)

            thresholds = applied["thresholds"]
            self.assertTrue(thresholds["configured"])
            self.assertTrue(thresholds["triggered"])
            self.assertEqual(thresholds["violated_ids"], ["AWS-S3-PUBLIC-ACL::example"])


if __name__ == "__main__":
    unittest.main()
