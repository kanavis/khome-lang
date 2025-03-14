from datetime import datetime, UTC
from typing import Annotated

import aiohttp
from fastapi import FastAPI, responses, Request, HTTPException, Depends, Body

from klang.config import Config
from klang.oauth import (
    make_auth_url,
    oauth_verifier_cookie_name,
    OAUTH_SESSION_LIFETIME,
    oauth_state_cookie_name, code_to_token, OAuthTokenResponse,
)


async def get_http_session():
    async with aiohttp.ClientSession() as session:
        yield session

HTTPClientDep = Annotated[aiohttp.ClientSession, Depends(get_http_session)]


def create_app(config: Config) -> FastAPI:
    app = FastAPI()

    @app.get("/")
    async def hello():
        return {"message": "Hello"}

    @app.get("/api/oauth/auth_url")
    async def auth_url():
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
    async def oauth_code_to_token(
        request: Request,
        http_session: HTTPClientDep,
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


    return app
