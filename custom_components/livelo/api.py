"""Cliente da lista de parceiros Livelo (www.livelo.com.br/juntar-pontos/todos-os-parceiros)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from .const import PAGE_HEADERS, PAGE_URL

NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
# "2026-10-22-00:00:00 GMT-03:00"
CAMPAIGN_DATE = re.compile(r"(\d{4})-(\d\d)-(\d\d)-(\d\d):(\d\d):(\d\d) GMT([+-])(\d\d):(\d\d)")
TAG = re.compile(r"<[^>]+>")


class LiveloError(Exception):
    """Não foi possível obter ou interpretar a lista de parceiros."""


@dataclass(frozen=True)
class Category:
    """Uma categoria do filtro de categorias da página."""

    value: str
    text: str


@dataclass(frozen=True)
class Partner:
    """Um parceiro e seus pontos por real atuais."""

    code: str
    name: str
    url: str
    image: str | None
    categories: tuple[str, ...]
    parity: float | None
    parity_club: float | None
    # Os pontos são por `currency_value` em `currency`: "R$" 1, mas também "U$" 1 ou "R$" 5.
    currency: str
    currency_value: float
    # "até N pontos": a paridade é o máximo, p. ex. só em produtos selecionados.
    up_to: bool
    promotion: bool
    campaign: str | None
    start: datetime | None
    end: datetime | None
    terms: str

    def snapshot(self) -> dict[str, Any]:
        """Os campos cuja mudança é notificada, serializáveis em JSON."""
        return {
            "name": self.name,
            "parity": self.parity,
            "parity_club": self.parity_club,
            "currency": self.currency,
            "currency_value": self.currency_value,
            "up_to": self.up_to,
            "promotion": self.promotion,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }


@dataclass(frozen=True)
class Catalog:
    """Todos os parceiros da página, por código, e as opções do filtro de categorias."""

    categories: list[Category]
    partners: dict[str, Partner]


def _parse_date(value: str | None) -> datetime | None:
    match = CAMPAIGN_DATE.fullmatch(value.strip()) if value else None
    if not match:
        return None
    y, mo, d, h, mi, s, sign, oh, om = match.groups()
    offset = timedelta(hours=int(oh), minutes=int(om)) * (-1 if sign == "-" else 1)
    return datetime(int(y), int(mo), int(d), int(h), int(mi), int(s), tzinfo=timezone(offset))


def _clean_terms(value: str | None) -> str:
    return " ".join(html.unescape(TAG.sub(" ", value or "")).split())


def _partner(raw: dict[str, Any]) -> Partner:
    parity = raw.get("parity") or {}
    return Partner(
        code=raw["id"],
        name=raw["name"].strip(),
        # Alguns links são relativos, como "/ganhe-pontos-compre-pontue-partner/...".
        url=urljoin(PAGE_URL, raw.get("partnerDetailsPage") or raw.get("link") or ""),
        image=raw.get("image"),
        categories=tuple(c for c in (raw.get("categories") or "").split() if c != "todos"),
        parity=parity.get("parity"),
        parity_club=parity.get("parityClub"),
        currency=parity.get("currency") or "R$",
        currency_value=parity.get("currencyValue") or 1,
        up_to=parity.get("separatorSlug") == "ATE",
        promotion=bool(parity.get("promotion")),
        campaign=parity.get("activeCampaign"),
        start=_parse_date(parity.get("dateStart")),
        end=_parse_date(parity.get("dateEnd")),
        terms=_clean_terms(parity.get("legalTerms")),
    )


def parse(page: str) -> Catalog:
    """Extrai os parceiros e as categorias dos dados Next.js da página."""
    match = NEXT_DATA.search(page)
    if not match:
        raise LiveloError("Page has no __NEXT_DATA__")
    try:
        components = json.loads(match.group(1))["props"]["pageProps"]["page"]["components"]
        props = [c["props"] for c in components if isinstance(c, dict) and isinstance(c.get("props"), dict)]
        # A página tem um carrossel de parceiros em destaque e a lista completa; queremos a completa.
        partner_lists = [p["configPartners"] for p in props if p.get("configPartners")]
        raw_partners = max(partner_lists, key=len)
        raw_categories = next(
            p["searchPartner"]["categories"] for p in props if isinstance(p.get("searchPartner"), dict)
        )
        partners = {raw["id"]: _partner(raw) for raw in raw_partners}
    except (ValueError, KeyError, TypeError, StopIteration) as err:
        raise LiveloError(f"Unexpected page structure: {err!r}") from err
    categories = [
        Category(c["value"], c["text"].strip()) for c in raw_categories if c.get("value") != "todos"
    ]
    return Catalog(categories, partners)


class LiveloClient:
    """Baixa e interpreta a página de parceiros."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def fetch(self) -> Catalog:
        """Retorna a lista de parceiros atual."""
        try:
            response = await self._client.get(PAGE_URL, headers=PAGE_HEADERS, timeout=60)
        except httpx.HTTPError as err:
            raise LiveloError(f"Cannot reach {PAGE_URL}: {err!r}") from err
        if response.status_code != 200:
            raise LiveloError(f"{PAGE_URL} returned HTTP {response.status_code}")
        return parse(response.text)
