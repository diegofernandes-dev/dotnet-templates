"""Contract checks for the sample consumer azure-pipelines.yml."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSUMER_PATH = REPO_ROOT / "azure-pipelines.yml"


class SampleConsumerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = CONSUMER_PATH.read_text(encoding="utf-8")

    def test_extends_platform_template(self) -> None:
        self.assertIn("extends:", self.text)
        self.assertIn("template: pipeline/templates/dotnet-k8s.yml", self.text)

    def test_does_not_pass_ci_pool_name(self) -> None:
        self.assertNotIn("ciPoolName", self.text)

    def test_does_not_pass_helm_chart_path(self) -> None:
        self.assertNotIn("helmChartPath", self.text)

    def test_does_not_override_aws_service_connection(self) -> None:
        self.assertNotIn("awsServiceConnection", self.text)

    def test_declares_environments(self) -> None:
        self.assertIn("environments:", self.text)


if __name__ == "__main__":
    unittest.main()
