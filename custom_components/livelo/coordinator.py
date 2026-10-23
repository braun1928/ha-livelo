"""Busca diária da lista de parceiros Livelo, com notificações das mudanças."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Catalog, LiveloClient, LiveloError
from .const import (
    CONF_CATEGORIES,
    CONF_NOTIFY,
    CONF_NOTIFY_NEW,
    CONF_PARTNERS,
    DOMAIN,
    STORAGE_VERSION,
)
from .notifications import Notification, changed_partners, new_partners

_LOGGER = logging.getLogger(__name__)

type LiveloConfigEntry = ConfigEntry[LiveloCoordinator]


class LiveloCoordinator(DataUpdateCoordinator[Catalog]):
    """Busca a lista de parceiros e notifica o que mudou desde a busca anterior."""

    config_entry: LiveloConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LiveloConfigEntry, client: LiveloClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None)
        self.client = client
        # Snapshots dos parceiros na busca anterior, para as mudanças sobreviverem a reinícios.
        self._store = Store[dict[str, dict[str, Any]]](
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )

    def watched(self, catalog: Catalog | None = None) -> set[str]:
        """Códigos dos parceiros escolhidos mais todos os parceiros das categorias escolhidas."""
        catalog = catalog or self.data
        options = self.config_entry.options
        codes = set(options.get(CONF_PARTNERS, []))
        categories = set(options.get(CONF_CATEGORIES, []))
        if catalog and categories:
            codes |= {p.code for p in catalog.partners.values() if categories.intersection(p.categories)}
        return codes

    async def _async_update_data(self) -> Catalog:
        try:
            catalog = await self.client.fetch()
        except LiveloError as err:
            raise UpdateFailed(str(err)) from err
        previous = await self._store.async_load()
        if previous is not None:
            notifications = changed_partners(previous, catalog, self.watched(catalog))
            if self.config_entry.options.get(CONF_NOTIFY_NEW, True):
                notifications += new_partners(previous, catalog)
            for notification in notifications:
                await self._async_send(notification)
        await self._store.async_save({code: p.snapshot() for code, p in catalog.partners.items()})
        return catalog

    async def _async_send(self, notification: Notification) -> None:
        self.hass.bus.async_fire(notification.event, notification.event_data)
        # `url` abre o link no iOS/macOS; `clickAction`, no Android.
        data = {
            "title": notification.title,
            "message": notification.message,
            "data": {"url": notification.url, "clickAction": notification.url},
        }
        for service in self.config_entry.options.get(CONF_NOTIFY, []):
            try:
                await self.hass.services.async_call("notify", service, data, blocking=True)
            except HomeAssistantError as err:
                _LOGGER.warning("Cannot send Livelo notification via notify.%s: %s", service, err)
