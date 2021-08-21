from nltk.corpus import wordnet
from nltk.corpus.reader import NOUN, VERB, ADV, ADJ
from nltk.stem import WordNetLemmatizer

__all__ = ["lemmatize", "lemma_eq", "is_synonym"]
LEMMATIZER = WordNetLemmatizer()


def nltk_pos(tag: str):
    if tag in {VERB, NOUN, ADV, ADJ}:
        return tag
    if "VB" in tag:
        return VERB
    if "NN" in tag or tag in {"CODE", "LIT"}:
        return NOUN
    if "RB" in tag:
        return ADV
    if "JJ" in tag:
        return ADJ
    return NOUN


def lemmatize(word: str, pos: str = NOUN) -> str:
    return LEMMATIZER.lemmatize(word, nltk_pos(pos))


def lemma_eq(word1: str, word2: str, pos: str = NOUN) -> bool:
    return lemmatize(word1.lower(), pos) == lemmatize(word2.lower(), pos)


def is_synonym(word1: str, word2: str, pos: str = None) -> bool:
    if pos:
        pos = nltk_pos(pos)
    word1 = lemmatize(word1.lower(), pos or NOUN)
    word2 = lemmatize(word2.lower(), pos or NOUN)

    for syn in wordnet.synsets(word1, pos):
        for lemma in syn.lemma_names():
            if lemma == word2 and lemma != word1:
                return True
    return False
