"""Trivial static checks for the platform Dockerfile."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = REPO_ROOT / "pipeline" / "docker" / "dotnet.Dockerfile"


class DockerfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = DOCKERFILE_PATH.read_text(encoding="utf-8")

    def test_exposes_8080(self) -> None:
        self.assertIn("EXPOSE 8080", self.text)


if __name__ == "__main__":
    unittest.main()
