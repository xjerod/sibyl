"""Drop legacy agent runner and sandbox tables.

The agent execution system (runners, sandboxes, orchestrators) has been
removed. Sibyl's focus is persistent memory and knowledge graph only.
These tables were created by migrations 0003, 0004, 0012-0015 and have
no active readers or writers.

Revision ID: 0017_drop_agent_runner_tables
Revises: 0016_raw_capture_sidecar
Create Date: 2026-04-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_drop_agent_runner_tables"
down_revision: str | None = "0016_raw_capture_sidecar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop tables in reverse dependency order (children before parents).
    # Use CASCADE to handle any remaining foreign key references.

    # 0014/0015: Sandbox infrastructure
    op.execute("DROP TABLE IF EXISTS sandbox_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS user_ssh_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS sandboxes CASCADE")

    # 0013: Inter-agent messaging
    op.execute("DROP TABLE IF EXISTS inter_agent_messages CASCADE")

    # 0012: Runner and agent state
    op.execute("DROP TABLE IF EXISTS orchestrator_states CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_states CASCADE")
    op.execute("DROP TABLE IF EXISTS runner_projects CASCADE")
    op.execute("DROP TABLE IF EXISTS runners CASCADE")

    # 0003/0004: Agent messages
    op.execute("DROP TABLE IF EXISTS agent_messages CASCADE")

    # Clean up orphaned enum types created by those migrations
    op.execute("DROP TYPE IF EXISTS agentmessagerole CASCADE")
    op.execute("DROP TYPE IF EXISTS agentmessagetype CASCADE")
    op.execute("DROP TYPE IF EXISTS runnerstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS agentstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS orchestratorstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS sandboxstatus CASCADE")
    op.execute("DROP TYPE IF EXISTS sandboxtaskstatus CASCADE")


def downgrade() -> None:
    pass
