# Pattern-Based Triggers

push-tmux supports pattern-based triggers that automatically execute commands when incoming messages match specific patterns.

## Overview

Triggers provide:
- Pattern matching on incoming messages (regex or simple text)
- Device-based filtering (only trigger from specific devices)
- Command execution with variable substitution
- Rate limiting and cooldown periods
- Execute-once conditions for one-time triggers
- Dynamic tmux session routing based on target device name

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
    target_device = "alerts"  # Target device name (maps to tmux session)
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

### Target Device (Session Routing)

Route commands to specific tmux sessions based on device name:

```toml
action = {
    template = "handle_alert.sh",
    target_device = "monitoring"  # Routes to 'monitoring' tmux session
}
```

Dynamic routing using variables:

```toml
action = {
    template = "process_log.sh",
    target_device = "{source_device}_logs"  # e.g., "server_logs" session
}
```

#### Mapping Tables

Use mapping tables to translate values to session names:

```toml
action = {
    template = "deploy.sh",
    target_device = "{group1}",
    mapping = {
        "dev" = "development",
        "prod" = "production",
        "test" = "testing"
    }
}
```

#### String Transformation Functions

Apply string functions to transform the target device name:

```toml
action = {
    template = "process.sh",
    target_device = "{group1}",
    transforms = [
        "lower()",           # Convert to lowercase
        "upper()",           # Convert to uppercase
        "substr(0, 5)",      # Substring (start, length)
        "replace(-, _)",     # Replace characters
        "prefix(session_)",  # Add prefix
        "suffix(_logs)",     # Add suffix
        "truncate(15)"       # Limit length
    ]
}
```

Transformations are applied in sequence after mapping:

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

### Using Mapping and Transforms

```toml
[triggers.environment_router]
match = {
    pattern = "deploy to (\\w+)",
    from_devices = ["ci-server"]
}
action = {
    template = "cd /app && deploy.sh",
    target_device = "{group1}",
    # First apply mapping
    mapping = {
        "dev" = "development-server",
        "prod" = "production-server"
    },
    # Then apply transforms
    transforms = [
        "suffix(_deploy)",
        "truncate(20)"
    ]
}
```

For message "deploy to dev":
1. Captures "dev" as group1
2. Maps "dev" → "development-server"
3. Applies suffix → "development-server_deploy"
4. Truncates to 20 chars → "development-server_d"

### Complex Session Naming

```toml
[triggers.branch_router]
match = {
    pattern = "build branch:(\\S+)"
}
action = {
    template = "git checkout {group1} && make build",
    target_device = "{group1}",
    transforms = [
        "lower()",          # feature/NEW-123 → feature/new-123
        "replace(/, _)",    # feature/new-123 → feature_new-123
        "prefix(build_)",   # feature_new-123 → build_feature_new-123
        "truncate(15)"      # build_feature_new-123 → build_feature_n
    ]
}
```

### Error Monitoring

```toml
[triggers.error_monitor]
match = {
    pattern = "(ERROR|CRITICAL|FATAL): (.+)",
    from_devices = ["app-server", "db-server"]
}
action = {
    template = "echo '[{timestamp}] {group1} from {source_device}: {group2}' >> /var/log/alerts.log",
    target_device = "ops-monitoring"  # Routes to ops-monitoring tmux session
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
    target_device = "deploy"  # Routes to deploy tmux session
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
    target_device = "maintenance"  # Routes to maintenance tmux session
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
    target_device = "search"  # Routes to search tmux session
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
    target_device = "system"  # Routes to system tmux session
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
    target_device = "{group1}"  # Route to specified device/session
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
    target_device = "security"  # Routes to security tmux session
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

## How It Works

1. **Message Reception**: When a message arrives from a Pushbullet device
2. **Pattern Matching**: The message is checked against all trigger patterns
3. **Device Filtering**: Only triggers with matching `from_devices` (if specified) proceed
4. **Condition Checking**: Cooldown, rate limiting, and execute-once conditions are verified
5. **Variable Expansion**: Template variables are replaced with actual values
6. **Session Routing**: Command is sent to the tmux session named by `target_device`
7. **Execution**: The expanded command is executed in the target tmux session

The `target_device` field serves as both:
- A way to specify which tmux session should receive the command
- A dynamic routing mechanism when using variables like `{source_device}` or `{group1}`

This design follows the push-tmux philosophy where device names map directly to tmux session names, enabling seamless message routing.