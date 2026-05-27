"""batch jobs

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""
from typing import Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels = None
depends_on = None


def _enum(name: str, *values: str):
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # 创建枚举
    batch_status = postgresql.ENUM(
        "pending", "running", "done", "partial", "failed", name="batch_status"
    )
    batch_status.create(bind, checkfirst=True)

    # batch_jobs
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("orig_file_id", sa.Integer(),
                  sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status",
                  _enum("batch_status", "pending", "running", "done", "partial", "failed"),
                  nullable=False, server_default="pending"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"])
    op.create_index("ix_batch_jobs_created_at", "batch_jobs", ["created_at"])

    # comparisons 加 batch_id 列
    op.add_column(
        "comparisons",
        sa.Column("batch_id", sa.Integer(),
                  sa.ForeignKey("batch_jobs.id", ondelete="CASCADE"))
    )
    op.create_index("ix_comparisons_batch_id", "comparisons", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_comparisons_batch_id", "comparisons")
    op.drop_column("comparisons", "batch_id")
    op.drop_table("batch_jobs")
    op.execute("DROP TYPE IF EXISTS batch_status")
