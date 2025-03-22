from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class DBConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str
    db: str


class OAuthClientConfig(BaseModel):
    client_id: str
    client_secret: str
    auth_uri: str
    token_uri: str
    callback_uri: str
    userinfo_uri: str
    logout_uri: str


class Config(BaseModel):
    db: DBConfig
    oauth_client: OAuthClientConfig
    openai_key: str
    narakeet_key: str
    illustrations_dir: Path
    sounds_dir: Path
    listen_host: str = "127.0.0.1"
    listen_port: int = 8088


def load_config(path: Path) -> Config:
    with open(path) as f:
        return Config.model_validate(yaml.safe_load(f))
