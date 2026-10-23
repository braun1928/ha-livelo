"""Torna os módulos da integração importáveis como `livelo.*` sem o Home Assistant.

O `__init__.py` da integração importa o Home Assistant; os módulos testados aqui (`api`,
`const`, `notifications`) não, então registramos o pacote sem executar o `__init__.py`.
"""

from pathlib import Path
import sys
import types

import pytest

PACKAGE = Path(__file__).parents[1] / "custom_components" / "livelo"
FIXTURE = Path(__file__).parent / "fixtures" / "todos-os-parceiros.html"

package = types.ModuleType("livelo")
package.__path__ = [str(PACKAGE)]
sys.modules.setdefault("livelo", package)


@pytest.fixture(scope="session")
def page() -> str:
    """Recorte da página de parceiros, gerado por scripts/update_fixture.py."""
    return FIXTURE.read_text(encoding="utf-8")
