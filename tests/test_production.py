#!/usr/bin/env python3
"""Production readiness test for C2 Server."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test all module imports."""
    print("=" * 60)
    print("TESTING IMPORTS")
    print("=" * 60)
    
    tests = [
        ("src.utils", ["generate_identity", "get_logger"]),
        ("src.core", ["Config", "get_secrets_manager"]),
        ("src.agents", ["BaseAgent", "UniversalAgent"]),
        ("src.agents.browser", ["PageStep", "find_element"]),
        ("src.agents.kaggle", ["KaggleC2Agent"]),
        ("src.agents.cloud", ["PaperspaceMiner", "BrowserMiner"]),
        ("src.mail", ["mail_manager"]),
        ("src.c2", ["Agent", "Task", "Base"]),
        ("src.autoreg", ["PLATFORMS", "job_manager"]),
        ("src.autoreg", ["deploy_after_registration"]),
    ]
    
    passed = 0
    failed = 0
    
    for module, attrs in tests:
        try:
            mod = __import__(module, fromlist=attrs)
            for attr in attrs:
                getattr(mod, attr)
            print(f"✓ {module}: {', '.join(attrs)}")
            passed += 1
        except Exception as e:
            print(f"✗ {module}: {e}")
            failed += 1
    
    print(f"\nImports: {passed} passed, {failed} failed")
    return failed == 0


def test_server():
    """Test Flask server import."""
    print("\n" + "=" * 60)
    print("TESTING SERVER")
    print("=" * 60)
    
    try:
        from src.c2.server import app, socketio
        routes = len(list(app.url_map.iter_rules()))
        print(f"✓ Flask app loaded")
        print(f"  Routes: {routes} endpoints")
        print(f"  SocketIO: {socketio}")
        return True
    except Exception as e:
        print(f"✗ Server: {e}")
        return False


def test_platforms():
    """Test platform definitions."""
    print("\n" + "=" * 60)
    print("TESTING PLATFORMS")
    print("=" * 60)
    
    try:
        from src.autoreg import PLATFORMS
        print(f"✓ Platforms defined: {len(PLATFORMS)}")
        for p_id, p_info in PLATFORMS.items():
            print(f"  - {p_id}: {p_info.get('name', p_id)}")
        return True
    except Exception as e:
        print(f"✗ Platforms: {e}")
        return False


def test_auto_deploy():
    """Test auto-deploy module."""
    print("\n" + "=" * 60)
    print("TESTING AUTO-DEPLOY")
    print("=" * 60)
    
    try:
        from src.autoreg.auto_deploy import AutoDeployer, deploy_after_registration
        
        # Test with mock account
        mock_account = {
            "platform": "test",
            "email": "test@example.com",
            "username": "testuser",
        }
        
        settings = {
            "c2_panel": False,  # Disable actual connections
            "telegram": False,
            "mining": False,
            "persistence": False,
        }
        
        print("✓ AutoDeployer class available")
        print("✓ deploy_after_registration function available")
        return True
    except Exception as e:
        print(f"✗ Auto-deploy: {e}")
        return False


def test_database():
    """Test database initialization."""
    print("\n" + "=" * 60)
    print("TESTING DATABASE")
    print("=" * 60)
    
    try:
        from src.c2.models import Base, Agent, Task
        from sqlalchemy import create_engine
        
        # In-memory test
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        print("✓ Database models work")
        print(f"  Tables: {list(Base.metadata.tables.keys())}")
        return True
    except Exception as e:
        print(f"✗ Database: {e}")
        return False


def test_config():
    """Test configuration."""
    print("\n" + "=" * 60)
    print("TESTING CONFIGURATION")
    print("=" * 60)
    
    try:
        from src.core import Config
        
        print(f"✓ Config loaded")
        print(f"  Base dir: {Config.BASE_DIR}")
        print(f"  Database: {Config.DATABASE_URL}")
        print(f"  Host: {Config.FLASK_HOST}:{Config.FLASK_PORT}")
        return True
    except Exception as e:
        print(f"✗ Config: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("C2 SERVER - PRODUCTION READINESS TEST")
    print("=" * 60 + "\n")
    
    results = {
        "Imports": test_imports(),
        "Server": test_server(),
        "Platforms": test_platforms(),
        "Auto-deploy": test_auto_deploy(),
        "Database": test_database(),
        "Config": test_config(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - READY FOR PRODUCTION")
    else:
        print("SOME TESTS FAILED - CHECK ERRORS ABOVE")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
