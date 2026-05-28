"""widen files.mime_type to 128

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # docx mime: application/vnd.openxmlformats-officedocument.wordprocessingml.document (71 字符)
    op.alter_column(
        "files", "mime_type",
        existing_type=sa.String(64),
        type_=sa.String(128),
        existing_nullable=False,
        existing_server_default="application/pdf",
    )


def downgrade() -> None:
    op.alter_column(
        "files", "mime_type",
        existing_type=sa.String(128),
        type_=sa.String(64),
        existing_nullable=False,
        existing_server_default="application/pdf",
    )
