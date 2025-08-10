# Pattern-Based Triggers

push-tmux supports pattern-based triggers that automatically execute commands when incoming messages match specific patterns.

## Overview

Triggers provide:
- Pattern matching on incoming messages (regex or simple text)
- Device-based filtering (only trigger from specific devices)
- Command execution with variable substitution
- Pushbullet notifications to any device
- Rate limiting and cooldown periods
- tmux session routing

## Configuration

Add trigger definitions to your `config.toml`:

```toml
[triggers.error_detector]
# Match conditions
match = {
    pattern = "ERROR|CRITICAL",  # Regular expression
    case_sensitive = false,
    from_devices = ["monitoring"]  # Optional: only from these devices
}
# Action to execute
action = {
    template = "notify-send 'Error from {source_device}: {match_text}'",
    target_session = "alerts",
    # Send notification back via Pushbullet
    send_to_pushbullet = true,
    target_device = "{source_device}",  # Dynamic device targeting
    pushbullet_title = "Error Processed"
}
# Execution conditions
conditions = {
    cooldown = 60,  # Seconds before can trigger again
    max_per_hour = 10,  # Maximum triggers per hour
    execute_once = false  # If true, only executes once
}
```

## Match Configuration

### Pattern Types

#### Regular Expression (default)
```toml
match = {
    pattern = "deploy (\\w+) to (\\w+)",  # Capture groups
    regex = true  # Optional, default is true
}
```

#### Simple String Matching
```toml
match = {
    pattern = "exact text to match",
    regex = false,
    case_sensitive = true
}
```

### Device Filtering
```toml
match = {
    pattern = "admin command",
    from_devices = ["admin-phone", "admin-laptop"]
}
```

## Action Configuration

### Command Template

Templates support variable substitution:

```toml
action = {
    template = "process.sh '{message}' --from={source_device} --time={timestamp}"
}
```

Available variables:
- `{message}` - Full original message
- `{source_device}` - Device that sent the message
- `{match}` or `{match_text}` - The matched portion of text
- `{group1}`, `{group2}`, etc. - Regex capture groups
- `{timestamp}` - ISO format timestamp
- `{date}` - Current date (YYYY-MM-DD)
- `{time}` - Current time (HH:MM:SS)
- Named capture groups from regex

### Pushbullet Notifications

Send notifications to specific devices:

```toml
action = {
    template = "handle_alert.sh",
    send_to_pushbullet = true,
    target_device = "admin-phone",  # Or use variables: "{source_device}_alerts"
    pushbullet_title = "Alert: {match_text}"
}
```

### Target Session

Route commands to specific tmux sessions:

```toml
action = {
    template = "tail -f /var/log/{group1}.log",
    target_session = "logs_{group1}"  # Dynamic session names
}
```

## Execution Conditions

### Cooldown Period

Prevent rapid re-triggering:

```toml
conditions = {
    cooldown = 300  # 5 minutes between triggers
}
```

### Rate Limiting

Limit triggers per hour:

```toml
conditions = {
    max_per_hour = 20  # Maximum 20 times per hour
}
```

### Execute Once

For one-time actions:

```toml
conditions = {
    execute_once = true  # Only runs once until restart
}
```

## Examples

### Error Monitoring

```toml
[triggers.error_monitor]
match = {
    pattern = "(ERROR|CRITICAL|FATAL): (.+)",
    from_devices = ["app-server", "db-server"]
}
action = {
    template = "echo '[{timestamp}] {group1} from {source_device}: {group2}' >> /var/log/alerts.log",
    send_to_pushbullet = true,
    target_device = "ops-team",
    pushbullet_title = "{group1} Alert"
}
conditions = {
    cooldown = 60,
    max_per_hour = 50
}
```

### Deployment Trigger

```toml
[triggers.deploy]
match = {
    pattern = "deploy branch:(\\w+) env:(\\w+)",
    from_devices = ["ci-server", "admin"]
}
action = {
    template = "cd /app && git checkout {group1} && ./deploy.sh {group2}",
    target_session = "deploy",
    send_to_pushbullet = true,
    target_device = "{source_device}",
    pushbullet_title = "Deployment started: {group1} to {group2}"
}
conditions = {
    execute_once = true  # Prevent accidental re-deployment
}
```

### Database Backup

```toml
[triggers.backup]
match = {
    pattern = "backup database (\\w+)",
    from_devices = ["admin", "backup-scheduler"]
}
action = {
    template = "pg_dump {group1} > /backups/{group1}_{date}_{time}.sql && echo 'Backup completed'",
    target_session = "maintenance",
    send_to_pushbullet = true,
    target_device = "{source_device}",
    pushbullet_title = "Backup completed: {group1}"
}
conditions = {
    cooldown = 3600  # One hour minimum between backups
}
```

### Log Search

```toml
[triggers.log_search]
match = {
    pattern = "search logs?: (.+)",
    case_sensitive = false
}
action = {
    template = "grep -i '{group1}' /var/log/*.log | tail -20",
    target_session = "search",
    send_to_pushbullet = true,
    target_device = "{source_device}",
    pushbullet_title = "Log search results for: {group1}"
}
```

### System Monitoring

```toml
[triggers.cpu_alert]
match = {
    pattern = "CPU: (\\d+)%",
    from_devices = ["monitoring"]
}
action = {
    template = "if [ {group1} -gt 80 ]; then systemctl restart app-service; echo 'Service restarted due to high CPU'; fi",
    target_session = "system",
    send_to_pushbullet = true,
    target_device = "admin",
    pushbullet_title = "High CPU Alert: {group1}%"
}
conditions = {
    cooldown = 300  # Don't restart more than once per 5 minutes
}
```

### Command Relay

```toml
[triggers.relay]
match = {
    pattern = "relay to (\\w+): (.+)",
    from_devices = ["controller"]
}
action = {
    template = "{group2}",  # Execute the command as-is
    target_session = "{group1}",  # Route to specified session
    send_to_pushbullet = true,
    target_device = "{group1}",  # Also notify the target device
    pushbullet_title = "Command from {source_device}"
}
```

## Security Considerations

### Command Injection Protection

Add a safety trigger to detect potential injection attempts:

```toml
[triggers.security_check]
match = {
    pattern = ";|&&|\\||`|\\$\\(",
    regex = true
}
action = {
    template = "echo 'Blocked suspicious command from {source_device}' >> /var/log/security.log",
    send_to_pushbullet = true,
    target_device = "security-admin",
    pushbullet_title = "Security Alert"
}
conditions = {
    max_per_hour = 100
}
```

### Device Restrictions

Always use `from_devices` for sensitive operations:

```toml
match = {
    pattern = "shutdown|restart|rm -rf",
    from_devices = ["admin-authorized-device"]
}
```

## Trigger Priority

When multiple triggers match a message, all matching triggers are executed in the order they appear in the configuration file.

## Testing Triggers

Test your triggers by sending messages to your device:

1. Simple test:
   ```
   ERROR: Test error message
   ```

2. With capture groups:
   ```
   deploy feature-branch to staging
   ```

3. Check execution:
   - View tmux session for command output
   - Check Pushbullet for notifications
   - Review logs for trigger activity

## Troubleshooting

### Trigger Not Firing

1. Check pattern syntax (test with online regex tools)
2. Verify device is in `from_devices` list
3. Check cooldown and rate limiting conditions
4. Ensure target tmux session exists
5. Run with `--debug` flag to see matching details

### Variable Not Substituting

1. Check variable name spelling
2. Ensure capture groups are properly defined
3. Use named groups for clarity: `(?P<name>\\w+)`

### Performance Considerations

- Complex regex patterns may slow down message processing
- Use specific `from_devices` filters to reduce processing
- Set appropriate rate limits to prevent resource exhaustion