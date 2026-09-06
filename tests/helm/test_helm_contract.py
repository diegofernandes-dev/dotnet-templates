"""Helm chart contract tests via helm lint/template."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_PATH = REPO_ROOT / "pipeline" / "helm" / "application"

RELEASE = "contract-test"
APP_NAME = "contract-api"
IMAGE_REPOSITORY = "example.invalid/contract-api"
IMAGE_TAG = "abc123"


def _helm(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["helm", *args],
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _default_set_args() -> list[str]:
    return [
        "--set",
        f"application.name={APP_NAME}",
        "--set",
        f"image.repository={IMAGE_REPOSITORY}",
        "--set",
        f"image.tag={IMAGE_TAG}",
    ]


def _render(*extra: str) -> list[dict[str, Any]]:
    result = _helm(
        "template",
        RELEASE,
        str(CHART_PATH),
        *_default_set_args(),
        *extra,
    )
    docs = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    return docs


def _by_kind(docs: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    matches = [doc for doc in docs if doc.get("kind") == kind]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {kind}, found {len(matches)}")
    return matches[0]


class HelmContractTests(unittest.TestCase):
    def test_helm_lint_passes(self) -> None:
        result = _helm("lint", str(CHART_PATH))
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_helm_template_passes(self) -> None:
        docs = _render()
        self.assertGreaterEqual(len(docs), 2)

    def test_application_identity(self) -> None:
        deployment = _by_kind(_render(), "Deployment")
        labels = deployment["metadata"]["labels"]
        self.assertEqual(labels["app.kubernetes.io/name"], APP_NAME)
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["name"], APP_NAME)
        self.assertNotEqual(labels["app.kubernetes.io/name"], "application")
        self.assertNotEqual(container["name"], "application")

    def test_release_instance_identity(self) -> None:
        docs = _render()
        for doc in docs:
            labels = doc.get("metadata", {}).get("labels", {})
            self.assertEqual(labels.get("app.kubernetes.io/instance"), RELEASE)

    def test_selectors_are_consistent(self) -> None:
        docs = _render()
        deployment = _by_kind(docs, "Deployment")
        service = _by_kind(docs, "Service")

        match_labels = deployment["spec"]["selector"]["matchLabels"]
        pod_labels = deployment["spec"]["template"]["metadata"]["labels"]
        service_selector = service["spec"]["selector"]

        for key, value in match_labels.items():
            self.assertEqual(
                pod_labels.get(key),
                value,
                f"Deployment matchLabels[{key}] not present on pod template",
            )

        for key, value in service_selector.items():
            self.assertEqual(
                pod_labels.get(key),
                value,
                f"Service selector[{key}] does not match Deployment pods",
            )

    def test_image_repository_and_tag(self) -> None:
        deployment = _by_kind(_render(), "Deployment")
        image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
        self.assertEqual(image, f"{IMAGE_REPOSITORY}:{IMAGE_TAG}")

    def test_application_port_and_health_contract(self) -> None:
        deployment = _by_kind(_render(), "Deployment")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["ports"][0]["containerPort"], 8080)
        self.assertEqual(container["livenessProbe"]["httpGet"]["path"], "/health")
        self.assertEqual(container["readinessProbe"]["httpGet"]["path"], "/health")

    def test_service_contract(self) -> None:
        service = _by_kind(_render(), "Service")
        self.assertEqual(service["spec"]["type"], "ClusterIP")
        port = service["spec"]["ports"][0]
        self.assertEqual(port["port"], 80)
        self.assertEqual(port["targetPort"], "http")

    def test_image_pull_secrets_absent_by_default(self) -> None:
        deployment = _by_kind(_render(), "Deployment")
        pod_spec = deployment["spec"]["template"]["spec"]
        self.assertNotIn("imagePullSecrets", pod_spec)

    def test_image_pull_secrets_when_configured(self) -> None:
        docs = _render("--set", "imagePullSecrets[0].name=test-registry")
        deployment = _by_kind(docs, "Deployment")
        secrets = deployment["spec"]["template"]["spec"]["imagePullSecrets"]
        self.assertEqual(secrets, [{"name": "test-registry"}])

    def test_empty_application_name_is_not_rejected(self) -> None:
        """Documents current chart behavior: empty name still renders (null label)."""
        result = _helm(
            "template",
            RELEASE,
            str(CHART_PATH),
            "--set",
            "application.name=",
            "--set",
            f"image.repository={IMAGE_REPOSITORY}",
            "--set",
            f"image.tag={IMAGE_TAG}",
        )
        self.assertEqual(result.returncode, 0)
        deployment = _by_kind(
            [doc for doc in yaml.safe_load_all(result.stdout) if doc],
            "Deployment",
        )
        # Helm emits `app.kubernetes.io/name:` with a null YAML value when empty.
        self.assertIsNone(
            deployment["metadata"]["labels"]["app.kubernetes.io/name"],
        )

    def test_empty_image_fields_render_empty_image_ref(self) -> None:
        """Documents current chart behavior: empty image fields are not rejected."""
        result = _helm(
            "template",
            RELEASE,
            str(CHART_PATH),
            "--set",
            f"application.name={APP_NAME}",
            "--set",
            "image.repository=",
            "--set",
            "image.tag=",
        )
        self.assertEqual(result.returncode, 0)
        deployment = _by_kind(
            [doc for doc in yaml.safe_load_all(result.stdout) if doc],
            "Deployment",
        )
        image = deployment["spec"]["template"]["spec"]["containers"][0]["image"]
        self.assertEqual(image, ":")


if __name__ == "__main__":
    unittest.main()
