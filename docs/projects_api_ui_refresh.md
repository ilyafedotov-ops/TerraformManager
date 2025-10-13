## Projects API & UI Refresh

- `/projects` now returns `latest_run`, `run_count`, `library_asset_count`, and `last_activity_at` alongside existing project fields. Supply `include_metadata=true` to hydrate metadata inline, and `search`/`limit` query parameters for list filtering.
- New endpoint `GET /projects/{project_id}/overview` aggregates summary data (latest run, run counts, library totals, recent assets, and metrics extracted from run summaries) to drive the dashboard overview tab.
- Project runs (`/projects/{project_id}/runs`) and library assets (`/projects/{project_id}/library`) are cursor-paginated. Responses include `{ items, next_cursor, total_count }`; pass `cursor=<last_id>` to fetch the next page.
- Diff responses (`/projects/{project_id}/library/{asset_id}/versions/{version_id}/diff`) are unchanged but exposed through the redesigned library tab with split/unified views and clipboard/download helpers.
- The projects workspace UI now features a left-hand sticky project rail with search, tabbed content (Overview, Runs, Artifacts, Library, Settings), and modal workflows for project creation and asset editing to minimize vertical scrolling.
