#!/usr/bin/env python3
"""System Monitor - Main module"""

def main():
    """Main entry point for system_monitor module."""
    import argparse

    from src.c2.orchestrator import Integration
    from src.c2.server import app as main_app
    from src.c2.server import socketio
    from src.utils.logger import get_logger

    log = get_logger('system_monitor')

    parser = argparse.ArgumentParser(description="System Monitor")
    parser.add_argument("--host", default="0.0.0.0", help="Host")
    parser.add_argument("--port", type=int, default=5000, help="Port")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    log.section("System Monitor")
    log.subsection("Initializing Integration")
    integration = Integration()
    integration.start()
    log.success("Integration started")

    log.subsection("Starting server")
    log.table(
        ["Parameter", "Value"],
        [
            ["Host", args.host],
            ["Port", args.port],
            ["Debug", "Yes" if args.debug else "No"],
            ["URL", f"http://{args.host}:{args.port}"],
            ["Local", f"http://127.0.0.1:{args.port}"],
        ],
    )

    socketio.run(main_app, host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()
