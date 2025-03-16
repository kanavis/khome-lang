from contextlib import asynccontextmanager

from fastapi import FastAPI

from klang.api.oauth import bind_oauth_api
from klang.api.vocabulary import bind_vocabulary_api
from klang.db import create_db_and_tables
from klang.storage import Storage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_db_and_tables()
    yield


def create_app(storage: Storage) -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/")
    async def hello():
        return {"message": "Hello"}

    bind_oauth_api(app)
    bind_vocabulary_api(app, storage)

    return app
