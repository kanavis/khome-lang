from klang.models import WordMeaning


def make_full_word(meaning: WordMeaning) -> str:
    if meaning.part_of_speech == "noun":
        if meaning.gender is None:
            raise ValueError("No gender for noun {} {}".format(meaning.word, meaning.id))
        else:
            if meaning.gender == "male":
                return "der " + meaning.word
            elif meaning.gender == "female":
                return "die " + meaning.word
            elif meaning.gender == "neutral":
                return "das " + meaning.word
            else:
                raise ValueError("Unknown gender {} for noun {} {}".format(
                    meaning.gender, meaning.word, meaning.id,
                ))
    else:
        return meaning.word
