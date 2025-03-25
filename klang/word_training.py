import random
from datetime import datetime
from enum import Enum
from typing import Optional, Self, List, Union, Dict, Generator, Literal

from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from klang.api.common import UserData
from klang.helpers import next_enum_map, clamp
from klang.models import Vocabulary, Lexicon


class WordTrainingPhase(Enum):
    REMEMBER = "remember"
    CHOOSE_TRANSLATION = "choose_translation"
    CHOOSE_WORD = "choose_word"
    WRITE_TRANSLATION = "write_translation"
    WRITE_WORD = "write_word"
    END = "end"


NEXT_PHASE_MAP: Dict[WordTrainingPhase, WordTrainingPhase] = (
    next_enum_map(WordTrainingPhase)
)


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class TrainingWord(BaseModel):
    vocabulary_id: int
    meaning_id: int
    word: str
    translation: str
    description: str
    part_of_speech: str
    gender: Optional[Gender]
    phase: WordTrainingPhase
    fails: int = 0

    @classmethod
    def from_vocabulary(cls, vocabulary: Vocabulary, language: str) -> Self:
        translation = vocabulary.word_meaning.get_translation(language)
        if vocabulary.learn_count > 0:
            phase = WordTrainingPhase.CHOOSE_TRANSLATION
        else:
            phase = WordTrainingPhase.REMEMBER
        return cls(
            vocabulary_id=vocabulary.id,
            meaning_id=vocabulary.word_meaning_id,
            word=vocabulary.word_meaning.word,
            translation=translation.translation,
            description=translation.description,
            part_of_speech=vocabulary.word_meaning.part_of_speech,
            gender=vocabulary.word_meaning.gender,
            phase=phase,
        )


class WordTraining(BaseModel):
    language: str
    words: Dict[int, TrainingWord]
    user_id: int

    def is_finished(self) -> bool:
        return all(word.phase == WordTrainingPhase.END for word in self.words.values())

    def non_finished_words(self) -> Generator[TrainingWord, None, None]:
        return (word for word in self.words.values() if word.phase != WordTrainingPhase.END)

    def non_finished_words_count(self) -> int:
        return sum(1 for word in self.words.values() if word.phase != WordTrainingPhase.END)


class TaskRemember(BaseModel):
    task_type: Literal["remember"] = "remember"
    word: TrainingWord
    full_word: str


class TaskChooseTranslation(BaseModel):
    task_type: Literal["choose_translation"] = "choose_translation"
    word: TrainingWord
    full_word: str
    wrong_translations: List[str]


class TaskChooseWord(BaseModel):
    task_type: Literal["choose_word"] = "choose_word"
    word: TrainingWord
    full_word: str
    wrong_words: List[str]


class TaskWriteTranslation(BaseModel):
    task_type: Literal["write_translation"] = "write_translation"
    word: TrainingWord
    full_word: str


class TaskWriteWord(BaseModel):
    task_type: Literal["write_word"] = "write_word"
    word: TrainingWord
    full_word: str


TTask = Union[
    TaskRemember,
    TaskChooseTranslation,
    TaskChooseWord,
    TaskWriteTranslation,
    TaskWriteWord,
]


def preprocess_word(word: str, part_of_speech: str, gender: Optional[str]) -> str:
    if part_of_speech == "noun" and gender is not None:
        if gender == "male":
            word = "der " + word
        elif gender == "female":
            word = "die " + word
        elif gender == "neutral":
            word = "das " + word
        else:
            raise ValueError(f"Unknown gender {gender}")

    return word


async def get_wrong_words(
    session: AsyncSession, word: str, part_of_speech: str, count: int,
) -> List[str]:
    query = select(Lexicon).where(
        Lexicon.word != word,
        Lexicon.part_of_speech == part_of_speech,
        Lexicon.top == True,
    ).order_by(func.random()).limit(count)
    return [
        preprocess_word(record.word, record.gender, record.part_of_speech)
        for record in (await session.exec(query)).all()
    ]


async def make_task(session: AsyncSession, word: TrainingWord) -> TTask:
    full_word = preprocess_word(word.word, word.part_of_speech, word.gender)
    if word.phase == WordTrainingPhase.REMEMBER:
        return TaskRemember(word=word, full_word=full_word)
    elif word.phase == WordTrainingPhase.CHOOSE_TRANSLATION:
        wrong = await get_wrong_words(session, word.word, word.part_of_speech, 3)
        return TaskChooseTranslation(word=word, full_word=full_word, wrong_translations=wrong)
    elif word.phase == WordTrainingPhase.CHOOSE_WORD:
        wrong = await get_wrong_words(session, word.word, word.part_of_speech, 3)
        return TaskChooseWord(word=word, full_word=full_word, wrong_words=wrong)
    elif word.phase == WordTrainingPhase.WRITE_TRANSLATION:
        return TaskWriteTranslation(word=word, full_word=full_word)
    elif word.phase == WordTrainingPhase.WRITE_WORD:
        return TaskWriteWord(word=word, full_word=full_word)
    elif word.phase == WordTrainingPhase.END:
        raise ValueError("Cannot make task for end phase")
    else:
        raise ValueError(f"Unknown phase {word.phase}")


async def next_task(session: AsyncSession, training: WordTraining) -> TTask:
    if training.is_finished():
        raise ValueError("Training is already finished")
    word = random.choice(list(training.non_finished_words()))
    task = await make_task(session, word)
    return task


async def success_word(vocabulary_id: int, training: WordTraining):
    try:
        word = training.words[vocabulary_id]
    except KeyError:
        raise ValueError(f"Word {vocabulary_id} not found in training")
    if word.phase != WordTrainingPhase.END:
        word.phase = NEXT_PHASE_MAP[word.phase]


async def check_finished(session: AsyncSession, training: WordTraining) -> bool:
    if training.is_finished():
        for word in training.words.values():
            query = select(Vocabulary).where(
                Vocabulary.id == word.vocabulary_id,
                Vocabulary.user_id == training.user_id,
            )
            vocabulary = (await session.exec(query)).first()
            if vocabulary is None:
                raise ValueError(f"Vocabulary record for '{word.word}' not found")
            vocabulary.learn_count += 1
            vocabulary.last_learned_at = datetime.now()
            vocabulary.last_fail_count = word.fails
        await session.commit()
        return True
    else:
        return False


async def fail_word(vocabulary_id: int, training: WordTraining):
    try:
        word = training.words[vocabulary_id]
    except KeyError:
        raise ValueError(f"Word {vocabulary_id} not found in training")
    word.fails += 1


async def new_word_training(
    session: AsyncSession, n_words: int, include_old: bool, user: UserData,
) -> WordTraining:
    if n_words > 50:
        raise ValueError("n_words must be not more than 20")
    if n_words < 0:
        raise ValueError("n_words must be positive")
    n_new_words = n_words if include_old else n_words - int(n_words / 2)
    n_old_words = n_words - n_new_words

    # Get new words
    query = select(Vocabulary).where(
        Vocabulary.user_id == user.user.id,
        Vocabulary.learn_count == 0,
    )
    new_words = (await session.exec(query)).all()
    vocabulary_words = random.choices(new_words, k=n_new_words)

    # Get old words if needed
    if n_old_words > 0:
        query = select(Vocabulary).where(
            Vocabulary.user_id == user.user.id,
            Vocabulary.learn_count > 0,
        )
        old_words: List[Vocabulary] = (await session.exec(query)).all()
        weights: List[float] = []
        for word in old_words:
            last_learned_at_days_ago = max(0, (datetime.now() - word.learned_at).days)
            # last_learned -> 90 => weight -> 10
            no_learn_time_weight = 10 * min(90, last_learned_at_days_ago) / 90
            last_fail_weight = clamp(word.last_fail_count, 1, 10)
            learn_count_weight = 10 - clamp(word.learn_count, 0, 9)
            weights.append(no_learn_time_weight * last_fail_weight * learn_count_weight)

        vocabulary_words += random.choices(old_words, weights=weights, k=n_old_words)

    # Shuffle vocabulary words
    vocabulary_words.shuffle()

    # Create training
    return WordTraining(
        language=user.settings.source_language.value,
        words={
            word.id: TrainingWord.from_vocabulary(word, user.settings.source_language.value)
            for word in vocabulary_words
        },
        user_id=user.user.id,
    )
