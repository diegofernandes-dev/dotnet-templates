# pipeline-template

Minimal Azure DevOps pipeline template for .NET APIs: build once on ephemeral Microsoft-hosted CI, push an immutable `linux/amd64` image to AWS ECR via OIDC, and promote that exact image through an ordered list of Kubernetes environments with Helm.

## Architecture

```text
APPLICATION
    |
    | appName
    | projectPath
    | imageRepository
    | helmReleaseName
    | environments[]
    v
+--------------------------------------+
|          PLATFORM TEMPLATE           |
|                                      |
| CI:                                  |
| Microsoft-hosted Ubuntu 24.04        |
| one ephemeral job                    |
| AWS OIDC Service Connection          |
| Buildx linux/amd64                   |
|                                      |
| Assets:                              |
| platform Dockerfile                  |
| generic Helm chart                   |
+------------------+-------------------+
                   |
                   v
              AWS STS / IAM
                   |
                   v
                  ECR
                   |
         <repo>:<commit-sha>
                   |
              linux/amd64
                   |
       ========================
          PRIVATE CD PLANE
       ========================
                   |
                   v
                env[0]
           self-hosted pool
                   |
                   v
                env[1]
           self-hosted pool
                   |
                   v
                  ...
```

## Ownership

### Application configuration

```text
appName
projectPath
imageRepository
helmReleaseName
```

### Environment target configuration

```text
environment.name
environment.azureEnvironment
environment.poolName
environment.namespace
```

### Platform implementation

```text
Microsoft-hosted CI
ubuntu-24.04
Dockerfile
Buildx
linux/amd64
generic Helm chart
Helm timeout
```

### Platform integrations

```text
AWS Toolkit for Azure DevOps
AWS Service Connection
OIDC
AWS IAM Role
AWS STS
ECR
```

Application teams do not need to decide details of **platform implementation** or **platform integrations**.

| Concern | Owner | Examples |
|---------|--------|----------|
| Application configuration | Consumer repo (`azure-pipelines.yml`) | `appName`, `projectPath`, `imageRepository`, `helmReleaseName` |
| Environment target configuration | Consumer `environments[]` | `name`, `azureEnvironment`, `poolName`, `namespace` |
| Platform implementation | This template | CI `ubuntu-24.04`, Dockerfile, Buildx `linux/amd64`, Helm chart, timeouts |
| Platform integrations | This template + infra | AWS Service Connection OIDC, IAM Role, ECR |

The consumer does **not** pass Dockerfile path, Helm chart path, container port, health path, CI pool, AWS credentials, or Helm timeout.

## Security rationale

CI executes on ephemeral Microsoft-hosted compute.

It does not require placement inside the private corporate network.

AWS access uses workload identity federation through an OIDC-enabled AWS Service Connection.

No long-lived AWS credentials are stored in the pipeline.

AWS STS issues temporary credentials for a narrowly scoped IAM Role.

Deployment remains on private self-hosted agents because Kubernetes connectivity is private.

## Template contract

Extend [`pipeline/templates/dotnet-k8s.yml`](pipeline/templates/dotnet-k8s.yml):

| Parameter | Required | Default | Category | Description |
|-----------|----------|---------|----------|-------------|
| `appName` | yes | — | application | Logical application identity (passed to Helm as `application.name`) |
| `projectPath` | yes | — | application | Path to the `.csproj` |
| `imageRepository` | yes | — | application | Full ECR image repository URI |
| `helmReleaseName` | yes | — | application | Helm release name (not derived from `appName`) |
| `environments` | yes | — | environment | Ordered list of promotion targets |
| `awsServiceConnection` | no | `aws-ecr-oidc` | **platform integration setting** | Azure DevOps AWS Service Connection name (OIDC). Override only when an installation uses a different connection name. |

`awsServiceConnection` is **not** application configuration.

### `environments[]`

Order in the array **is** the promotion order. The consumer does not declare `dependsOn`; the template emits stages in that sequence after CI.

| Field | Description |
|-------|-------------|
| `name` | Stage/deployment id fragment (see naming rules) |
| `azureEnvironment` | Azure DevOps Environment resource name (explicit; not derived) |
| `poolName` | Self-hosted agent pool for that deployment |
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

- Runtime target: **`linux/amd64` only** (explicit Buildx `--platform linux/amd64`)
- One Buildx build+push operation per pipeline run
- Tag is always `$(Build.SourceVersion)` (commit SHA)
- Every environment deploys `<imageRepository>:$(Build.SourceVersion)` — no rebuild, retag, `latest`, or per-environment image
- No architecture-specific tags (`-amd64` / `-arm64`)
- No multi-arch image index in this slice

### Application contract (platform chart)

- Application listens on port **8080**
- `GET /health` returns a successful health response

These are fixed platform conventions for this version. They are not public consumer parameters.

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
- Chart has no architecture / `nodeSelector` logic — runtime selects the published `linux/amd64` image

## Prerequisites

### Azure DevOps

- Organization and project
- [AWS Toolkit for Azure DevOps](https://marketplace.visualstudio.com/items?itemName=AmazonWebServices.aws-vsts-tools) **1.15+** (OIDC support)
- AWS Service Connection named `aws-ecr-oidc` (or override via `awsServiceConnection`):
  - Type: AWS
  - Role to Assume: IAM Role ARN for CI/ECR push
  - **Use OIDC: enabled**
  - No Access Key / Secret Key
- Each `azureEnvironment` already created
- Deploy agent pool(s) with `helm` and private cluster access

### AWS

- ECR repository already exists for `imageRepository` (pipeline does **not** run `create-repository`)
- Prefer **ECR tag immutability enabled** (infrastructure responsibility; pipeline does not configure it)
- IAM OIDC identity provider for Azure DevOps
- IAM Role assumed by the Service Connection (least privilege; see below)

### OIDC trust model

Issuer (per Azure DevOps organization):

```text
https://vstoken.dev.azure.com/{OrganizationGUID}
```

Audience (fixed for Azure DevOps):

```text
api://AzureADTokenExchange
```

Subject (pins one Service Connection):

```text
sc://{Organization}/{Project}/{ServiceConnection}
```

Example trust policy shape (replace placeholders; do not widen with wildcards):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/vstoken.dev.azure.com/ORGANIZATION_GUID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "vstoken.dev.azure.com/ORGANIZATION_GUID:aud": "api://AzureADTokenExchange",
          "vstoken.dev.azure.com/ORGANIZATION_GUID:sub": "sc://ORG/PROJECT/aws-ecr-oidc"
        }
      }
    }
  ]
}
```

### Expected IAM permissions (reference only)

Pipeline does **not** create IAM. Attach approximately:

- `ecr:GetAuthorizationToken` on `Resource: *`
- On the authorized repository ARN(s) only:
  - `ecr:BatchCheckLayerAvailability`
  - `ecr:GetDownloadUrlForLayer`
  - `ecr:BatchGetImage`
  - `ecr:InitiateLayerUpload`
  - `ecr:UploadLayerPart`
  - `ecr:CompleteLayerUpload`
  - `ecr:PutImage`

Do **not** grant `AdministratorAccess`, `PowerUserAccess`, `ecr:*`, or broad access to EKS / Secrets Manager / IAM admin.

## Sample consumer

[`azure-pipelines.yml`](azure-pipelines.yml) and [`src/Sample.Api`](src/Sample.Api) are an **example consumer**, not platform rules.

| Lab setting | Value |
|-------------|-------|
| ECR | `448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api` |
| CI | Microsoft-hosted `ubuntu-24.04` (platform decision) |
| Deploy pools | `Self-Hosted-Rancher` (all envs in this lab) |
| Environments | `develop`, `homolog`, `production` |
| Namespaces | `sample-api-dev`, `sample-api-hml`, `sample-api-prd` |
| AWS Service Connection | `aws-ecr-oidc` (platform default) |

If this lab uses an `ecr-pull` imagePullSecret, configure it on the target namespaces (or ServiceAccounts) outside the chart.

Consumer shape:

```yaml
extends:
  template: pipeline/templates/dotnet-k8s.yml
  parameters:
    appName: sample-api
    projectPath: src/Sample.Api/Sample.Api.csproj
    imageRepository: 448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api
    helmReleaseName: sample-api
    environments:
      - name: dev
        azureEnvironment: develop
        poolName: Self-Hosted-Rancher
        namespace: sample-api-dev
      # ...
```

Do **not** pass `ciPoolName`. Normally do **not** pass `awsServiceConnection` (platform default applies).

## Platform contract tests

Structural tests for this **platform repository** (not for consumer application pipelines).

They protect template and Helm chart invariants already implemented here: CI hosted plane, OIDC surface, single `linux/amd64` publish, immutable `$(Build.SourceVersion)` promotion, generic multi-environment deployment jobs, internal chart path, and Helm render contracts (identity, selectors, probes, Service, `imagePullSecrets`).

Run locally:

```bash
./tests/run-tests.sh
```

Requires `python3` and `helm` on `PATH`. Dependencies are installed into `tests/.venv` from `tests/requirements.txt`.

| Layer | What it covers |
|-------|----------------|
| Local contract tests | Deterministic structural checks + `helm lint` / `helm template` |
| Azure DevOps integration | Real template expansion, OIDC/STS/ECR, private cluster deploy |

Optional platform CI: point a separate Azure DevOps pipeline at [`azure-pipelines.platform-tests.yml`](azure-pipelines.platform-tests.yml). Do **not** add these tests to `pipeline/templates/dotnet-k8s.yml`.

## Local lab note (not a platform contract)


The official CI artifact is **`linux/amd64`**.

The current personal lab runs on Apple Silicon (MacBook Pro M4) with Rancher Desktop. To exercise the **same** corporate image locally, enable x86_64 emulation — preferably **VZ + Rosetta**. Emulation is a lab concern only; the template does not special-case it.

Lab performance under emulation is **not** representative of production.

Lab goal: validate deployment, image pull, Helm, probes, Service, and basic functional behavior of the AMD64 artifact that will later run on corporate AMD64 clusters.

Harness examples (run locally; **not** in the corporate pipeline):

```bash
docker pull <imageRepository>:<sha>
docker inspect <imageRepository>:<sha> --format '{{.Architecture}}'
# expected: amd64

docker run --rm --platform linux/amd64 -p 8080:8080 <imageRepository>:<sha>
# then Helm deploy the same tag into Rancher Desktop Kubernetes
```

ARM64 / multi-arch platform support remains a **future** requirement if corporate runtimes need it.

## Monorepo limitation

This repository currently packs the sample app, the YAML template, the Dockerfile, and the Helm chart together.

Azure DevOps can load YAML templates from another repository at compile time, but **runtime assets** (Dockerfile, Helm chart) need an explicit checkout/distribution strategy when the template is consumed from a different repo.

That strategy is **not** part of this slice.

## Known limitations / debt

- The Dockerfile assumes the published assembly basename matches the `.csproj` filename (no `assemblyName` parameter yet)
- No approvals, checks, or gates on Azure DevOps Environments yet
- No values files per environment; one image and the same chart settings for all targets
- No `linux/arm64` / multi-arch image index (platform runtime target is `linux/amd64` only)
- Helm chart does not yet `required` `application.name` / `image.repository` / `image.tag`; empty values still render (documented by negative contract tests)
