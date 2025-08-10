# Slash Command Usage Examples

## Setup

1. Add slash command definitions to your `config.toml`:

```toml
[slash_commands.deploy]
template = "cd /app && git checkout {branch} && npm run deploy"
defaults = { branch = "main" }
allowed_devices = ["server"]

[slash_commands.test]
template = "pytest {path} -v {options}"
defaults = { path = ".", options = "" }

[slash_commands.restart]
template = "sudo systemctl restart {service}"
defaults = { service = "nginx" }
```

2. Start the listener:

```bash
push-tmux start
```

## Sending Commands

Send messages to your device via Pushbullet:

### Basic Usage
```
/deploy
```
Executes: `cd /app && git checkout main && npm run deploy`

### With Arguments
```
/deploy branch:feature-xyz
```
Executes: `cd /app && git checkout feature-xyz && npm run deploy`

### Multiple Arguments
```
/test path:tests/unit options:--coverage
```
Executes: `pytest tests/unit -v --coverage`

### Service Restart
```
/restart service:postgresql
```
Executes: `sudo systemctl restart postgresql`

## Argument Formats

You can use either colon (`:`) or equals (`=`) for arguments:

- `/command key:value`
- `/command key=value`
- `/command key1:value1 key2=value2`

## Advanced Features

### Device Restrictions

Commands with `allowed_devices` will only run on specified devices:

```toml
[slash_commands.production_deploy]
template = "kubectl apply -f production.yaml"
allowed_devices = ["production-server"]
```

### Target Session

Route commands to specific tmux sessions:

```toml
[slash_commands.monitor]
template = "htop"
target_session = "monitoring"
```

### Execute Once

Prevent duplicate executions:

```toml
[slash_commands.backup]
template = "pg_dump mydb > backup.sql"
execute_once = true
```

## Real-World Examples

### Git Operations
```toml
[slash_commands.pull]
template = "cd {repo} && git pull origin {branch}"
defaults = { repo = "/home/user/project", branch = "main" }
```

Send: `/pull branch:develop`

### Docker Management
```toml
[slash_commands.docker]
template = "docker-compose {action} {service}"
defaults = { action = "restart", service = "" }
```

Send: `/docker action:up service:web`

### Log Monitoring
```toml
[slash_commands.logs]
template = "tail -f {file} | grep -E '{pattern}'"
defaults = { file = "/var/log/app.log", pattern = "ERROR|WARNING" }
target_session = "logs"
```

Send: `/logs pattern:CRITICAL`

### SSH Connections
```toml
[slash_commands.ssh]
template = "ssh {user}@{host}"
defaults = { user = "admin" }
```

Send: `/ssh host:192.168.1.100 user:root`