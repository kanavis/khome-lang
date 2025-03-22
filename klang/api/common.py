from dataclasses import dataclass
from typing import Annotated

from aiohttp import ClientSession
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends
from fastapi.security import OAuth2AuthorizationCodeBearer

from klang.config import Config
from klang.db import SessionDep
from klang.oauth import token_to_user, OAuthUser
from klang.user_settings import UserSettings, load_settings


oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="api/oauth/auth_url",
    tokenUrl="api/oauth/code_to_token",
    refreshUrl="api/oauth/refresh_token",
)


@dataclass
class UserData:
    user: OAuthUser
    settings: UserSettings


@inject
async def get_user_data(
    session: SessionDep,
    config: FromDishka[Config],
    http_client: FromDishka[ClientSession],
    user_token: Annotated[str, Depends(oauth2_scheme)],
) -> UserData:
    user = await token_to_user(http_client=http_client, config=config, token=user_token)
    user_settings = await load_settings(session, user.id)
    return UserData(user=user, settings=user_settings)


UserDep = Annotated[UserData, Depends(get_user_data)]
