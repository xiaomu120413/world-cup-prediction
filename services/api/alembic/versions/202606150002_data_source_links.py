from alembic import op

revision = "202606150002"
down_revision = "202606130001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists data_source_links (
            id uuid primary key default gen_random_uuid(),
            entity_type varchar(64) not null,
            entity_key varchar(256) not null,
            source varchar(64) not null,
            source_type varchar(64) not null,
            source_url text,
            raw_snapshot_id uuid references raw_snapshots(id) on delete set null,
            source_record_id varchar(128),
            confidence numeric(4,3) not null default 1.0,
            fetched_at timestamptz not null default now(),
            metadata jsonb not null default '{}'::jsonb,
            created_at timestamptz not null default now(),
            constraint uq_data_source_links_entity_source unique (entity_type, entity_key, source, source_type)
        )
        """
    )
    op.execute("create index if not exists idx_data_source_links_entity on data_source_links(entity_type, entity_key)")
    op.execute("create index if not exists idx_data_source_links_raw_snapshot on data_source_links(raw_snapshot_id)")


def downgrade() -> None:
    op.execute("drop index if exists idx_data_source_links_raw_snapshot")
    op.execute("drop index if exists idx_data_source_links_entity")
    op.execute("drop table if exists data_source_links")
