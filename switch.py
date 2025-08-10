"""Switch platform for ChoreNet integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ChoreNetCoordinator
from .const import (
    DOMAIN,
    CHORE_STATUS_PENDING,
    CHORE_STATUS_COMPLETED,
    CHORE_STATUS_OVERDUE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChoreNet switch platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create completion switches for each person's active chores
    for instance_key, instance in coordinator.chore_instances.items():
        if instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]:
            chore = coordinator.chores.get(instance["chore_id"], {})
            for person_id in instance.get("assigned_people", []):
                person = coordinator.people.get(person_id, {})
                entities.append(
                    ChoreCompletionSwitch(
                        coordinator, instance_key, instance, chore, person_id, person
                    )
                )
    
    async_add_entities(entities, update_before_add=True)


class ChoreCompletionSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to mark a chore as completed for a specific person."""

    def __init__(
        self,
        coordinator: ChoreNetCoordinator,
        instance_key: str,
        instance: dict[str, Any],
        chore: dict[str, Any],
        person_id: str,
        person: dict[str, Any],
    ) -> None:
        """Initialize the chore completion switch."""
        super().__init__(coordinator)
        self._instance_key = instance_key
        self._instance = instance
        self._chore = chore
        self._person_id = person_id
        self._person = person
        
        chore_name = chore.get("name", "Unknown Chore")
        person_name = person.get("name", person_id)
        
        self._attr_name = f"{person_name} - {chore_name}"
        self._attr_unique_id = f"{DOMAIN}_{instance_key}_{person_id}_completion"
        self._attr_icon = "mdi:check-circle-outline"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "ChoreNet",
            "manufacturer": "ChoreNet",
            "model": "Chore Tracker",
            "sw_version": coordinator.hass.data[DOMAIN].get("build_version", "1.0.3"),
        }

    @property
    def is_on(self) -> bool:
        """Return true if the chore is completed by this person."""
        instance = self.coordinator.chore_instances.get(self._instance_key, {})
        completions = instance.get("completions", {})
        return completions.get(self._person_id, False)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        instance = self.coordinator.chore_instances.get(self._instance_key, {})
        return instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        instance = self.coordinator.chore_instances.get(self._instance_key, {})
        chore = self.coordinator.chores.get(instance.get("chore_id"), {})
        
        return {
            "chore_id": chore.get("chore_id", "unknown"),
            "chore_name": chore.get("name", "Unknown"),
            "person_id": self._person_id,
            "person_name": self._person.get("name", self._person_id),
            "due_date": instance.get("due_date"),
            "status": instance.get("status"),
            "required": chore.get("required", True),
            "time_period": chore.get("time_period", "all_day"),
            "description": chore.get("description", ""),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mark the chore as completed for this person."""
        success = await self.coordinator.complete_chore(self._instance_key, self._person_id)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning(
                "Failed to complete chore %s for person %s",
                self._instance_key,
                self._person_id,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Mark the chore as not completed for this person."""
        instance = self.coordinator.chore_instances.get(self._instance_key)
        if instance:
            instance["completions"][self._person_id] = False
            
            # If chore was fully completed, change it back to pending/overdue
            if instance.get("status") == CHORE_STATUS_COMPLETED:
                instance["status"] = CHORE_STATUS_PENDING
            
            await self.coordinator._save_data()
            await self.coordinator.async_request_refresh()
