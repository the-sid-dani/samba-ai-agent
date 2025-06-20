"""sambaai -> sambaaibot

Revision ID: 54a74a0417fc
Revises: 94dc3d0236f8
Create Date: 2024-12-11 18:05:05.490737

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "54a74a0417fc"
down_revision = "94dc3d0236f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("chat_session", "sambaai_flow", new_column_name="sambaaibot_flow")


def downgrade() -> None:
    op.alter_column("chat_session", "sambaaibot_flow", new_column_name="sambaai_flow")
