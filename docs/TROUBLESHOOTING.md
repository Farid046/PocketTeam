# Troubleshooting Guide

Common issues and how to fix them.

## Installation & Setup

### "pocketteam: command not found"

**Problem**: The CLI is not in your PATH after installation.

**Solution**:

```bash
# Re-install from source
pip install -e .

# Or add to PATH manually
export PATH="$PATH:$(python -c 'import site; print(site.USER_SITE)')/bin"
```

### "Claude Code not found"

**Problem**: PocketTeam cannot detect Claude Code installation.

**Solution**:

Claude Code is built into Claude's web interface. If you're running PocketTeam in a headless environment:

1. **Verify you're in Claude Code**:
   - Open claude.ai in a browser
   - Click "Use code" to activate Claude Code
   - Run `pocketteam --version` in the terminal

2. **Check working directory**:
   ```bash
   pwd  # Should show a project directory
   pocketteam init  # Initialize the project
   ```

3. **If in a container/VM**, ensure:
   - Claude Code is active (not in chat-only mode)
   - Terminal access is enabled
   - `/tmp` is writable for temporary files

### ".pocketteam directory missing"

**Problem**: Config directory doesn't exist after `pocketteam init`.

**Solution**:

```bash
# Re-initialize
pocketteam init --name my-project

# Verify creation
ls -la .pocketteam/

# Check permissions
chmod -R 755 .pocketteam/
```

## Configuration Issues

### "Config file not found"

**Problem**: `.pocketteam/config.yaml` doesn't exist or is unreadable.

**Solution**:

```bash
# Check if file exists
ls -la .pocketteam/config.yaml

# If not, initialize
pocketteam init

# If permission denied, fix permissions
chmod 600 .pocketteam/config.yaml
```

### "Invalid configuration"

**Problem**: YAML syntax error in config file.

**Solution**:

```bash
# Validate config
pocketteam config validate

# View errors
pocketteam config check

# Edit and fix YAML syntax
nano .pocketteam/config.yaml
# Common issues: missing colons, bad indentation, unquoted strings
```

### "Environment variable not resolved"

**Problem**: Config shows `$ANTHROPIC_API_KEY` instead of the actual value.

**Solution**:

```bash
# Check if variable is set
echo $ANTHROPIC_API_KEY

# If empty, load from .env
source .pocketteam/.env

# Verify it's loaded
echo $ANTHROPIC_API_KEY  # Should show the actual key

# Re-run the command
pocketteam agent run --task "..."
```

## Authentication Issues

### "API key invalid or unauthorized"

**Problem**: Anthropic API returns 401 Unauthorized.

**Solution**:

1. **Check the key is valid**:
   ```bash
   cat .pocketteam/.env | grep ANTHROPIC_API_KEY
   # Should be: sk-ant-... (not empty or malformed)
   ```

2. **Check key permissions**:
   - Log in to console.anthropic.com
   - Check that the key has usage enabled
   - Verify billing is active

3. **Switch to subscription mode**:
   ```bash
   pocketteam config set auth.mode subscription
   ```
   (Uses Claude Code's included tokens instead)

4. **Check network connectivity**:
   ```bash
   curl https://api.anthropic.com/health
   ```

### "Telegram token invalid"

**Problem**: Telegram returns 401 or bot doesn't respond.

**Solution**:

1. **Verify the token**:
   ```bash
   cat .pocketteam/.env | grep TELEGRAM_BOT_TOKEN
   # Should be: 123456:ABC-DEF... (not empty)
   ```

2. **Test the token**:
   ```bash
   curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" | jq .
   # Should return bot info, not {"ok": false}
   ```

3. **Regenerate the token**:
   - Message @BotFather on Telegram
   - Select your bot
   - Run `/token`
   - Copy the new token to `.pocketteam/.env`

4. **Check chat ID**:
   ```bash
   cat .pocketteam/config.yaml | grep chat_id
   # Should be a valid number, not empty
   ```

### "Bearer token expired"

**Problem**: Dashboard shows "Unauthorized" or WebSocket disconnects.

**Solution**:

The auth token in the dashboard URL expires after 60 minutes of inactivity.

1. **Refresh the dashboard page**:
   - Close the tab/window
   - Restart the dashboard: `pocketteam skill run dashboard-deploy`
   - Open the new URL

2. **Check token in URL**:
   ```
   http://localhost:3847/?token=abc123...
   # Token should be present and valid
   ```

## Telegram Integration

### "Telegram messages not arriving"

**Problem**: COO doesn't receive messages from Telegram.

**Solution**:

1. **Check that Telegram is configured**:
   ```bash
   pocketteam config show telegram
   # Should show bot_token and chat_id
   ```

2. **Verify the chat ID**:
   - Send any message to the bot in the chat
   - Check the logs: `tail -f .pocketteam/telegram-inbox.jsonl`
   - Look for the most recent entry with your chat ID

3. **Test manually**:
   ```bash
   curl -X POST \
     -H 'Content-Type: application/json' \
     -d '{"chat_id": "YOUR_CHAT_ID", "text": "Test message"}' \
     "https://api.telegram.org/botYOUR_TOKEN/sendMessage"
   ```

4. **Check inbox file**:
   ```bash
   tail -f .pocketteam/telegram-inbox.jsonl
   # Should show incoming messages with status "received"
   ```

### "Telegram messages delivered but COO not resuming"

**Problem**: Messages appear in inbox but COO doesn't respond.

**Solution**:

1. **Check auto_resume setting**:
   ```bash
   pocketteam config show telegram
   # Should show auto_resume: true
   ```

2. **Check session status**:
   ```bash
   pocketteam agent status coo
   # Should show IDLE or RUNNING, not PAUSED
   ```

3. **Manually resume**:
   ```bash
   pocketteam session resume
   ```

### "Telegram inbox grows too large"

**Problem**: `.pocketteam/telegram-inbox.jsonl` becomes very large.

**Solution**:

Archive old messages:

```bash
# Backup the inbox
cp .pocketteam/telegram-inbox.jsonl .pocketteam/telegram-inbox.backup.jsonl

# Keep only last N days (example: keep 7 days)
python -c "
import json
from datetime import datetime, timedelta
from pathlib import Path

inbox = Path('.pocketteam/telegram-inbox.jsonl')
cutoff = datetime.now() - timedelta(days=7)

with open(inbox) as f:
    lines = [
        line for line in f
        if datetime.fromisoformat(json.loads(line)['ts'].replace('Z', '+00:00')) > cutoff
    ]

with open(inbox, 'w') as f:
    f.writelines(lines)
"

# Or truncate completely
> .pocketteam/telegram-inbox.jsonl
```

## Dashboard Issues

### "Dashboard fails to start"

**Problem**: `docker compose up` fails or port is already in use.

**Solution**:

1. **Check Docker is running**:
   ```bash
   docker ps
   # If error, start Docker: `docker daemon start` or open Docker Desktop
   ```

2. **Check port availability**:
   ```bash
   lsof -i :3847
   # If occupied, kill the process or use a different port:
   pocketteam config set dashboard.port 3848
   ```

3. **Check docker-compose version**:
   ```bash
   docker compose version
   # Should be v2.0 or later
   # If v1, set in config: pocketteam config set dashboard.compose_command "docker-compose"
   ```

4. **Check logs**:
   ```bash
   docker compose -f .pocketteam/docker-compose.yml logs
   # Will show the actual error
   ```

5. **Clean up**:
   ```bash
   # Stop all containers
   docker compose -f .pocketteam/docker-compose.yml down

   # Remove image and retry
   docker rmi pocketteam-dashboard:1.0.0
   pocketteam skill run dashboard-deploy
   ```

### "Dashboard shows "Unauthorized" or blank page"

**Problem**: Can't access the dashboard or see 401 errors.

**Solution**:

1. **Check the access URL**:
   - When you run `dashboard-deploy`, it prints: `Dashboard running at: http://localhost:3847?token=abc123...`
   - Make sure you're using the full URL with the `?token=` parameter

2. **Verify auth token is in the URL**:
   ```bash
   # Good:
   http://localhost:3847?token=abc123def456...

   # Bad:
   http://localhost:3847/  # Missing token
   ```

3. **Regenerate token**:
   ```bash
   docker compose -f .pocketteam/docker-compose.yml restart
   # Then run `pocketteam skill run dashboard-deploy` again for a new token
   ```

4. **Check browser console**:
   - Open DevTools (F12)
   - Check Console and Network tabs
   - Look for 401 errors on WebSocket connection
   - Note the error message and check Bearer token format

### "Dashboard not updating in real-time"

**Problem**: Events appear with delay or don't update at all.

**Solution**:

1. **Check WebSocket connection**:
   - Open DevTools (F12)
   - Go to Network tab → WS (WebSocket)
   - Look for a connection to `ws://localhost:3847/api/v1/ws`
   - Status should be "101 Switching Protocols" (green)

2. **If no WebSocket**:
   ```bash
   # Check dashboard logs
   docker logs $(docker ps -q -f "ancestor=pocketteam-dashboard:1.0.0")

   # Restart dashboard
   docker compose -f .pocketteam/docker-compose.yml restart
   ```

3. **If WebSocket is red**:
   - Token may have expired
   - Refresh the page to get a new token
   - Try a different browser

4. **Check events are being written**:
   ```bash
   tail -f .pocketteam/events/stream.jsonl
   # Should show new lines when agents run
   ```

### "Dashboard times out or runs slowly"

**Problem**: Dashboard is unresponsive or takes >5s to load.

**Solution**:

1. **Check system resources**:
   ```bash
   docker stats
   # Dashboard container should use <200MB RAM
   # If more, there's a memory leak
   ```

2. **Check network latency**:
   ```bash
   ping localhost
   # Should be <5ms
   ```

3. **Clear browser cache**:
   - DevTools → Application → Clear Storage
   - Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)

4. **Reduce event history**:
   ```bash
   # Dashboard keeps last 100 events in memory
   # If .pocketteam/events/stream.jsonl is huge, restart:
   docker compose -f .pocketteam/docker-compose.yml restart
   ```

## Agent Issues

### "Agent timeout (max turns exceeded)"

**Problem**: Agent reaches max turns and stops without completing the task.

**Solution**:

1. **Check max turns for the agent**:
   ```bash
   grep "<agent-name>" pocketteam/constants.py | grep AGENT_MAX_TURNS
   # Example: "planner": 25 turns
   ```

2. **Break the task into smaller pieces**:
   ```
   pocketteam agent run --agent engineer --task "Implement part 1 of the feature"
   pocketteam agent run --agent engineer --task "Implement part 2 of the feature"
   ```

3. **Upgrade the agent to a better model**:
   ```
   ralph: implement this complex feature
   # ralph: mode upgrades engineer to Opus if needed
   ```

4. **Increase max turns** (advanced):
   - Edit `pocketteam/constants.py`
   - Change `AGENT_MAX_TURNS["<agent-name>"]` to a higher value
   - Restart PocketTeam

### "Agent exceeds budget limit"

**Problem**: Agent's estimated cost exceeds the per-agent budget.

**Solution**:

1. **Check the budget for the agent**:
   ```bash
   grep "<agent-name>" pocketteam/constants.py | grep AGENT_BUDGETS
   # Example: "engineer": 5.0 USD
   ```

2. **Only in API key mode** (subscription mode has no budget limits):
   ```bash
   pocketteam config show auth
   # Check the mode
   ```

3. **Options**:
   - Switch to subscription mode: `pocketteam config set auth.mode subscription`
   - Break the task into smaller pieces (use cheaper agents first)
   - Increase the per-task budget: `pocketteam config set budget.max_per_task 10.0`

### "Agent produces low-quality output"

**Problem**: Agent's work is incomplete, has errors, or doesn't match the task.

**Solution**:

1. **Use the Reviewer agent**:
   ```bash
   pocketteam agent run --agent reviewer --task "Review this code: ..."
   ```

2. **Provide more context**:
   - Include relevant files and examples
   - Describe success criteria clearly
   - Note constraints and edge cases

3. **Upgrade the agent model**:
   ```
   ralph: <task>
   # Upgrades engineer to Opus for complex tasks
   ```

4. **Check the agent's transcript**:
   ```bash
   ls -la .pocketteam/sessions/
   # Find the latest session
   cat .pocketteam/sessions/session-*.jsonl | tail -50
   # Review the agent's reasoning
   ```

## Monitoring Issues

### "Monitor agent not running"

**Problem**: 24/7 health checks are disabled.

**Solution**:

```bash
# Enable monitoring
pocketteam config set monitoring.enabled true

# Check status
pocketteam monitor status

# Start monitor manually
pocketteam monitor start
```

### "Monitor auto-fix not working"

**Problem**: Health checks pass/fail but fixes don't run.

**Solution**:

1. **Check auto-fix is enabled**:
   ```bash
   pocketteam config show monitoring
   # Should show auto_fix: true
   ```

2. **Check health URL is valid**:
   ```bash
   curl -s $(pocketteam config show | grep health_url | cut -d: -f2)
   # Should return {"status": "ok"} or similar
   ```

3. **Check max_fix_attempts**:
   ```bash
   pocketteam config show monitoring
   # Default: 3 attempts, then escalate
   ```

4. **View monitor logs**:
   ```bash
   tail -f .pocketteam/artifacts/audit/$(date +%Y-%m-%d).jsonl
   # Will show monitor actions and results
   ```

## Network & Connectivity

### "Network allowlist error"

**Problem**: Tool call is blocked because domain is not approved.

**Solution**:

1. **Check the error**:
   ```
   Error: domain "example.com" not in approved_domains
   ```

2. **Add the domain**:
   ```bash
   pocketteam config set network.approved_domains '["api.example.com"]'
   ```

3. **Or edit config directly**:
   ```yaml
   network:
     approved_domains:
       - api.example.com
       - cdn.example.com
   ```

4. **Verify it was added**:
   ```bash
   pocketteam config show network
   ```

## Logs & Debugging

### "Enable debug logging"

```bash
# In bash
export LOGLEVEL=DEBUG
pocketteam agent run --task "..."

# Or in Claude Code terminal
LOGLEVEL=DEBUG python -m pocketteam agent run --task "..."
```

### "View event stream"

```bash
# Real-time
tail -f .pocketteam/events/stream.jsonl

# Pretty-printed
python -c "
import json
with open('.pocketteam/events/stream.jsonl') as f:
    for line in f:
        print(json.dumps(json.loads(line), indent=2))
"

# Filter by agent
grep '"agent": "engineer"' .pocketteam/events/stream.jsonl

# Filter by timestamp (last hour)
python -c "
import json
from datetime import datetime, timedelta
cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
with open('.pocketteam/events/stream.jsonl') as f:
    for line in f:
        obj = json.loads(line)
        if obj['ts'] > cutoff:
            print(json.dumps(obj, indent=2))
"
```

### "View audit trail"

```bash
# Today's audit log
cat .pocketteam/artifacts/audit/$(date +%Y-%m-%d).jsonl | tail -20

# Search for specific action
grep '"action": ".*code.*"' .pocketteam/artifacts/audit/$(date +%Y-%m-%d).jsonl
```

### "Export logs for debugging"

```bash
# Tar up all artifacts
tar czf pocketteam-logs.tar.gz .pocketteam/artifacts/ .pocketteam/events/

# Share with the team (redact secrets first!)
```

## Getting Help

1. **Check the docs**: https://github.com/farid046/pocketteam/tree/main/docs
2. **Search issues**: https://github.com/farid046/pocketteam/issues
3. **Open a new issue** with:
   - Error message (full output)
   - Command you ran
   - Config relevant section (redact secrets)
   - Logs from `.pocketteam/` directory (redacted)
4. **Contact the team** via GitHub Discussions

## Reporting Bugs

Include:
- PocketTeam version: `pocketteam --version`
- Python version: `python --version`
- OS: `uname -a`
- Error message (full traceback)
- Steps to reproduce
- Relevant files (config, logs, etc.) with secrets redacted
