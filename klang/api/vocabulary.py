from typing import List, Dict, Annotated

from fastapi import FastAPI, Body, HTTPException
from openai import BaseModel
from sqlmodel import select

from klang.api.common import UserDep, LLMClientDep, StorageDep
from klang.db import SessionDep
from klang.lang import make_full_word
from klang.models import Lexicon, Vocabulary, WordMeaning, WordMeaningTranslation
from fastapi.staticfiles import StaticFiles

from klang.storage import Storage


def bind_vocabulary_api(app: FastAPI, storage: Storage):
    app.mount(
        "/api/lexicon/illustrations",
        StaticFiles(directory=storage.get_illustrations_dir()),
        name="lexicon_illustrations",
    )
    app.mount(
        "/api/lexicon/sounds",
        StaticFiles(directory=storage.get_sounds_dir()),
        name="lexicon_sounds",
    )

    @app.get("/api/lexicon/search")
    async def lexicon_search(
        session: SessionDep,
        _user_data: UserDep,
        query: str,
    ) -> List[str]:
        sql_query = select(Lexicon).where(Lexicon.word.like(f"{query}%"))
        return [row.word for row in (await session.exec(sql_query))]

    class WordMeaningOut(BaseModel):
        full_word: str
        meaning: WordMeaning
        translations: Dict[str, WordMeaningTranslation]
        added: bool

    @app.get("/api/lexicon/meanings")
    async def lexicon_meanings(
        session: SessionDep,
        _user_data: UserDep,
        llm_client: LLMClientDep,
        word: str,
        llm: bool = False,
    ) -> List[WordMeaningOut]:
        sql_query = select(WordMeaning).where(WordMeaning.word == word)
        meanings = (await session.exec(sql_query)).all()
        if len(meanings) == 0:
            if llm:
                meanings = await llm_client.wait_word_meanings(session, word)
            else:
                raise HTTPException(
                    status_code=404, detail="Init required", headers={"X-Init-Required": "true"},
                )
        result = []
        for meaning in meanings:
            sql_query = select(Vocabulary).where(Vocabulary.word_meaning_id == meaning.id)
            added = bool((await session.exec(sql_query)).first())
            translations = {x.language: x for x in meaning.translations}
            full_word = make_full_word(meaning)
            result.append(WordMeaningOut(
                full_word=full_word, meaning=meaning, added=added, translations=translations,
            ))

        return result

    @app.get("/api/lexicon/ensure_illustrations")
    async def lexicon_ensure_illustrations(
        session: SessionDep,
        _user_data: UserDep,
        llm_client: LLMClientDep,
        storage_obj: StorageDep,
        word_meaning_id: int,
        llm: bool = False,
    ) -> bool:
        illustration_path = storage_obj.get_illustration_path(word_meaning_id)
        if illustration_path.exists():
            return True
        else:
            if llm:
                await llm_client.wait_word_meaning_illustration(
                    session, word_meaning_id, illustration_path,
                )
            else:
                raise HTTPException(
                    status_code=404, detail="Init required", headers={"X-Init-Required": "true"},
                )
            return True

    @app.get("/api/lexicon/ensure_sounds")
    async def lexicon_ensure_sounds(
        _user_data: UserDep,
        llm_client: LLMClientDep,
        storage_obj: StorageDep,
        full_word: str,
        llm: bool = False,
    ) -> bool:
        sound_path = storage_obj.get_sound_path(full_word)
        if sound_path.exists():
            return True
        else:
            if llm:
                await llm_client.wait_word_sound(
                    word=full_word, mp3_path=sound_path,
                )
            else:
                raise HTTPException(
                    status_code=404, detail="Init required", headers={"X-Init-Required": "true"},
                )
            return True

    @app.get("/api/vocabulary")
    async def vocabulary(
        session: SessionDep,
        user_data: UserDep,
    ) -> List[Vocabulary]:
        sql_query = select(Vocabulary).where(Vocabulary.user_id == user_data.user.id)
        return (await session.exec(sql_query)).all()

    class AddVocabularyIn(BaseModel):
        meaning_id: int

    @app.put("/api/vocabulary")
    async def add_vocabulary(
        session: SessionDep,
        user_data: UserDep,
        request: AddVocabularyIn,
    ) -> bool:
        record = Vocabulary(user_id=user_data.user.id, word_meaning_id=request.meaning_id)
        session.add(record)
        await session.commit()
        return True
