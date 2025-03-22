from datetime import datetime, UTC
from typing import Annotated

from aiohttp import ClientSession
from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import FastAPI, responses, Request, HTTPException, Body

from klang.api.common import UserDep
from klang.config import Config
from klang.oauth import (
    make_auth_url,
    oauth_verifier_cookie_name,
    OAUTH_SESSION_LIFETIME,
    oauth_state_cookie_name, code_to_token, OAuthTokenResponse, refresh_token_to_token,
    make_logout_url,
)


def bind_oauth_api(app: FastAPI):
    @app.get("/api/oauth/auth_url")
    @inject
    async def auth_url(config: FromDishka[Config]):
        url, verifier, state = make_auth_url(config)
        response = responses.JSONResponse({"url": url})
        response.set_cookie(
            oauth_verifier_cookie_name(),
            verifier,
            httponly=True,
            expires=datetime.now(UTC) + OAUTH_SESSION_LIFETIME,
        )
        response.set_cookie(
            oauth_state_cookie_name(),
            state,
            httponly=True,
            expires=datetime.now(UTC) + OAUTH_SESSION_LIFETIME,
        )
        return response

    @app.post("/api/oauth/code_to_token")
    @inject
    async def oauth_code_to_token(
        request: Request,
        config: FromDishka[Config],
        http_session: FromDishka[ClientSession],
        code: Annotated[str, Body()],
        state: Annotated[str, Body()],
    ) -> OAuthTokenResponse:
        verifier = request.cookies.get(oauth_verifier_cookie_name())
        if verifier is None:
            raise HTTPException(status_code=400, detail="oauth verifier cookie missing")
        state_cookie = request.cookies.get(oauth_state_cookie_name())
        if state_cookie is None:
            raise HTTPException(status_code=400, detail="oauth state cookie missing")
        if state != state_cookie:
            raise HTTPException(status_code=400, detail="wrong state")

        return await code_to_token(config, http_session, code, verifier)

    @app.get("/api/oauth/me")
    async def oauth_me(
        user_data: UserDep,
    ):
        return user_data

    @app.post("/api/oauth/refresh_token")
    @inject
    async def oauth_refresh_token(
        config: FromDishka[Config],
        http_session: FromDishka[ClientSession],
        refresh_token: Annotated[str, Body()],
    ):
        return await refresh_token_to_token(config, http_session, refresh_token)

    @app.post("/api/oauth/logout_url")
    @inject
    async def oauth_refresh_token(
        config: FromDishka[Config],
        cancel_uri: Annotated[str, Body()],
        redirect_uri: Annotated[str, Body()],
    ):
        next_uri = make_logout_url(config, cancel_uri, redirect_uri)
        return {"redirect_uri": next_uri}