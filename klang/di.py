from typing import AsyncGenerator

from aiohttp import ClientSession
from dishka import Provider, provide, Scope, make_async_container, AsyncContainer

from klang.config import Config
from klang.llm import LLMClient
from klang.storage import Storage


class ConfigProvider(Provider):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    @provide(scope=Scope.RUNTIME)
    def new_config(self) -> Config:
        return self.config


class HTTPClientProvider(Provider):
    @provide(scope=Scope.RUNTIME)
    async def new_client(self) -> AsyncGenerator[ClientSession, None]:
        async with ClientSession() as session:
            yield session


class StorageProvider(Provider):
    @provide(scope=Scope.RUNTIME)
    def new_storage(self, config: Config) -> Storage:
        return Storage(config=config)


class LLMProvider(Provider):
    @provide(scope=Scope.RUNTIME)
    async def new_llm(self, config: Config) -> AsyncGenerator[LLMClient, None]:
        async with LLMClient(config) as llm:
            yield llm


def make_di_container(config: Config) -> AsyncContainer:
    return make_async_container(
        ConfigProvider(config),
        HTTPClientProvider(),
        StorageProvider(),
        LLMProvider(),
    )
