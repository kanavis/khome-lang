from pathlib import Path

from klang.config import Config


class Storage:
    def __init__(self, config: Config):
        self.config = config
        self.config.illustrations_dir.mkdir(parents=True, exist_ok=True)
        self.config.sounds_dir.mkdir(parents=True, exist_ok=True)

    def get_illustrations_dir(self) -> Path:
        return self.config.illustrations_dir

    def get_illustration_path(self, word_meaning_id: int) -> Path:
        return self.config.illustrations_dir / f"{word_meaning_id}.png"

    def get_sounds_dir(self) -> Path:
        return self.config.sounds_dir

    def get_sound_path(self, word: str) -> Path:
        return self.config.sounds_dir / f"{word}.mp3"
