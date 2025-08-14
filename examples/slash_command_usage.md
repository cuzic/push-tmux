# Slash Command Usage Examples

## New: Fallback Behavior for Undefined Commands

Starting from the latest version, push-tmux can handle undefined slash commands gracefully. This ensures compatibility with other tools like claude-code that use slash commands.

### Configuration

```toml
[slash_commands_settings]
# Enable fallback for undefined slash commands (default: true)
# When true, undefined commands like /login will be sent as normal messages
# When false, undefined commands will show an error message (legacy behavior)
fallback_undefined = true
```

### Behavior Examples

With `fallback_undefined = true` (default):
- `/deploy` (defined) → Executes custom command
- `/login` (undefined) → Sent as "/login" to tmux
- `hello` (no slash) → Sent as "hello" to tmux

With `fallback_undefined = false` (legacy):
- `/deploy` (defined) → Executes custom command
- `/login` (undefined) → Shows error "Unknown command: /login"
- `hello` (no slash) → Sent as "hello" to tmux

## Setup

1. Add slash command definitions to your `config.toml`:

```toml
# Optional: Configure fallback behavior
[slash_commands_settings]
fallback_undefined = true  # default value

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

## Timer Commands (New!)

push-tmux now supports delayed execution of commands using the `delay_seconds` configuration or `delay` argument.

### Configuration

```toml
[slash_commands.timer]
template = "echo '⏰ {message}'"
defaults = { message = "Timer finished!" }
delay_seconds = 10  # Execute after 10 seconds

[slash_commands.pomodoro]
template = "echo '🍅 Pomodoro finished! Take a break.'"
delay_seconds = 1500  # 25 minutes
```

### Usage Examples

1. **Basic timer (10 seconds default)**:
   ```
   /timer
   ```
   Output: ⏰ Timer set for 10 seconds

2. **Custom delay**:
   ```
   /timer delay:30 message:"Meeting starting!"
   ```
   Output: ⏰ Timer set for 30 seconds

3. **Pomodoro timer**:
   ```
   /pomodoro
   ```
   Output: ⏰ Timer set for 1500 seconds (25 minutes)

4. **Quick reminder**:
   ```
   /reminder delay:120 text:"Check the build"
   ```
   Output: ⏰ Timer set for 120 seconds

### Features

- **Non-blocking**: Timers run asynchronously without blocking tmux
- **Multiple timers**: Run multiple timers simultaneously
- **Dynamic delays**: Override default delay with `delay` argument
- **Immediate feedback**: Get confirmation when timer is set

### Practical Use Cases

1. **Pomodoro Technique**:
   ```toml
   [slash_commands.work]
   template = "echo '💼 Work session started'"
   delay_seconds = 1500  # 25 minutes
   
   [slash_commands.break]
   template = "echo '☕ Take a 5-minute break'"
   delay_seconds = 300  # 5 minutes
   ```

2. **Meeting Reminders**:
   ```
   /reminder delay:600 text:"Team standup in 10 minutes"
   ```

3. **Build Notifications**:
   ```
   /timer delay:180 message:"Check CI/CD pipeline"
   ```

4. **Multiple Timers**:
   ```
   /timer delay:60 message:"1 minute"
   /timer delay:120 message:"2 minutes"
   /timer delay:180 message:"3 minutes"
   ```
   All three timers run concurrently!

## Built-in Commands

push-tmux includes several built-in commands that provide special functionality beyond simple command execution.

### /capture - Capture tmux Pane Content

The `/capture` command captures the content of a tmux pane and sends it back to the requesting device via Pushbullet.

#### Usage

1. **Capture current pane**:
   ```
   /capture
   ```
   Captures the content of the currently active tmux pane.

2. **Capture specific pane by pts**:
   ```
   /capture pts/3
   ```
   Captures the content of the pane with pts/3.

3. **Capture by session:window.pane**:
   ```
   /capture mysession:0.1
   ```
   Captures content from session "mysession", window 0, pane 1.

#### Features

- **Content Reply**: Captured content is sent back to the device that sent the command
- **Automatic Truncation**: Long content is truncated to 4096 characters to fit Pushbullet limits
- **Error Handling**: Clear error messages if pane cannot be found or captured

#### Use Cases

1. **Remote Monitoring**:
   - Check log output from your phone
   - Monitor long-running processes
   - Review error messages

2. **Content Sharing**:
   - Share terminal output with team members
   - Save important command results
   - Document system states

3. **Debugging**:
   - Capture error messages for analysis
   - Review command history
   - Check application status

#### Example Workflow

1. Start a process in tmux:
   ```bash
   tmux new-session -s monitoring
   tail -f /var/log/application.log
   ```

2. From your phone, send via Pushbullet:
   ```
   /capture monitoring:0.0
   ```

3. Receive the log content back on your phone as a Pushbullet note.

#### Limitations

- Maximum 4096 characters per capture (Pushbullet API limit)
- Requires tmux to be running
- Source device must be registered with Pushbullet to receive replies