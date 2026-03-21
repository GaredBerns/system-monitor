"""Load balancer configuration for C2 Server"""

NGINX_CONFIG = """
upstream c2_backend {
    least_conn;
    server 127.0.0.1:8443 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8444 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8445 weight=1 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name c2.example.com;
    
    ssl_certificate /etc/ssl/certs/c2.crt;
    ssl_certificate_key /etc/ssl/private/c2.key;
    
    location /socket.io/ {
        proxy_pass http://c2_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
    
    location /api/ {
        proxy_pass http://c2_backend;
        limit_req zone=api burst=20 nodelay;
    }
    
    location / {
        proxy_pass http://c2_backend;
    }
}

limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
"""

DOCKER_COMPOSE = """
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    restart: unless-stopped
  
  c2-1:
    build: .
    ports: ["8443:8443"]
    environment:
      REDIS_HOST: redis
      INSTANCE_ID: 1
    depends_on: [redis]
    restart: unless-stopped
  
  c2-2:
    build: .
    ports: ["8444:8443"]
    environment:
      REDIS_HOST: redis
      INSTANCE_ID: 2
    depends_on: [redis]
    restart: unless-stopped
  
  nginx:
    image: nginx:alpine
    ports: ["443:443"]
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf:ro"]
    depends_on: [c2-1, c2-2]
    restart: unless-stopped

volumes:
  redis_data:
"""
