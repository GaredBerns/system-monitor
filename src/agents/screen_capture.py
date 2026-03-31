#!/usr/bin/env python3
"""
SCREEN CAPTURE - Cross-platform screenshot and webcam capture.
Supports: Linux (X11, Wayland), Windows, macOS.
"""

import os
import sys
import json
import time
import base64
import platform
import subprocess
import threading
import tempfile
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import io

class ScreenCapture:
    """Cross-platform screen and webcam capture."""
    
    def __init__(self, output_dir: str = None, quality: int = 85):
        self.platform = platform.system().lower()
        self.output_dir = output_dir or str(Path.home() / ".cache" / ".system_screens")
        self.quality = quality
        self.running = False
        self.interval = 60  # Default interval for periodic capture
        
        # Ensure output directory
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            "total_screenshots": 0,
            "total_webcam": 0,
            "start_time": None,
            "errors": []
        }
    
    # ─── SCREENSHOT ────────────────────────────────────────────────────
    
    def screenshot(self, display: str = None) -> Optional[str]:
        """Take a screenshot."""
        filepath = None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.output_dir, f"screen_{timestamp}.png")
            
            if self.platform == "linux":
                filepath = self._screenshot_linux(filepath, display)
            elif self.platform == "windows":
                filepath = self._screenshot_windows(filepath)
            elif self.platform == "darwin":
                filepath = self._screenshot_macos(filepath)
            else:
                raise Exception(f"Unsupported platform: {self.platform}")
            
            if filepath and os.path.exists(filepath):
                self.stats["total_screenshots"] += 1
                print(f"[+] Screenshot saved: {filepath}")
                return filepath
        
        except Exception as e:
            self.stats["errors"].append(str(e))
            print(f"[-] Screenshot error: {e}")
        
        return None
    
    def _screenshot_linux(self, filepath: str, display: str = None) -> str:
        """Linux screenshot using various methods."""
        
        # Method 1: Try scrot (simple and fast)
        try:
            result = subprocess.run(
                ["scrot", filepath],
                capture_output=True, timeout=10,
                env={**os.environ, "DISPLAY": display or os.environ.get("DISPLAY", ":0")}
            )
            if result.returncode == 0:
                return filepath
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Method 2: Try gnome-screenshot
        try:
            result = subprocess.run(
                ["gnome-screenshot", "-f", filepath],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return filepath
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Method 3: Try import (ImageMagick)
        try:
            result = subprocess.run(
                ["import", "-window", "root", filepath],
                capture_output=True, timeout=10,
                env={**os.environ, "DISPLAY": display or os.environ.get("DISPLAY", ":0")}
            )
            if result.returncode == 0:
                return filepath
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Method 4: Try xwd
        try:
            with open(filepath, 'wb') as f:
                result = subprocess.run(
                    ["xwd", "-root"],
                    stdout=f,
                    capture_output=True, timeout=10,
                    env={**os.environ, "DISPLAY": display or os.environ.get("DISPLAY", ":0")}
                )
            # Convert xwd to png
            subprocess.run(
                ["convert", filepath, filepath],
                capture_output=True, timeout=10
            )
            if os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        except Exception:
            pass
        
        # Method 5: Python PIL
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(filepath, "PNG", quality=self.quality)
            return filepath
        except ImportError:
            pass
        except Exception:
            pass
        
        # Method 6: Try grim (Wayland)
        try:
            result = subprocess.run(
                ["grim", filepath],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return filepath
        except FileNotFoundError:
            pass
        
        raise Exception("No screenshot method available")
    
    def _screenshot_windows(self, filepath: str) -> str:
        """Windows screenshot."""
        
        # Method 1: PIL
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(filepath, "PNG", quality=self.quality)
            return filepath
        except ImportError:
            pass
        except Exception:
            pass
        
        # Method 2: PowerShell
        try:
            ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save("{filepath.replace(chr(92), chr(92)*2)}")
$graphics.Dispose()
$bitmap.Dispose()
'''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(filepath):
                return filepath
        except Exception:
            pass
        
        # Method 3: nircmd (if available)
        try:
            result = subprocess.run(
                ["nircmd", "savescreenshot", filepath],
                capture_output=True, timeout=10
            )
            if os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        
        raise Exception("No screenshot method available")
    
    def _screenshot_macos(self, filepath: str) -> str:
        """macOS screenshot using screencapture."""
        try:
            result = subprocess.run(
                ["screencapture", "-x", filepath],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                return filepath
        except Exception as e:
            raise Exception(f"screencapture failed: {e}")
        
        raise Exception("screencapture failed")
    
    # ─── WEBCAM CAPTURE ────────────────────────────────────────────────
    
    def webcam_capture(self, device: int = 0) -> Optional[str]:
        """Capture image from webcam."""
        filepath = None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.output_dir, f"webcam_{timestamp}.jpg")
            
            if self.platform == "linux":
                filepath = self._webcam_linux(filepath, device)
            elif self.platform == "windows":
                filepath = self._webcam_windows(filepath, device)
            elif self.platform == "darwin":
                filepath = self._webcam_macos(filepath, device)
            
            if filepath and os.path.exists(filepath):
                self.stats["total_webcam"] += 1
                print(f"[+] Webcam capture saved: {filepath}")
                return filepath
        
        except Exception as e:
            self.stats["errors"].append(str(e))
            print(f"[-] Webcam error: {e}")
        
        return None
    
    def _webcam_linux(self, filepath: str, device: int = 0) -> str:
        """Linux webcam capture using fswebcam or ffmpeg."""
        
        # Method 1: fswebcam
        try:
            result = subprocess.run(
                ["fswebcam", "-d", f"/dev/video{device}", "--no-banner", filepath],
                capture_output=True, timeout=10
            )
            if result.returncode == 0 and os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        
        # Method 2: ffmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-f", "v4l2", "-i", f"/dev/video{device}",
                 "-frames:v", "1", "-y", filepath],
                capture_output=True, timeout=10
            )
            if os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        
        # Method 3: OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(device)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(filepath, frame)
                cap.release()
                return filepath
        except ImportError:
            pass
        
        raise Exception("No webcam method available")
    
    def _webcam_windows(self, filepath: str, device: int = 0) -> str:
        """Windows webcam capture using ffmpeg or OpenCV."""
        
        # Method 1: ffmpeg (dshow)
        try:
            result = subprocess.run(
                ["ffmpeg", "-f", "dshow", "-i", "video=Integrated Camera",
                 "-frames:v", "1", "-y", filepath],
                capture_output=True, timeout=10
            )
            if os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        
        # Method 2: OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(device, cv2.CAP_DSHOW)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(filepath, frame)
                cap.release()
                return filepath
        except ImportError:
            pass
        
        # Method 3: PowerShell with MediaCapture
        try:
            ps_script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asyncOp = [Windows.Media.Capture.MediaCapture]::new()
$asyncOp.InitializeAsync().AsTask().Wait()
$enc = [Windows.Media.MediaProperties.ImageEncodingProperties]::CreateJpeg()
$stream = [Windows.Storage.Streams.InMemoryRandomAccessStream]::new()
$asyncOp.CapturePhotoToStreamAsync($enc, $stream).AsTask().Wait()
$reader = [Windows.Storage.Streams.DataReader]::new($stream)
$reader.LoadAsync($stream.Size).AsTask().Wait()
$bytes = New-Object byte[] $reader.UnconsumedBufferLength
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes("{filepath.replace(chr(92), chr(92)*2)}", $bytes)
'''
            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=30
            )
            if os.path.exists(filepath):
                return filepath
        except Exception:
            pass
        
        raise Exception("No webcam method available")
    
    def _webcam_macos(self, filepath: str, device: int = 0) -> str:
        """macOS webcam capture using imagesnap or OpenCV."""
        
        # Method 1: imagesnap
        try:
            result = subprocess.run(
                ["imagesnap", "-w", "1", filepath],
                capture_output=True, timeout=10
            )
            if os.path.exists(filepath):
                return filepath
        except FileNotFoundError:
            pass
        
        # Method 2: OpenCV
        try:
            import cv2
            cap = cv2.VideoCapture(device)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(filepath, frame)
                cap.release()
                return filepath
        except ImportError:
            pass
        
        raise Exception("No webcam method available")
    
    # ─── PERIODIC CAPTURE ─────────────────────────────────────────────
    
    def start_periodic(self, interval: int = 60, webcam: bool = False):
        """Start periodic screen capture."""
        self.running = True
        self.interval = interval
        self.stats["start_time"] = datetime.now().isoformat()
        
        def capture_loop():
            while self.running:
                self.screenshot()
                if webcam:
                    self.webcam_capture()
                time.sleep(self.interval)
        
        self._thread = threading.Thread(target=capture_loop, daemon=True)
        self._thread.start()
        print(f"[*] Periodic capture started (interval={interval}s, webcam={webcam})")
    
    def stop_periodic(self):
        """Stop periodic capture."""
        self.running = False
        if hasattr(self, "_thread"):
            self._thread.join(timeout=5)
        print(f"[*] Periodic capture stopped")
    
    # ─── UTILITIES ────────────────────────────────────────────────────
    
    def to_base64(self, filepath: str) -> Optional[str]:
        """Convert image to base64."""
        try:
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except:
            return None
    
    def to_bytes(self, filepath: str) -> Optional[bytes]:
        """Read image as bytes."""
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except:
            return None
    
    def get_stats(self) -> Dict:
        """Get capture statistics."""
        return self.stats
    
    def list_captures(self) -> List[str]:
        """List all captured files."""
        try:
            return [str(f) for f in Path(self.output_dir).glob("*")]
        except:
            return []
    
    def clear_captures(self):
        """Delete all captured files."""
        for f in Path(self.output_dir).glob("*"):
            try:
                f.unlink()
            except:
                pass
        self.stats["total_screenshots"] = 0
        self.stats["total_webcam"] = 0


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description="Screen Capture")
    parser.add_argument("--screenshot", "-s", action="store_true", help="Take screenshot")
    parser.add_argument("--webcam", "-w", action="store_true", help="Capture webcam")
    parser.add_argument("--periodic", "-p", type=int, help="Periodic capture interval (seconds)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--base64", "-b", action="store_true", help="Output as base64")
    
    args = parser.parse_args()
    
    capture = ScreenCapture(args.output)
    
    def signal_handler(sig, frame):
        print("\n[*] Stopping...")
        capture.stop_periodic()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.periodic:
        capture.start_periodic(args.periodic, args.webcam)
        while True:
            time.sleep(1)
    elif args.screenshot:
        filepath = capture.screenshot()
        if filepath and args.base64:
            print(capture.to_base64(filepath))
    elif args.webcam:
        filepath = capture.webcam_capture()
        if filepath and args.base64:
            print(capture.to_base64(filepath))
    else:
        # Default: take screenshot
        filepath = capture.screenshot()
        if filepath and args.base64:
            print(capture.to_base64(filepath))
