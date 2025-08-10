"""Binary sensor platform for ChoreNet integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    """Set up ChoreNet binary sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    
    # Create "all chores completed" binary sensor
    entities.append(AllChoresCompletedSensor(coordinator))
    
    # Create "has overdue chores" binary sensor
    entities.append(HasOverdueChoresSensor(coordinator))
    
    # Create per-person "has active chores" binary sensors
    for person_id, person in coordinator.people.items():
        entities.append(PersonHasActiveChoresSensor(coordinator, person_id, person))
        entities.append(PersonAllChoresCompletedSensor(coordinator, person_id, person))
    
    async_add_entities(entities)


class ChoreNetBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for ChoreNet binary sensors."""

    def __init__(self, coordinator: ChoreNetCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.entry_id)},
            "name": "ChoreNet",
            "manufacturer": "ChoreNet",
            "model": "Chore Tracker",
            "sw_version": coordinator.hass.data[DOMAIN].get("build_version", "1.0.3"),
        }


class AllChoresCompletedSensor(ChoreNetBinarySensorBase):
    """Binary sensor indicating if all active chores are completed."""

    def __init__(self, coordinator: ChoreNetCoordinator) -> None:
        """Initialize the all chores completed sensor."""
        super().__init__(coordinator)
        self._attr_name = "All Chores Completed"
        self._attr_unique_id = f"{DOMAIN}_all_chores_completed"
        self._attr_icon = "mdi:check-all"

    @property
    def is_on(self) -> bool:
        """Return true if all active chores are completed."""
        active_instances = [
            instance for instance in self.coordinator.chore_instances.values()
            if instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
        ]
        
        if not active_instances:
            return False  # No active chores means nothing to complete
        
        for instance in active_instances:
            assigned_people = instance.get("assigned_people", [])
            completions = instance.get("completions", {})
            
            # Check if all assigned people have completed this chore
            if not all(completions.get(person_id, False) for person_id in assigned_people):
                return False
        
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        active_instances = [
            instance for instance in self.coordinator.chore_instances.values()
            if instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
        ]
        
        total_active = len(active_instances)
        completed_count = 0
        
        for instance in active_instances:
            assigned_people = instance.get("assigned_people", [])
            completions = instance.get("completions", {})
            
            if all(completions.get(person_id, False) for person_id in assigned_people):
                completed_count += 1
        
        return {
            "total_active_chores": total_active,
            "completed_chores": completed_count,
            "remaining_chores": total_active - completed_count,
        }


class HasOverdueChoresSensor(ChoreNetBinarySensorBase):
    """Binary sensor indicating if there are any overdue chores."""

    def __init__(self, coordinator: ChoreNetCoordinator) -> None:
        """Initialize the has overdue chores sensor."""
        super().__init__(coordinator)
        self._attr_name = "Has Overdue Chores"
        self._attr_unique_id = f"{DOMAIN}_has_overdue_chores"
        self._attr_icon = "mdi:clock-alert"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if there are overdue chores."""
        return any(
            instance.get("status") == CHORE_STATUS_OVERDUE
            for instance in self.coordinator.chore_instances.values()
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        overdue_instances = [
            instance for instance in self.coordinator.chore_instances.values()
            if instance.get("status") == CHORE_STATUS_OVERDUE
        ]
        
        overdue_chores = []
        for instance in overdue_instances:
            chore = self.coordinator.chores.get(instance["chore_id"], {})
            overdue_chores.append({
                "name": chore.get("name", "Unknown"),
                "due_date": instance.get("due_date"),
                "assigned_people": instance.get("assigned_people", []),
            })
        
        return {
            "overdue_count": len(overdue_instances),
            "overdue_chores": overdue_chores,
        }


class PersonHasActiveChoresSensor(ChoreNetBinarySensorBase):
    """Binary sensor indicating if a person has active chores."""

    def __init__(
        self,
        coordinator: ChoreNetCoordinator,
        person_id: str,
        person: dict[str, Any],
    ) -> None:
        """Initialize the person has active chores sensor."""
        super().__init__(coordinator)
        self._person_id = person_id
        self._person = person
        self._attr_name = f"{person.get('name', person_id)} Has Active Chores"
        self._attr_unique_id = f"{DOMAIN}_{person_id}_has_active_chores"
        self._attr_icon = "mdi:account-clock"

    @property
    def is_on(self) -> bool:
        """Return true if the person has active chores."""
        for instance in self.coordinator.chore_instances.values():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
                and not instance.get("completions", {}).get(self._person_id, False)
            ):
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        active_count = 0
        overdue_count = 0
        required_count = 0
        optional_count = 0
        
        for instance in self.coordinator.chore_instances.values():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
                and not instance.get("completions", {}).get(self._person_id, False)
            ):
                active_count += 1
                
                if instance.get("status") == CHORE_STATUS_OVERDUE:
                    overdue_count += 1
                
                chore = self.coordinator.chores.get(instance["chore_id"], {})
                if chore.get("required", True):
                    required_count += 1
                else:
                    optional_count += 1
        
        return {
            "person_id": self._person_id,
            "person_name": self._person.get("name", self._person_id),
            "active_chores_count": active_count,
            "overdue_chores_count": overdue_count,
            "required_chores_count": required_count,
            "optional_chores_count": optional_count,
        }


class PersonAllChoresCompletedSensor(ChoreNetBinarySensorBase):
    """Binary sensor indicating if a person has completed all their assigned chores."""

    def __init__(
        self,
        coordinator: ChoreNetCoordinator,
        person_id: str,
        person: dict[str, Any],
    ) -> None:
        """Initialize the person all chores completed sensor."""
        super().__init__(coordinator)
        self._person_id = person_id
        self._person = person
        self._attr_name = f"{person.get('name', person_id)} All Chores Completed"
        self._attr_unique_id = f"{DOMAIN}_{person_id}_all_chores_completed"
        self._attr_icon = "mdi:account-check"

    @property
    def is_on(self) -> bool:
        """Return true if the person has completed all their assigned chores."""
        # Get all active chore instances assigned to this person
        person_active_chores = []
        for instance in self.coordinator.chore_instances.values():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
            ):
                person_active_chores.append(instance)
        
        # If no active chores, return False (nothing to complete)
        if not person_active_chores:
            return False
        
        # Check if all are completed by this person
        return all(
            instance.get("completions", {}).get(self._person_id, False)
            for instance in person_active_chores
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        person_active_chores = []
        completed_chores = []
        
        for instance in self.coordinator.chore_instances.values():
            if (
                self._person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
            ):
                person_active_chores.append(instance)
                if instance.get("completions", {}).get(self._person_id, False):
                    chore = self.coordinator.chores.get(instance["chore_id"], {})
                    completed_chores.append({
                        "name": chore.get("name", "Unknown"),
                        "due_date": instance.get("due_date"),
                        "required": chore.get("required", True),
                    })
        
        return {
            "person_id": self._person_id,
            "person_name": self._person.get("name", self._person_id),
            "total_assigned_chores": len(person_active_chores),
            "completed_chores_count": len(completed_chores),
            "completed_chores": completed_chores,
            "completion_automation": self._person.get("completion_automation"),
        }
