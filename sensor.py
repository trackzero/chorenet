"""Sensor platform for ChoreNet integration."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ChoreNetCoordinator
from .const import (
    DOMAIN,
    CHORE_STATUS_PENDING,
    CHORE_STATUS_COMPLETED,
    CHORE_STATUS_OVERDUE,
    CHORE_STATUS_INACTIVE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChoreNet sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create person chore count sensors
    for person_id, person in coordinator.people.items():
        entities.append(PersonChoreSensor(coordinator, person_id, person))
    
    # Create chore status sensors
    for chore_id, chore in coordinator.chores.items():
        entities.append(ChoreStatusSensor(coordinator, chore_id, chore))
    
    # Create active chores count sensor
    entities.append(ActiveChoresCountSensor(coordinator))
    
    async_add_entities(entities)


class ChoreNetSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for ChoreNet sensors."""

    def __init__(self, coordinator: ChoreNetCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "ChoreNet",
            "manufacturer": "ChoreNet",
            "model": "Chore Tracker",
            "sw_version": coordinator.hass.data[DOMAIN].get("build_version", "1.0.3"),
        }


class PersonChoreSensor(ChoreNetSensorBase):
    """Sensor showing active chores count for a person."""

    def __init__(
        self,
        coordinator: ChoreNetCoordinator,
        person_id: str,
        person: dict[str, Any],
    ) -> None:
        """Initialize the person chore sensor."""
        super().__init__(coordinator)
        self._person_id = person_id
        self._person = person
        self._attr_name = f"{person.get('name', person_id)} Active Chores"
        self._attr_unique_id = f"{DOMAIN}_{person_id}_active_chores"
        self._attr_icon = "mdi:clipboard-list"
        self._attr_native_unit_of_measurement = "chores"

    @property
    def native_value(self) -> int:
        """Return the number of active chores for this person."""
        active_count = 0
        
        for instance in self.coordinator.chore_instances.values():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
                and not instance.get("completions", {}).get(self._person_id, False)
            ):
                active_count += 1
        
        return active_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        active_chores = []
        overdue_chores = []
        
        for instance_key, instance in self.coordinator.chore_instances.items():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
                and not instance.get("completions", {}).get(self._person_id, False)
            ):
                chore = self.coordinator.chores.get(instance["chore_id"], {})
                chore_info = {
                    "name": chore.get("name", "Unknown"),
                    "due_date": instance.get("due_date"),
                    "status": instance.get("status"),
                    "required": chore.get("required", True),
                }
                
                if instance.get("status") == CHORE_STATUS_OVERDUE:
                    overdue_chores.append(chore_info)
                else:
                    active_chores.append(chore_info)
        
        return {
            "person_id": self._person_id,
            "person_name": self._person.get("name", self._person_id),
            "active_chores": active_chores,
            "overdue_chores": overdue_chores,
            "overdue_count": len(overdue_chores),
        }


class ChoreStatusSensor(ChoreNetSensorBase):
    """Sensor showing the status of a specific chore."""

    def __init__(
        self,
        coordinator: ChoreNetCoordinator,
        chore_id: str,
        chore: dict[str, Any],
    ) -> None:
        """Initialize the chore status sensor."""
        super().__init__(coordinator)
        self._chore_id = chore_id
        self._chore = chore
        self._attr_name = f"{chore.get('name', chore_id)} Status"
        self._attr_unique_id = f"{DOMAIN}_{chore_id}_status"
        self._attr_icon = "mdi:clipboard-check"

    @property
    def native_value(self) -> str:
        """Return the current status of the chore."""
        # Find the most recent instance of this chore
        latest_instance = None
        latest_date = None
        
        for instance in self.coordinator.chore_instances.values():
            if instance.get("chore_id") == self._chore_id:
                instance_date = datetime.fromisoformat(instance.get("due_date", ""))
                if latest_date is None or instance_date > latest_date:
                    latest_date = instance_date
                    latest_instance = instance
        
        if latest_instance:
            return latest_instance.get("status", CHORE_STATUS_INACTIVE)
        
        return CHORE_STATUS_INACTIVE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        # Find the most recent instance
        latest_instance = None
        latest_date = None
        
        for instance in self.coordinator.chore_instances.values():
            if instance.get("chore_id") == self._chore_id:
                instance_date = datetime.fromisoformat(instance.get("due_date", ""))
                if latest_date is None or instance_date > latest_date:
                    latest_date = instance_date
                    latest_instance = instance
        
        attributes = {
            "chore_id": self._chore_id,
            "chore_name": self._chore.get("name", self._chore_id),
            "description": self._chore.get("description", ""),
            "assigned_people": self._chore.get("assigned_people", []),
            "time_period": self._chore.get("time_period", "all_day"),
            "required": self._chore.get("required", True),
            "enabled": self._chore.get("enabled", True),
            "recurrence": self._chore.get("recurrence", {}),
        }
        
        if latest_instance:
            attributes.update({
                "due_date": latest_instance.get("due_date"),
                "completions": latest_instance.get("completions", {}),
                "completion_automation": self._chore.get("completion_automation"),
            })
            
            # Calculate next due date
            recurrence = self._chore.get("recurrence", {})
            if recurrence.get("type") != "once":
                next_due = self._calculate_next_due_date()
                if next_due:
                    attributes["next_due_date"] = next_due.isoformat()
        
        return attributes

    def _calculate_next_due_date(self) -> datetime | None:
        """Calculate the next due date for this chore."""
        # This would implement the same logic as in the coordinator
        # For now, return a simple daily recurrence
        return dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0) + dt_util.dt.timedelta(days=1)


class ActiveChoresCountSensor(ChoreNetSensorBase):
    """Sensor showing total count of active chores across all people."""

    def __init__(self, coordinator: ChoreNetCoordinator) -> None:
        """Initialize the active chores count sensor."""
        super().__init__(coordinator)
        self._attr_name = "Active Chores Count"
        self._attr_unique_id = f"{DOMAIN}_active_chores_count"
        self._attr_icon = "mdi:format-list-checks"
        self._attr_native_unit_of_measurement = "chores"

    @property
    def native_value(self) -> int:
        """Return the total number of active chores."""
        return len([
            instance for instance in self.coordinator.chore_instances.values()
            if instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
        ])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        pending_count = 0
        overdue_count = 0
        
        for instance in self.coordinator.chore_instances.values():
            status = instance.get("status")
            if status == CHORE_STATUS_PENDING:
                pending_count += 1
            elif status == CHORE_STATUS_OVERDUE:
                overdue_count += 1
        
        return {
            "pending_count": pending_count,
            "overdue_count": overdue_count,
            "total_people": len(self.coordinator.people),
            "total_chores_configured": len(self.coordinator.chores),
        }
