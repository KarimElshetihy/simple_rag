"""Install the pgvector extension."""

from typing import Sequence, Union

from alembic import op


revision: str = "a41e6bc92d71"
down_revision: Union[str, Sequence[str], None] = "d7230428ef4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    pass
