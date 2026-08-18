"""Safe retrieval and compact parsing of public podcast RSS and Atom feeds."""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree


MAX_PODCAST_FEED_BYTES = 4 * 1024 * 1024
MAX_PODCAST_EPISODES = 300
FETCH_TIMEOUT_SECONDS = 20
USER_AGENT = "Poznamkovnik/1.0 podcast reader"


class PodcastFeedError(ValueError):
    """The feed cannot safely be fetched or interpreted as a podcast."""


@dataclass(frozen=True)
class PodcastEpisode:
    external_id: str
    title: str
    description: str
    media_url: str
    media_type: str
    published_at: str
    duration_seconds: int
    image_url: str
    position: int


@dataclass(frozen=True)
class PodcastFeed:
    feed_url: str
    title: str
    website_url: str
    description: str
    image_url: str
    episodes: list[PodcastEpisode]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request: Request, fp: Any, code: int, message: str, headers: Any, newurl: str) -> Request | None:
        validate_public_url(newurl, "Presmerovanie podcastu", resolve_host=True)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def validate_public_url(value: Any, label: str, *, resolve_host: bool = False) -> str:
    url = str(value or "").strip()[:2_000]
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise PodcastFeedError(f"{label} musí mať platnú verejnú adresu http alebo https.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise PodcastFeedError(f"{label} nesmie smerovať na lokálnu adresu.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None:
        _assert_public_address(address, label)
        return url
    if resolve_host:
        try:
            addresses = {result[4][0] for result in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
        except OSError as error:
            raise PodcastFeedError(f"Hostiteľa podcastu sa nepodarilo nájsť: {hostname}.") from error
        if not addresses:
            raise PodcastFeedError(f"Hostiteľa podcastu sa nepodarilo nájsť: {hostname}.")
        for raw_address in addresses:
            _assert_public_address(ipaddress.ip_address(raw_address), label)
    return url


def fetch_podcast_feed(value: Any) -> PodcastFeed:
    feed_url = validate_public_url(value, "Adresa podcastu", resolve_host=True)
    request = Request(feed_url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with build_opener(_SafeRedirectHandler()).open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            final_url = validate_public_url(response.geturl(), "Adresa podcastu", resolve_host=True)
            payload = response.read(MAX_PODCAST_FEED_BYTES + 1)
    except HTTPError as error:
        raise PodcastFeedError(f"Podcast sa nepodarilo načítať (HTTP {error.code}).") from error
    except (URLError, TimeoutError, OSError) as error:
        raise PodcastFeedError("Podcast sa nepodarilo načítať. Skontroluj adresu feedu a pripojenie.") from error
    if len(payload) > MAX_PODCAST_FEED_BYTES:
        raise PodcastFeedError("Feed podcastu je príliš veľký.")
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise PodcastFeedError("Adresa neobsahuje platný RSS alebo Atom feed.") from error
    if _local_name(root.tag) == "feed":
        return _parse_atom(root, final_url)
    channel = _first_child(root, "channel") if _local_name(root.tag) == "rss" else None
    if channel is None:
        raise PodcastFeedError("Feed nemá podporovanú štruktúru RSS alebo Atom.")
    return _parse_rss(channel, final_url)


def _assert_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address, label: str) -> None:
    if not address.is_global:
        raise PodcastFeedError(f"{label} nesmie smerovať na súkromnú alebo lokálnu sieť.")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_child(element: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((child for child in element if _local_name(child.tag) == name), None)


def _children(element: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _text(element: ElementTree.Element | None, limit: int = 10_000) -> str:
    if element is None:
        return ""
    raw = " ".join(part for part in element.itertext() if part)
    parser = _TextExtractor()
    try:
        parser.feed(unescape(raw))
        raw = " ".join(parser.parts)
    except Exception:
        pass
    return " ".join(raw.split())[:limit]


def _child_text(element: ElementTree.Element, *names: str, limit: int = 10_000) -> str:
    for name in names:
        value = _text(_first_child(element, name), limit)
        if value:
            return value
    return ""


def _safe_external_url(value: str, base_url: str) -> str:
    if not value:
        return ""
    try:
        return validate_public_url(urljoin(base_url, value), "Adresa v podcaste")
    except PodcastFeedError:
        return ""


def _rss_link(element: ElementTree.Element, base_url: str) -> str:
    return _safe_external_url(_child_text(element, "link", limit=2_000), base_url)


def _atom_link(element: ElementTree.Element, base_url: str, relation: str = "alternate") -> str:
    for link in _children(element, "link"):
        if link.attrib.get("rel", "alternate").lower() == relation and link.attrib.get("href"):
            return _safe_external_url(link.attrib["href"], base_url)
    return ""


def _image_url(element: ElementTree.Element, base_url: str) -> str:
    for child in element.iter():
        if _local_name(child.tag) != "image":
            continue
        candidate = child.attrib.get("href") or child.attrib.get("url") or _child_text(child, "url", limit=2_000)
        url = _safe_external_url(candidate, base_url)
        if url:
            return url
    return ""


def _duration_seconds(value: str) -> int:
    raw = value.strip()
    if not raw:
        return 0
    if raw.isdigit():
        return min(172_800, int(raw))
    parts = raw.split(":")
    if not all(part.isdigit() for part in parts) or len(parts) not in {2, 3}:
        return 0
    numbers = [int(part) for part in parts]
    seconds = numbers[-1] + numbers[-2] * 60 + (numbers[0] * 3600 if len(numbers) == 3 else 0)
    return min(172_800, seconds)


def _published_at(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    try:
        if "," in raw:
            parsed = parsedate_to_datetime(raw)
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, IndexError):
        return raw[:64]


def _episode_identifier(value: str, media_url: str, position: int) -> str:
    source = value.strip() or media_url or str(position)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:48]


def _parse_rss(channel: ElementTree.Element, feed_url: str) -> PodcastFeed:
    title = _child_text(channel, "title", limit=240) or urlsplit(feed_url).hostname or "Podcast"
    description = _child_text(channel, "description", "summary", "subtitle", limit=10_000)
    image_url = _image_url(channel, feed_url)
    episodes: list[PodcastEpisode] = []
    for position, item in enumerate(_children(channel, "item")):
        enclosure = _first_child(item, "enclosure")
        media_url = _safe_external_url(enclosure.attrib.get("url", "") if enclosure is not None else "", feed_url)
        if not media_url:
            continue
        item_title = _child_text(item, "title", limit=400) or "Bez názvu"
        external_id = _episode_identifier(_child_text(item, "guid", "id", limit=2_000), media_url, position)
        episodes.append(PodcastEpisode(
            external_id=external_id,
            title=item_title,
            description=_child_text(item, "description", "summary", "encoded", limit=20_000),
            media_url=media_url,
            media_type=(enclosure.attrib.get("type", "") if enclosure is not None else "")[:160],
            published_at=_published_at(_child_text(item, "pubdate", "published", "updated", limit=160)),
            duration_seconds=_duration_seconds(_child_text(item, "duration", limit=80)),
            image_url=_image_url(item, feed_url) or image_url,
            position=position,
        ))
        if len(episodes) >= MAX_PODCAST_EPISODES:
            break
    return PodcastFeed(feed_url, title, _rss_link(channel, feed_url), description, image_url, episodes)


def _parse_atom(root: ElementTree.Element, feed_url: str) -> PodcastFeed:
    title = _child_text(root, "title", limit=240) or urlsplit(feed_url).hostname or "Podcast"
    description = _child_text(root, "subtitle", "summary", limit=10_000)
    image_url = _image_url(root, feed_url)
    episodes: list[PodcastEpisode] = []
    for position, item in enumerate(_children(root, "entry")):
        media_url = _atom_link(item, feed_url, "enclosure")
        if not media_url:
            continue
        enclosure = next((link for link in _children(item, "link") if link.attrib.get("rel", "").lower() == "enclosure"), None)
        item_title = _child_text(item, "title", limit=400) or "Bez názvu"
        external_id = _episode_identifier(_child_text(item, "id", limit=2_000), media_url, position)
        episodes.append(PodcastEpisode(
            external_id=external_id,
            title=item_title,
            description=_child_text(item, "summary", "content", limit=20_000),
            media_url=media_url,
            media_type=(enclosure.attrib.get("type", "") if enclosure is not None else "")[:160],
            published_at=_published_at(_child_text(item, "published", "updated", limit=160)),
            duration_seconds=0,
            image_url=_image_url(item, feed_url) or image_url,
            position=position,
        ))
        if len(episodes) >= MAX_PODCAST_EPISODES:
            break
    return PodcastFeed(feed_url, title, _atom_link(root, feed_url), description, image_url, episodes)
