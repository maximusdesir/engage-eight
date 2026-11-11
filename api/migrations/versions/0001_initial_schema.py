"""initial schema: team-scoped plays and uploads

Every play, upload, opponent and vocab mapping belongs to a team. Databases
created before migrations existed (by create_all, with ownerless plays) are
not upgraded; see app.db.session.init_db.

Revision ID: 0001
Revises: 
Create Date: 2026-11-10 14:38:40.589582
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('predictions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('game_state', sa.Text(), nullable=False),
    sa.Column('result', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_predictions_user_id'), ['user_id'], unique=False)

    op.create_table('teams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('level', sa.String(length=20), nullable=False),
    sa.Column('season', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_teams_owner_id'), ['owner_id'], unique=False)

    op.create_table('opponents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('oc_name', sa.String(length=120), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('opponents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_opponents_team_id'), ['team_id'], unique=False)

    op.create_table('vocab_mappings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('raw_value', sa.String(length=80), nullable=False),
    sa.Column('canonical_value', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'kind', 'raw_value', name='uq_vocab_team_kind_raw')
    )
    with op.batch_alter_table('vocab_mappings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vocab_mappings_team_id'), ['team_id'], unique=False)

    op.create_table('games',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('opponent_id', sa.Integer(), nullable=True),
    sa.Column('season', sa.Integer(), nullable=True),
    sa.Column('week', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['opponent_id'], ['opponents.id'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_games_team_id'), ['team_id'], unique=False)

    op.create_table('uploads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('opponent_id', sa.Integer(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('n_plays', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['opponent_id'], ['opponents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('team_id', 'sha256', name='uq_upload_team_sha256')
    )
    with op.batch_alter_table('uploads', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_uploads_team_id'), ['team_id'], unique=False)

    op.create_table('plays',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('opponent_id', sa.Integer(), nullable=True),
    sa.Column('upload_id', sa.Integer(), nullable=True),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.Column('offense_team', sa.String(length=40), nullable=True),
    sa.Column('defense_team', sa.String(length=40), nullable=True),
    sa.Column('quarter', sa.Integer(), nullable=True),
    sa.Column('game_seconds_remaining', sa.Integer(), nullable=True),
    sa.Column('down', sa.Integer(), nullable=True),
    sa.Column('ydstogo', sa.Integer(), nullable=True),
    sa.Column('yardline_100', sa.Integer(), nullable=True),
    sa.Column('hash', sa.String(length=1), nullable=True),
    sa.Column('score_differential', sa.Integer(), nullable=True),
    sa.Column('personnel', sa.String(length=4), nullable=True),
    sa.Column('formation', sa.String(length=40), nullable=True),
    sa.Column('motion_type', sa.String(length=40), nullable=True),
    sa.Column('shotgun', sa.Boolean(), nullable=True),
    sa.Column('no_huddle', sa.Boolean(), nullable=True),
    sa.Column('play_type', sa.String(length=10), nullable=True),
    sa.Column('play_family', sa.String(length=40), nullable=True),
    sa.Column('pass_concept', sa.String(length=40), nullable=True),
    sa.Column('run_concept', sa.String(length=40), nullable=True),
    sa.Column('result_yards', sa.Integer(), nullable=True),
    sa.Column('epa', sa.Float(), nullable=True),
    sa.Column('explosive', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
    sa.ForeignKeyConstraint(['opponent_id'], ['opponents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('plays', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plays_down'), ['down'], unique=False)
        batch_op.create_index(batch_op.f('ix_plays_game_id'), ['game_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plays_offense_team'), ['offense_team'], unique=False)
        batch_op.create_index(batch_op.f('ix_plays_opponent_id'), ['opponent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plays_team_id'), ['team_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plays_upload_id'), ['upload_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('plays', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plays_upload_id'))
        batch_op.drop_index(batch_op.f('ix_plays_team_id'))
        batch_op.drop_index(batch_op.f('ix_plays_opponent_id'))
        batch_op.drop_index(batch_op.f('ix_plays_offense_team'))
        batch_op.drop_index(batch_op.f('ix_plays_game_id'))
        batch_op.drop_index(batch_op.f('ix_plays_down'))

    op.drop_table('plays')
    with op.batch_alter_table('uploads', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_uploads_team_id'))

    op.drop_table('uploads')
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_games_team_id'))

    op.drop_table('games')
    with op.batch_alter_table('vocab_mappings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vocab_mappings_team_id'))

    op.drop_table('vocab_mappings')
    with op.batch_alter_table('opponents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_opponents_team_id'))

    op.drop_table('opponents')
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_teams_owner_id'))

    op.drop_table('teams')
    with op.batch_alter_table('predictions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_predictions_user_id'))

    op.drop_table('predictions')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
