"""The ChoreNet integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
    SERVICE_COMPLETE_CHORE,
    SERVICE_RESET_CHORE,
    SERVICE_ADD_CHORE,
    SERVICE_REMOVE_CHORE,
    EVENT_CHORE_COMPLETED,
    EVENT_ALL_CHORES_COMPLETED,
    EVENT_CHORES_ACTIVATED,
    EVENT_PERSON_COMPLETED,
    CHORE_STATUS_PENDING,
    CHORE_STATUS_COMPLETED,
    CHORE_STATUS_OVERDUE,
    CHORE_STATUS_INACTIVE,
    CHORE_PERIOD_MORNING,
    CHORE_PERIOD_AFTERNOON,
    CHORE_PERIOD_EVENING,
    CHORE_PERIOD_ALL_DAY,
    RECURRENCE_DAILY,
    RECURRENCE_WEEKLY,
    RECURRENCE_MONTHLY,
    CONF_PEOPLE,
    CONF_CHORES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChoreNet from a config entry."""
    
    # Initialize storage
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    
    # Merge storage data with config entry options
    config_data = {
        "people": entry.options.get(CONF_PEOPLE, {}),
        "chores": entry.options.get(CONF_CHORES, {}),
        "chore_instances": data.get("chore_instances", {}),
    }
    
    # Initialize coordinator
    coordinator = ChoreNetCoordinator(hass, store, config_data, entry)
    await coordinator.async_config_entry_first_refresh()
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_register_services(hass, coordinator)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok


class ChoreNetCoordinator(DataUpdateCoordinator):
    """ChoreNet data update coordinator."""

    def __init__(self, hass: HomeAssistant, store: Store, data: dict[str, Any], config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.store = store
        self.config_entry = config_entry
        self._data = data
        self._people = data.get("people", {})
        self._chores = data.get("chores", {})
        self._chore_instances = data.get("chore_instances", {})

    @property
    def people(self) -> dict[str, Any]:
        """Return people configuration."""
        return self._people

    @property
    def chores(self) -> dict[str, Any]:
        """Return chores configuration."""
        return self._chores

    @property
    def chore_instances(self) -> dict[str, Any]:
        """Return current chore instances."""
        return self._chore_instances

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the coordinator."""
        now = dt_util.now()
        
        # Update chore instances based on current time
        await self._update_chore_instances(now)
        
        # Check for newly activated chores
        await self._check_activated_chores(now)
        
        # Check if all chores are completed
        await self._check_all_chores_completed()
        
        return {
            "people": self._people,
            "chores": self._chores,
            "chore_instances": self._chore_instances,
            "last_update": now,
        }

    async def _update_chore_instances(self, now: datetime) -> None:
        """Update chore instances based on current time and recurrence."""
        for chore_id, chore in self._chores.items():
            # Generate instances for this chore
            await self._generate_chore_instances(chore_id, chore, now)
            
            # Mark overdue chores
            await self._mark_overdue_chores(chore_id, chore, now)

    async def _generate_chore_instances(self, chore_id: str, chore: dict, now: datetime) -> None:
        """Generate chore instances based on recurrence pattern."""
        if not chore.get("enabled", True):
            return
            
        recurrence = chore.get("recurrence", {})
        recurrence_type = recurrence.get("type", RECURRENCE_DAILY)
        
        # Calculate next due date
        next_due = self._calculate_next_due_date(chore, now)
        
        if next_due and next_due <= now:
            # Create instance if it doesn't exist
            instance_key = f"{chore_id}_{next_due.date().isoformat()}"
            
            if instance_key not in self._chore_instances:
                self._chore_instances[instance_key] = {
                    "chore_id": chore_id,
                    "due_date": next_due.isoformat(),
                    "status": CHORE_STATUS_INACTIVE,
                    "assigned_people": chore.get("assigned_people", []),
                    "completions": {},
                }

    def _calculate_next_due_date(self, chore: dict, now: datetime) -> datetime | None:
        """Calculate the next due date for a chore."""
        recurrence = chore.get("recurrence", {})
        recurrence_type = recurrence.get("type", RECURRENCE_DAILY)
        
        if recurrence_type == RECURRENCE_DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif recurrence_type == RECURRENCE_WEEKLY:
            # Find next occurrence of specified weekday
            target_weekday = recurrence.get("weekday", 0)  # 0 = Monday
            days_ahead = target_weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif recurrence_type == RECURRENCE_MONTHLY:
            # Find next occurrence of specified day of month
            target_day = recurrence.get("day", 1)
            if now.day <= target_day:
                return now.replace(day=target_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                # Next month
                next_month = now.replace(day=1) + timedelta(days=32)
                return next_month.replace(day=target_day, hour=0, minute=0, second=0, microsecond=0)
        
        return None

    async def _mark_overdue_chores(self, chore_id: str, chore: dict, now: datetime) -> None:
        """Mark chores as overdue if they're past their time window."""
        for instance_key, instance in self._chore_instances.items():
            if instance["chore_id"] != chore_id:
                continue
                
            if instance["status"] == CHORE_STATUS_PENDING:
                due_date = datetime.fromisoformat(instance["due_date"])
                time_period = chore.get("time_period", CHORE_PERIOD_ALL_DAY)
                
                # Check if chore is overdue based on time period
                if self._is_chore_overdue(due_date, time_period, now):
                    instance["status"] = CHORE_STATUS_OVERDUE

    def _is_chore_overdue(self, due_date: datetime, time_period: str, now: datetime) -> bool:
        """Check if a chore is overdue based on its time period."""
        if time_period == CHORE_PERIOD_ALL_DAY:
            return now.date() > due_date.date()
        
        # For specific time periods, check if we're past that window
        # This would need person-specific time windows
        return now.date() > due_date.date()

    async def _check_activated_chores(self, now: datetime) -> None:
        """Check for newly activated chores and fire events."""
        newly_activated = []
        
        for instance_key, instance in self._chore_instances.items():
            if instance["status"] == CHORE_STATUS_INACTIVE:
                chore = self._chores.get(instance["chore_id"])
                if chore and self._should_activate_chore(instance, chore, now):
                    instance["status"] = CHORE_STATUS_PENDING
                    newly_activated.append(instance)
        
        if newly_activated:
            self.hass.bus.async_fire(EVENT_CHORES_ACTIVATED, {"chores": newly_activated})

    def _should_activate_chore(self, instance: dict, chore: dict, now: datetime) -> bool:
        """Determine if a chore should be activated based on time windows."""
        time_period = chore.get("time_period", CHORE_PERIOD_ALL_DAY)
        
        if time_period == CHORE_PERIOD_ALL_DAY:
            return True
            
        # Check person-specific time windows
        for person_id in instance["assigned_people"]:
            person = self._people.get(person_id)
            if person and self._is_in_time_window(person, time_period, now):
                return True
                
        return False

    def _is_in_time_window(self, person: dict, time_period: str, now: datetime) -> bool:
        """Check if current time is within the person's time window."""
        time_windows = person.get("time_windows", {})
        
        if time_period == CHORE_PERIOD_MORNING:
            start_time = time_windows.get("morning_start", "06:00")
            end_time = time_windows.get("morning_end", "12:00")
        elif time_period == CHORE_PERIOD_AFTERNOON:
            start_time = time_windows.get("afternoon_start", "12:00")
            end_time = time_windows.get("afternoon_end", "18:00")
        elif time_period == CHORE_PERIOD_EVENING:
            start_time = time_windows.get("evening_start", "18:00")
            end_time = time_windows.get("evening_end", "22:00")
        else:
            return True
            
        current_time = now.strftime("%H:%M")
        return start_time <= current_time <= end_time

    async def _check_all_chores_completed(self) -> None:
        """Check if all active chores are completed and fire event."""
        active_chores = [
            instance for instance in self._chore_instances.values()
            if instance["status"] in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
        ]
        
        if active_chores:
            completed_chores = [
                instance for instance in active_chores
                if all(instance["completions"].values())
            ]
            
            if len(completed_chores) == len(active_chores):
                self.hass.bus.async_fire(EVENT_ALL_CHORES_COMPLETED, {
                    "completed_chores": completed_chores
                })

    async def complete_chore(self, chore_instance_id: str, person_id: str) -> bool:
        """Mark a chore as completed for a person."""
        instance = self._chore_instances.get(chore_instance_id)
        if not instance:
            return False
            
        instance["completions"][person_id] = True
        
        # Check if chore is fully completed by all assigned people
        assigned_people = instance["assigned_people"]
        if all(instance["completions"].get(pid, False) for pid in assigned_people):
            instance["status"] = CHORE_STATUS_COMPLETED
            
            # Fire completion event
            chore = self._chores.get(instance["chore_id"])
            self.hass.bus.async_fire(EVENT_CHORE_COMPLETED, {
                "chore": chore,
                "instance": instance,
            })
            
            # Trigger automation if specified for this chore
            if chore and chore.get("completion_automation"):
                await self.hass.services.async_call(
                    "automation", "trigger",
                    {"entity_id": chore["completion_automation"]},
                    blocking=False
                )
        
        # Check if this person has completed ALL their chores
        await self._check_person_all_chores_completed(person_id)
        
        await self._save_data()
        return True

    async def _check_person_all_chores_completed(self, person_id: str) -> None:
        """Check if a person has completed all their assigned chores and fire event."""
        person = self._people.get(person_id)
        if not person:
            return
        
        # Get all active chore instances assigned to this person
        person_active_chores = []
        for instance in self._chore_instances.values():
            if (
                person_id in instance.get("assigned_people", [])
                and instance.get("status") in [CHORE_STATUS_PENDING, CHORE_STATUS_OVERDUE]
            ):
                person_active_chores.append(instance)
        
        # Check if all are completed by this person
        if person_active_chores:
            all_completed = all(
                instance.get("completions", {}).get(person_id, False)
                for instance in person_active_chores
            )
            
            if all_completed:
                # Fire person completed event
                self.hass.bus.async_fire(EVENT_PERSON_COMPLETED, {
                    "person_id": person_id,
                    "person_name": person.get("name", person_id),
                    "completed_chores": person_active_chores,
                })
                
                # Trigger person's completion automation if specified
                if person.get("completion_automation"):
                    await self.hass.services.async_call(
                        "automation", "trigger",
                        {"entity_id": person["completion_automation"]},
                        blocking=False
                    )

    async def _save_data(self) -> None:
        """Save data to storage."""
        data = {
            "people": self._people,
            "chores": self._chores,
            "chore_instances": self._chore_instances,
        }
        await self.store.async_save(data)


async def _async_register_services(hass: HomeAssistant, coordinator: ChoreNetCoordinator) -> None:
    """Register ChoreNet services."""
    
    async def complete_chore_service(call: ServiceCall) -> None:
        """Handle complete chore service call."""
        chore_instance_id = call.data.get("chore_instance_id")
        person_id = call.data.get("person_id")
        
        if chore_instance_id and person_id:
            await coordinator.complete_chore(chore_instance_id, person_id)
            await coordinator.async_request_refresh()
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_CHORE,
        complete_chore_service
    )
