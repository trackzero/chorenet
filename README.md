# ChoreNet - Home Assistant Chore Tracking Integration

ChoreNet is a comprehensive Home Assistant custom integration designed to track and manage household chores for multiple people with flexible scheduling and automation capabilities.

## Features

- **Multi-person Support**: Track chores for multiple household members
- **Flexible Scheduling**: Support for daily, weekly, monthly, and one-time chores
- **Time Windows**: Configure morning, afternoon, evening, or all-day chores with per-person customizable time windows
- **Automation Integration**: Trigger automations when chores are completed or when all chores are done
- **Status Tracking**: Monitor pending, completed, overdue, and inactive chores
- **Rich Entities**: Sensors, switches, and binary sensors provide comprehensive state information

## Installation

### Via HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "ChoreNet" in HACS
3. Install the integration
4. Restart Home Assistant
5. Add ChoreNet via the integrations page

### Manual Installation

1. Copy the `custom_components/chorenet` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add ChoreNet via the integrations page (Settings → Devices & Services → Add Integration)

## Configuration

### Initial Setup

1. Go to Settings → Devices & Services
2. Click "Add Integration" and search for "ChoreNet"
3. Follow the configuration flow to set up your integration

### Adding People

1. Go to the ChoreNet integration options
2. Select "People" management
3. Add people with custom time windows:
   - Morning: Default 06:00-12:00
   - Afternoon: Default 12:00-18:00
   - Evening: Default 18:00-22:00

### Adding Chores

1. Go to the ChoreNet integration options
2. Select "Chores" management
3. Configure chores with:
   - Name and description
   - Assigned people (multiple selection)
   - Time period (morning/afternoon/evening/all day)
   - Recurrence pattern (daily/weekly/monthly/once)
   - Required vs optional status
   - Automation to trigger on completion

## Entities Created

### Sensors

- **Person Active Chores**: Shows count of active chores per person with detailed attributes
- **Chore Status**: Shows current status of each configured chore
- **Active Chores Count**: Total count of active chores across all people

### Switches

- **Chore Completion Switches**: One switch per person per active chore for marking completion

### Binary Sensors

- **All Chores Completed**: True when all active chores are completed
- **Has Overdue Chores**: True when any chores are overdue
- **Person Has Active Chores**: Per-person indicator of active chores

## Services

### `chorenet.complete_chore`

Mark a chore as completed for a specific person.

```yaml
service: chorenet.complete_chore
data:
  chore_instance_id: "dishes_2025-08-09"
  person_id: "alice"
```

### `chorenet.reset_chore`

Reset a chore completion status.

```yaml
service: chorenet.reset_chore
data:
  chore_instance_id: "dishes_2025-08-09"
  person_id: "alice"
```

### `chorenet.add_chore`

Add a new chore dynamically.

```yaml
service: chorenet.add_chore
data:
  name: "Take out trash"
  assigned_people: ["alice", "bob"]
  time_period: "evening"
  recurrence_type: "weekly"
  weekday: 0  # Monday
  required: true
```

### `chorenet.remove_chore`

Remove a chore from the system.

```yaml
service: chorenet.remove_chore
data:
  chore_id: "trash"
```

## Events

ChoreNet fires several events that can trigger automations:

### `chorenet_chore_completed`

Fired when a chore is fully completed by all assigned people.

```yaml
event_type: chorenet_chore_completed
event_data:
  chore:
    name: "Dishes"
    chore_id: "dishes"
  instance:
    chore_id: "dishes"
    due_date: "2025-08-09T00:00:00"
    status: "completed"
```

### `chorenet_all_chores_completed`

Fired when all active chores are completed.

```yaml
event_type: chorenet_all_chores_completed
event_data:
  completed_chores: []  # List of completed chore instances
```

### `chorenet_chores_activated`

Fired when chores become active (e.g., entering evening time window).

```yaml
event_type: chorenet_chores_activated
event_data:
  chores: []  # List of newly activated chore instances
```

## Automation Examples

### Notify when all chores are done

```yaml
automation:
  - alias: "All Chores Completed Notification"
    trigger:
      - platform: event
        event_type: chorenet_all_chores_completed
    action:
      - service: notify.mobile_app_alice_phone
        data:
          title: "🎉 All Chores Completed!"
          message: "Great job everyone! All chores are done for today."
```

### Remind about overdue chores

```yaml
automation:
  - alias: "Overdue Chores Reminder"
    trigger:
      - platform: state
        entity_id: binary_sensor.has_overdue_chores
        to: "on"
    action:
      - service: notify.family
        data:
          title: "⏰ Overdue Chores"
          message: "Some chores are overdue. Please check the ChoreNet dashboard."
```

### Individual chore completion rewards

```yaml
automation:
  - alias: "Chore Completion Reward"
    trigger:
      - platform: event
        event_type: chorenet_chore_completed
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.chore.name == 'Dishes' }}"
    action:
      - service: light.turn_on
        target:
          entity_id: light.kitchen_led
        data:
          color_name: "green"
          brightness: 255
      - delay: "00:00:05"
      - service: light.turn_off
        target:
          entity_id: light.kitchen_led
```

## Recurrence Patterns

### Daily
Chores repeat every day.

### Weekly
Chores repeat on specific days of the week:
- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

### Monthly
Chores repeat on specific days of the month (1-31).

### Once
Chores occur only once and don't repeat.

## Time Periods

Chores can be assigned to specific time periods:

- **Morning**: Configurable per person (default 06:00-12:00)
- **Afternoon**: Configurable per person (default 12:00-18:00)  
- **Evening**: Configurable per person (default 18:00-22:00)
- **All Day**: Active throughout the day

Chores only become active during their assigned time periods, and the `chorenet_chores_activated` event fires when crossing into a new time window.

## Troubleshooting

### Chores not appearing
- Check that people are configured before adding chores
- Verify time windows are set correctly
- Ensure recurrence patterns are properly configured

### Automations not triggering
- Verify automation entity IDs exist in Home Assistant
- Check that the completion_automation field is set on chores
- Monitor the Home Assistant logs for any errors

### Time window issues
- Ensure time windows don't overlap inappropriately
- Check that time formats are correct (HH:MM)
- Verify timezone settings in Home Assistant

## Contributing

This is an open-source project. Feel free to contribute by:
- Reporting bugs
- Suggesting new features
- Submitting pull requests
- Improving documentation

## License

This project is licensed under the MIT License.
