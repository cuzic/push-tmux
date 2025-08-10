# Slash Commands

push-tmux supports slash commands that allow you to send templated commands to tmux sessions via Pushbullet messages.

## Overview

Slash commands provide a way to:
- Define command templates in `config.toml`
- Send commands with optional arguments via device messages
- Control which devices can execute specific commands
- Route commands to specific tmux sessions
- Execute commands only once (trigger conditions)

## Configuration

Add slash command definitions to your `config.toml`:

```toml
[slash_commands.deploy]
# Template with placeholders
template = "cd /app && git checkout {branch} && docker-compose up -d {service}"
# Default values for optional arguments
defaults = { branch = "main", service = "all" }
# Optional: restrict to specific devices
allowed_devices = ["production-server", "staging-server"]
# Optional: specify target tmux session
target_session = "deploy"
# Optional: execute only once
execute_once = true
```

## Usage

Send a message to your device with a slash command:

```
/deploy branch:feature service:api
```

This will expand to:
```
cd /app && git checkout feature && docker-compose up -d api
```

### Argument Formats

Arguments can be specified in multiple formats:
- Colon format: `/command key:value`
- Equals format: `/command key=value`
- Mixed format: `/command key1:value1 key2=value2`
- Positional arguments: `/command arg1 arg2` (accessed as `{arg0}`, `{arg1}`)

### Examples

#### Basic Commands

```toml
[slash_commands.test]
template = "pytest {path} -v"
defaults = { path = "." }
```

Send: `/test path:tests/unit`
Executes: `pytest tests/unit -v`

#### Service Management

```toml
[slash_commands.restart]
template = "sudo systemctl restart {service}"
defaults = { service = "nginx" }
allowed_devices = ["server"]
```

Send: `/restart service:postgresql`
Executes: `sudo systemctl restart postgresql` (only on "server" device)

#### Database Operations

```toml
[slash_commands.backup]
template = "pg_dump {database} > backup_{database}_{timestamp}.sql"
defaults = { database = "myapp", timestamp = "$(date +%Y%m%d_%H%M%S)" }
execute_once = true
```

Send: `/backup database:production`
Executes: `pg_dump production > backup_production_$(date +%Y%m%d_%H%M%S).sql` (only once)

#### Remote Access

```toml
[slash_commands.ssh]
template = "ssh {user}@{host} -p {port}"
defaults = { user = "admin", port = "22" }
```

Send: `/ssh host:192.168.1.100 user:root port:2222`
Executes: `ssh root@192.168.1.100 -p 2222`

#### Monitoring

```toml
[slash_commands.log]
template = "tail -f {file} | grep {filter}"
defaults = { file = "/var/log/app.log", filter = "ERROR" }
target_session = "monitoring"
```

Send: `/log filter:WARNING`
Executes: `tail -f /var/log/app.log | grep WARNING` (in "monitoring" tmux session)

## Advanced Features

### Device Restrictions

Use `allowed_devices` to limit command execution to specific devices:

```toml
[slash_commands.dangerous_command]
template = "sudo rm -rf {path}"
allowed_devices = ["admin-device"]  # Only "admin-device" can run this
```

### Target Sessions

Route commands to specific tmux sessions:

```toml
[slash_commands.monitor]
template = "htop"
target_session = "system"  # Always runs in "system" session
```

### Execute Once

Prevent duplicate executions:

```toml
[slash_commands.migration]
template = "python manage.py migrate"
execute_once = true  # Will only run once per session
```

### Session Override

Override the target session in the command:

```
/deploy branch:main session:production
```

## Security Considerations

1. **Device Restrictions**: Always use `allowed_devices` for sensitive commands
2. **Template Validation**: Ensure templates don't contain unescaped user input
3. **Defaults**: Set safe default values to prevent accidental damage
4. **Execute Once**: Use for destructive or expensive operations

## Troubleshooting

### Command Not Executing

1. Check if the command is defined in `config.toml`
2. Verify device is in `allowed_devices` list (if specified)
3. Check if `execute_once` is preventing re-execution
4. Ensure target tmux session exists

### Argument Issues

1. Verify argument names match template placeholders
2. Check default values are provided for optional arguments
3. Use quotes for values with spaces: `/command arg:"value with spaces"`

### Debug Mode

Run listener with debug flag to see command expansion:

```bash
push-tmux start --debug
```

## Examples Configuration File

See `examples/config_slash_commands.toml` for a complete configuration example with various slash command definitions.