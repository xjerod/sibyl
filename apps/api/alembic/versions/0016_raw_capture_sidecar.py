"""Add raw capture sidecar for quick memory intake.

Revision ID: 0016_raw_capture_sidecar
Revises: 0015_sandbox_p0_fixes
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_raw_capture_sidecar"
down_revision: str | None = "0015_sandbox_p0_fixes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_captures",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(128), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("capture_surface", sa.String(64), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_raw_captures_organization_id", "raw_captures", ["organization_id"])
    op.create_index("ix_raw_captures_entity_id", "raw_captures", ["entity_id"])
    op.create_index("ix_raw_captures_entity_type", "raw_captures", ["entity_type"])
    op.create_index(
        "ix_raw_captures_capture_surface",
        "raw_captures",
        ["capture_surface"],
    )
    op.create_index(
        "ix_raw_captures_created_by_user_id",
        "raw_captures",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_raw_captures_organization_created_at",
        "raw_captures",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_captures_organization_created_at", table_name="raw_captures")
    op.drop_index("ix_raw_captures_created_by_user_id", table_name="raw_captures")
    op.drop_index("ix_raw_captures_capture_surface", table_name="raw_captures")
    op.drop_index("ix_raw_captures_entity_type", table_name="raw_captures")
    op.drop_index("ix_raw_captures_entity_id", table_name="raw_captures")
    op.drop_index("ix_raw_captures_organization_id", table_name="raw_captures")
    op.drop_table("raw_captures")
