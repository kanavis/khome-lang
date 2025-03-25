from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator

from fastapi import FastAPI
from pydantic import BaseModel
from sqlmodel import delete, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from klang.api.common import UserDep, UserData
from klang.db import SessionDep
from klang.models import UserTraining
from klang.word_training import (
    new_word_training,
    fail_word,
    WordTraining,
    success_word,
    next_task,
    TTask, check_finished,
)


class TrainingOut(BaseModel):
    training_id: int


class TrainingIn(BaseModel):
    n_words: int
    include_old: bool


class WordIn(BaseModel):
    training_id: int
    vocabulary_id: int


def bind_training_api(app: FastAPI):
    @app.get("/training/word")
    async def create_word_training(
        session: SessionDep,
        user: UserDep,
    ) -> Optional[TrainingOut]:
        query = select(UserTraining).where(
            UserTraining.user_id == user.user.id,
            col(UserTraining.training_type) == "word",
        )
        db_training = (await session.exec(query)).first()
        if db_training is None:
            return None
        else:
            return TrainingOut(training_id=db_training.id)

    @app.post("/training/word")
    async def create_word_training(
        session: SessionDep,
        user: UserDep,
        data: TrainingIn,
    ) -> TrainingOut:
        training = await new_word_training(
            session=session, n_words=data.n_words, include_old=data.include_old, user=user,
        )
        query = delete(UserTraining).where(
            UserTraining.user_id == user.user.id,
            col(UserTraining.training_type) == "word",
        )
        await session.exec(query)

        db_training = UserTraining(
            user_id=user.user.id,
            training_type="word",
            training_data=training.model_dump_json(),
        )
        session.add(db_training)
        await session.commit()
        await session.refresh(db_training)

        return TrainingOut(training_id=db_training.id)

    @asynccontextmanager
    async def _load_training(
        session: AsyncSession, user: UserData, training_id: int, save: bool = True,
    ) -> AsyncIterator[WordTraining]:
        query = select(UserTraining).where(
            UserTraining.user_id == user.user.id,
            col(UserTraining.training_type) == "word",
            UserTraining.id == training_id,
        )
        db_training = (await session.exec(query)).first()
        if db_training is None:
            raise ValueError(f"Training {training_id} not found")
        training = WordTraining.model_validate_json(db_training.training_data)
        yield training
        if save:
            db_training.training_data = training.model_dump_json()
            await session.commit()
            await session.refresh(db_training)

    @app.post("/training/word/error")
    async def error_word_training(
        session: SessionDep,
        user: UserDep,
        data: WordIn,
    ) -> None:
        async with _load_training(session, user, data.training_id) as training:
            await fail_word(vocabulary_id=data.vocabulary_id, training=training)

    @app.post("/training/word/success")
    async def success_word_training(
        session: SessionDep,
        user: UserDep,
        data: WordIn,
    ) -> None:
        async with _load_training(session, user, data.training_id) as training:
            await success_word(vocabulary_id=data.vocabulary_id, training=training)

    @app.get("/training/word/next")
    async def get_next_word_training(
        session: SessionDep,
        user: UserDep,
        training_id: int,
    ) -> TTask:
        async with _load_training(session, user, training_id, save=False) as training:
            return await next_task(session, training)

    @app.get("/training/word/complete")
    async def complete_word_training(
        session: SessionDep,
        user: UserDep,
        training_id: int,
    ) -> bool:
        async with _load_training(session, user, training_id) as training:
            return await check_finished(session, training)
