"""
Database migration: Add Terraform Management tables
- State management
- Workspace management
- Plan management

Run with: python -m backend.db.migrations.add_terraform_management_tables
"""

from pathlib import Path
import sqlite3
from backend.db.session import DEFAULT_DB_PATH
from backend.utils.logging import get_logger

LOGGER = get_logger(__name__)


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Get database connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def migrate_state_tables(conn: sqlite3.Connection) -> None:
    """Create state management tables."""
    LOGGER.info("Creating state management tables...")

    # terraform_states table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terraform_states (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            workspace TEXT NOT NULL DEFAULT 'default',
            backend_type TEXT NOT NULL,
            backend_config TEXT,
            serial INTEGER,
            terraform_version TEXT,
            lineage TEXT,
            resource_count INTEGER,
            output_count INTEGER,
            state_snapshot BLOB,
            checksum TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_terraform_states_project ON terraform_states(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_terraform_states_workspace ON terraform_states(project_id, workspace)")

    # terraform_state_resources table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terraform_state_resources (
            id TEXT PRIMARY KEY,
            state_id TEXT NOT NULL,
            address TEXT NOT NULL,
            module_address TEXT,
            mode TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            schema_version INTEGER,
            attributes TEXT,
            sensitive_attributes TEXT,
            dependencies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_resources_state ON terraform_state_resources(state_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_resources_type ON terraform_state_resources(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_resources_address ON terraform_state_resources(state_id, address)")

    # terraform_state_outputs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terraform_state_outputs (
            id TEXT PRIMARY KEY,
            state_id TEXT NOT NULL,
            name TEXT NOT NULL,
            value TEXT,
            sensitive BOOLEAN DEFAULT FALSE,
            type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_state_outputs_state ON terraform_state_outputs(state_id)")

    # drift_detections table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drift_detections (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            state_id TEXT,
            workspace TEXT NOT NULL DEFAULT 'default',
            detection_method TEXT NOT NULL,
            total_drifted INTEGER DEFAULT 0,
            resources_added INTEGER DEFAULT 0,
            resources_modified INTEGER DEFAULT 0,
            resources_deleted INTEGER DEFAULT 0,
            drift_details TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (state_id) REFERENCES terraform_states(id) ON DELETE SET NULL
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_project ON drift_detections(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_drift_detected_at ON drift_detections(detected_at DESC)")

    conn.commit()
    LOGGER.info("State management tables created successfully")


def migrate_workspace_tables(conn: sqlite3.Connection) -> None:
    """Create workspace management tables."""
    LOGGER.info("Creating workspace management tables...")

    # terraform_workspaces table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terraform_workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            working_directory TEXT NOT NULL,
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP,
            selected_at TIMESTAMP,
            last_scanned_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, working_directory, name)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_project ON terraform_workspaces(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_active ON terraform_workspaces(project_id, is_active)")

    # workspace_variables table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_variables (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            sensitive BOOLEAN DEFAULT FALSE,
            source TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE,
            UNIQUE(workspace_id, key)
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_vars_workspace ON workspace_variables(workspace_id)")

    # workspace_comparisons table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspace_comparisons (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            workspace_a_id TEXT NOT NULL,
            workspace_b_id TEXT NOT NULL,
            comparison_type TEXT NOT NULL,
            differences_count INTEGER DEFAULT 0,
            differences TEXT,
            compared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_a_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_b_id) REFERENCES terraform_workspaces(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_comparisons_project ON workspace_comparisons(project_id)")

    # Update existing tables - add workspace column to project_runs if not exists
    try:
        conn.execute("ALTER TABLE project_runs ADD COLUMN workspace TEXT DEFAULT 'default'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_project_runs_workspace ON project_runs(workspace)")
        LOGGER.info("Added workspace column to project_runs")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise
        LOGGER.info("Workspace column already exists in project_runs")

    conn.commit()
    LOGGER.info("Workspace management tables created successfully")


def migrate_plan_tables(conn: sqlite3.Connection) -> None:
    """Create plan management tables."""
    LOGGER.info("Creating plan management tables...")

    # terraform_plans table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS terraform_plans (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            run_id TEXT,
            workspace TEXT NOT NULL DEFAULT 'default',
            working_directory TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            target_resources TEXT,
            has_changes BOOLEAN DEFAULT FALSE,
            resource_changes TEXT,
            output_changes TEXT,
            total_resources INTEGER DEFAULT 0,
            resources_to_add INTEGER DEFAULT 0,
            resources_to_change INTEGER DEFAULT 0,
            resources_to_destroy INTEGER DEFAULT 0,
            resources_to_replace INTEGER DEFAULT 0,
            plan_file_path TEXT,
            plan_json_path TEXT,
            plan_output TEXT,
            cost_estimate TEXT,
            security_impact TEXT,
            approval_status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (run_id) REFERENCES project_runs(id) ON DELETE SET NULL
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_project ON terraform_plans(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_workspace ON terraform_plans(workspace)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_approval ON terraform_plans(approval_status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plans_created ON terraform_plans(created_at DESC)")

    # plan_resource_changes table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_resource_changes (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            resource_address TEXT NOT NULL,
            module_address TEXT,
            mode TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            action TEXT NOT NULL,
            action_reason TEXT,
            before_attributes TEXT,
            after_attributes TEXT,
            before_sensitive TEXT,
            after_sensitive TEXT,
            attribute_changes TEXT,
            security_impact_score INTEGER,
            cost_impact REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES terraform_plans(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_changes_plan ON plan_resource_changes(plan_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_changes_action ON plan_resource_changes(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_changes_type ON plan_resource_changes(type)")

    # plan_approvals table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_approvals (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            status TEXT NOT NULL,
            comments TEXT,
            required BOOLEAN DEFAULT TRUE,
            approved_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES terraform_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (approver_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_approvals_plan ON plan_approvals(plan_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_approvals_status ON plan_approvals(status)")

    conn.commit()
    LOGGER.info("Plan management tables created successfully")


def verify_migration(conn: sqlite3.Connection) -> None:
    """Verify all tables were created."""
    LOGGER.info("Verifying migration...")

    expected_tables = [
        # State management
        'terraform_states',
        'terraform_state_resources',
        'terraform_state_outputs',
        'drift_detections',
        # Workspace management
        'terraform_workspaces',
        'workspace_variables',
        'workspace_comparisons',
        # Plan management
        'terraform_plans',
        'plan_resource_changes',
        'plan_approvals',
    ]

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    missing_tables = set(expected_tables) - existing_tables
    if missing_tables:
        LOGGER.error(f"Missing tables: {missing_tables}")
        raise RuntimeError(f"Migration incomplete: missing tables {missing_tables}")

    LOGGER.info(f"All {len(expected_tables)} tables created successfully")

    # Verify workspace column in project_runs
    cursor.execute("PRAGMA table_info(project_runs)")
    columns = {row[1] for row in cursor.fetchall()}
    if 'workspace' not in columns:
        LOGGER.warning("workspace column not found in project_runs")

    LOGGER.info("Migration verification complete")


def run_migration(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Run the complete migration."""
    LOGGER.info(f"Starting Terraform management tables migration on {db_path}")

    conn = get_connection(db_path)

    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Run migrations
        migrate_state_tables(conn)
        migrate_workspace_tables(conn)
        migrate_plan_tables(conn)

        # Verify
        verify_migration(conn)

        LOGGER.info("Migration completed successfully")

    except Exception as e:
        conn.rollback()
        LOGGER.error(f"Migration failed: {e}", exc_info=True)
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    run_migration(db_path)
