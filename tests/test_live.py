"""Verificação da página real; roda só com `pytest -m live` (semanal no GitHub Actions).

Detecta cedo quando a Livelo muda a página ou o Akamai passa a bloquear a requisição.
"""

import asyncio

import httpx
from livelo.api import LiveloClient
import pytest

pytestmark = pytest.mark.live


def test_live_page() -> None:
    async def fetch():
        async with httpx.AsyncClient(http2=True) as client:
            return await LiveloClient(client).fetch()

    catalog = asyncio.run(fetch())
    assert len(catalog.categories) >= 10
    assert len(catalog.partners) >= 100
    priced = [p for p in catalog.partners.values() if p.parity is not None]
    assert len(priced) >= 0.9 * len(catalog.partners)
    assert all(p.name and p.url.startswith("https://") for p in catalog.partners.values())
    promotions = [p for p in priced if p.promotion]
    # Todas as promoções vistas até hoje têm datas; se muitas deixarem de ter, a página mudou.
    assert sum(1 for p in promotions if p.start and p.end) >= 0.8 * len(promotions)
