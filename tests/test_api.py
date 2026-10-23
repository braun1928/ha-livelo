"""Leitura da página de parceiros."""

from datetime import datetime, timedelta, timezone

from livelo.api import LiveloError, parse
import pytest

BRT = timezone(timedelta(hours=-3))


def test_full_list_not_carousel(page: str) -> None:
    catalog = parse(page)
    # O carrossel de destaques (QPV, BHP) é a lista menor e deve ser ignorado.
    assert set(catalog.partners) == {"ABC", "AGX", "BAN", "BBB", "BOK", "DCR", "LVM", "NTS", "XXX"}


def test_categories(page: str) -> None:
    categories = parse(page).categories
    assert len(categories) == 30
    assert "todos" not in {c.value for c in categories}
    assert categories[0].value == "alimentosebebidas"
    assert categories[0].text == "Alimentos e Bebidas"


def test_partner(page: str) -> None:
    nts = parse(page).partners["NTS"]
    assert nts.name == "Netshoes"
    assert nts.url == "https://livelo.com.br/juntar-pontos/parceiros/netshoes/NTS"
    assert (nts.parity, nts.parity_club) == (4, 6)
    assert (nts.currency, nts.currency_value) == ("R$", 1)
    assert nts.up_to
    assert nts.promotion
    assert nts.campaign == "PROMOTION_CLUB"
    assert nts.start == datetime(2026, 10, 23, 0, 0, tzinfo=BRT)
    assert nts.end == datetime(2026, 10, 25, 23, 59, tzinfo=BRT)
    assert "todos" not in nts.categories
    assert "calcados" in nts.categories
    assert "<" not in nts.terms


def test_relative_url(page: str) -> None:
    assert parse(page).partners["LVM"].url == (
        "https://www.livelo.com.br/ganhe-pontos-compre-pontue-partner/ligavitoria/LVC"
    )


def test_currency(page: str) -> None:
    partners = parse(page).partners
    assert (partners["BOK"].currency, partners["BOK"].currency_value) == ("U$", 1)
    assert (partners["BAN"].currency, partners["BAN"].currency_value) == ("R$", 5)


def test_without_promotion(page: str) -> None:
    abc = parse(page).partners["ABC"]
    assert not abc.up_to
    assert not abc.promotion
    assert abc.start is None and abc.end is None


def test_without_parity(page: str) -> None:
    xxx = parse(page).partners["XXX"]
    assert xxx.parity is None and xxx.parity_club is None
    assert not xxx.promotion
    assert xxx.terms == ""


def test_snapshot_is_json(page: str) -> None:
    snapshot = parse(page).partners["NTS"].snapshot()
    assert snapshot["start"] == "2026-10-23T00:00:00-03:00"
    assert snapshot["currency"] == "R$"


@pytest.mark.parametrize(
    "page",
    [
        "<html></html>",
        '<script id="__NEXT_DATA__">not json</script>',
        '<script id="__NEXT_DATA__">{"props": {}}</script>',
        '<script id="__NEXT_DATA__">{"props": {"pageProps": {"page": {"components": []}}}}</script>',
    ],
)
def test_unexpected_page(page: str) -> None:
    with pytest.raises(LiveloError):
        parse(page)
