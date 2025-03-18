import asyncio
import base64
import concurrent.futures
import logging
import random
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, TypeVar, Generic

import aiofiles
import yarl
from aiohttp import ClientSession
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy.exc import OperationalError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from klang.config import Config
from klang.db import get_session
from klang.models import WordMeaning, WordMeaningTranslation, LLMLog

log = logging.getLogger(__name__)

NARAKEET_URL = f'https://api.narakeet.com/text-to-speech/mp3'
NARAKEET_VOICES = ["Andreas", "Klara"]

T = TypeVar("T")
S = TypeVar("S")


class PartOfSpeech(Enum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    OTHER = "other"


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class LLMWordTranslation(BaseModel):
    translation: str
    description: str


class LLMWordMeaning(BaseModel):
    part_of_speech: PartOfSpeech
    gender: Optional[Gender]
    english_translation: LLMWordTranslation
    russian_translation: LLMWordTranslation


class LLMWord(BaseModel):
    word: str
    meanings: List[LLMWordMeaning]


@dataclass
class TaskEventContainer:
    event: asyncio.Event
    exception: Optional[Exception] = None


@dataclass
class WordMeaningTask:
    event_container: TaskEventContainer
    word: str


@dataclass
class WordIllustrationTask:
    event_container: TaskEventContainer
    word: str
    description: str
    png_path: Path


@dataclass
class WordSoundTask:
    event_container: TaskEventContainer
    word: str
    mp3_path: Path


@dataclass
class TaskContainer(Generic[T, S]):
    lock: asyncio.Lock
    events: Dict[S, TaskEventContainer]
    queue: asyncio.Queue[T]
    process_task: Optional[asyncio.Task] = None


@dataclass
class TaskContainerWordMeaning(TaskContainer[WordMeaningTask, str]):
    pass


@dataclass
class TaskContainerWordIllustration(TaskContainer[WordIllustrationTask, int]):
    pass


@dataclass
class TaskContainerWordSound(TaskContainer[WordSoundTask, str]):
    pass


def _save_img_sync(png_path: Path, b64_json: str):
    with open(png_path, "wb") as f:
        f.write(base64.b64decode(b64_json))


class LLMClient:
    SYSTEM_CONTEXT = "You are generating a content for a high quality word learning website."

    def __init__(self, config: Config):
        self.config = config

        self.openai = AsyncOpenAI(api_key=config.openai_key)
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=10)

        self._word_meaning_tasks = TaskContainerWordMeaning(
            lock=asyncio.Lock(), events={}, queue=asyncio.Queue[WordMeaningTask](1000),
        )
        self._word_illustration_tasks = TaskContainerWordIllustration(
            lock=asyncio.Lock(), events={}, queue=asyncio.Queue[WordIllustrationTask](1000),
        )
        self._word_sound_tasks = TaskContainerWordSound(
            lock=asyncio.Lock(), events={}, queue=asyncio.Queue[WordSoundTask](1000),
        )

    async def start(self):
        if self._word_meaning_tasks.process_task is not None:
            raise RuntimeError("Already running")
        if self._word_illustration_tasks.process_task is not None:
            raise RuntimeError("Already running")
        if self._word_sound_tasks.process_task is not None:
            raise RuntimeError("Already running")
        self._word_meaning_tasks.process_task = asyncio.create_task(
            self._process_word_meanings_forever()
        )
        self._word_illustration_tasks.process_task = asyncio.create_task(
            self._process_word_illustrations_forever(),
        )
        self._word_sound_tasks.process_task = asyncio.create_task(
            self._process_word_sounds_forever(),
        )

    async def _process_word_meanings_forever(self):
        while True:
            try:
                await self._process_word_meanings()
            except Exception as e:
                log.exception(f"Error processing word meanings: {e}. Restarting")
                await asyncio.sleep(1)

    async def _process_word_meanings(self):
        log.info("Starting word meaning processing")
        while True:
            async with get_session() as session:
                task = await self._word_meaning_tasks.queue.get()
                log.info(f"Processing task for word meanings of '{task.word}'")
                try:
                    await self._generate_word_meanings(session, task.word)
                    task.event_container.event.set()
                except OperationalError as e:
                    log.error("DB operational error (meaning) {}".format(e))
                    task.event_container.event.set()
                    task.event_container.exception = e
                except Exception as e:
                    log.exception(f"Error processing word meaning of '{task.word}': {e}")
                    task.event_container.event.set()
                    task.event_container.exception = e

    async def _process_word_illustrations_forever(self):
        while True:
            try:
                await self._process_word_illustrations()
            except Exception as e:
                log.exception(f"Error processing word illustrations: {e}. Restarting")
                await asyncio.sleep(1)

    async def _process_word_illustrations(self):
        log.info("Starting word illustration processing")
        while True:
            async with get_session() as session:
                task = await self._word_illustration_tasks.queue.get()
                log.info(f"Processing task for word illustration of '{task.word}'")
                try:
                    await self._generate_word_illustration(
                        session, task.word, task.description, task.png_path,
                    )
                    task.event_container.event.set()
                except OperationalError as e:
                    log.error("DB operational error (illustration) {}".format(e))
                    task.event_container.event.set()
                    task.event_container.exception = e
                except Exception as e:
                    log.exception(f"Error processing word illustration: {e}")
                    task.event_container.event.set()
                    task.event_container.exception = e

    async def _process_word_sounds_forever(self):
        while True:
            try:
                await self._process_word_sounds()
            except Exception as e:
                log.exception(f"Error processing word sounds: {e}. Restarting")
                await asyncio.sleep(1)

    async def _process_word_sounds(self):
        log.info("Starting word sounds processing")
        while True:
            async with (
                get_session() as session,
                ClientSession() as http_client,
            ):
                task = await self._word_sound_tasks.queue.get()
                log.info(f"Processing task for word sound of '{task.word}'")
                try:
                    await self._generate_word_sound(
                        session, http_client, task.word, task.mp3_path,
                    )
                    task.event_container.event.set()
                except OperationalError as e:
                    log.error("DB operational error (sound) {}".format(e))
                    task.event_container.event.set()
                    task.event_container.exception = e
                except Exception as e:
                    log.exception(f"Error processing word sound: {e}")
                    task.event_container.event.set()
                    task.event_container.exception = e

    def _make_messages_with_context(self, request: str) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.SYSTEM_CONTEXT},
            {"role": "user", "content": request},
        ]

    async def wait_word_meanings(
        self, session: AsyncSession, word: str,
    ) -> List[WordMeaning]:
        sql_query: Select = select(WordMeaning).where(WordMeaning.word == word)
        result = list((await session.exec(sql_query)).all())
        if len(result) > 0:
            return result

        async with self._word_meaning_tasks.lock:
            event_container = self._word_meaning_tasks.events.get(word)
            if event_container is None:
                event_container = TaskEventContainer(event=asyncio.Event())
                task = WordMeaningTask(event_container=event_container, word=word)
                self._word_meaning_tasks.events[word] = event_container
                log.info(f"Queueing task for word meanings of '{word}'")
                self._word_meaning_tasks.queue.put_nowait(task)

        await event_container.event.wait()
        if event_container.exception is not None:
            raise event_container.exception
        sql_query = select(WordMeaning).where(WordMeaning.word == word)
        result = list((await session.exec(sql_query)).all())
        if len(result) == 0:
            raise RuntimeError(f"LLM task complete, but no results found for meanings of '{word}'")
        return result

    async def wait_word_meaning_illustration(
        self, session: AsyncSession, word_meaning_id: int, png_path: Path,
    ):
        if png_path.exists():
            return

        query: Select = select(WordMeaning).where(WordMeaning.id == word_meaning_id)
        word_meaning: WordMeaning = (await session.exec(query)).first()
        if word_meaning is None:
            raise RuntimeError(f"Word meaning with id {word_meaning_id} not found")

        for word_translation in word_meaning.translations:
            if word_translation.language == "en":
                translated_word = word_translation.translation
                translated_description = word_translation.description
                break
        else:
            raise RuntimeError(f"No en translation for word meaning with id {word_meaning_id}")

        if png_path.exists():
            return

        async with self._word_illustration_tasks.lock:
            event_container = self._word_illustration_tasks.events.get(word_meaning_id)
            if event_container is None:
                event_container = TaskEventContainer(event=asyncio.Event())
                task = WordIllustrationTask(
                    event_container=event_container,
                    word=translated_word,
                    description=translated_description,
                    png_path=png_path,
                )
                self._word_illustration_tasks.events[word_meaning_id] = event_container
                log.info(f"Queueing task for word illustration of '{translated_word}'")
                self._word_illustration_tasks.queue.put_nowait(task)

        await event_container.event.wait()
        if event_container.exception is not None:
            raise event_container.exception
        if not png_path.exists():
            raise RuntimeError(
                f"LLM task complete, but no illustration found for meaning id {word_meaning_id}",
            )

    async def wait_word_sound(
        self, word: str, mp3_path: Path,
    ):
        if mp3_path.exists():
            return

        async with self._word_sound_tasks.lock:
            event_container = self._word_sound_tasks.events.get(word)
            if event_container is None:
                event_container = TaskEventContainer(event=asyncio.Event())
                task = WordSoundTask(event_container=event_container, word=word, mp3_path=mp3_path)
                self._word_sound_tasks.events[word] = event_container
                log.info(f"Queueing task for word sound of '{word}'")
                self._word_sound_tasks.queue.put_nowait(task)

        await event_container.event.wait()
        if event_container.exception is not None:
            raise event_container.exception

        if not mp3_path.exists():
            raise RuntimeError(f"LLM task complete, but no results found for sound of '{word}'")

    async def _generate_word_meanings(self, session: AsyncSession, word: str):
        sql_query: Select = select(WordMeaning).where(WordMeaning.word == word)
        result = (await session.exec(sql_query)).all()
        if len(result) > 0:
            log.info(f"Word meanings for '{word}' already exist")
            return
        completion = await self.openai.beta.chat.completions.parse(
            model="gpt-4o",
            messages=self._make_messages_with_context(
                "Translation of a german word \"{}\" to russian and english, "
                "with description, maximum 3 most popular meanings, "
                "avoid duplicates and close synonyms.".format(word)
            ),
            response_format=LLMWord,
            n=1,
        )
        session.add(LLMLog(
            request_type="translation",
            request_data=word,
            response_data=completion.choices[0].message.parsed.model_dump_json(),
            amount_in=completion.usage.prompt_tokens,
            amount_out=completion.usage.completion_tokens,
        ))
        llm_word = completion.choices[0].message.parsed
        if llm_word is None:
            raise RuntimeError("LLM returned a null object")

        for llm_meaning, rating in zip(llm_word.meanings, (100_000, 50_000, 10_000)):
            meaning = WordMeaning(
                word=llm_word.word,
                part_of_speech=llm_meaning.part_of_speech.value,
                gender=llm_meaning.gender.value if llm_meaning.gender else None,
            )
            meaning.translations.append(WordMeaningTranslation(
                rating=rating,
                language="en",
                translation=llm_meaning.english_translation.translation,
                description=llm_meaning.english_translation.description,
            ))
            meaning.translations.append(WordMeaningTranslation(
                rating=rating,
                language="ru",
                translation=llm_meaning.russian_translation.translation,
                description=llm_meaning.russian_translation.description,
            ))
            session.add(meaning)
        await session.commit()
        log.info(f"LLM-generated word meanings for {word}")

    async def _generate_word_illustration(
        self, session: AsyncSession, word: str, description: str, png_path: Path,
    ):
        if png_path.exists():
            log.info(f"Word illustration '{png_path.name}' already exists")
            return
        result = await self.openai.images.generate(
            model="dall-e-3",
            prompt=(
                "Draw illustration to concept \"{}. {}\" "
                "without any words on a picture, just the illustration "
                "with a relatively simple and straightforward style".format(
                    word, description,
                )
            ),
            size="1024x1024",
            quality="standard",
            response_format="b64_json",
            n=1,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor, _save_img_sync, png_path, result.data[0].b64_json,
        )

        session.add(LLMLog(
            request_type="translation",
            request_data=description,
            response_data="",
            amount_in=0,
            amount_out=1024,
        ))
        await session.commit()
        log.info(f"LLM-generated word illustration for '{description}'")

    async def _generate_word_sound(
        self, session: AsyncSession, http_client: ClientSession, word: str, mp3_path: Path,
    ):
        if mp3_path.exists():
            log.info(f"Word sound '{mp3_path.name}' already exists")
            return
        voice = random.choice(NARAKEET_VOICES)
        url = yarl.URL(NARAKEET_URL).with_query({
            "voice": voice,
            "voice-speed": "0.9",
        })
        async with http_client.post(
            str(url),
            data=word,
            headers={
                "Accept": "application/octet-stream",
                "Content-Type": "text/plain",
                'x-api-key': self.config.narakeet_key,
            },
        ) as response:
            response.raise_for_status()
            duration_seconds = response.headers.get("x-duration-seconds")
            try:
                duration_seconds_parsed = int(duration_seconds)
            except (ValueError, TypeError):
                duration_seconds_parsed = 0
                log.error(f"Wrong duration seconds header '{duration_seconds}' for word '{word}'")
            async with aiofiles.open(mp3_path, "wb") as f:
                while True:
                    data = await response.content.read(1024 * 64)
                    if len(data) == 0:
                        break
                    await f.write(data)

        session.add(LLMLog(
            request_type="sound",
            request_data=word,
            response_data="",
            amount_in=0,
            amount_out=duration_seconds_parsed,
        ))
        await session.commit()
        log.info(f"LLM-generated word sound for '{word}'")
