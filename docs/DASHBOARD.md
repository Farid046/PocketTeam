# Dashboard Documentation

The PocketTeam Dashboard is a real-time 3D isometric visualization of your AI team at work. It shows which agents are active, what they're doing, and how much they cost.

## Quick Start

### Deploy the Dashboard

```bash
pocketteam skill run dashboard-deploy
```

This will:
1. Build the Docker image
2. Start a container on port 3847
3. Print the access URL with auth token:
   ```
   Dashboard running at: http://localhost:3847?token=abc123def456...
   ```

### Access the Dashboard

Open the URL in your browser. You'll see:
- **Isometric Office**: Real-time 3D view of agents working
- **Event Feed**: Recent actions (agent spawned, tool used, completed)
- **Usage Panel**: Token and cost breakdown
- **Audit Trail**: Detailed logs of all actions

## Architecture

### Backend (Node.js + Express)

The dashboard backend runs in a Docker container and exposes:
- REST API at `/api/v1/*`
- WebSocket at `/ws` for real-time updates
- Static frontend at `/`

Key files:
- `dashboard/src/server/server.ts` — Express setup and routing
- `dashboard/src/server/api/routes.ts` — REST endpoints
- `dashboard/src/server/api/websocket.ts` — WebSocket handler
- `dashboard/src/server/auth.ts` — Bearer token authentication

### Frontend (React + TypeScript)

The dashboard frontend runs in the browser and:
- Connects via WebSocket for real-time updates
- Renders a 3D isometric office (Canvas + React)
- Manages state with Zustand
- No external dependencies (pixel-art style)

Key files:
- `dashboard/src/frontend/App.tsx` — Main entry point
- `dashboard/src/frontend/views/OfficeView.tsx` — 3D office visualization
- `dashboard/src/frontend/components/EventFeed.tsx` — Event list
- `dashboard/src/frontend/store/useStore.ts` — State management
- `dashboard/src/frontend/ws/useWebSocket.ts` — WebSocket client

### Data Sources

The backend reads from:
- `.pocketteam/events/stream.jsonl` — Agent lifecycle events
- `.pocketteam/artifacts/audit/` — Detailed action logs
- `.pocketteam/sessions/` — Active session state
- Subagent readers — Real-time agent status

## REST API Endpoints

All endpoints require Bearer token authentication (except `/health` which is public).

### GET /api/v1/health

Public health check endpoint.

**Response**:
```json
{
  "status": "ok"
}
```

**Use case**: Load balancers, monitoring services.

### GET /api/v1/agents

Get current state of all agents.

**Response**:
```json
[
  {
    "id": "agent-uuid",
    "type": "engineer",
    "status": "running",
    "sessionId": "session-123",
    "startedAt": "2026-03-26T10:15:00Z",
    "lastUpdate": "2026-03-26T10:15:05Z",
    "model": "claude-sonnet-4-6",
    "activity": "Implementing feature X",
    "toolCount": 5,
    "costUsd": 0.25
  },
  ...
]
```

**Fields**:
- `id`: Unique agent ID
- `type`: Agent type (engineer, qa, security, etc.)
- `status`: one of `idle`, `running`, `paused`, `error`
- `sessionId`: Current session ID
- `startedAt`: ISO 8601 timestamp
- `lastUpdate`: Last status update time
- `model`: Claude model being used
- `activity`: Brief description of current work
- `toolCount`: Number of tools executed in this run
- `costUsd`: Estimated cost so far

### GET /api/v1/events?limit=100

Get recent events from the event stream.

**Query parameters**:
- `limit` (optional): Max events to return. Default: 100. Max: 1000.

**Response**:
```json
[
  {
    "ts": "2026-03-26T10:15:00Z",
    "agent": "engineer",
    "type": "spawn",
    "status": "started",
    "action": "Implementing feature X",
    "agent_id": "agent-uuid",
    "model": "claude-sonnet-4-6"
  },
  {
    "ts": "2026-03-26T10:15:05Z",
    "agent": "engineer",
    "type": "tool_use",
    "tool": "Write",
    "status": "success",
    "action": "Created src/feature.ts"
  },
  {
    "ts": "2026-03-26T10:15:10Z",
    "agent": "engineer",
    "type": "complete",
    "status": "done",
    "action": "Finished (8 tool calls, 10s)",
    "agent_id": "agent-uuid"
  },
  ...
]
```

**Event types**:
- `spawn` — Agent started
- `tool_use` — Tool executed
- `complete` — Agent finished
- `error` — Agent error occurred

### GET /api/v1/audit?date=today

Get audit log entries for a specific date.

**Query parameters**:
- `date` (optional): Date to fetch. Only `today` is supported in v0.1. Default: today.

**Response**:
```json
[
  {
    "ts": "2026-03-26T10:15:00Z",
    "agent": "engineer",
    "action": "tool_use Write",
    "tool": "Write",
    "file": "src/feature.ts",
    "status": "success",
    "cost_usd": 0.05
  },
  ...
]
```

### GET /api/v1/audit/stats

Get aggregated audit statistics.

**Response**:
```json
{
  "total_actions": 150,
  "by_agent": {
    "engineer": 75,
    "qa": 40,
    "security": 20,
    "other": 15
  },
  "by_action": {
    "tool_use": 120,
    "spawn": 15,
    "complete": 15
  },
  "by_tool": {
    "Write": 40,
    "Bash": 35,
    "Read": 30,
    "Glob": 15
  },
  "total_cost_usd": 2.45,
  "errors": 3,
  "success_rate": 0.98
}
```

### GET /api/v1/usage?sessionId=...

Get token and cost usage for a session.

**Query parameters**:
- `sessionId` (optional): Session ID. If not provided, uses the latest session.

**Response**:
```json
{
  "sessionId": "session-123",
  "startedAt": "2026-03-26T10:00:00Z",
  "tokens": {
    "input": 15000,
    "output": 8000,
    "total": 23000
  },
  "cost": {
    "by_agent": {
      "planner": 0.50,
      "engineer": 1.25,
      "qa": 0.75,
      "reviewer": 0.30
    },
    "total_usd": 2.80,
    "estimated_daily": 3.36
  },
  "breakdown": {
    "subscription": 0.00,
    "api_key": 2.80
  }
}
```

### GET /api/v1/killswitch

Get kill switch status.

**Response**:
```json
{
  "active": false
}
```

If `active` is true, all agents are stopped.

### POST /api/v1/ws-ticket

Create a short-lived WebSocket upgrade ticket.

**Request**: None (Bearer token in header)

**Response**:
```json
{
  "ticket": "abc123def456...",
  "expiresAt": 1234567890000
}
```

**Use case**: Get a ticket to upgrade to WebSocket. Ticket is single-use with 60s TTL.

## WebSocket Messages

The dashboard connects to `ws://localhost:3847/api/v1/ws?ticket=<ticket>` for real-time updates.

All messages are JSON objects with `type` and `payload` fields:

```typescript
type WsMessage = {
  type: string;
  payload: unknown;
};
```

### Server → Client Messages

#### `snapshot`

Full state dump sent on first connection.

**Payload**:
```json
{
  "agents": [...],  // Array of AgentState
  "events": [...],  // Array of PocketTeamEvent
  "auditStats": {...},  // Aggregated AuditStats
  "auditEntries": [...],  // Last 100 AuditEntry
  "killSwitch": false,  // Boolean
  "sessionUsage": {...},  // SessionUsage or null
  "cooActivity": {...},  // COO activity or null
  "sessionStatus": {...}  // SessionStatus
}
```

#### `agent:spawned`

Agent was spawned.

**Payload**: `AgentState` (see `/agents` endpoint)

#### `agent:update`

Agent status changed.

**Payload**: `AgentState`

#### `agent:completed`

Agent finished (no longer running).

**Payload**:
```json
{
  "id": "agent-uuid",
  "duration": 45  // seconds
}
```

#### `event:new`

New event in the stream.

**Payload**: `PocketTeamEvent`

#### `audit:new`

New audit entry.

**Payload**: `AuditEntry`

#### `usage:update`

Token/cost usage updated.

**Payload**: `SessionUsage`

#### `killswitch:change`

Kill switch was activated or deactivated.

**Payload**:
```json
{
  "active": true  // or false
}
```

#### `session:status`

Session status changed (paused, resumed, etc.).

**Payload**: `SessionStatus`

### Client → Server Messages

Currently, the WebSocket is **one-way** (server → client). The client connects and listens for updates. To control the system, use REST endpoints.

Future versions may add:
- `killswitch:toggle` — Activate/deactivate kill switch
- `agent:pause` — Pause a running agent
- `session:resume` — Resume a paused session

## Authentication

### Bearer Token

All API endpoints (except `/health`) require a Bearer token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3847/api/v1/agents
```

The token is printed when you run `dashboard-deploy`:

```
Dashboard running at: http://localhost:3847?token=YOUR_TOKEN
```

### Token in Frontend

The frontend automatically includes the token from the URL query parameter:

```javascript
const token = new URLSearchParams(window.location.search).get('token');
const headers = {
  'Authorization': `Bearer ${token}`
};
```

### WebSocket Tickets

WebSocket connections use a different auth mechanism to avoid exposing the token in the URL:

1. **Client requests a ticket** via `POST /api/v1/ws-ticket`
   - Includes Bearer token in header
   - Receives a short-lived ticket (60s TTL, single-use)

2. **Client upgrades to WebSocket** via `ws://...?ticket=<ticket>`
   - No Bearer token needed
   - Server validates ticket instead

3. **Ticket is consumed** after validation

This prevents the WebSocket URL from containing the bearer token (bad practice).

## Redaction

All API responses go through a **two-layer redaction system**:

### Layer 1: Sensitive Content Removal

Removes tool result content that may contain secrets:
- API responses with passwords
- SSH keys
- Database dumps
- etc.

### Layer 2: Regex-Based Redaction

Removes patterns matching sensitive data:
- `sk-ant-...` (API keys)
- `Bearer: ****` (tokens)
- `password: ****` (credentials)
- Email addresses
- Phone numbers
- etc.

## Data Retention

- **Events**: Last 1000 entries in memory
- **Audit logs**: Last 100 entries in memory
- **Agent state**: Current agents only (no history)
- **Sessions**: Persisted to `.pocketteam/sessions/` (on disk)

## Performance

- **Message batching**: Events are debounced by 200ms
- **Payload size**: Full snapshot is ~50KB, incremental updates ~1-5KB
- **Refresh rate**: Real-time (200ms batches)
- **Memory usage**: ~200MB per dashboard instance

## Troubleshooting

### Dashboard won't start

```bash
# Check Docker is running
docker ps

# Check port is available
lsof -i :3847

# Check logs
docker logs $(docker ps -q -f "ancestor=pocketteam-dashboard:0.1.0")

# Restart
docker compose -f .pocketteam/docker-compose.yml restart
```

### WebSocket disconnects

- Token may have expired (60 min idle)
- Refresh the page to get a new token
- Check browser DevTools → Network → WS for errors

### Dashboard shows stale data

- WebSocket may be disconnected
- Check DevTools → Console for errors
- Refresh the page

### API returns 401

- Token is missing or invalid
- Check that URL includes `?token=YOUR_TOKEN`
- Regenerate token: `docker compose -f .pocketteam/docker-compose.yml restart`

## Deployment

### Local Development

```bash
cd dashboard
npm install
npm run dev
# Runs on http://localhost:5173 with hot reload
```

### Production Docker

```bash
# Build image
docker build -t pocketteam-dashboard:0.1.0 dashboard/

# Run container
docker run -p 3847:3847 \
  -e AUTH_TOKEN=your-token \
  pocketteam-dashboard:0.1.0

# Or via docker-compose
pocketteam skill run dashboard-deploy
```

### Kubernetes

The dashboard can be deployed to Kubernetes. Key requirements:
- Mount `.pocketteam/` volume for event stream access
- Mount `.pocketteam/artifacts/` for audit logs
- Expose port 3847
- Set `AUTH_TOKEN` environment variable

Example manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pocketteam-dashboard
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dashboard
  template:
    metadata:
      labels:
        app: dashboard
    spec:
      containers:
      - name: dashboard
        image: pocketteam-dashboard:0.1.0
        ports:
        - containerPort: 3847
        env:
        - name: AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: pocketteam-secrets
              key: dashboard-token
        volumeMounts:
        - name: pocketteam
          mountPath: /app/.pocketteam
      volumes:
      - name: pocketteam
        persistentVolumeClaim:
          claimName: pocketteam-pvc
```

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) — Dashboard config options
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Common issues and fixes
- [API.md](API.md) — Full API specification (if exists)
