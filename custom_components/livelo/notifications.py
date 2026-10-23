"""Textos e detecção de mudanças das notificações, sem depender do Home Assistant."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .api import Catalog, Partner
from .const import EVENT_NEW_PARTNER, EVENT_PARTNER_CHANGED, TZ

# Campos do snapshot cuja mudança é notificada (parceiro renomeado não é novidade).
TRACKED = ("parity", "parity_club", "up_to", "promotion", "start", "end")


@dataclass(frozen=True)
class Notification:
    """Uma notificação e o evento correspondente."""

    title: str
    message: str
    url: str
    event: str
    event_data: dict[str, Any] = field(default_factory=dict)


def _number(value: float | None) -> str:
    return "?" if value is None else f"{value:g}".replace(".", ",")


def per_currency(currency: str = "R$", currency_value: float = 1) -> str:
    """P. ex. "/R$", "/U$" ou " a cada R$ 5"."""
    return f"/{currency}" if currency_value == 1 else f" a cada {currency} {_number(currency_value)}"


def format_parity(
    parity: float | None,
    parity_club: float | None,
    up_to: bool,
    currency: str = "R$",
    currency_value: float = 1,
) -> str:
    """P. ex. "até 4 pts/R$ · Clube 6"."""
    prefix = "até " if up_to else ""
    unit = "pt" if parity == 1 else "pts"
    per = per_currency(currency, currency_value)
    return f"{prefix}{_number(parity)} {unit}{per} · Clube {_number(parity_club)}"


def partner_parity(partner: Partner) -> str:
    """`format_parity` com os dados atuais do parceiro."""
    return format_parity(
        partner.parity, partner.parity_club, partner.up_to, partner.currency, partner.currency_value
    )


def format_campaign(start: datetime | None, end: datetime | None) -> str | None:
    """P. ex. "Promoção de 23/10 a 25/10/2026"."""
    # As datas são da Livelo, então ficam no horário de Brasília: converter 23:59 para outro
    # fuso poderia mudar o dia.
    if start and end:
        start, end = start.astimezone(TZ), end.astimezone(TZ)
        first = f"{start:%d/%m}" if start.year == end.year else f"{start:%d/%m/%Y}"
        return f"Promoção de {first} a {end:%d/%m/%Y}"
    if end:
        return f"Promoção até {end.astimezone(TZ):%d/%m/%Y}"
    return None


def _change_message(partner: Partner, old: dict[str, Any]) -> str:
    # Snapshots antigos não têm a moeda; ela praticamente nunca muda.
    before = format_parity(
        old["parity"],
        old["parity_club"],
        old.get("up_to", False),
        old.get("currency", partner.currency),
        old.get("currency_value", partner.currency_value),
    )
    lines = [f"{partner_parity(partner)} (antes {before})"]
    if partner.promotion:
        lines.append(format_campaign(partner.start, partner.end) or "Em promoção")
    elif old["promotion"]:
        lines.append("Promoção encerrada")
    return "\n".join(lines)


def changed_partners(
    previous: dict[str, dict[str, Any]], catalog: Catalog, watched: Iterable[str]
) -> list[Notification]:
    """Notificações dos parceiros acompanhados cujos pontos ou campanha mudaram."""
    notifications = []
    for code in sorted(watched):
        partner, old = catalog.partners.get(code), previous.get(code)
        # Um parceiro que acabou de entrar numa categoria acompanhada não tem com o que comparar.
        if partner is None or old is None:
            continue
        new = partner.snapshot()
        if all(old.get(key) == new[key] for key in TRACKED):
            continue
        notifications.append(
            Notification(
                title=f"Livelo: {partner.name}",
                message=_change_message(partner, old),
                url=partner.url,
                event=EVENT_PARTNER_CHANGED,
                event_data={"code": code, "url": partner.url, "old": old, "new": new},
            )
        )
    return notifications


def new_partners(previous: dict[str, dict[str, Any]], catalog: Catalog) -> list[Notification]:
    """Notificações dos parceiros que não estavam na busca anterior."""
    labels = {c.value: c.text for c in catalog.categories}
    notifications = []
    for code in sorted(catalog.partners.keys() - previous.keys()):
        partner = catalog.partners[code]
        lines = [f"{partner.name}: {partner_parity(partner)}"]
        if partner.promotion:
            lines.append(format_campaign(partner.start, partner.end) or "Em promoção")
        if partner.categories:
            lines.append(", ".join(labels.get(c, c) for c in partner.categories))
        notifications.append(
            Notification(
                title="Livelo: novo parceiro",
                message="\n".join(lines),
                url=partner.url,
                event=EVENT_NEW_PARTNER,
                event_data={"code": code, "url": partner.url, "new": partner.snapshot()},
            )
        )
    return notifications
