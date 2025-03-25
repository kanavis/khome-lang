from contextlib import asynccontextmanager

from dishka import AsyncContainer
from fastapi import FastAPI

from klang.api.oauth import bind_oauth_api
from klang.api.training import bind_training_api
from klang.api.vocabulary import bind_vocabulary_api
from klang.config import Config
from klang.db import create_db_and_tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_db_and_tables()
    yield


def create_app(config: Config) -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def hello():
        return {"message": "Hello"}

    bind_oauth_api(app)
    bind_vocabulary_api(app, config)
    bind_training_api(app)

    return app
