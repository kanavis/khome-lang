import argparse
from pathlib import Path

import uvicorn

from klang.app import create_app
from klang.config import load_config
from klang.logs import setup_logging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--host", type=str)
    parser.add_argument("--port", type=int)

    args = parser.parse_args()
    setup_logging()
    config = load_config(args.config)

    host = args.host if args.host is not None else config.listen_host
    port = args.port if args.port is not None else config.listen_port
    app = create_app(config)
    uvicorn.run(app, host=host, port=port, log_config=None)
