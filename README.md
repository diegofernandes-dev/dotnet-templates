# dotnet-templates

Sample .NET API consumer for the trusted CI templates in [`diegofernandes-dev/pipeline-template`](https://github.com/diegofernandes-dev/pipeline-template).

This repository owns only application concerns:

```text
Sample.sln
src/Sample.Api
tests/Sample.Api.Tests
global.json
packages.lock.json (per project)
azure-pipelines.yml (bootstrap)
```

Platform assets (YAML template, Dockerfile, build script, contract tests) live in `pipeline-template`.

Promotion / Kubernetes deployment is **not** performed by this pipeline. That boundary belongs to Delivery Management (ADR-012).

## Layout

```text
Sample.sln
├── src/Sample.Api/          # deployable ASP.NET API (net10.0), GET /health
└── tests/Sample.Api.Tests/  # xUnit WebApplicationFactory coverage
```

## global.json

SDK version is owned by this repository. Sample pin:

```json
{
  "sdk": {
    "version": "10.0.102",
    "rollForward": "disable"
  }
}
```

`rollForward: disable` is intentional with NuGet lock files so the SDK and dependency graph stay in lockstep.

## NuGet lock files

Both projects set `RestorePackagesWithLockFile=true` and commit `packages.lock.json`.

CI restores with `--locked-mode` and never regenerates locks. Update locks locally when package references change:

```bash
dotnet restore Sample.sln
# or, when intentionally refreshing the graph:
dotnet restore Sample.sln --force-evaluate
```

## Consumer azure-pipelines.yml

```yaml
resources:
  repositories:
    - repository: dotnetTemplates
      type: github
      name: diegofernandes-dev/pipeline-template
      endpoint: github-diegofernandes-dev
      ref: refs/tags/v0.2.0

extends:
  template: pipeline/templates/dotnet-ci.yml@dotnetTemplates
  parameters:
    appName: sample-api
    projectPath: src/Sample.Api/Sample.Api.csproj
    buildPath: Sample.sln
    imageRepository: 448003890252.dkr.ecr.us-east-1.amazonaws.com/sample-api
```

No `environments`, `helmReleaseName`, or other deployment parameters.
