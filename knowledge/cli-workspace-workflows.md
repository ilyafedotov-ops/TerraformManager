# CLI Project Workspace Workflows

Use these flows when you want the CLI to behave like the hosted Projects experience. All examples assume you already created a project (via the UI or `python -m backend.cli project create`).

## Prerequisites

- Activate your virtualenv and install requirements (including `pytest` for regression tests).
- Authenticate once with `python -m backend.cli auth login --email you@example.com --base-url http://localhost:8890` so the CLI can call project APIs when needed.
- Ensure the project workspace under `data/projects/<slug>/` contains the Terraform sources you want to operate on.

## Generate a Baseline Within the Workspace

```bash
python -m backend.cli baseline --path stacks/team-a \
  --project-slug platform-team \
  --include-waived
```

This resolves `stacks/team-a` relative to `data/projects/platform-team/`, runs the reviewer without Terraform validate, and writes the waiver file to `data/projects/platform-team/configs/tfreview.baseline.yaml` by default. Pass `--out configs/team-a.baseline.yaml` to pick another relative output path inside the workspace.

## Render Generator Docs Into Project Folders

```bash
python -m backend.cli docs \
  --project-slug platform-team \
  --skip-reindex
```

Docs are written to `data/projects/platform-team/docs/generators/` and mirrored to `data/projects/platform-team/knowledge/generated/`. Set `--knowledge-out ""` to skip the mirror or `--knowledge-out project-notes` to mirror into another project-relative folder. Run `python -m backend.cli reindex` later to refresh the knowledge index if you skipped it here.

## Upload Artifacts to a Project Run

```bash
python -m backend.cli project upload \
  --project-id <uuid> \
  --run-id <run uuid> \
  --file reports/terraform_review_report.json \
  --dest reports/terraform_review_report.json \
  --tags "report,ci" \
  --metadata '{"source": "nightly"}' \
  --media-type application/json
```

The CLI copies the local file into `data/projects/<slug>/runs/<run>/reports/terraform_review_report.json`, records the artifact, and (optionally) stores tags + metadata so UI/API consumers can filter artifacts. Use `--no-overwrite` to prevent replacing existing files.

## Tips

- All project-aware commands (`scan`, `baseline`, `docs`, `project upload`, `project generator`) guard against paths that escape the managed workspace tree. Reference files relative to `data/projects/<slug>/` to avoid rejections.
- When commands produce artifacts (reports, HTML, docs, baselines), they automatically save entries under `data/projects/<slug>/runs/<run-id>/` and make them visible in `/projects/:id/runs/:runId` without extra API calls.
- Re-run `python -m backend.cli reindex` after adding new Markdown under `knowledge/` or a project-specific knowledge mirror so search results pick up the content.
