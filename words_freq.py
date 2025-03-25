import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict

from openai import OpenAI


@dataclass
class Word:
    word: str
    freq: Optional[float] = None
    pos: Optional[str] = None


@dataclass
class Freq:
    freq: float
    pos: str


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--words-file", type=Path, required=True)
    parser.add_argument("--freq-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    args = parser.parse_args()

    words: List[Word] = []
    with open(args.words_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                words.append(Word(word=line))

    freq: Dict[str, Freq] = {}
    with open(args.freq_file, "r") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("\t")
                if parts[0] == "unknown":
                    continue
                if len(parts) != 4:
                    raise ValueError("Invalid line {} '{}'".format(i, line))
                if parts[0] != parts[1]:
                    continue
                freq[parts[0]] = Freq(freq=float(parts[3]), pos=parts[2])

    found_freq = 0
    for word in words:
        if word.word in freq:
            word.freq = freq[word.word].freq
            word.pos = freq[word.word].pos
            found_freq += 1

    print("Found {} words with frequencies".format(found_freq))
    words = sorted(words, key=lambda x: x.freq or 0, reverse=True)
    with open(args.output_file, "w") as f:
        for i, word in enumerate(words):
            f.write("{};{};{};\n".format(
                word.word,
                word.freq or 0,
                1 if i < 10000 else 0,
            ))


if __name__ == "__main__":
    main()
