from dataclasses import dataclass
from typing import Annotated

import aiohttp
from fastapi import Depends
from fastapi.security import OAuth2AuthorizationCodeBearer

from klang.config import Config, get_default_config
from klang.db import SessionDep
from klang.llm import LLMClient
from klang.oauth import token_to_user, OAuthUser
from klang.storage import Storage
from klang.user_settings import UserSettings, load_settings


async def get_http_session():
    async with aiohttp.ClientSession() as session:
        yield session

HTTPClientDep = Annotated[aiohttp.ClientSession, Depends(get_http_session)]


ConfigDep = Annotated[Config, Depends(get_default_config)]


oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="api/oauth/auth_url",
    tokenUrl="api/oauth/code_to_token",
    refreshUrl="api/oauth/refresh_token",
)


@dataclass
class UserData:
    user: OAuthUser
    settings: UserSettings


async def get_user_data(
    session: SessionDep,
    config: ConfigDep,
    http_client: HTTPClientDep,
    user_token: Annotated[str, Depends(oauth2_scheme)],
) -> UserData:
    user = await token_to_user(http_client=http_client, config=config, token=user_token)
    user_settings = await load_settings(session, user.id)
    return UserData(user=user, settings=user_settings)


UserDep = Annotated[UserData, Depends(get_user_data)]


async def get_llm_client(config: ConfigDep):
    client = LLMClient(config)
    await client.start()
    return client


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]


def get_storage(config: ConfigDep):
    return Storage(config)


StorageDep = Annotated[Storage, Depends(get_storage)]
