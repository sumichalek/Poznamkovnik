from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


LOOKUP_TIMEOUT_SECONDS = 8
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(?:17|18|19|20|21)\d{2}")


class BibliographyLookupError(ValueError):
    """Raised when a public metadata service cannot resolve an identifier."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _clean_text(value: Any, maximum: int = 2_000) -> str:
    return " ".join(str(value or "").split()).strip()[:maximum]


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, dict):
            return _clean_text(first.get("title") or first.get("name") or first.get("value"))
        return _clean_text(first)
    if isinstance(value, dict):
        return _clean_text(value.get("title") or value.get("name") or value.get("value"))
    return _clean_text(value)


def _year(value: Any) -> str:
    if isinstance(value, list) and value and isinstance(value[0], list) and value[0]:
        return _clean_text(value[0][0], 12)
    match = YEAR_PATTERN.search(_clean_text(value, 80))
    return match.group(0) if match else ""


def _creator_name(creator: Any) -> str:
    if not isinstance(creator, dict):
        return ""
    literal = _clean_text(creator.get("name"))
    if literal:
        return literal
    return " ".join(part for part in (_clean_text(creator.get("given")), _clean_text(creator.get("family"))) if part)


def _creator_names(creators: Any) -> str:
    if not isinstance(creators, list):
        return ""
    return "; ".join(name for name in (_creator_name(creator) for creator in creators) if name)[:1_200]


def _kind(value: Any) -> str:
    text = _clean_text(value).casefold()
    if any(token in text for token in ("journal-article", "article", "proceedings-article")):
        return "article"
    if "book" in text or "monograph" in text:
        return "book"
    if "dataset" in text or "data" in text:
        return "dataset"
    if "web" in text:
        return "web"
    return "source"


def _isbn_is_valid(value: str) -> bool:
    if len(value) == 13 and value.isdigit():
        return sum((1 if index % 2 == 0 else 3) * int(digit) for index, digit in enumerate(value)) % 10 == 0
    if len(value) == 10 and re.fullmatch(r"\d{9}[\dX]", value):
        return sum((10 - index) * (10 if digit == "X" else int(digit)) for index, digit in enumerate(value)) % 11 == 0
    return False


def detect_identifier(value: Any) -> dict[str, str]:
    raw = _clean_text(value, 600)
    if not raw:
        raise BibliographyLookupError("Zadaj DOI alebo ISBN.")

    doi = raw
    if doi.casefold().startswith("doi:"):
        doi = doi[4:].strip()
    parsed = urlsplit(doi)
    if parsed.scheme and parsed.netloc.casefold() in {"doi.org", "www.doi.org", "dx.doi.org"}:
        doi = unquote(parsed.path.lstrip("/"))
    doi = doi.strip().rstrip(".,;")
    if DOI_PATTERN.fullmatch(doi):
        return {"type": "doi", "value": doi.casefold()}

    isbn = re.sub(r"[^0-9Xx]", "", raw).upper()
    if _isbn_is_valid(isbn):
        return {"type": "isbn", "value": isbn}
    raise BibliographyLookupError("Nevidím platný DOI ani ISBN. Skontroluj jeho zápis.")


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Poznamkovnik bibliograficke-udaje/1.0"
        },
    )
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=LOOKUP_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise BibliographyLookupError("Služba metadát neodpovedala úspešne.")
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            raise BibliographyLookupError("Pre tento identifikátor sa nenašli verejné údaje.") from error
        raise BibliographyLookupError("Služba metadát je dočasne nedostupná.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise BibliographyLookupError("Služba metadát je dočasne nedostupná.") from error
    if not isinstance(payload, dict):
        raise BibliographyLookupError("Služba metadát vrátila neplatnú odpoveď.")
    return payload


def _proposal(provider: str, identifier: dict[str, str], title: Any, kind: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: _clean_text(value) for key, value in metadata.items() if _clean_text(value)}
    if identifier["type"] == "doi":
        cleaned["doi"] = identifier["value"]
    else:
        cleaned["isbn"] = identifier["value"]
    return {
        "provider": provider,
        "identifier": identifier,
        "proposal": {
            "title": _clean_text(title, 240),
            "kind": _kind(kind),
            "metadata": cleaned,
        },
        "retrievedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _from_crossref(identifier: dict[str, str]) -> dict[str, Any]:
    payload = _fetch_json(f"https://api.crossref.org/works/{quote(identifier['value'], safe='')}")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise BibliographyLookupError("Crossref neposkytol použiteľné údaje.")
    dates = message.get("published-print") or message.get("published-online") or message.get("issued") or {}
    date_parts = dates.get("date-parts") if isinstance(dates, dict) else []
    return _proposal(
        "Crossref",
        identifier,
        _first_text(message.get("title")),
        message.get("type"),
        {
            "author": _creator_names(message.get("author")),
            "year": _year(date_parts),
            "url": message.get("URL"),
            "publisher": message.get("publisher"),
            "publicationTitle": _first_text(message.get("container-title")),
            "volume": message.get("volume"),
            "issue": message.get("issue"),
            "pages": message.get("page"),
            "language": message.get("language"),
        },
    )


def _from_datacite(identifier: dict[str, str]) -> dict[str, Any]:
    payload = _fetch_json(f"https://api.datacite.org/dois/{quote(identifier['value'], safe='')}")
    attributes = payload.get("data", {}).get("attributes") if isinstance(payload.get("data"), dict) else None
    if not isinstance(attributes, dict):
        raise BibliographyLookupError("DataCite neposkytol použiteľné údaje.")
    container = attributes.get("container") if isinstance(attributes.get("container"), dict) else {}
    types = attributes.get("types") if isinstance(attributes.get("types"), dict) else {}
    return _proposal(
        "DataCite",
        identifier,
        _first_text(attributes.get("titles")),
        types.get("resourceTypeGeneral"),
        {
            "author": _creator_names(attributes.get("creators")),
            "year": attributes.get("publicationYear"),
            "url": attributes.get("url"),
            "publisher": attributes.get("publisher"),
            "publicationTitle": container.get("title"),
            "volume": container.get("volume"),
            "issue": container.get("issue"),
            "pages": "-".join(part for part in (str(container.get("firstPage") or ""), str(container.get("lastPage") or "")) if part),
            "language": attributes.get("language"),
        },
    )


def _from_open_library(identifier: dict[str, str]) -> dict[str, Any]:
    isbn = identifier["value"]
    payload = _fetch_json(
        f"https://openlibrary.org/api/books?bibkeys=ISBN:{quote(isbn, safe='')}&format=json&jscmd=data"
    )
    record = payload.get(f"ISBN:{isbn}")
    if not isinstance(record, dict):
        raise BibliographyLookupError("Pre tento ISBN sa nenašli verejné údaje.")
    return _proposal(
        "Open Library",
        identifier,
        record.get("title"),
        "book",
        {
            "author": _creator_names(record.get("authors")),
            "year": _year(record.get("publish_date")),
            "url": record.get("url") or f"https://openlibrary.org/isbn/{isbn}",
            "publisher": _first_text(record.get("publishers")),
            "pages": record.get("number_of_pages"),
        },
    )


def lookup_bibliographic_metadata(value: Any) -> dict[str, Any]:
    identifier = detect_identifier(value)
    if identifier["type"] == "isbn":
        return _from_open_library(identifier)

    try:
        return _from_crossref(identifier)
    except BibliographyLookupError as crossref_error:
        try:
            return _from_datacite(identifier)
        except BibliographyLookupError:
            raise crossref_error
