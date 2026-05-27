"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels = None
depends_on = None


# 把 ENUM 定义集中、关闭 create_type 让我们自己控制创建时机
def _enum(name: str, *values: str):
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()

    # 先把所有 ENUM 用 checkfirst 创建一次，幂等
    user_role = postgresql.ENUM("admin", "reviewer", name="user_role")
    cmp_status = postgresql.ENUM("pending", "running", "done", "failed", name="comparison_status")
    rev_status = postgresql.ENUM("not_started", "in_review", "completed", name="review_status")
    diff_cat = postgresql.ENUM(
        "replace", "delete", "insert", "handwritten", "stamp_covered", "moved",
        name="diff_category",
    )
    diff_sev = postgresql.ENUM("critical", "normal", "info", name="diff_severity")
    diff_act = postgresql.ENUM("confirmed", "ignored", name="diff_review_action")
    for e in (user_role, cmp_status, rev_status, diff_cat, diff_sev, diff_act):
        e.create(bind, checkfirst=True)

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("role", _enum("user_role", "admin", "reviewer"),
                  nullable=False, server_default="reviewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # files
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha1", sa.String(40), unique=True, nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("mime_type", sa.String(64), nullable=False, server_default="application/pdf"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_files_sha1", "files", ["sha1"])

    # comparisons
    op.create_table(
        "comparisons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("orig_file_id", sa.Integer(),
                  sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scan_file_id", sa.Integer(),
                  sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status",
                  _enum("comparison_status", "pending", "running", "done", "failed"),
                  nullable=False, server_default="pending"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_phase", sa.String(32), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text()),
        sa.Column("settings_json", sa.JSON()),
        sa.Column("summary_json", sa.JSON()),
        sa.Column("review_status",
                  _enum("review_status", "not_started", "in_review", "completed"),
                  nullable=False, server_default="not_started"),
        sa.Column("review_completed_by",
                  sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_comparisons_status", "comparisons", ["status"])
    op.create_index("ix_comparisons_review_status", "comparisons", ["review_status"])
    op.create_index("ix_comparisons_created_at", "comparisons", ["created_at"])

    # diffs
    op.create_table(
        "diffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comparison_id", sa.Integer(),
                  sa.ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("category",
                  _enum("diff_category", "replace", "delete", "insert",
                        "handwritten", "stamp_covered", "moved"),
                  nullable=False),
        sa.Column("severity",
                  _enum("diff_severity", "critical", "normal", "info"),
                  nullable=False),
        sa.Column("orig_page", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("scan_page", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("orig_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("scan_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("orig_bbox", sa.JSON()),
        sa.Column("scan_bbox", sa.JSON()),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_footer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_action",
                  _enum("diff_review_action", "confirmed", "ignored")),
        sa.Column("review_note", sa.Text()),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_diffs_comparison_id", "diffs", ["comparison_id"])
    op.create_index("ix_diffs_seq_no", "diffs", ["seq_no"])
    op.create_index("ix_diffs_category", "diffs", ["category"])
    op.create_index("ix_diffs_severity", "diffs", ["severity"])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False, server_default=""),
        sa.Column("target_id", sa.Integer()),
        sa.Column("payload_json", sa.JSON()),
        sa.Column("ip", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("diffs")
    op.drop_table("comparisons")
    op.drop_table("files")
    op.drop_table("users")
    for name in ("diff_review_action", "diff_severity", "diff_category",
                 "review_status", "comparison_status", "user_role"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
