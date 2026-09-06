"""Structural contract tests for pipeline/templates/dotnet-k8s.yml."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "pipeline" / "templates" / "dotnet-k8s.yml"


class PipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = TEMPLATE_PATH.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def test_ci_uses_ubuntu_24_04_vm_image(self) -> None:
        self.assertIn("vmImage: ubuntu-24.04", self.text)

    def test_ci_pool_name_not_in_public_contract(self) -> None:
        self.assertNotIn("ciPoolName", self.text)

    def test_ci_stage_has_exactly_one_job(self) -> None:
        ci_block = self._stage_block("CI")
        job_count = len(re.findall(r"(?m)^\s+- job:", ci_block))
        deployment_count = len(re.findall(r"(?m)^\s+- deployment:", ci_block))
        self.assertEqual(job_count, 1, "CI stage must contain exactly one job")
        self.assertEqual(deployment_count, 0, "CI stage must not use deployment jobs")

    def test_aws_oidc_task_and_default_connection(self) -> None:
        self.assertIn("AWSShellScript@1", self.text)
        self.assertIn("awsCredentials: ${{ parameters.awsServiceConnection }}", self.text)
        self.assertRegex(
            self.text,
            r"(?ms)- name: awsServiceConnection\s+type: string\s+default: aws-ecr-oidc",
        )

    def test_no_static_aws_credentials_in_template(self) -> None:
        forbidden = (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AccessKey",
            "SecretKey",
            "aws configure",
        )
        for token in forbidden:
            self.assertNotIn(token, self.text, f"forbidden credential pattern: {token}")

    def test_ecr_is_not_provisioned(self) -> None:
        self.assertNotIn("aws ecr create-repository", self.text)

    def test_explicit_linux_amd64_platform(self) -> None:
        self.assertIn("--platform linux/amd64", self.text)

    def test_single_image_publication_via_buildx(self) -> None:
        buildx_builds = re.findall(r"(?m)^\s*docker buildx build\b", self.text)
        self.assertEqual(len(buildx_builds), 1, "exactly one docker buildx build expected")
        self.assertIn("--push", self.text)

        plain_builds = re.findall(r"(?m)^\s*docker build\b", self.text)
        self.assertEqual(plain_builds, [], "plain docker build must not appear")

        deploy_block = self._deploy_loop_block()
        self.assertNotIn("docker build", deploy_block)
        self.assertNotIn("docker push", deploy_block)
        self.assertNotIn("buildx build", deploy_block)

    def test_immutable_source_version_identity(self) -> None:
        self.assertIn('IMAGE="${IMAGE_REPOSITORY}:$(Build.SourceVersion)"', self.text)
        self.assertIn('--set image.tag="$(Build.SourceVersion)"', self.text)
        self.assertNotIn(":latest", self.text)
        self.assertNotIn("$(Build.BuildId)", self.text)

    def test_multi_environment_parameter_is_generic(self) -> None:
        self.assertRegex(
            self.text,
            r"(?ms)- name: environments\s+type: object",
        )
        self.assertIn("${{ each env in parameters.environments }}", self.text)
        for hardcoded in ("DeployDEV", "DeployHML", "DeployPRD"):
            self.assertNotIn(hardcoded, self.text)

    def test_deployment_jobs_use_environment_pool_and_namespace(self) -> None:
        self.assertIn("- deployment: Deploy_${{ env.name }}", self.text)
        self.assertIn("environment: ${{ env.azureEnvironment }}", self.text)
        self.assertIn("name: ${{ env.poolName }}", self.text)
        self.assertIn('--namespace "${{ env.namespace }}"', self.text)

    def test_helm_chart_path_is_internal(self) -> None:
        self.assertIn('"pipeline/helm/application"', self.text)
        self.assertNotIn("helmChartPath", self.text)

    def test_namespace_is_not_provisioned(self) -> None:
        self.assertNotIn("--create-namespace", self.text)

    def test_inline_script_surface_contracts(self) -> None:
        self.assertIn("dkr.ecr", self.text)
        self.assertIn("EcrRegion", self.text)
        self.assertIn("aws sts get-caller-identity", self.text)
        self.assertIn("aws ecr get-login-password", self.text)
        self.assertIn("docker login", self.text)
        self.assertIn("aws ecr describe-images", self.text)
        self.assertIn("helm upgrade --install", self.text)
        self.assertIn("--wait", self.text)
        self.assertIn("--atomic", self.text)
        self.assertIn("--timeout 5m", self.text)

    def _stage_block(self, stage_name: str) -> str:
        pattern = rf"(?ms)^  - stage: {re.escape(stage_name)}\n(.*?)(?=^  - |^  - \$\{{{{|\Z)"
        match = re.search(pattern, self.text)
        self.assertIsNotNone(match, f"stage {stage_name} not found")
        assert match is not None
        return match.group(0)

    def _deploy_loop_block(self) -> str:
        marker = "${{ each env in parameters.environments }}"
        idx = self.text.find(marker)
        self.assertGreaterEqual(idx, 0, "environment loop not found")
        return self.text[idx:]


if __name__ == "__main__":
    unittest.main()
