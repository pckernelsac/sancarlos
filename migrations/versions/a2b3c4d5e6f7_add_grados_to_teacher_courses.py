"""add_grados_to_teacher_courses

Revision ID: a2b3c4d5e6f7
Revises: 33024b739760
Create Date: 2026-04-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = '33024b739760'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('teacher_courses',
                  sa.Column('grados', sa.String(40), nullable=True))


def downgrade():
    op.drop_column('teacher_courses', 'grados')
