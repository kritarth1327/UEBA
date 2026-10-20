"""pipeline columns and ingestion runs

Adds dataset provenance / label-count columns, prediction component breakdown,
alert source + uniqueness, and the ingestion_runs table. All new columns are
nullable or defaulted, so existing rows remain valid.

Revision ID: a1c4e7d90b21
Revises: 785bff5920fe
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c4e7d90b21'
down_revision: Union[str, Sequence[str], None] = '785bff5920fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('daily_behavior_profiles') as b:
        b.add_column(sa.Column('dataset_source', sa.String(32), nullable=True))
        b.add_column(sa.Column('event_count', sa.Integer(), nullable=True))
        b.add_column(sa.Column('anomalous_event_count', sa.Integer(), nullable=True))
        b.create_index('ix_daily_behavior_profiles_dataset_source', ['dataset_source'])
    with op.batch_alter_table('model_predictions') as b:
        b.add_column(sa.Column('components_json', sa.Text(), nullable=True))
        b.add_column(sa.Column('config_version', sa.String(64), nullable=True))
    with op.batch_alter_table('personal_baselines') as b:
        b.add_column(sa.Column('config_json', sa.Text(), nullable=True))
    with op.batch_alter_table('alerts') as b:
        b.add_column(sa.Column('source', sa.String(32), nullable=False, server_default='hybrid_risk'))
        b.create_index('ix_alerts_source', ['source'])
        b.create_unique_constraint('uq_alert_user_date_source', ['user_id', 'date', 'source'])
    op.create_table(
        'ingestion_runs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('dataset', sa.String(32), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.Column('source_path', sa.String(255), nullable=False),
        sa.Column('schema_version', sa.String(16), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('report_json', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_ingestion_runs_dataset', 'ingestion_runs', ['dataset'])
    op.create_index('ix_ingestion_runs_fingerprint', 'ingestion_runs', ['fingerprint'])
    op.create_index('ix_ingestion_runs_status', 'ingestion_runs', ['status'])


def downgrade() -> None:
    op.drop_table('ingestion_runs')
    with op.batch_alter_table('personal_baselines') as b:
        b.drop_column('config_json')
    with op.batch_alter_table('alerts') as b:
        b.drop_constraint('uq_alert_user_date_source', type_='unique')
        b.drop_index('ix_alerts_source')
        b.drop_column('source')
    with op.batch_alter_table('model_predictions') as b:
        b.drop_column('config_version')
        b.drop_column('components_json')
    with op.batch_alter_table('daily_behavior_profiles') as b:
        b.drop_index('ix_daily_behavior_profiles_dataset_source')
        b.drop_column('anomalous_event_count')
        b.drop_column('event_count')
        b.drop_column('dataset_source')
