"""Abstract base class for device controllers."""
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from PIL import Image


class DeviceController(ABC):
    """Interface to interact with an Android device screen and input."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection or verify device accessibility."""
        pass

    @abstractmethod
    def get_screen_size(self) -> Tuple[int, int]:
        """Return (width, height) in pixels."""
        pass

    @abstractmethod
    def take_screenshot(self) -> Image.Image:
        """Capture screenshot and return PIL Image."""
        pass

    @abstractmethod
    def tap(self, x: int, y: int) -> bool:
        """Tap at the given (x, y) coordinates on the screen."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if device is connected and responsive."""
        pass
