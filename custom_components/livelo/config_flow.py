"""Config flow da integração Livelo."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)

from . import create_client
from .api import Catalog, LiveloError
from .const import (
    CONF_CATEGORIES,
    CONF_NOTIFY,
    CONF_NOTIFY_NEW,
    CONF_PARTNERS,
    CONF_UPDATE_TIME,
    DEFAULT_UPDATE_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_catalog(hass: HomeAssistant) -> Catalog:
    """A lista de parceiros da entry carregada, ou uma busca nova."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.runtime_data.data:
            return entry.runtime_data.data
    return await create_client(hass).fetch()


def _multi_select(options: list[SelectOptionDict]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN)
    )


def _schema(hass: HomeAssistant, catalog: Catalog, current: dict[str, Any]) -> vol.Schema:
    categories = {c.value: c.text for c in catalog.categories}
    partners = {code: f"{p.name} ({code})" for code, p in catalog.partners.items()}
    # Mantém selecionáveis as escolhas que saíram da página, senão salvar falharia na validação.
    for value in current.get(CONF_CATEGORIES, []):
        categories.setdefault(value, value)
    for code in current.get(CONF_PARTNERS, []):
        partners.setdefault(code, code)
    # `send_message` é a ação baseada em entidades, que não aceita título nem link.
    services = sorted(
        {s for s in hass.services.async_services_for_domain("notify") if s != "send_message"}
        | set(current.get(CONF_NOTIFY, []))
    )
    return vol.Schema(
        {
            vol.Optional(CONF_CATEGORIES, default=[]): _multi_select(
                [
                    SelectOptionDict(value=v, label=label)
                    for v, label in sorted(categories.items(), key=lambda kv: kv[1].lower())
                ]
            ),
            vol.Optional(CONF_PARTNERS, default=[]): _multi_select(
                [
                    SelectOptionDict(value=v, label=label)
                    for v, label in sorted(partners.items(), key=lambda kv: kv[1].lower())
                ]
            ),
            vol.Optional(CONF_NOTIFY, default=[]): _multi_select(
                [SelectOptionDict(value=s, label=f"notify.{s}") for s in services]
            ),
            vol.Optional(CONF_NOTIFY_NEW, default=True): BooleanSelector(),
            vol.Optional(CONF_UPDATE_TIME, default=DEFAULT_UPDATE_TIME): TimeSelector(),
        }
    )


class LiveloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow da Livelo."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Escolhe os parceiros, as categorias e os destinos das notificações."""
        if user_input is not None:
            return self.async_create_entry(title="Livelo", data={}, options=user_input)
        try:
            catalog = await _async_catalog(self.hass)
        except LiveloError:
            _LOGGER.exception("Cannot fetch the Livelo partner list")
            return self.async_abort(reason="cannot_connect")
        return self.async_show_form(step_id="user", data_schema=_schema(self.hass, catalog, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Retorna o options flow."""
        return LiveloOptionsFlow()


class LiveloOptionsFlow(OptionsFlow):
    """Altera os parceiros, as categorias e os destinos das notificações."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Gerencia as opções."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        try:
            catalog = await _async_catalog(self.hass)
        except LiveloError:
            _LOGGER.exception("Cannot fetch the Livelo partner list")
            return self.async_abort(reason="cannot_connect")
        current = dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _schema(self.hass, catalog, current), current
            ),
        )
