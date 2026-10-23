"""Sensores: um por parceiro acompanhado, mais os acompanhados em promoção."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Partner
from .const import DOMAIN, PAGE_URL
from .coordinator import LiveloConfigEntry, LiveloCoordinator
from .notifications import format_campaign, partner_parity, per_currency

PROMOTIONS = "promotions"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiveloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Adiciona os sensores, e novos quando um parceiro entra numa categoria acompanhada."""
    coordinator = entry.runtime_data
    known = coordinator.watched()

    # Remove os sensores de parceiros que não são mais acompanhados.
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in known | {PROMOTIONS}:
            registry.async_remove(entity.entity_id)

    async_add_entities(
        [LiveloPromotionsSensor(coordinator)]
        + [LiveloPartnerSensor(coordinator, code) for code in sorted(known)]
    )

    @callback
    def _add_new() -> None:
        new = coordinator.watched() - known
        if new:
            known.update(new)
            async_add_entities(LiveloPartnerSensor(coordinator, code) for code in sorted(new))

    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class LiveloEntity(CoordinatorEntity[LiveloCoordinator], SensorEntity):
    """Um sensor no dispositivo de serviço Livelo."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LiveloCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Livelo",
            manufacturer="Livelo",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=PAGE_URL,
        )


class LiveloPartnerSensor(LiveloEntity):
    """Pontos por real (ou dólar) num parceiro, para quem não é do Clube."""

    def __init__(self, coordinator: LiveloCoordinator, code: str) -> None:
        super().__init__(coordinator)
        self.code = code
        self._attr_unique_id = code

    @property
    def partner(self) -> Partner | None:
        """O parceiro na busca mais recente."""
        return self.coordinator.data.partners.get(self.code) if self.coordinator.data else None

    @property
    def name(self) -> str:
        return self.partner.name if self.partner else self.code

    @property
    def available(self) -> bool:
        return super().available and self.partner is not None and self.partner.parity is not None

    @property
    def native_value(self) -> float | None:
        return self.partner.parity if self.partner else None

    @property
    def native_unit_of_measurement(self) -> str:
        partner = self.partner
        return "pts" + (per_currency(partner.currency, partner.currency_value) if partner else "/R$")

    @property
    def entity_picture(self) -> str | None:
        return self.partner.image if self.partner else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        partner = self.partner
        if partner is None:
            return None
        return {
            "code": partner.code,
            "parity_club": partner.parity_club,
            "up_to": partner.up_to,
            "currency": partner.currency,
            "currency_value": partner.currency_value,
            "summary": partner_parity(partner),
            "promotion": partner.promotion,
            "campaign": partner.campaign,
            "campaign_start": partner.start.isoformat() if partner.start else None,
            "campaign_end": partner.end.isoformat() if partner.end else None,
            "campaign_text": format_campaign(partner.start, partner.end) if partner.promotion else None,
            "terms": partner.terms,
            "categories": list(partner.categories),
            "url": partner.url,
        }


class LiveloPromotionsSensor(LiveloEntity):
    """Quantos parceiros acompanhados estão em promoção, e quais."""

    _attr_translation_key = PROMOTIONS
    _attr_unique_id = PROMOTIONS
    _attr_icon = "mdi:sale"

    def _promotions(self) -> list[Partner]:
        if not self.coordinator.data:
            return []
        partners = self.coordinator.data.partners
        return sorted(
            (partners[c] for c in self.coordinator.watched() if c in partners and partners[c].promotion),
            key=lambda p: p.name.lower(),
        )

    @property
    def native_value(self) -> int:
        return len(self._promotions())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "partners": [
                {
                    "name": p.name,
                    "summary": partner_parity(p),
                    "campaign": format_campaign(p.start, p.end),
                    "url": p.url,
                }
                for p in self._promotions()
            ]
        }
