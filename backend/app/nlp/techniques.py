"""Contains the NLP techiniques that can be applied onto text chunks.

Example::

    text: str
    nlp = Techniques(text)
    nlp.extractive_summarisation(5)

Todo:
    * Add more techiniques
"""
from collections import Counter
from functools import cached_property
from heapq import nlargest
from typing_extensions import runtime

from spacy.language import Language
from spacy.tokens.doc import Doc
from spacy.tokens.span import Span
import spacy


class Word:
    """Apply NLP techiniques on text.

    Attributes:
        __doc : spaCy Doc class
    """

    __doc: Doc
    __accepted_pos_tags = {"NOUN", "PROPN"}

    def __init__(self, model: Language, text: str):
        """Run English spacy model on text chunk.

        Args:
            model : instance of a spaCy text-processing pipeline
            text : chunk of text from scholarly article

        Raises:
            RunTimeError: if pipeline doesn't contain lemmatizer

        """
        if not model.has_pipe("lemmatizer"):
            raise RuntimeError("Language models requires lemmatizer pipeline")

        self.__doc = model(text)

    @cached_property
    def noun_freq(self) -> dict[str, int]:
        """Calculate the frequencies of noun lemmas in a given document.

        Returns:
            Dictionary containing the frequency of each word
        """
        word_frequencies = {}
        for word in self.__doc:
            if (
                not word.is_punct
                and not word.is_stop
                and word.pos_ in self.__accepted_pos_tags
            ):
                if word.lemma_ not in word_frequencies.keys():
                    word_frequencies[word.lemma_] = 1
                else:
                    word_frequencies[word.lemma_] += 1

        return word_frequencies

    def extractive_summarisation(self, n: int) -> list[str]:
        """Return summary down to 'n' amount of sentences.

        Args:
            n : amount of sentences to be reduced down to

        Returns:
            List of strings containing the extractive summarisation
        """
        word_frequencies = self.noun_freq

        max_frequency = max(word_frequencies.values())
        normalized_frequencies: dict[str, float] = {}
        for word in word_frequencies.keys():
            normalized_frequencies[word] = word_frequencies[word] / max_frequency

        # need to optimise this, only counts sentence if fullstop,
        # space then capital letter/punctuation/number
        sentence_tokens = [sent for sent in self.__doc.sents]

        sentence_scores: dict[Span, float] = {}
        for sent in sentence_tokens:
            for word in sent:
                l_word = word.text.lower()
                if l_word in normalized_frequencies.keys():
                    if sent not in sentence_scores.keys():
                        sentence_scores[sent] = normalized_frequencies[l_word]
                        continue
                    sentence_scores[sent] += normalized_frequencies[l_word]

        summarised_sentences = nlargest(
            n, sentence_scores, key=lambda k: sentence_scores[k]
        )

        final_sentences = [w.text for w in summarised_sentences]

        return final_sentences

    def words_threshold_n(self, n: int, dic: dict[str, int]) -> list[tuple[str, int]]:
        """Return list of tuples containing words that occur more than n times.

        Args:
            n : threshold of occurances for word to be returned

        Returns:
            List of n words including their frequency
        """

        noun_freq = Counter({k: c for k, c in dic.items() if c >= n})

        return noun_freq.most_common()


class Phrase:

    __doc: Doc

    def __init__(self, model: Language, text: str):
        # consider how to add it to pipeline if already has positionrank
        if model.has_pipe("positionrank"):
            model.remove_pipe("positionrank")

        model.add_pipe(
            "positionrank",
            config={"scrubber": {"@misc": "prefix_scrubber"}},
        )
        self.__doc = model(text)

    @cached_property
    def ranks(self) -> dict[str, int]:
        """Returns sorted dictionary with phrases ranked by their rank

        In textrank, the rank of a phrase is defined by its amount of links to
        other phrases.
        Returns:
            Dictionary of phrases mapping to their rank
        """
        phrases = {}
        # examine the top-ranked phrases in the document
        for phrase in self.__doc._.phrases:
            if phrase.text:
                phrases[phrase.text] = phrase.rank

        return phrases

    @cached_property
    def counts(self) -> dict[str, int]:
        """Returns sorted dictionary with phrases ranked by their count

        Returns:
            Dictionary of phrases mapping to their count
        """
        phrases = {}
        # examine the top-ranked phrases in the document
        for phrase in self.__doc._.phrases:
            if phrase.text:
                phrases[phrase.text] = phrase.count

        return dict(sorted(phrases.items(), key=lambda item: item[1], reverse=True))

    @spacy.registry.misc("prefix_scrubber")
    def prefix_scrubber():
        """Contains function for scrubbing the document

        Ensures that it removes leading determinants, punctuation, stopwords and also
        single word results.

        Returns:
            scrubed string
        """

        def scrubber_func(span: Span) -> str:

            result = []

            while span[0].pos_ == "DET":
                span = span[1:]

            for token in span:
                if not token.is_punct and not token.is_stop:
                    result.append(token.text.lower())

            if len(result) == 1:
                return ""

            return " ".join(result)

        return scrubber_func
