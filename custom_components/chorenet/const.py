"""Constants for ChoreNet integration."""

# Integration constants
DOMAIN = "chorenet"
NAME = "ChoreNet"
VERSION = "1.0.0"

# Configuration constants
CONF_PEOPLE = "people"
CONF_CHORES = "chores"
CONF_TIME_WINDOWS = "time_windows"
CONF_MORNING_START = "morning_start"
CONF_MORNING_END = "morning_end"
CONF_AFTERNOON_START = "afternoon_start"
CONF_AFTERNOON_END = "afternoon_end"
CONF_EVENING_START = "evening_start"
CONF_EVENING_END = "evening_end"

# Chore constants
CHORE_STATUS_PENDING = "pending"
CHORE_STATUS_COMPLETED = "completed"
CHORE_STATUS_OVERDUE = "overdue"
CHORE_STATUS_INACTIVE = "inactive"

CHORE_PERIOD_MORNING = "morning"
CHORE_PERIOD_AFTERNOON = "afternoon"
CHORE_PERIOD_EVENING = "evening"
CHORE_PERIOD_ALL_DAY = "all_day"

RECURRENCE_DAILY = "daily"
RECURRENCE_WEEKLY = "weekly"
RECURRENCE_MONTHLY = "monthly"
RECURRENCE_ONCE = "once"

# Default time windows
DEFAULT_TIME_WINDOWS = {
    CONF_MORNING_START: "06:00",
    CONF_MORNING_END: "12:00",
    CONF_AFTERNOON_START: "12:00",
    CONF_AFTERNOON_END: "18:00",
    CONF_EVENING_START: "18:00",
    CONF_EVENING_END: "22:00"
}

# Storage keys
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

# Services
SERVICE_COMPLETE_CHORE = "complete_chore"
SERVICE_RESET_CHORE = "reset_chore"
SERVICE_ADD_CHORE = "add_chore"
SERVICE_REMOVE_CHORE = "remove_chore"

# Event types
EVENT_CHORE_COMPLETED = f"{DOMAIN}_chore_completed"
EVENT_ALL_CHORES_COMPLETED = f"{DOMAIN}_all_chores_completed"
EVENT_CHORES_ACTIVATED = f"{DOMAIN}_chores_activated"

# Update interval
UPDATE_INTERVAL = 60  # seconds
