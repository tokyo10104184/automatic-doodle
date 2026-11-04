"""Termux local ADB driver for Android."""
import io
import re
import shutil
import subprocess
import logging
from typing import Tuple, Optional
from PIL import Image
from .base import DeviceController

logger = logging.getLogger(__name__)


class TermuxAdbDriver(DeviceController):
    """Controls the local Android device directly from Termux via ADB.

    Termux connects to localhost wireless debugging (e.g., adb connect 127.0.0.1:<port>).
    Once paired and connected, screencap and input tap run directly against localhost.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5555, adb_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.adb_bin = adb_path or shutil.which("adb") or "adb"
        self._target_device = f"{self.host}:{self.port}"
        self._screen_size: Optional[Tuple[int, int]] = None

    def _run_adb_cmd(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        cmd = [self.adb_bin, "-s", self._target_device] + args
        try:
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
        except subprocess.SubprocessError as e:
            logger.error("ADB command failed: %s: %s", cmd, e)
            raise

    def connect(self) -> bool:
        """Connects to adb target device."""
        try:
            cmd = [self.adb_bin, "connect", self._target_device]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            output = res.stdout + res.stderr
            logger.info("ADB connect output: %s", output.strip())
            if "connected to" in output.lower():
                self._update_screen_size()
                return True

            # If already connected, devices list should have it
            return self.is_connected()
        except Exception as e:
            logger.error("Failed to connect via ADB: %s", e)
            return False

    def is_connected(self) -> bool:
        try:
            cmd = [self.adb_bin, "devices"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            for line in res.stdout.splitlines():
                if self._target_device in line and "device" in line and not "offline" in line:
                    return True
            return False
        except Exception:
            return False

    def _update_screen_size(self) -> Tuple[int, int]:
        res = self._run_adb_cmd(["shell", "wm", "size"], check=False)
        output = res.stdout.decode("utf-8", errors="ignore")
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", output)
        if match:
            w, h = int(match.group(1)), int(match.group(2))
            self._screen_size = (w, h)
            return self._screen_size
        return (1080, 2400)

    def get_screen_size(self) -> Tuple[int, int]:
        if not self._screen_size:
            return self._update_screen_size()
        return self._screen_size

    def take_screenshot(self) -> Image.Image:
        """Captures a screenshot via `adb exec-out screencap -p` and returns PIL Image."""
        # Note: exec-out directly returns binary PNG without CRLF issues on modern adb
        cmd = [self.adb_bin, "-s", self._target_device, "exec-out", "screencap", "-p"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0 or not res.stdout:
            # Fallback to shell screencap
            cmd = [self.adb_bin, "-s", self._target_device, "shell", "screencap", "-p"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Remove \r\n conversion if needed
            raw_bytes = res.stdout.replace(b"\r\n", b"\n")
        else:
            raw_bytes = res.stdout

        if not raw_bytes:
            raise RuntimeError("Empty screenshot output from ADB")

        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
        if not self._screen_size:
            self._screen_size = image.size
        return image

    def tap(self, x: int, y: int) -> bool:
        """Taps screen coordinate (x, y) using `adb shell input tap x y`."""
        logger.info("Tapping at (%d, %d)", x, y)
        res = self._run_adb_cmd(["shell", "input", "tap", str(x), str(y)], check=False)
        return res.returncode == 0
