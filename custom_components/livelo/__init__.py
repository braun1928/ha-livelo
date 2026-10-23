"""Parceiros Livelo: pontos por real, com notificações quando mudam."""

from __future__ import annotations

from datetime import datetime, time

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util.ssl import SSL_ALPN_HTTP11_HTTP2

from .api import LiveloClient
from .const import CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME, DOMAIN
from .coordinator import LiveloConfigEntry, LiveloCoordinator

PLATFORMS = [Platform.SENSOR]


def create_client(hass: HomeAssistant) -> LiveloClient:
    """Retorna um cliente; o Akamai rejeita HTTP/1.1, então ele precisa falar HTTP/2."""
    return LiveloClient(get_async_client(hass, alpn_protocols=SSL_ALPN_HTTP11_HTTP2))


async def async_setup_entry(hass: HomeAssistant, entry: LiveloConfigEntry) -> bool:
    """Configura a Livelo a partir de uma config entry."""
    coordinator = LiveloCoordinator(hass, entry, create_client(hass))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    @callback
    def _daily(_now: datetime) -> None:
        entry.async_create_background_task(hass, coordinator.async_refresh(), f"{DOMAIN}_daily")

    # No fuso horário configurado no Home Assistant.
    at = time.fromisoformat(entry.options.get(CONF_UPDATE_TIME, DEFAULT_UPDATE_TIME))
    entry.async_on_unload(
        async_track_time_change(hass, _daily, hour=at.hour, minute=at.minute, second=0)
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LiveloConfigEntry) -> bool:
    """Descarrega uma config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: LiveloConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
