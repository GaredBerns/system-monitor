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

DOMAIN="gbctwoserver.net"
TUNNEL_NAME="c2-server"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
VENV="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/data/c2-server.pid"
LOG_FILE="$SCRIPT_DIR/logs/c2-server.log"

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
    
    # Tunnel status
    echo ""
    echo -e "${CYAN}Tunnel Status:${NC}"
    if pgrep -f "cloudflared tunnel run" > /dev/null; then
        echo -e "${GREEN}✓ Running${NC}"
        echo -e "  Public: https://$DOMAIN"
    else
        echo -e "${YELLOW}✗ Not running${NC}"
    fi
}

server_logs() {
    if [ "$1" = "follow" ] || [ "$1" = "-f" ]; then
        tail -f "$LOG_FILE"
    else
        tail -100 "$LOG_FILE"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# TUNNEL COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

tunnel_install() {
    show_banner
    echo -e "${YELLOW}Installing cloudflared...${NC}"
    
    if ! command -v cloudflared &> /dev/null; then
        if command -v apt &> /dev/null; then
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
            sudo dpkg -i /tmp/cloudflared.deb 2>/dev/null || sudo apt-get install -f -y
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y cloudflared
        else
            mkdir -p ~/.local/bin
            curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared
            chmod +x ~/.local/bin/cloudflared
        fi
    fi
    
    echo -e "${GREEN}✓ cloudflared installed${NC}"
    
    # Login if needed
    if [ ! -f ~/.cloudflared/cert.pem ]; then
        echo -e "${YELLOW}Logging into Cloudflare...${NC}"
        echo -e "${YELLOW}A browser will open. Please authenticate.${NC}"
        cloudflared tunnel login
    fi
    
    echo -e "${GREEN}✓ Authenticated${NC}"
    
    # Create tunnel if needed
    TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}' || true)
    
    if [ -z "$TUNNEL_ID" ]; then
        echo -e "${YELLOW}Creating tunnel '$TUNNEL_NAME'...${NC}"
        cloudflared tunnel create "$TUNNEL_NAME"
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    fi
    
    echo -e "${GREEN}✓ Tunnel: $TUNNEL_NAME ($TUNNEL_ID)${NC}"
    
    # Configure DNS
    echo -e "${YELLOW}Configuring DNS...${NC}"
    cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>/dev/null || true
    cloudflared tunnel route dns "$TUNNEL_NAME" "www.$DOMAIN" 2>/dev/null || true
    
    # Create config
    mkdir -p ~/.cloudflared
    cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: ~/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $DOMAIN
    service: http://localhost:$PORT
  - hostname: www.$DOMAIN
    service: http://localhost:$PORT
  - service: http_status:404
EOF
    
    echo -e "${GREEN}✓ Config created${NC}"
    
    # Create systemd service
    cat > /tmp/cloudflared.service << EOF
[Unit]
Description=Cloudflare Tunnel for $DOMAIN
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$(command -v cloudflared) tunnel run $TUNNEL_NAME
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              TUNNEL SETUP COMPLETE!${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Domain:   ${GREEN}https://$DOMAIN${NC}"
    echo -e "Tunnel:   ${GREEN}$TUNNEL_NAME${NC}"
    echo ""
    echo -e "${YELLOW}Auto-start on boot:${NC}"
    echo "  sudo cp /tmp/cloudflared.service /etc/systemd/system/"
    echo "  sudo systemctl enable --now cloudflared"
}

tunnel_start() {
    echo -e "${YELLOW}Starting tunnel...${NC}"
    
    # Check if tunnel exists
    if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
        echo -e "${RED}✗ Tunnel not configured. Run: $0 tunnel install${NC}"
        return 1
    fi
    
    # Kill existing
    pkill -f "cloudflared tunnel run" 2>/dev/null || true
    sleep 1
    
    # Start tunnel
    cloudflared tunnel run "$TUNNEL_NAME" &
    TUNNEL_PID=$!
    
    sleep 2
    
    if kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Tunnel started (PID: $TUNNEL_PID)${NC}"
        echo -e "${CYAN}  Public: https://$DOMAIN${NC}"
    else
        echo -e "${RED}✗ Failed to start tunnel${NC}"
        return 1
    fi
}

tunnel_stop() {
    echo -e "${YELLOW}Stopping tunnel...${NC}"
    pkill -f "cloudflared tunnel run" 2>/dev/null || true
    echo -e "${GREEN}✓ Tunnel stopped${NC}"
}

tunnel_quick() {
    echo -e "${YELLOW}Starting quick tunnel (temporary URL)...${NC}"
    pkill -f "cloudflared tunnel --url" 2>/dev/null || true
    sleep 1
    
    cloudflared tunnel --url "http://localhost:$PORT" 2>&1 | tee /tmp/tunnel.log &
    
    echo -e "${YELLOW}Waiting for URL...${NC}"
    sleep 5
    
    URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' /tmp/tunnel.log | head -1)
    
    if [ -n "$URL" ]; then
        echo ""
        echo -e "${GREEN}✓ Quick tunnel created!${NC}"
        echo -e "${CYAN}  Public: $URL${NC}"
        echo "$URL" > /tmp/tunnel_url.txt
    else
        echo -e "${RED}✗ Failed to get URL${NC}"
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# COMBINED COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

start_all() {
    show_banner
    server_stop
    sleep 1
    server_start
    sleep 2
    tunnel_start
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  C2 SERVER + TUNNEL RUNNING!                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Public:  ${GREEN}https://$DOMAIN${NC}"
    echo -e "  Local:   ${CYAN}http://localhost:$PORT${NC}"
}

stop_all() {
    show_banner
    tunnel_stop
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
