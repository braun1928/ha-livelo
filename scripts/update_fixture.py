#!/usr/bin/env python3
"""Gera tests/fixtures/todos-os-parceiros.html a partir da página atual.

Mantém só os dados que a integração lê (parceiros e categorias) e um parceiro de cada caso
coberto pelos testes. Depois de rodar, ajuste os testes se os valores desses parceiros
tiverem mudado.

Uso: python scripts/update_fixture.py   (requer httpx[http2])
"""

import json
from pathlib import Path
import re
import sys
import types

import httpx

ROOT = Path(__file__).parents[1]
package = types.ModuleType("livelo")
package.__path__ = [str(ROOT / "custom_components" / "livelo")]
sys.modules["livelo"] = package

from livelo.const import PAGE_HEADERS, PAGE_URL  # noqa: E402

# NTS: "até" e promoção do Clube; BOK: pontos por U$; BAN: pontos a cada R$ 5; ABC: sem
# promoção; BBB: promoção só para o Clube; DCR: datas sem promoção; AGX: promoção;
# XXX: sem paridade; LVM: link relativo.
KEEP = ["NTS", "BOK", "BAN", "ABC", "BBB", "DCR", "AGX", "XXX", "LVM"]
# Parceiros do carrossel de destaques, que deve ser ignorado por ser a lista menor.
CAROUSEL = 2

response = httpx.Client(http2=True).get(PAGE_URL, headers=PAGE_HEADERS, timeout=60)
response.raise_for_status()
data = json.loads(
    re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.S).group(1)
)

components = []
for component in data["props"]["pageProps"]["page"]["components"]:
    props = component.get("props") if isinstance(component, dict) else None
    if not isinstance(props, dict) or not props.get("configPartners"):
        continue
    partners = props["configPartners"]
    if "searchPartner" in props:
        kept = [p for p in partners if p["id"] in KEEP]
        missing = set(KEEP) - {p["id"] for p in kept}
        if missing:
            sys.exit(f"Parceiros fora da página: {sorted(missing)}; atualize KEEP")
        trimmed = {
            "configPartners": kept,
            "searchPartner": {"categories": props["searchPartner"]["categories"]},
        }
    else:
        trimmed = {"configPartners": partners[:CAROUSEL]}
    components.append({"props": trimmed})

page = {"props": {"pageProps": {"page": {"components": components}}}}
html = (
    "<!DOCTYPE html><html><body>"
    f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(page, ensure_ascii=False)}</script>'
    "</body></html>\n"
)
(ROOT / "tests" / "fixtures" / "todos-os-parceiros.html").write_text(html, encoding="utf-8")
print(f"{len(html)} bytes, {len(components)} componentes")
