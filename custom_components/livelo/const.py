"""Constantes da integração Livelo."""

from zoneinfo import ZoneInfo

DOMAIN = "livelo"

CONF_CATEGORIES = "categories"
CONF_PARTNERS = "partners"
CONF_NOTIFY = "notify_services"
CONF_NOTIFY_NEW = "notify_new_partners"
CONF_UPDATE_TIME = "update_time"

TZ = ZoneInfo("America/Sao_Paulo")
# Horário da verificação diária, no fuso do Home Assistant.
DEFAULT_UPDATE_TIME = "07:00:00"

PAGE_URL = "https://www.livelo.com.br/juntar-pontos/todos-os-parceiros"

# A página fica atrás do Akamai, que só aceita requisições HTTP/2 com cabeçalhos de navegador.
PAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

EVENT_PARTNER_CHANGED = f"{DOMAIN}_partner_changed"
EVENT_NEW_PARTNER = f"{DOMAIN}_new_partner"

STORAGE_VERSION = 1
