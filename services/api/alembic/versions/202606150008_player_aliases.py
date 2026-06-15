"""Add player alias mappings."""

from alembic import op

revision = "202606150008"
down_revision = "202606150007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists player_aliases (
            id uuid primary key default gen_random_uuid(),
            player_id uuid not null references players(id) on delete cascade,
            team_id uuid not null references teams(id) on delete cascade,
            source varchar(64) not null,
            source_player_id varchar(128),
            alias varchar(128) not null,
            confidence numeric(4,3) not null default 1.0,
            is_primary boolean not null default false,
            constraint uq_player_aliases_source_player_id unique (source, source_player_id)
        )
        """
    )
    op.execute(
        "create index if not exists idx_player_aliases_source_team_alias on player_aliases(source, team_id, alias)"
    )
    op.execute("create index if not exists idx_player_aliases_player on player_aliases(player_id)")


def downgrade() -> None:
    op.execute("drop index if exists idx_player_aliases_player")
    op.execute("drop index if exists idx_player_aliases_source_team_alias")
    op.execute("drop table if exists player_aliases")
