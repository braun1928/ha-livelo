# Livelo para Home Assistant

Acompanha os pontos por real dos [parceiros Livelo](https://www.livelo.com.br/juntar-pontos/todos-os-parceiros)
e notifica quando eles mudam.

- Escolha parceiros individualmente e/ou por categoria (o filtro de categorias da página) nas
  opções da integração. Uma categoria inclui os parceiros que entrarem nela depois.
- Verifica diariamente no horário escolhido nas opções (no fuso do Home Assistant; padrão
  07:00), e também quando o Home Assistant inicia ou as opções mudam, comparando com a
  verificação anterior, que é mantida entre reinícios.
- Notifica pelas ações `notify` escolhidas (p. ex. o app Home Assistant) quando os pontos, os
  pontos do Clube ou a campanha de um parceiro acompanhado mudam e, opcionalmente, quando
  qualquer parceiro novo entra na Livelo. As notificações trazem as datas da campanha e abrem a
  página do parceiro ao serem tocadas.
- Também dispara os eventos `livelo_partner_changed` e `livelo_new_partner` (`code`, `url`,
  `old`, `new`) para suas próprias automações.

## Entidades

- `sensor.livelo_<parceiro>`: pontos por real para quem não é do Clube (alguns parceiros pontuam
  por dólar, `pts/U$`, ou a cada R$ 5), com o logo do parceiro como imagem. Atributos:
  `parity_club`, `currency`/`currency_value`, `up_to` ("até": o máximo, p. ex. em produtos
  selecionados), `summary`, `promotion`, `campaign_start`/`campaign_end`, `campaign_text`,
  `terms`, `categories`, `url`.
- `sensor.livelo_promotions`: quantos parceiros acompanhados estão em promoção, com a lista no
  atributo `partners`.

## Instalação

Pelo HACS: adicione `https://github.com/braun1928/ha-livelo` como repositório personalizado
(tipo Integration) e instale a Livelo. Ou copie `custom_components/livelo` para
`config/custom_components/` do Home Assistant. Reinicie e vá em Configurações → Dispositivos e
serviços → Adicionar integração → Livelo.

## Widget (iPhone/Mac)

No app Home Assistant, adicione um widget **Detalhes** (ele renderiza templates), p. ex.:

```jinja
{% for p in state_attr('sensor.livelo_promotions', 'partners') -%}
{{ p.name }}: {{ p.summary }}
{% endfor %}
```

## Como funciona

A lista de parceiros, as categorias e as datas das campanhas vêm dos dados Next.js embutidos na
página de parceiros. A página fica atrás do Akamai, que só aceita requisições HTTP/2 com
cabeçalhos de navegador, então a integração usa o cliente httpx HTTP/2 do Home Assistant.
Não oficial: pode quebrar se a Livelo mudar a página.

## Desenvolvimento

```sh
pip install -r requirements_test.txt
pytest            # testes com um recorte salvo da página (tests/fixtures)
pytest -m live    # lê a página real
```

O GitHub Actions roda o hassfest, a validação do HACS e os testes a cada push e
semanalmente, e o `pytest -m live` toda segunda-feira, para avisar quando a Livelo mudar a
página. Quando isso acontecer, atualize o recorte com `python scripts/update_fixture.py` e
ajuste os testes.
