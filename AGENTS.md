# Repository Guidelines

## Project Structure & Module Organization
- `app.py` delivers the Streamlit UI with Generate, Review, and Knowledge tabs; keep UI helpers close to their tab definitions.
- `backend/` hosts reusable logic: `cli.py` (entry point), `scanner.py` (rule engine + terraform hooks), `rag.py` (knowledge retrieval), `generators/` (Jinja templates), and `utils/` for diff helpers.
- `knowledge/` supplies Markdown explanations referenced by the reviewer; add new concepts here and re-index via the CLI.
- `docs/report_schema.json` defines the machine-readable findings contract, while `sample/` contains intentionally insecure Terraform projects for regression checks.

## Build, Test, and Development Commands
```bash
python -m venv .venv && source .venv/bin/activate  # create local env
pip install -r requirements.txt                    # install app + backend deps
streamlit run app.py                               # launch GUI
python -m backend.cli scan sample --out report.json  # run reviewer on fixtures
python -m backend.cli scan --path YOUR_DIR --terraform-validate  # optional terraform hook
```
- Regenerate the TF-IDF index after adding knowledge documents with `python -m backend.cli reindex`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, `snake_case` for functions/modules, and `CamelCase` for classes; prefer descriptive names that reflect Terraform resources (e.g., `scan_aws_s3_policy`).
- Include type hints on public functions in `backend/` modules and add docstrings when behavior is non-obvious, especially around policy checks.
- Jinja templates in `backend/generators/` should use clear block names and Terraform-style resource IDs (e.g., `aws_s3_bucket.default`).

## Testing Guidelines
- Exercise the reviewer against `sample/` before merging: `python -m backend.cli scan sample --out tmp/report.json && cat tmp/report.json`.
- Validate generated Terraform by importing new templates into a throwaway directory and running `terraform fmt && terraform validate` when Terraform is installed.
- When adding automated coverage, place tests under `tests/backend/...` and mirror module names; name files `test_<module>.py`.

## Commit & Pull Request Guidelines
- Use imperative, scope-prefixed commit messages such as `feat(scanner): expand s3 encryption rule`; group unrelated changes into separate commits.
- PRs should summarize functional impact, list manual/verifier commands run, and attach key artifacts (e.g., sanitized `report.json` snippets or screenshots from the GUI).
- Reference tracking issues in the PR description and call out any new Terraform templates or policies that require doc updates.

## Security & Configuration Tips
- Never commit real cloud credentials; rely on environment variables or `.streamlit/secrets.toml` excluded via `.gitignore`.
- Scrub uploaded Terraform files of secrets before sharing in issues, and update `docs/report_schema.json` if new sensitive fields are exposed in findings.
