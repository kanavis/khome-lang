import argparse
import os
import time
from enum import Enum
from pathlib import Path
from typing import Optional

from openai import OpenAI, OpenAIError
from pydantic import BaseModel


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class PartOfSpeech(Enum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    OTHER = "other"


class WordInfo(BaseModel):
    part_of_speech: PartOfSpeech
    gender: Optional[Gender]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freq-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--line", type=int, default=0)
    args = parser.parse_args()
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key is None:
        raise ValueError("OPENAI_API_KEY is not set")

    openai = OpenAI(api_key=openai_key)

    with open(args.freq_file, "r") as f:
        with open(args.output_file, "a+") as f_out:
            for i, line in enumerate(f):
                if i < args.line:
                    continue
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(";")
                    if len(parts) != 4:
                        raise ValueError("Invalid line {} '{}'".format(i, line))
                    word = parts[0]
                    freq = float(parts[1])
                    is_top = parts[2] == "1"
                    if is_top:
                        while True:
                            print("LLM for line {}".format(i))
                            try:
                                data = openai.beta.chat.completions.parse(
                                    model="gpt-4o",
                                    messages=[
                                        {
                                            "role": "system",
                                            "content": "You are generating a content for a "
                                                       "high quality word learning website.",
                                        },
                                        {
                                            "role": "user",
                                            "content": "Info about german word '{}'".format(word),
                                        },
                                    ],
                                    response_format=WordInfo,
                                    n=1,
                                )
                            except OpenAIError as e:
                                print("Error for line {} '{}': {}. Retrying..".format(i, line, e))
                                time.sleep(5)
                                continue
                            llm_data = data.choices[0].message.parsed
                            if llm_data is None:
                                raise Exception("No LLM data for line {} '{}'".format(i, line))
                            gender = llm_data.gender
                            part_of_speech = llm_data.part_of_speech
                            break
                    else:
                        gender = None
                        part_of_speech = None

                    f_out.write("{};{};{};{};{};{}\n".format(
                        i,
                        word,
                        freq,
                        1 if is_top else 0,
                        part_of_speech.value if part_of_speech is not None else "",
                        gender.value if gender is not None else "",
                    ))


if __name__ == "__main__":
    main()
