from dataclasses import dataclass, field
import logging
from enum import Enum
from typing import get_type_hints

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from klang.models import UserSettingsValue

log = logging.getLogger(__name__)


class LanguageEnum(Enum):
    EN = "en"
    RU = "ru"


@dataclass
class UserSettings:
    source_language: LanguageEnum = field(
        default=LanguageEnum.EN, metadata={"description": "Language to learn in"},
    )
    words_per_day: int = field(default=30, metadata={"description": "Words per day"})
    notification_email: str = field(default="", metadata={"description": "Notification email"})
    enable_notifications: bool = field(
        default=False, metadata={"description": "Enable notifications"},
    )


@dataclass
class UserSettingEntry:
    key: str
    type: str
    description: str


async def load_settings(session: AsyncSession, user_id: int) -> UserSettings:
    settings = UserSettings()
    query = select(UserSettingsValue).where(UserSettingsValue.user_id == user_id)
    type_hints = get_type_hints(UserSettings)
    for settings_value in (await session.exec(query)):
        key: str = settings_value.key
        raw_value: str = settings_value.value
        if key in type_hints:
            type_hint = type_hints[key]
            if type_hint is int:
                setattr(settings, key, int(raw_value))
            elif type_hint is str:
                setattr(settings, key, raw_value)
            elif type_hint is bool:
                setattr(settings, key, raw_value == "True")
            elif issubclass(type_hint, Enum):
                setattr(settings, key, type_hint(raw_value))
            else:
                log.warning(f"Unsupported type hint for setting {key}: {type_hint}")

    return settings
