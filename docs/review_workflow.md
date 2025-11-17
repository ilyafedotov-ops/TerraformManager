# Report Review Workflow

## Overview

TerraformManager now tracks the lifecycle of saved reviewer reports directly in the core `/reports` API. Each report record captures a workflow status, optional assignee, due date, free-form notes, and a chronological comment thread so teams can triage findings without leaving the dashboard.

The Svelte dashboard exposes the same metadata in the new **Review Inspector** panel, allowing reviewers to filter queues, update ownership, and collaborate through inline threads while the backend persists a full audit trail.

## Workflow Metadata

Every report exposes the following review fields:

| Field            | Type              | Notes                                                                 |
| ---------------- | ----------------- | --------------------------------------------------------------------- |
| `review_status`  | `string`          | One of `pending`, `in_review`, `changes_requested`, `resolved`, `waived`. Defaults to `pending`. |
| `review_assignee`| `string \| null`  | Free-form identifier (e.g. email, Slack handle).                      |
| `review_due_at`  | ISO timestamp     | Optional due date; parsed as UTC on write.                            |
| `review_notes`   | `string \| null`  | Short summary of current state or next actions.                       |
| `updated_at`     | ISO timestamp     | Automatically maintained whenever metadata or comments change.        |

The storage layer backfills these columns automatically on startup; no manual migration steps are required.

## API Endpoints

### List Reports

```
GET /reports
```

Query parameters:

| Parameter       | Description |
| --------------- | ----------- |
| `limit` (1-500) | Page size (default 50). |
| `offset`        | Zero-based offset (default 0). |
| `status`        | Repeatable filter for review status (e.g. `status=resolved`). |
| `assignee`      | Case-insensitive match on `review_assignee`. |
| `search`        | Fuzzy match against report ID, assignee, or notes. |
| `created_after` / `created_before` | ISO timestamp window. |
| `order`         | `asc` or `desc` (created-at sort; default `desc`). |

Response:

```jsonc
{
  "items": [
    {
      "id": "r1",
      "summary": {...},
      "created_at": "2025-01-01T12:00:00Z",
      "updated_at": "2025-01-02T09:15:00Z",
      "review_status": "in_review",
      "review_assignee": "alice@example.com",
      "review_due_at": "2025-01-05T00:00:00Z",
      "review_notes": "Waiting on Terraform plan."
    }
  ],
  "total_count": 42,
  "limit": 20,
  "offset": 0,
  "next_offset": 20,
  "has_more": true,
  "aggregates": {
    "status_counts": {
      "pending": 12,
      "in_review": 8,
      "changes_requested": 6,
      "resolved": 14,
      "waived": 2
    },
    "severity_counts": {
      "high": 17,
      "medium": 24,
      "low": 31
    }
  }
}
```

### Update Metadata

```
PATCH /reports/{id}
```

Body payload (all fields optional):

```json
{
  "review_status": "changes_requested",
  "review_assignee": "carol@example.com",
  "review_due_at": "2025-02-01T00:00:00Z",
  "review_notes": "Awaiting revised cost estimates."
}
```

Returns the updated metadata snapshot:

```json
{
  "id": "r1",
  "review_status": "changes_requested",
  "review_assignee": "carol@example.com",
  "review_due_at": "2025-02-01T00:00:00Z",
  "review_notes": "Awaiting revised cost estimates.",
  "updated_at": "2025-01-20T15:10:43.221528+00:00"
}
```

### Comments

* `GET /reports/{id}/comments` – returns `{ "items": [...] }` ordered oldest-first.
* `POST /reports/{id}/comments` – requires `body`; optional `author`. Returns the created comment.
* `DELETE /reports/{id}/comments/{comment_id}` – removes the comment and updates the parent report’s `updated_at`.

Example create request:

```json
{
  "body": "Re-run drift analysis after merging PR-124.",
  "author": "dana@example.com"
}
```

Example response:

```json
{
  "id": "c1b61946-7d3d-460b-8670-89d4f21ab44d",
  "report_id": "r1",
  "author": "dana@example.com",
  "body": "Re-run drift analysis after merging PR-124.",
  "created_at": "2025-01-20T16:00:00Z",
  "updated_at": "2025-01-20T16:00:00Z"
}
```

## Frontend UX

* **Overview Cards** – surface aggregate counts (total reports per status, severity mix) using the API-provided aggregates.
* **Filter Bar** – status chips, assignee filter, free-text search, and page-size selector drive `limit`, `offset`, and query parameters in the load function.
* **Review Inspector** – when a row is selected, the panel displays metadata, allows editing via the PATCH endpoint, and embeds the comment thread.
* **Table Actions** – row selection is decoupled from destructive actions; exporting and deleting continue to use the existing artifact endpoints.

## Migration Notes

* `storage.init_db` now appends the new columns for existing SQLite databases. Deployments do not require manual migrations.
* Legacy rows default to `review_status = 'pending'` and inherit `updated_at = created_at` until further updates.
* The Svelte client guards for empty datasets and gracefully handles missing metadata.

## Suggested Workflow

1. Filter the `/reports` view by status or assignee to triage your queue.
2. Assign ownership and due dates via the inspector, capturing context in `review_notes`.
3. Use comments for discussion and escalation; the latest updates bubble `updated_at` so recent activity is surfaced.
4. Transition `review_status` to `resolved` (or `waived`) once findings are addressed, optionally attaching exported artifacts for audit.
