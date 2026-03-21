# C2 Server - Command & Control Panel

A comprehensive C2 framework with multi-platform agents, GPU optimization, auto-registration, and encrypted communications.

## Features

- **Web Dashboard**: Full-featured Flask-based control panel with real-time updates
- **Multi-Platform Agents**: Support for Linux, macOS, Colab, and Kaggle platforms
- **Auto-Registration**: Automated account creation with CAPTCHA solving
- **GPU Optimization**: PyTorch-based compute engine for ML workloads
- **Secure Communication**: Encrypted agent communication and data transport
- **Email Management**: Integrated temporary email services
- **Browser Automation**: Playwright and Selenium-based automation

## Installation

### From Git Repository

```bash
# Install server
pip install git+https://github.com/GaredBerns/C2_server -- server

# Install optimizer  
pip install git+https://github.com/GaredBerns/C2_server -- optimizer
```

### Manual Installation

```bash
git clone https://github.com/GaredBerns/C2_server.git
cd C2_server
pip install -r requirements.txt
pip install -e .
```

## Quick Start

### Start Server

```bash
# Using pip installation
c2-server

# Or directly
python -m C2_server.server
```

### Start Optimizer

```bash
# Using pip installation  
c2-optimizer

# Or directly
python -m C2_server.optimizer_cli
```

## Configuration

### Environment Variables

```bash
# Security
SECRET_KEY=your-secret-key

# CAPTCHA Services
CAPTCHA_API_KEY=your-2captcha-key
FCB_API_KEYS=key1,key2,key3

# Email Services
BOOMLIFY_API_KEYS=key1,key2,key3

# Database
DATABASE_URL=sqlite:///data/c2.db

# Debug
DEBUG=True
VERBOSE_MAIL=1
```

### Directory Structure

```
C2_server/
├── agents/              # Platform-specific agents
├── optimizer/           # GPU optimization engine
├── templates/           # Web dashboard templates
├── static/             # Static assets
├── data/               # Database and uploads
├── browsers/           # Playwright browsers
└── share/              # Shared resources
```

## Components

### Server (`server.py`)
- Flask web application
- WebSocket real-time updates
- Agent management
- User authentication
- File uploads/downloads

### Optimizer (`optimizer/`)
- PyTorch compute engine
- GPU management
- Model training utilities
- Persistent storage

### Agents (`agents/`)
- `agent_linux.py`: Linux system agent
- `agent_macos.py`: macOS system agent  
- `agent_colab.py`: Google Colab agent
- `kaggle_agent.py`: Kaggle kernel agent

### Auto-Registration (`autoreg.py`, `autoreg_worker.py`)
- Multi-platform account creation
- CAPTCHA solving integration
- Browser automation
- Identity generation

### Utilities
- `utils.py`: Common utilities and identity generation
- `tempmail.py`: Temporary email management
- `captcha_solver.py`: CAPTCHA bypass engine
- `page_utils.py`: Web page utilities

## Usage Examples

### Agent Deployment

```python
from C2_server import agent_linux

# Deploy Linux agent
agent = agent_linux.LinuxAgent(
    server_url="ws://localhost:5000",
    agent_id="unique-agent-id"
)
agent.start()
```

### GPU Optimization

```python
from C2_server import ComputeEngine

# Initialize GPU optimizer
engine = ComputeEngine(device='auto')
engine.initialize()

# Run optimization
results = engine.optimize_model(model, dataset)
```

### Auto-Registration

```python
from C2_server import job_manager, generate_identity

# Create registration job
identity = generate_identity()
job = job_manager.create_job(
    platform='kaggle',
    identity=identity,
    email='temp@example.com'
)
```

## Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Code Formatting

```bash
black C2_server/
flake8 C2_server/
```

### Testing

```bash
pytest tests/
```

## Security Notes

- Always use strong secret keys in production
- Configure firewall rules appropriately
- Use HTTPS in production environments
- Regularly update dependencies
- Monitor agent connections

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions, please use the GitHub issue tracker.
