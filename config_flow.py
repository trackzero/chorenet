"""Config flow for ChoreNet integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    CONF_PEOPLE,
    CONF_CHORES,
    CONF_TIME_WINDOWS,
    CONF_MORNING_START,
    CONF_MORNING_END,
    CONF_AFTERNOON_START,
    CONF_AFTERNOON_END,
    CONF_EVENING_START,
    CONF_EVENING_END,
    DEFAULT_TIME_WINDOWS,
    CHORE_PERIOD_MORNING,
    CHORE_PERIOD_AFTERNOON,
    CHORE_PERIOD_EVENING,
    CHORE_PERIOD_ALL_DAY,
    RECURRENCE_DAILY,
    RECURRENCE_WEEKLY,
    RECURRENCE_MONTHLY,
    RECURRENCE_ONCE,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

STEP_INIT = "user"
STEP_PEOPLE = "people"
STEP_CHORES = "chores"
STEP_TIME_WINDOWS = "time_windows"


class ChoreNetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChoreNet."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._people: dict[str, Any] = {}
        self._chores: dict[str, Any] = {}
        self._current_person_id: str | None = None
        self._current_chore_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Create the integration entry
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                },
                options={
                    CONF_PEOPLE: self._people,
                    CONF_CHORES: self._chores,
                }
            )

        return self.async_show_form(
            step_id=STEP_INIT,
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="ChoreNet"): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ChoreNetOptionsFlow:
        """Create the options flow."""
        return ChoreNetOptionsFlow(config_entry)


class ChoreNetOptionsFlow(config_entries.OptionsFlow):
    """ChoreNet options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._people: dict[str, Any] = config_entry.options.get(CONF_PEOPLE, {})
        self._chores: dict[str, Any] = config_entry.options.get(CONF_CHORES, {})
        self._current_person_id: str | None = None
        self._current_chore_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            menu_selection = user_input.get("menu_selection")
            if menu_selection == "people":
                return await self.async_step_people()
            elif menu_selection == "chores":
                return await self.async_step_chores()
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("menu_selection"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "people", "label": "Manage People"},
                            {"value": "chores", "label": "Manage Chores"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_people(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle people management."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_person":
                return await self.async_step_add_person()
            elif action == "edit_person":
                return await self.async_step_select_person_to_edit()
            elif action == "remove_person":
                return await self.async_step_select_person_to_remove()
            elif action == "done":
                return await self._update_options()

        people_list = [f"{name} ({person_id})" for person_id, person in self._people.items() for name in [person.get("name", person_id)]]
        
        return self.async_show_form(
            step_id="people",
            data_schema=vol.Schema({
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "add_person", "label": "Add Person"},
                            {"value": "edit_person", "label": "Edit Person"},
                            {"value": "remove_person", "label": "Remove Person"},
                            {"value": "done", "label": "Done"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "people_list": "\n".join(people_list) if people_list else "No people configured"
            },
        )

    async def async_step_add_person(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a person."""
        errors: dict[str, str] = {}

        if user_input is not None:
            person_id = user_input["person_id"].lower().replace(" ", "_")
            
            if person_id in self._people:
                errors["person_id"] = "Person ID already exists"
            else:
                # Get automation entities for per-person completion
                automation_entities = [
                    entity.entity_id for entity in self.hass.states.async_all()
                    if entity.entity_id.startswith("automation.")
                ]
                automation_options = [{"value": "", "label": "None"}] + [
                    {"value": entity_id, "label": entity_id} for entity_id in automation_entities
                ]
                
                self._people[person_id] = {
                    "name": user_input["name"],
                    "person_id": person_id,
                    "time_windows": DEFAULT_TIME_WINDOWS.copy(),
                    "completion_automation": user_input.get("completion_automation"),
                }
                self._current_person_id = person_id
                return await self.async_step_configure_time_windows()

        # Get automation entities for selection
        automation_entities = [
            entity.entity_id for entity in self.hass.states.async_all()
            if entity.entity_id.startswith("automation.")
        ]
        automation_options = [{"value": "", "label": "None"}] + [
            {"value": entity_id, "label": entity_id} for entity_id in automation_entities
        ]

        return self.async_show_form(
            step_id="add_person",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("person_id"): str,
                vol.Optional("completion_automation"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=automation_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            errors=errors,
            description_placeholders={
                "name_help": "The display name for this person (e.g., 'Alice', 'Mom', 'Kid1')",
                "person_id_help": "A unique identifier for this person. Use lowercase letters and underscores only (e.g., 'alice', 'mom', 'kid_1'). This cannot be changed later.",
                "automation_help": "Optional: Select an automation to trigger when this person completes ALL their assigned chores."
            },
        )

    async def async_step_configure_time_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure time windows for a person."""
        if user_input is not None:
            if self._current_person_id:
                self._people[self._current_person_id]["time_windows"] = {
                    CONF_MORNING_START: user_input[CONF_MORNING_START],
                    CONF_MORNING_END: user_input[CONF_MORNING_END],
                    CONF_AFTERNOON_START: user_input[CONF_AFTERNOON_START],
                    CONF_AFTERNOON_END: user_input[CONF_AFTERNOON_END],
                    CONF_EVENING_START: user_input[CONF_EVENING_START],
                    CONF_EVENING_END: user_input[CONF_EVENING_END],
                }
                self._current_person_id = None
            
            return await self.async_step_people()

        person = self._people.get(self._current_person_id, {})
        time_windows = person.get("time_windows", DEFAULT_TIME_WINDOWS)

        return self.async_show_form(
            step_id="configure_time_windows",
            data_schema=vol.Schema({
                vol.Required(CONF_MORNING_START, default=time_windows.get(CONF_MORNING_START, "06:00")): str,
                vol.Required(CONF_MORNING_END, default=time_windows.get(CONF_MORNING_END, "12:00")): str,
                vol.Required(CONF_AFTERNOON_START, default=time_windows.get(CONF_AFTERNOON_START, "12:00")): str,
                vol.Required(CONF_AFTERNOON_END, default=time_windows.get(CONF_AFTERNOON_END, "18:00")): str,
                vol.Required(CONF_EVENING_START, default=time_windows.get(CONF_EVENING_START, "18:00")): str,
                vol.Required(CONF_EVENING_END, default=time_windows.get(CONF_EVENING_END, "22:00")): str,
            }),
            description_placeholders={
                "person_name": person.get("name", "Unknown"),
                "time_help": "Configure when morning, afternoon, and evening time periods are active for this person. Use 24-hour format (e.g., 06:00, 18:00). Chores assigned to specific time periods will only become active during these windows."
            },
        )

    async def async_step_chores(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle chores management."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_chore":
                return await self.async_step_add_chore()
            elif action == "edit_chore":
                return await self.async_step_select_chore_to_edit()
            elif action == "remove_chore":
                return await self.async_step_select_chore_to_remove()
            elif action == "done":
                return await self._update_options()

        chores_list = [f"{name} ({chore_id})" for chore_id, chore in self._chores.items() for name in [chore.get("name", chore_id)]]
        
        return self.async_show_form(
            step_id="chores",
            data_schema=vol.Schema({
                vol.Required("action"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": "add_chore", "label": "Add Chore"},
                            {"value": "edit_chore", "label": "Edit Chore"},
                            {"value": "remove_chore", "label": "Remove Chore"},
                            {"value": "done", "label": "Done"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
            description_placeholders={
                "chores_list": "\n".join(chores_list) if chores_list else "No chores configured"
            },
        )

    async def async_step_add_chore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a chore."""
        errors: dict[str, str] = {}

        if user_input is not None:
            chore_id = user_input["chore_id"].lower().replace(" ", "_")
            
            if chore_id in self._chores:
                errors["chore_id"] = "Chore ID already exists"
            else:
                # Get people options for assignment
                people_options = [
                    {"value": person_id, "label": person.get("name", person_id)}
                    for person_id, person in self._people.items()
                ]
                
                if not people_options:
                    errors["base"] = "No people configured. Add people first."
                else:
                    recurrence_data = {}
                    recurrence_type = user_input["recurrence_type"]
                    
                    if recurrence_type == RECURRENCE_WEEKLY:
                        recurrence_data["weekday"] = user_input.get("weekday", 0)
                    elif recurrence_type == RECURRENCE_MONTHLY:
                        recurrence_data["day"] = user_input.get("day", 1)
                    
                    self._chores[chore_id] = {
                        "name": user_input["name"],
                        "chore_id": chore_id,
                        "description": user_input.get("description", ""),
                        "assigned_people": user_input["assigned_people"],
                        "time_period": user_input["time_period"],
                        "required": user_input.get("required", True),
                        "enabled": True,
                        "recurrence": {
                            "type": recurrence_type,
                            **recurrence_data
                        },
                        "completion_automation": user_input.get("completion_automation"),
                    }
                    return await self.async_step_chores()

        if errors.get("base"):
            return self.async_show_form(
                step_id="add_chore",
                errors=errors,
            )

        people_options = [
            {"value": person_id, "label": person.get("name", person_id)}
            for person_id, person in self._people.items()
        ]

        # Get automation entities for selection
        automation_entities = [
            entity.entity_id for entity in self.hass.states.async_all()
            if entity.entity_id.startswith("automation.")
        ]
        automation_options = [{"value": "", "label": "None"}] + [
            {"value": entity_id, "label": entity_id} for entity_id in automation_entities
        ]

        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required("chore_id"): str,
            vol.Optional("description", default=""): str,
            vol.Required("assigned_people"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=people_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("time_period", default=CHORE_PERIOD_ALL_DAY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": CHORE_PERIOD_MORNING, "label": "Morning"},
                        {"value": CHORE_PERIOD_AFTERNOON, "label": "Afternoon"},
                        {"value": CHORE_PERIOD_EVENING, "label": "Evening"},
                        {"value": CHORE_PERIOD_ALL_DAY, "label": "All Day"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("recurrence_type", default=RECURRENCE_DAILY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": RECURRENCE_DAILY, "label": "Daily"},
                        {"value": RECURRENCE_WEEKLY, "label": "Weekly"},
                        {"value": RECURRENCE_MONTHLY, "label": "Monthly"},
                        {"value": RECURRENCE_ONCE, "label": "Once"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("required", default=True): bool,
            vol.Optional("completion_automation"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=automation_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="add_chore",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "chore_help": "Configure a new chore with its schedule and assignments",
                "name_help": "Display name for the chore (e.g., 'Take out trash', 'Do dishes')",
                "chore_id_help": "Unique identifier using lowercase letters and underscores (e.g., 'trash', 'dishes')",
                "description_help": "Optional: Additional details about the chore",
                "assigned_people_help": "Select one or more people. For multi-person chores, any assigned person can mark it complete",
                "time_period_help": "When this chore becomes active. 'All Day' is always active, others follow person's time windows",
                "recurrence_help": "How often: Daily (every day), Weekly (specific weekday), Monthly (specific date), Once (single occurrence)",
                "required_help": "Required chores must be completed, optional chores are nice-to-have",
                "automation_help": "Optional: Automation to trigger when this specific chore is completed by ALL assigned people"
            },
        )

    async def async_step_select_person_to_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select person to edit."""
        if user_input is not None:
            self._current_person_id = user_input["person_id"]
            return await self.async_step_configure_time_windows()

        people_options = [
            {"value": person_id, "label": person.get("name", person_id)}
            for person_id, person in self._people.items()
        ]

        return self.async_show_form(
            step_id="select_person_to_edit",
            data_schema=vol.Schema({
                vol.Required("person_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=people_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def async_step_select_person_to_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select person to remove."""
        if user_input is not None:
            person_id = user_input["person_id"]
            self._people.pop(person_id, None)
            return await self.async_step_people()

        people_options = [
            {"value": person_id, "label": person.get("name", person_id)}
            for person_id, person in self._people.items()
        ]

        return self.async_show_form(
            step_id="select_person_to_remove",
            data_schema=vol.Schema({
                vol.Required("person_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=people_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }),
        )

    async def _update_options(self) -> FlowResult:
        """Update the options."""
        return self.async_create_entry(
            title="",
            data={
                CONF_PEOPLE: self._people,
                CONF_CHORES: self._chores,
            },
        )
