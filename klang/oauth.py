import base64
import secrets
import string
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Tuple, Optional

import aiohttp
import yarl
from aiohttp import ClientSession
from fastapi import HTTPException
from pydantic import BaseModel

from klang.config import Config

SECURE_ALPHABET = string.ascii_letters + string.digits + "!#$%*+,-.:;<=>?@^_|~"
OAUTH_SESSION_LIFETIME = timedelta(minutes=30)


class OAuthError(Exception):
    pass


class OAuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    expires: str | None


def random_secure_string(n_symbols=64):
    return ''.join(secrets.choice(SECURE_ALPHABET) for _ in range(n_symbols))


def verifier_to_challenge_s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(
        sha256(verifier.encode("utf-8")).digest(),
    ).decode("utf-8").rstrip("=")


def make_auth_url(config: Config) -> Tuple[str, str, str]:
    verifier = random_secure_string()
    state = random_secure_string()
    return str(yarl.URL(config.oauth_client.auth_uri).with_query(
        {
            "client_id": config.oauth_client.client_id,
            "redirect_uri": config.oauth_client.callback_uri,
            "response_type": "code",
            "state": state,
            "code_challenge": verifier_to_challenge_s256(verifier),
            "code_challenge_method": "S256",
        },
    )), verifier, state


def oauth_verifier_cookie_name() -> str:
    return "oauth_verifier"


def oauth_state_cookie_name() -> str:
    return "oauth_state"


async def code_to_token(
    config: Config, http_session: aiohttp.ClientSession, code: str, verifier: str,
) -> OAuthTokenResponse:
    async with http_session.post(
        config.oauth_client.token_uri,
        data={
            "client_id": config.oauth_client.client_id,
            "client_secret": config.oauth_client.client_secret,
            "redirect_uri": config.oauth_client.callback_uri,
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
        }
    ) as result:
        if result.status != 200:
            raise OAuthError(
                "Auth server returned {}: {}".format(result.status, await result.text()),
            )
        try:
            data = await result.json()
            return OAuthTokenResponse(**data)
        except (ValueError, KeyError, TypeError):
            raise OAuthError(
                "Auth server returned invalid response: {}".format(await result.text())
            )


class OAuthUser(BaseModel):
    id: int
    email: str
    created_at: datetime
    is_superuser: bool
    username: Optional[str] = None


async def token_to_user(http_client: ClientSession, config: Config, token: str) -> OAuthUser:
    async with http_client.get(
        config.oauth_client.userinfo_uri,
        headers={"Authorization": f"Bearer {token}"},
    ) as result:
        if result.status != 200:
            raise HTTPException(
                status_code=401,
                detail="Auth server returned {}: {}".format(result.status, await result.text()),
            )
        try:
            data = await result.json()
            return OAuthUser(**data)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                status_code=401,
                detail="Auth server returned invalid response: {}".format(await result.text()),
            )
