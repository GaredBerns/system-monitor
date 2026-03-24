#!/bin/bash
# C2 Server Management Script
# Production server control with Eventlet

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Settings
VENV="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/data/c2-server.pid"
LOG_FILE="$SCRIPT_DIR/logs/c2-server.log"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"

show_banner() {
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         C2 SERVER - MANAGER                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
}

check_venv() {
    if [ ! -d "$VENV" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --no-cache-dir \
            flask flask-socketio flask-bcrypt requests python-dotenv \
            psutil cryptography faker numpy pandas pillow \
            eventlet gunicorn pyyaml
    fi
}

start() {
    show_banner
    check_venv
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${RED}✗ Server already running (PID: $(cat $PID_FILE))${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Starting C2 Server...${NC}"
    echo -e "${BLUE}  Host: $HOST${NC}"
    echo -e "${BLUE}  Port: $PORT${NC}"
    
    mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/data"
    
    source "$VENV/bin/activate"
    
    nohup "$VENV/bin/python" "$SCRIPT_DIR/wsgi.py" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${GREEN}✓ Server started (PID: $(cat $PID_FILE))${NC}"
        echo -e "${CYAN}  URL: http://127.0.0.1:$PORT${NC}"
    else
        echo -e "${RED}✗ Failed to start server${NC}"
        tail -20 "$LOG_FILE"
        exit 1
    fi
}

stop() {
    show_banner
    
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}✗ Server not running${NC}"
        exit 0
    fi
    
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}Stopping server (PID: $PID)...${NC}"
        kill -TERM "$PID"
        sleep 2
        
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID"
        fi
        
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ Server stopped${NC}"
    else
        echo -e "${YELLOW}✗ Server not running${NC}"
        rm -f "$PID_FILE"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    show_banner
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}✓ Server running (PID: $PID)${NC}"
        echo -e "${BLUE}  URL: http://127.0.0.1:$PORT${NC}"
        
        if curl -s "http://127.0.0.1:$PORT/" > /dev/null 2>&1; then
            echo -e "${GREEN}  Status: Responding${NC}"
        else
            echo -e "${YELLOW}  Status: Not responding${NC}"
        fi
    else
        echo -e "${RED}✗ Server not running${NC}"
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    fi
}

logs() {
    if [ "$1" = "follow" ]; then
        tail -f "$LOG_FILE"
    else
        tail -100 "$LOG_FILE"
    fi
}

dev() {
    show_banner
    check_venv
    
    echo -e "${YELLOW}Starting in development mode...${NC}"
    source "$VENV/bin/activate"
    python "$SCRIPT_DIR/run_unified.py" --host "$HOST" --port "$PORT" --debug
}

install_service() {
    show_banner
    
    USER=$(whoami)
    GROUP=$(id -gn)
    
    sed "s/%USER%/$USER/g; s/%GROUP%/$GROUP/g" \
        "$SCRIPT_DIR/deploy/c2-server.service" > /tmp/c2-server.service
    
    echo -e "${YELLOW}Installing systemd service...${NC}"
    sudo cp /tmp/c2-server.service /etc/systemd/system/c2-server.service
    sudo systemctl daemon-reload
    sudo systemctl enable c2-server
    
    echo -e "${GREEN}✓ Service installed${NC}"
    echo -e "${CYAN}  Commands:${NC}"
    echo -e "  sudo systemctl start c2-server"
    echo -e "  sudo systemctl stop c2-server"
    echo -e "  sudo systemctl status c2-server"
}

case "${1:-}" in
    start)      start ;;
    stop)       stop ;;
    restart)    restart ;;
    status)     status ;;
    logs)       logs "$2" ;;
    dev)        dev ;;
    install)    install_service ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [follow]|dev|install}"
        echo ""
        echo "Commands:"
        echo "  start   - Start server"
        echo "  stop    - Stop server"
        echo "  restart - Restart server"
        echo "  status  - Check server status"
        echo "  logs    - View logs (add 'follow' for tail -f)"
        echo "  dev     - Start in development mode"
        echo "  install - Install as systemd service"
        exit 1
        ;;
esac
