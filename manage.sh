#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# C2 SERVER - UNIFIED MANAGEMENT SCRIPT
# All-in-one: Server control + Tunnel + Installation + Database sync
# ═══════════════════════════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN="gbctwoserver.pages.dev"
TUNNEL_NAME="c2-server"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
VENV="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/data/c2-server.pid"
LOG_FILE="$SCRIPT_DIR/logs/c2-server.log"
NGROK_PID_FILE="$SCRIPT_DIR/data/ngrok.pid"
NGROK_LOG_FILE="$SCRIPT_DIR/logs/ngrok.log"
NGROK_AUTHTOKEN="3BSLfBkyp4PMXsaom9XTj5mcsDb_2YJmW96LrznsCNPWddTcP"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────────────────────────────────────

show_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    C2 SERVER MANAGER                         ║"
    echo "║                    Domain: $DOMAIN                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# VENV MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

check_venv() {
    if [ ! -d "$VENV" ]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --no-cache-dir -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || \
        "$VENV/bin/pip" install --no-cache-dir \
            flask flask-socketio flask-bcrypt requests python-dotenv \
            psutil cryptography faker numpy pandas pillow \
            eventlet gunicorn pyyaml 2>/dev/null
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# SERVER COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

server_start() {
    show_banner
    check_venv
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${RED}✗ Server already running (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi
    
    echo -e "${GREEN}Starting C2 Server...${NC}"
    echo -e "${BLUE}  Host: $HOST${NC}"
    echo -e "${BLUE}  Port: $PORT${NC}"
    
    mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/data"
    
    source "$VENV/bin/activate"
    nohup "$VENV/bin/python" "$SCRIPT_DIR/run_unified.py" --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo -e "${GREEN}✓ Server started (PID: $(cat $PID_FILE))${NC}"
        echo -e "${CYAN}  Local: http://127.0.0.1:$PORT${NC}"
        echo -e "${CYAN}  Telegram C2: Direct API (no tunnel needed)${NC}"
    else
        echo -e "${RED}✗ Failed to start server${NC}"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

server_stop() {
    echo -e "${YELLOW}Stopping server...${NC}"
    
    # Kill Python server
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill -TERM "$PID" 2>/dev/null || true
            sleep 2
            kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any remaining
    pkill -f "python.*run_unified" 2>/dev/null || true
    
    echo -e "${GREEN}✓ Server stopped${NC}"
}

server_status() {
    echo -e "${CYAN}Server Status:${NC}"
    
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        PID=$(cat "$PID_FILE")
        echo -e "${GREEN}✓ Running (PID: $PID)${NC}"
        echo -e "  Local: http://127.0.0.1:$PORT"
        
        if curl -s "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}  Health: OK${NC}"
        else
            echo -e "${YELLOW}  Health: Not responding${NC}"
        fi
    else
        echo -e "${RED}✗ Not running${NC}"
        [ -f "$PID_FILE" ] && rm -f "$PID_FILE"
    fi
    
    # Telegram C2 status
    echo ""
    echo -e "${CYAN}Telegram C2 Status:${NC}"
    echo -e "${GREEN}✓ Direct API mode (no tunnel needed)${NC}"
}

server_logs() {
    if [ "$1" = "follow" ] || [ "$1" = "-f" ]; then
        tail -f "$LOG_FILE"
    else
        tail -100 "$LOG_FILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM C2 - Direct API (no tunnel needed)
# ─────────────────────────────────────────────────────────────────────────────

telegram_status() {
    echo -e "${CYAN}Telegram C2 Status:${NC}"
    echo -e "${GREEN}✓ Direct API mode${NC}"
    echo -e "${CYAN}  No tunnel or public URL needed${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# INSTALLATION
# ─────────────────────────────────────────────────────────────────────────────

install_deps() {
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r "$SCRIPT_DIR/requirements.txt"
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# COMBINED COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

start_all() {
    show_banner
    server_stop
    sleep 1
    server_start
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  C2 SERVER RUNNING (Telegram C2 Direct API)          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Local:   ${CYAN}http://localhost:$PORT${NC}"
    echo -e "  C2:      ${GREEN}Telegram API (no tunnel needed)${NC}"
}

stop_all() {
    show_banner
    server_stop
    echo -e "${GREEN}✓ All stopped${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

db_export() {
    local output="${1:-db_export_$(date +%Y%m%d_%H%M%S).json}"
    echo -e "${YELLOW}Exporting database to $output...${NC}"
    python3 "$SCRIPT_DIR/scripts/sync_db.py" --export -o "$output"
    echo -e "${GREEN}✓ Exported${NC}"
}

db_import() {
    local input="$1"
    if [ -z "$input" ]; then
        echo -e "${RED}Usage: $0 db import <file.json>${NC}"
        return 1
    fi
    echo -e "${YELLOW}Importing database from $input...${NC}"
    python3 "$SCRIPT_DIR/scripts/sync_db.py" --import "$input"
    echo -e "${GREEN}✓ Imported${NC}"
}

db_pull() {
    local url="${1:-https://$DOMAIN}"
    echo -e "${YELLOW}Pulling data from $url...${NC}"
    python3 "$SCRIPT_DIR/scripts/sync_db.py" --pull "$url"
}

db_merge() {
    local url="${1:-https://$DOMAIN}"
    echo -e "${YELLOW}Merging data from $url...${NC}"
    python3 "$SCRIPT_DIR/scripts/sync_db.py" --merge "$url"
}

# ─────────────────────────────────────────────────────────────────────────────
# INSTALLATION
# ─────────────────────────────────────────────────────────────────────────────

install_all() {
    show_banner
    
    echo -e "${YELLOW}Installing system dependencies...${NC}"
    if command -v apt &> /dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-pip python3-venv curl wget
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip python3-virtualenv curl wget
    fi
    
    echo -e "${YELLOW}Creating directories...${NC}"
    mkdir -p data/backups data/uploads logs
    
    echo -e "${YELLOW}Setting up virtual environment...${NC}"
    check_venv
    
    echo -e "${YELLOW}Installing tunnel...${NC}"
    tunnel_install
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           INSTALLATION COMPLETE!${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Start server:  ${GREEN}$0 start${NC}"
    echo -e "Start all:     ${GREEN}$0 up${NC}"
    echo -e "Status:        ${GREEN}$0 status${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# HELP
# ─────────────────────────────────────────────────────────────────────────────

show_help() {
    show_banner
    echo "Usage: $0 <command> [args]"
    echo ""
    echo -e "${CYAN}Server Commands:${NC}"
    echo "  start           Start server"
    echo "  stop            Stop server"
    echo "  restart         Restart server"
    echo "  status          Show status"
    echo "  logs [follow]   View logs"
    echo ""
    echo -e "${CYAN}Ngrok Commands:${NC}"
    echo "  ngrok start     Start ngrok tunnel"
    echo "  ngrok stop      Stop ngrok tunnel"
    echo "  ngrok status    Show ngrok status"
    echo ""
    echo -e "${CYAN}Tunnel Commands:${NC}"
    echo "  tunnel install  Setup permanent tunnel for $DOMAIN"
    echo "  tunnel start    Start tunnel"
    echo "  tunnel stop     Stop tunnel"
    echo "  tunnel quick    Start temporary tunnel (random URL)"
    echo ""
    echo -e "${CYAN}Combined Commands:${NC}"
    echo "  up              Start server + tunnel"
    echo "  down            Stop server + tunnel"
    echo ""
    echo -e "${CYAN}Database Commands:${NC}"
    echo "  db export [file]    Export database to JSON"
    echo "  db import <file>    Import database from JSON"
    echo "  db pull [url]      Pull data from remote server"
    echo "  db merge [url]     Merge remote data into local"
    echo ""
    echo -e "${CYAN}Installation:${NC}"
    echo "  install         Full installation (deps + venv + tunnel)"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 up                    # Start everything"
    echo "  $0 tunnel quick          # Quick temporary tunnel"
    echo "  $0 db pull https://...   # Pull from Render"
    echo ""
    echo -e "${PURPLE}Domain: https://$DOMAIN${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

case "${1:-}" in
    # Server
    start)      server_start ;;
    stop)       server_stop ;;
    restart)    server_stop; sleep 1; server_start ;;
    status)     server_status ;;
    logs)       server_logs "$2" ;;
    
    # Tunnel
    tunnel)
        case "${2:-}" in
            install)    tunnel_install ;;
            start)      tunnel_start ;;
            stop)       tunnel_stop ;;
            quick)      tunnel_quick ;;
            *)          echo "Usage: $0 tunnel {install|start|stop|quick}" ;;
        esac
        ;;
    
    # Ngrok
    ngrok)
        case "${2:-}" in
            start)      ngrok_start ;;
            stop)       ngrok_stop ;;
            status)     ngrok_status ;;
            *)          echo "Usage: $0 ngrok {start|stop|status}" ;;
        esac
        ;;
    
    # Combined
    up)         start_all ;;
    down)       stop_all ;;
    
    # Database
    db)
        case "${2:-}" in
            export) db_export "$3" ;;
            import) db_import "$3" ;;
            pull)   db_pull "$3" ;;
            merge)  db_merge "$3" ;;
            *)      echo "Usage: $0 db {export|import|pull|merge}" ;;
        esac
        ;;
    
    # Installation
    install)    install_all ;;
    
    # Help
    help|--help|-h) show_help ;;
    *)          show_help ;;
esac
