# pipeline-template

Minimal Azure DevOps pipeline template for a .NET application: build once, push an immutable image to AWS ECR, deploy that exact image with Helm.

## Architecture

```text
Azure DevOps Agent (CI)
        |
        | restore/build/test
        | ensure ECR repository
        | docker build/push
        v
     AWS ECR (us-east-1)
        |
        | image:<commit-sha>
        v
Azure DevOps Agent no Kubernetes (Deploy)
        |
        | helm upgrade --install
        v
    Kubernetes
```

## Prerequisites

- Azure DevOps organization and project
- Agent pool for CI (Docker, AWS CLI, .NET 10 available or installable via `UseDotNet@2`)
- CI agent already authenticated and authorized for AWS ECR (`docker push` and `aws ecr create-repository`)
- Self-hosted deploy agent running inside Kubernetes (`helm` and `kubectl` available, cluster access already configured)
- Target namespace able to pull from ECR (e.g. `ecr-pull` imagePullSecret)
- Helm chart and application in this repository

> AWS credential bootstrap (keys, instance profile, etc.) is intentionally outside this template. The pipeline assumes the agent can already call AWS ECR APIs and `docker push`.

## Lab onboarding (Rancher Desktop)

This repo is wired for:

| Setting | Value |
|---------|-------|
| ECR | `448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api` |
| Region | `us-east-1` |
| CI / Deploy pool | `Self-Hosted-Rancher` |
| Namespace | `sample-api` |

The CI stage creates the ECR repository if it does not exist.

## Configuration

Edit [`azure-pipelines.yml`](azure-pipelines.yml) parameters:

| Parameter | Description |
|-----------|-------------|
| `appName` | Application name used in job display names |
| `projectPath` | Path to the `.csproj` |
| `imageRepository` | Full ECR repository URI |
| `ciPoolName` | Agent pool for CI (default `Default`) |
| `deployPoolName` | Agent pool for Deploy (self-hosted in Kubernetes) |
| `kubernetesNamespace` | Target Kubernetes namespace |
| `helmReleaseName` | Helm release name |
| `helmChartPath` | Path to the Helm chart |

Image tag is always `$(Build.SourceVersion)` (commit SHA). The same `repository:tag` produced by CI is what Deploy installs.
