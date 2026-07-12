import { describe, expectTypeOf, it } from 'vitest';

import type { PlanRecord, TerraformStateRecord, WorkspaceRecord } from './client';

describe('Terraform management API records', () => {
	it('matches the state list response contract', () => {
		expectTypeOf<TerraformStateRecord>().toMatchTypeOf<{
			id: string;
			project_id: string;
			workspace: string;
			backend_type: string;
			backend_config: Record<string, unknown>;
			serial: number | null;
			terraform_version: string | null;
			lineage: string | null;
			resource_count: number | null;
			output_count: number | null;
			checksum: string | null;
			imported_at: string | null;
			created_at: string | null;
		}>();
	});

	it('matches the workspace list response contract', () => {
		expectTypeOf<WorkspaceRecord>().toMatchTypeOf<{
			id: string;
			project_id: string;
			name: string;
			working_directory: string;
			is_default: boolean;
			is_active: boolean;
			created_at: string | null;
			selected_at: string | null;
			last_scanned_at: string | null;
		}>();
	});

	it('matches the plan list response contract', () => {
		expectTypeOf<PlanRecord>().toMatchTypeOf<{
			id: string;
			project_id: string;
			run_id: string | null;
			workspace: string;
			working_directory: string;
			plan_type: string;
			target_resources: string[];
			has_changes: boolean;
			resource_changes: Record<string, unknown>;
			output_changes: Record<string, unknown>;
			total_resources: number;
			resources_to_add: number;
			resources_to_change: number;
			resources_to_destroy: number;
			resources_to_replace: number;
			plan_file_path: string | null;
			plan_json_path: string | null;
			plan_output: string | null;
			cost_estimate: Record<string, unknown>;
			security_impact: Record<string, unknown>;
			approval_status: string;
			approved_by: string | null;
			approved_at: string | null;
			expires_at: string | null;
			created_at: string | null;
		}>();
	});
});
