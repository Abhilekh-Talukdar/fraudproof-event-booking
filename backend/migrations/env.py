from logging.config import fileConfig
from pathlib import Path

from alembic import context
from flask import current_app

config = context.config
if config.config_file_name is not None and Path(config.config_file_name).exists():
    fileConfig(config.config_file_name)


def get_metadata():
    return current_app.extensions["migrate"].db.metadata


def run_migrations_offline():
    context.configure(
        url=current_app.extensions["migrate"].db.engine.url,
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = current_app.extensions["migrate"].db.engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=get_metadata(), compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
