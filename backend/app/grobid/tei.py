# noqa: D100
import string
from typing import Generator

from app.grobid.models import (
    Affiliation,
    Article,
    Author,
    Citation,
    CitationIDs,
    Date,
    PageRange,
    PersonName,
    Ref,
    RefText,
    Scope,
    Section,
)
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag
from spacy.language import Language


class GrobidParserError(BaseException):
    """Exception for TEI class."""

    pass


# TODO: use DOI from PyMuPDF to cache XML
# NOTE: shouldn't TEI methods be static?
class TEI:
    """Methods used to parse TEI XML into serializable objects."""

    soup: BeautifulSoup
    __model: Language
    __accepted_entities = {"GPE", "ORG", "PERSON"}

    def __init__(self, stream: bytes, model: Language) -> None:
        """
        TEI class constructor.

        Args:
            stream: XML bytes
            model: spaCy language model

        Raises:
            GrobidParserError: if model arg doesn't have parser pipeline
        """
        self.soup = BeautifulSoup(stream, "lxml-xml")
        if not model.has_pipe("parser"):
            raise GrobidParserError("Language models require parser pipeline")
        self.__model = model

    def parse(self) -> Article:
        """
        Attempt to parse the XML into Article object.

        Parsing is strict (fails if any fields are missing)

        Returns:
            Article object
        """
        body = self.soup.body

        if not isinstance(body, Tag):
            raise GrobidParserError("Missing body")

        abstract: Section | None = self.section(self.soup.abstract, title="Abstract")

        sections: list[Section] = []
        for div in body.find_all("div"):
            if (section := self.section(div)) is not None:
                sections.append(section)

        if (source := self.soup.find("sourceDesc")) is None:
            raise GrobidParserError("Missing source description")

        biblstruct_tag = source.find("biblStruct")
        if not isinstance(biblstruct_tag, Tag):
            raise GrobidParserError("Missing bibliography")

        bibliography = self.citation(biblstruct_tag)
        keywords = self.keywords(self.soup.keywords)

        listbibl_tag = self.soup.find("listBibl")
        if not isinstance(listbibl_tag, Tag):
            raise GrobidParserError("Missing citations")

        citations = {}
        for struct_tag in listbibl_tag.find_all("biblStruct"):
            if isinstance(struct_tag, Tag):
                name = struct_tag.get("xml:id")
                citations[name] = self.citation(struct_tag)

        return Article(
            abstract=abstract,
            sections=sections,
            bibliography=bibliography,
            keywords=keywords,
            citations=citations,
        )

    def citation(self, source_tag: Tag) -> Citation:
        """
        Parse citation.

        Args:
            source_tag : biblStruct XML Tag

        Returns:
            Citation object
        """
        # NOTE: may return empty string
        citation = Citation(title=self.title(source_tag, attrs={"type": "main"}))
        citation.authors = self.authors(source_tag)
        ids = CitationIDs(
            DOI=self.idno(source_tag, attrs={"type": "DOI"}),
            arXiv=self.idno(source_tag, attrs={"type": "arXiv"}),
        )
        if not ids.is_empty():
            citation.ids = ids

        citation.date = self.date(source_tag)
        citation.target = self.target(source_tag)
        citation.publisher = self.publisher(source_tag)
        citation.scope = self.scope(source_tag)
        if journal := self.title(source_tag, attrs={"level": "j"}):
            if journal != citation.title:
                citation.journal = journal
        if series := self.title(source_tag, attrs={"level": "s"}):
            if series != citation.title:
                citation.series = series

        return citation

    def title(self, source_tag: Tag | None, attrs: dict[str, str] = {}) -> str:
        """
        Parse title tag text.

        Args:
            source_tag : XML tag
            attrs: dictionary of filters on attribute values. Default is empty dict.

        Returns:
            Text in title tag if it exists
        """
        title: str = ""
        if source_tag is not None:
            if (title_tag := source_tag.find("title", attrs=attrs)) is not None:
                title = title_tag.text

        return title

    def target(self, source_tag: Tag | None) -> str | None:
        """
        Parse ptr tag target.

        Args:
            source_tag : XML tag

        Returns:
            Target location in ptr tag if it exists
        """
        if source_tag is not None:
            if (ptr_tag := source_tag.ptr) is not None:
                if "target" in ptr_tag.attrs:
                    # TODO: validate URL
                    return ptr_tag.attrs["target"]

    def idno(self, source_tag: Tag | None, attrs: dict[str, str] = {}) -> str | None:
        """
        Parse idno tag.

        Args:
            source_tag : XML tag
            attrs: dictionary of filters on attribute values. Default is empty dict.

        Returns:
            Text content of idno_tag if it exists
        """
        if source_tag is not None:
            if (idno_tag := source_tag.find("idno", attrs=attrs)) is not None:
                return idno_tag.text or None

    def keywords(self, source_tag: Tag | None) -> set[str]:
        """
        Parse all term tags.

        Uses spaCy model to extract noun chunks.

        Args:
            source_tag : XML tag

        Returns:
            Set of keywords
        """
        keywords: set[str] = set()

        if source_tag is not None:
            for term_tag in source_tag.find_all("term"):
                if term_tag.text:
                    doc = self.__model(term_tag.text)
                    for keyword in doc.noun_chunks:
                        if clean_keyword := self.clean_title_string(keyword.text):
                            keywords.add(clean_keyword)

        return keywords

    def publisher(self, source_tag: Tag | None) -> str | None:
        """
        Parse publisher tag text.

        Args:
            source_tag : XML tag

        Returns:
            Text in publisher tag if it exists
        """
        if source_tag is not None:
            if (publisher_tag := source_tag.find("publisher")) is not None:
                return publisher_tag.text or None

    def date(self, source_tag: Tag | None) -> Date | None:
        """
        Parse date tag.

        Args:
            source_tag : XML tag

        Returns:
            Date object if date tag is valid
        """
        if source_tag is not None:
            if (date_tag := source_tag.date) is not None:
                if "when" in date_tag.attrs:
                    when = date_tag.attrs["when"]

                    return self.__parse_date(when)

    def __parse_date(self, date: str, sep="-") -> Date | None:
        # Assumes date uses hyphen as separator by default
        tokens = date.split(sep=sep)

        match len(tokens):
            case 1:
                year = tokens[0]
                return Date(year)
            case 2:
                year, month = tokens
                return Date(year, month)
            case 3:
                year, month, day = tokens
                return Date(year, month, day)

    def scope(self, source_tag: Tag | None) -> Scope | None:
        """
        Parse all biblScope tags.

        Args:
            source_tag : XML tag

        Returns:
            Scope object if biblScope tags exist
        """
        if source_tag is not None:
            scope = Scope()
            for scope_tag in source_tag.find_all("biblScope"):
                match scope_tag.attrs["unit"]:
                    case "page":
                        try:
                            if "from" in scope_tag.attrs and "to" in scope_tag.attrs:
                                from_page = int(scope_tag["from"])
                                to_page = int(scope_tag["to"])
                            elif scope_tag.text:
                                from_page = int(scope_tag.text)
                                to_page = from_page
                            else:
                                continue

                            scope.pages = PageRange(
                                from_page=from_page, to_page=to_page
                            )
                        except ValueError:
                            continue
                    case "volume":
                        try:
                            volume = int(scope_tag.text)
                            scope.volume = volume
                        except ValueError:
                            continue

            if not scope.is_empty():
                return scope

    def authors(self, source_tag: Tag | None) -> list[Author]:
        """
        Parse all author tags.

        Uses NER to check if the author name is valid.

        Args:
            source_tag : XML tag

        Returns:
            List of Author objects
        """
        authors: list[Author] = []
        if source_tag is not None:
            for author in source_tag.find_all("author"):
                author_obj: Author | None = None
                if (persname := author.find("persName")) is not None:
                    if (surname_tag := persname.find("surname")) is not None:
                        person_name = PersonName(surname=surname_tag.text)
                        if forename_tag := persname.find("forename", {"type": "first"}):
                            person_name.first_name = forename_tag.text

                        # Use NER to check if it is a name
                        # FIXME: doesn't work very well for surname only
                        ents = self.__model(person_name.to_string()).ents
                        if ents and ents[0].label_ in self.__accepted_entities:
                            author_obj = Author(person_name=person_name)
                            authors.append(author_obj)

                if author_obj is not None:
                    if email_tag := author.find("email"):
                        author_obj.email = email_tag.text

                    for affiliation_tag in author.find_all("affiliation"):
                        affiliation_obj = Affiliation()
                        for orgname_tag in affiliation_tag.find_all("orgName"):
                            match orgname_tag["type"]:
                                case "institution":
                                    affiliation_obj.institution = orgname_tag.text
                                case "department":
                                    affiliation_obj.department = orgname_tag.text
                                case "laboratory":
                                    affiliation_obj.laboratory = orgname_tag.text

                        if not affiliation_obj.is_empty():
                            author_obj.affiliations.append(affiliation_obj)

        return authors

    def section(self, source_tag: Tag | None, title: str = "") -> Section | None:
        """
        Parse div tag with head tag.

        Capitalizes title if not already.

        Section can have an empty body.

        Args:
            source_tag : XML tag
            title: forces the parsing of the section. Default is empty string (false)

        Returns:
            Section object if valid section.
        """
        if source_tag is not None:
            head = source_tag.find("head")
            if isinstance(head, Tag):
                head_text: str = head.get_text()
                if head.has_attr("n") or head_text[0] in string.ascii_letters:
                    if head_text.isupper() or head_text.islower():
                        head_text = head_text.capitalize()

                section = Section(title=head_text)
            elif title:
                section = Section(title=title)
            else:
                return

            paragraphs = source_tag.find_all("p")
            for p in paragraphs:
                if p and (ref_text := self.ref_text(p)) is not None:
                    section.paragraphs.append(ref_text)

            return section

    def __text_and_refs(
        self,
        source_tag: Tag,
    ) -> Generator[PageElement, str, None]:
        # Generator with both NavigableStrings and ref Tags
        for descendant in source_tag.descendants:
            descendant_type = type(descendant)
            if descendant_type is Tag and descendant.name == "ref":  # type: ignore
                yield descendant
            elif descendant_type is NavigableString:
                yield descendant

    def ref_text(self, source_tag: Tag | None) -> RefText | None:
        """
        Parse text with ref tags.

        Args:
            source_tag : XML tag

        Returns:
            RefText object
        """
        if source_tag is not None:
            text_and_refs = self.__text_and_refs(source_tag)
            start = 0
            ref_text = RefText(text="")
            for el in text_and_refs:
                start = len(ref_text.text)
                if isinstance(el, Tag):
                    end = start + len(el.text)
                    ref = Ref(start=start, end=end)
                    if (el_type := el.attrs.get("type")) is not None:
                        ref.type_ = el_type

                    # NOTE: if target[0] is '#', check for citation
                    if (el_target := el.attrs.get("target")) is not None:
                        ref.target = el_target

                    ref_text.refs.append(ref)
                else:
                    ref_text.text += str(el)

            return ref_text

    @staticmethod
    def clean_title_string(s: str) -> str:
        """
        Remove non-alpha leading characters from string.

        Args:
            s : title string

        Returns:
            Clean title string
        """
        s = s.strip()

        while s and not s[0].isalpha():
            s = s[1:]

        return s.capitalize()
