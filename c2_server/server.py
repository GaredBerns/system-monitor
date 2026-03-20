"""C2 Server entry point."""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Start C2 server."""
    from server import app, socketio
    import ssl
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    
    print("[C2] Starting server on https://0.0.0.0:8443")
    socketio.run(app, host='0.0.0.0', port=8443, ssl_context=context)

if __name__ == '__main__':
    main()
