from datetime import datetime

from sqlalchemy import text
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint


class UserSettingsValue(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    key: str = Field()
    value: str = Field()


class Lexicon(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    word: str = Field(index=True, unique=True)


class WordMeaning(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    word: str = Field(index=True)
    part_of_speech: str = Field()
    gender: str | None = Field(nullable=True)
    translations: list["WordMeaningTranslation"] = Relationship(
        back_populates="word_meaning", sa_relationship_kwargs={"lazy": "selectin"},
    )


class WordMeaningTranslation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("word_meaning_id", "language"),)

    id: int | None = Field(default=None, primary_key=True)
    rating: int = Field(index=True)
    word_meaning_id: int = Field(index=True, foreign_key="wordmeaning.id")
    word_meaning: WordMeaning = Relationship(back_populates="translations")
    language: str = Field(index=True)
    translation: str = Field()
    description: str = Field()


class Vocabulary(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    word_meaning_id: int = Field(index=True, foreign_key="wordmeaning.id")
    word_meaning: WordMeaning = Relationship()
    user_id: int = Field(index=True)
    created_at: datetime = Field(sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")})
    last_learned_at: datetime | None = Field(nullable=True)
    last_fail_count: int | None = Field(nullable=True)
    learn_count: int = Field(default=0)


class StudyLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    word_meaning_id: int = Field(index=True, foreign_key="wordmeaning.id")
    word_meaning: WordMeaning = Relationship()
    user_id: int = Field(index=True)


class LLMLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    request_time: datetime = Field(sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")})
    request_type: str = Field()
    request_data: str = Field()
    response_data: str = Field()
    amount_in: int = Field()
    amount_out: int = Field()
