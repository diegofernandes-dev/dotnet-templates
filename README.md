# pipeline-template

Minimal Azure DevOps pipeline template for .NET APIs: build once, push an immutable image to AWS ECR, promote that exact image through an ordered list of Kubernetes environments with Helm.

## Architecture

```text
APPLICATION REPOSITORY CONFIG
        |
        | appName
        | projectPath
        | imageRepository
        | helmReleaseName
        | environments[]
        v
+--------------------------------+
|       PLATFORM TEMPLATE        |
|                                |
|  Azure Pipelines YAML          |
|  .NET Dockerfile               |
|  Generic Helm chart            |
+--------------------------------+
        |
        | build once / push once
        v
      AWS ECR
        |
        | exact same SHA image
        v
 env[0] -> env[1] -> env[2] -> ...
```

## Application configuration vs platform vs environment

| Concern | Owner | Examples |
|---------|--------|----------|
| Application configuration | Consumer repo (`azure-pipelines.yml`) | `appName`, `projectPath`, `imageRepository`, `helmReleaseName` |
| Platform implementation | This template | Dockerfile path, Helm chart path, `docker build`/`push`, Helm command, timeouts |
| Environment target configuration | Consumer `environments[]` | `name`, `azureEnvironment`, `poolName`, `namespace` |

The consumer does **not** pass Dockerfile path, Helm chart path, container port, health path, AWS credentials, or Helm timeout. Those are internal template decisions.

## Template contract

Extend [`pipeline/templates/dotnet-k8s.yml`](pipeline/templates/dotnet-k8s.yml):

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `appName` | yes | — | Logical application identity (passed to Helm as `application.name`) |
| `projectPath` | yes | — | Path to the `.csproj` |
| `imageRepository` | yes | — | Full container image repository URI (e.g. ECR) |
| `ciPoolName` | no | `Default` | Agent pool for CI |
| `helmReleaseName` | yes | — | Helm release name (deployment instance; not derived from `appName`) |
| `environments` | yes | — | Ordered list of promotion targets (see below) |

### `environments[]`

Order in the array **is** the promotion order. The consumer does not declare `dependsOn`; the template emits stages in that sequence after CI.

| Field | Description |
|-------|-------------|
| `name` | Stage/deployment id fragment (see naming rules) |
| `azureEnvironment` | Azure DevOps Environment resource name (explicit; not derived) |
| `poolName` | Agent pool for that deployment |
| `namespace` | Kubernetes namespace (explicit; must already exist) |

Example shape:

```yaml
environments:
  - name: sandbox
    azureEnvironment: my-app-sandbox
    poolName: MyPool
    namespace: my-app-sandbox
  - name: production
    azureEnvironment: my-app-production
    poolName: MyPool
    namespace: my-app-production
```

### Stage name rules

`environment.name` is used at **compile time** as part of stage and deployment job identifiers (e.g. `Deploy_dev`).

It must be a valid Azure Pipelines identifier:

- start with a letter
- then only letters, digits, or underscore (`_`)
- no spaces, hyphens, or other punctuation

The template does not sanitize names.

### Image tagging and promotion

- Exactly one `docker build` and one `docker push` per pipeline run
- Tag is always `$(Build.SourceVersion)` (commit SHA)
- Every environment deploys `<imageRepository>:$(Build.SourceVersion)` — no rebuild, retag, `latest`, or per-environment image

### Platform assets (internal)

| Asset | Location |
|-------|----------|
| Dockerfile | `pipeline/docker/dotnet.Dockerfile` |
| Helm chart | `pipeline/helm/application` |

### Helm chart contract

- Chart identity is generic (`application`); it is **not** the application name
- Application identity is set via `application.name` (from `appName`)
- Labels: `app.kubernetes.io/name` = application name; `app.kubernetes.io/instance` = Helm release
- `imagePullSecrets` defaults to empty; the chart does not invent cluster credentials

## Prerequisites

- Azure DevOps organization and project
- CI agent pool with Docker and .NET 10 (or installable via `UseDotNet@2`)
- CI agent already authenticated so `docker push <imageRepository>:<tag>` works (ECR repository must already exist)
- Deploy agent(s) with `helm` and cluster access for each target
- Each `azureEnvironment` already created in Azure DevOps
- Each `namespace` already created and prepared (RBAC, pull access, etc.) — the pipeline does **not** use `--create-namespace`
- Cluster able to pull the image (lab-specific secrets such as `ecr-pull` are infrastructure setup, not a platform chart default)

AWS credential bootstrap (keys, instance profile, service connections) is intentionally outside this template.

## Sample consumer / local lab

[`azure-pipelines.yml`](azure-pipelines.yml) and [`src/Sample.Api`](src/Sample.Api) are an **example consumer**, not platform rules.

| Lab setting | Value |
|-------------|-------|
| ECR | `448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api` |
| CI pool | `Self-Hosted-Rancher` |
| Deploy pools | `Self-Hosted-Rancher` (all envs in this lab) |
| Environments | `develop`, `homolog`, `production` |
| Namespaces | `sample-api-dev`, `sample-api-hml`, `sample-api-prd` |

If this lab uses an `ecr-pull` imagePullSecret, configure it on the target namespaces (or ServiceAccounts) outside the chart. Do not treat `ecr-pull` as a platform convention.

Consumer shape:

```yaml
extends:
  template: pipeline/templates/dotnet-k8s.yml
  parameters:
    appName: sample-api
    projectPath: src/Sample.Api/Sample.Api.csproj
    imageRepository: 448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api
    ciPoolName: Self-Hosted-Rancher
    helmReleaseName: sample-api
    environments:
      - name: dev
        azureEnvironment: develop
        poolName: Self-Hosted-Rancher
        namespace: sample-api-dev
      # ...
```

## Monorepo limitation

This repository currently packs the sample app, the YAML template, the Dockerfile, and the Helm chart together.

Azure DevOps can load YAML templates from another repository at compile time, but **runtime assets** (Dockerfile, Helm chart) need an explicit checkout/distribution strategy when the template is consumed from a different repo.

That strategy is **not** part of this slice. Do not assume cross-repository reuse of Dockerfile/chart is solved yet.

## Known limitations / debt

- The Dockerfile assumes the published assembly basename matches the `.csproj` filename (no `assemblyName` parameter yet)
- No approvals, checks, or gates on Azure DevOps Environments yet
- No values files per environment; one image and the same chart settings for all targets
