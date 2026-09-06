# dotnet-templates

Sample .NET API consumer for the platform templates in [`diegofernandes-dev/pipeline-template`](https://github.com/diegofernandes-dev/pipeline-template).

This repository owns only application concerns:

```text
src/Sample.Api
global.json
azure-pipelines.yml (bootstrap)
```

Platform assets (YAML template, Dockerfile, Helm chart, contract tests) live in `pipeline-template`.

## Sample.Api

Minimal ASP.NET Core app (`net10.0`) with `GET /health` on port **8080**.

## global.json

SDK version is owned by this repository via [`global.json`](global.json). The platform template installs the SDK with `UseDotNet@2` / `useGlobalJson: true` and fails if no applicable `global.json` is found.

## Consumer azure-pipelines.yml

```yaml
resources:
  repositories:
    - repository: dotnetTemplates
      type: github
      name: diegofernandes-dev/pipeline-template
      endpoint: github-diegofernandes-dev
      ref: refs/tags/v0.1.1

extends:
  template: pipeline/templates/dotnet-k8s.yml@dotnetTemplates
  parameters:
    appName: sample-api
    projectPath: src/Sample.Api/Sample.Api.csproj
    imageRepository: 448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api
    helmReleaseName: sample-api
    environments: [...]
```

Required alias: **`dotnetTemplates`**. Platform ref must be immutable (`refs/tags/...` or commit SHA). Do not pass Dockerfile/Helm paths, CI pool, or SDK/runtime versions.

## Lab prerequisites

| Setting | Value |
|---------|-------|
| Azure DevOps | `diegolab` / `platform-engineering` |
| GitHub Service Connection | `github-diegofernandes-dev` |
| AWS Service Connection | `aws-ecr-oidc` (platform default) |
| ECR | `448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api` |
| Deploy pool | `Self-Hosted-Rancher` |
| Environments | `develop`, `homolog`, `production` |
| Namespaces | `sample-api-dev`, `sample-api-hml`, `sample-api-prd` |

See the [`pipeline-template` README](https://github.com/diegofernandes-dev/pipeline-template) for platform ownership, build-once semantics, checkout paths, and supported deployment model.
