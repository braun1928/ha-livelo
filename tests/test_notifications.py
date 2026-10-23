"""Textos das notificações e detecção de mudanças."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from livelo.api import Catalog, parse
from livelo.const import EVENT_NEW_PARTNER, EVENT_PARTNER_CHANGED
from livelo.notifications import (
    changed_partners,
    format_campaign,
    format_parity,
    new_partners,
    partner_parity,
)
import pytest

BRT = timezone(timedelta(hours=-3))


@pytest.fixture
def catalog(page: str) -> Catalog:
    return parse(page)


@pytest.fixture
def previous(catalog: Catalog) -> dict:
    """O snapshot salvo se nada tivesse mudado."""
    return {code: p.snapshot() for code, p in catalog.partners.items()}


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ((4, 6, True), "até 4 pts/R$ · Clube 6"),
        ((1, 1, False), "1 pt/R$ · Clube 1"),
        ((1.5, 2, False), "1,5 pts/R$ · Clube 2"),
        ((None, None, False), "? pts/R$ · Clube ?"),
        ((4, 4, False, "U$", 1), "4 pts/U$ · Clube 4"),
        ((2, 2, False, "R$", 5), "2 pts a cada R$ 5 · Clube 2"),
    ],
)
def test_format_parity(args: tuple, expected: str) -> None:
    assert format_parity(*args) == expected


def test_partner_parity(catalog: Catalog) -> None:
    assert partner_parity(catalog.partners["BOK"]) == "4 pts/U$ · Clube 4"
    assert partner_parity(catalog.partners["BAN"]) == "2 pts a cada R$ 5 · Clube 2"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (datetime(2026, 10, 23, tzinfo=BRT), datetime(2026, 10, 25, 23, 59, tzinfo=BRT), "Promoção de 23/10 a 25/10/2026"),
        (datetime(2026, 12, 30, tzinfo=BRT), datetime(2027, 1, 2, 23, 59, tzinfo=BRT), "Promoção de 30/12/2026 a 02/01/2027"),
        (None, datetime(2026, 10, 25, 23, 59, tzinfo=BRT), "Promoção até 25/10/2026"),
        (datetime(2026, 10, 23, tzinfo=BRT), None, None),
        (None, None, None),
    ],
)
def test_format_campaign(start: datetime | None, end: datetime | None, expected: str | None) -> None:
    assert format_campaign(start, end) == expected


def test_campaign_stays_in_brasilia_time() -> None:
    # 23:59 em Brasília é 02:59 UTC do dia seguinte; a data mostrada deve ser a da Livelo.
    end = datetime(2026, 10, 26, 2, 59, tzinfo=timezone.utc)
    assert format_campaign(None, end) == "Promoção até 25/10/2026"


def test_nothing_changed(catalog: Catalog, previous: dict) -> None:
    assert changed_partners(previous, catalog, catalog.partners) == []
    assert new_partners(previous, catalog) == []


def test_promotion_started(catalog: Catalog, previous: dict) -> None:
    previous["NTS"].update(parity=2, parity_club=2, up_to=False, promotion=False, start=None, end=None)
    [notification] = changed_partners(previous, catalog, {"NTS", "ABC"})
    assert notification.title == "Livelo: Netshoes"
    assert notification.message == (
        "até 4 pts/R$ · Clube 6 (antes 2 pts/R$ · Clube 2)\nPromoção de 23/10 a 25/10/2026"
    )
    assert notification.url == "https://livelo.com.br/juntar-pontos/parceiros/netshoes/NTS"
    assert notification.event == EVENT_PARTNER_CHANGED
    assert notification.event_data["code"] == "NTS"
    assert notification.event_data["old"]["parity"] == 2
    assert notification.event_data["new"]["parity"] == 4


def test_promotion_ended(catalog: Catalog, previous: dict) -> None:
    previous["ABC"].update(parity=5, parity_club=8, promotion=True)
    [notification] = changed_partners(previous, catalog, {"ABC"})
    assert notification.message == "1 pt/R$ · Clube 1 (antes 5 pts/R$ · Clube 8)\nPromoção encerrada"


def test_campaign_extended(catalog: Catalog, previous: dict) -> None:
    previous["NTS"]["end"] = "2026-10-24T23:59:00-03:00"
    [notification] = changed_partners(previous, catalog, {"NTS"})
    assert notification.message.endswith("Promoção de 23/10 a 25/10/2026")


def test_only_watched(catalog: Catalog, previous: dict) -> None:
    previous["NTS"]["parity"] = 2
    assert changed_partners(previous, catalog, {"ABC"}) == []


def test_rename_is_not_news(catalog: Catalog, previous: dict) -> None:
    previous["NTS"]["name"] = "Net Shoes"
    assert changed_partners(previous, catalog, {"NTS"}) == []


def test_snapshot_without_currency(catalog: Catalog, previous: dict) -> None:
    """Snapshots salvos antes da moeda existir não geram notificação nem quebram o texto."""
    for snapshot in previous.values():
        snapshot.pop("currency")
        snapshot.pop("currency_value")
    assert changed_partners(previous, catalog, catalog.partners) == []
    previous["BOK"]["parity"] = 2
    [notification] = changed_partners(previous, catalog, {"BOK"})
    assert notification.message == "4 pts/U$ · Clube 4 (antes 2 pts/U$ · Clube 4)"


def test_watched_but_unknown(catalog: Catalog, previous: dict) -> None:
    # Parceiro que saiu da página, ou que ainda não estava no snapshot anterior.
    del previous["NTS"]
    assert changed_partners(previous, catalog, {"NTS", "GONE"}) == []


def test_new_partner(catalog: Catalog, previous: dict) -> None:
    del previous["BBB"]
    [notification] = new_partners(previous, catalog)
    assert notification.title == "Livelo: novo parceiro"
    assert notification.message == (
        "Bibi: 1 pt/R$ · Clube 6\nPromoção de 22/10 a 31/10/2026\nInfantil, Calçados, Bebês"
    )
    assert notification.url == "https://livelo.com.br/juntar-pontos/parceiros/bibi-calcados/BBB"
    assert notification.event == EVENT_NEW_PARTNER


def test_new_partner_without_promotion(catalog: Catalog, previous: dict) -> None:
    del previous["BOK"]
    [notification] = new_partners(previous, catalog)
    assert notification.message == "Booking com: 4 pts/U$ · Clube 4\nHotéis"


def test_new_partner_unlisted_category(catalog: Catalog, previous: dict) -> None:
    # Categorias fora do filtro da página aparecem pelo código.
    del previous["DCR"]
    [notification] = new_partners(previous, catalog)
    assert notification.message.endswith("\npassagensaereas")


def test_promotion_without_dates(catalog: Catalog, previous: dict) -> None:
    catalog.partners["ABC"] = replace(catalog.partners["ABC"], promotion=True)
    [notification] = changed_partners(previous, catalog, {"ABC"})
    assert notification.message.endswith("\nEm promoção")
