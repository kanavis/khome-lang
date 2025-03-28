import argparse
from pathlib import Path

import uvicorn
from dishka.integrations.fastapi import setup_dishka

from klang.app import create_app
from klang.config import load_config
from klang.db import setup_db_engine
from klang.di import make_di_container
from klang.logs import setup_logging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--host", type=str)
    parser.add_argument("--port", type=int)

    args = parser.parse_args()
    setup_logging()
    config = load_config(args.config)
    container = make_di_container(config)

    setup_db_engine(
        db_user=config.db.user,
        db_password=config.db.password,
        db_host=config.db.host,
        db_port=config.db.port,
        db_name=config.db.db,
    )

    host = args.host if args.host is not None else config.listen_host
    port = args.port if args.port is not None else config.listen_port
    app = create_app(config)
    setup_dishka(container, app)
    uvicorn.run(app, host=host, port=port, log_config=None)
