"""C2 Server entry point."""

def main():
    """Start C2 server."""
    from server import app, socketio
    import ssl
    import os
    
    cert_path = os.environ.get("C2_CERT", "cert.pem")
    key_path = os.environ.get("C2_KEY", "key.pem")
    
    ssl_context = None
    scheme = "http"
    port = int(os.environ.get("C2_PORT", "8443"))
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        ssl_context = context
        scheme = "https"
    
    print(f"[C2] Starting server on {scheme}://0.0.0.0:{port}")
    socketio.run(app, host='0.0.0.0', port=port, ssl_context=ssl_context)

if __name__ == '__main__':
    main()
