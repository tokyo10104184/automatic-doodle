"""Mock device driver for offline simulation and automated tests."""
import logging
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from .base import DeviceController

logger = logging.getLogger(__name__)


class MockDeviceDriver(DeviceController):
    """Simulates an Android device for testing and demonstration.

    Can cycle through synthetic quiz images and records tapped coordinates.
    """

    def __init__(self, screen_size: Tuple[int, int] = (1080, 2400)):
        self.screen_size = screen_size
        self._connected = True
        self.tapped_coordinates: List[Tuple[int, int]] = []
        self._preset_images: List[Image.Image] = []
        self._current_image_idx = 0

    def add_preset_image(self, img: Image.Image):
        self._preset_images.append(img)

    def connect(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_size

    def take_screenshot(self) -> Image.Image:
        if self._preset_images:
            img = self._preset_images[self._current_image_idx]
            self._current_image_idx = (self._current_image_idx + 1) % len(self._preset_images)
            return img.copy()

        # Generate a default synthetic quiz screen if none provided
        return self._create_synthetic_quiz_screen(
            question="日本の首都はどこでしょうか？",
            options=["1. 大阪", "2. 京都", "3. 東京", "4. 名古屋"],
        )

    def tap(self, x: int, y: int) -> bool:
        logger.info("[MockDevice] Tapped coordinate (%d, %d)", x, y)
        self.tapped_coordinates.append((x, y))
        return True

    def _create_synthetic_quiz_screen(
        self,
        question: str,
        options: List[str],
    ) -> Image.Image:
        w, h = self.screen_size
        img = Image.new("RGB", (w, h), color=(240, 244, 248))
        draw = ImageDraw.Draw(img)

        # Header bar
        draw.rectangle([(0, 0), (w, 150)], fill=(33, 150, 243))
        draw.text((50, 60), "Quiz App (Demo)", fill=(255, 255, 255))

        # Question card
        q_box = [(60, 250), (w - 60, 600)]
        draw.rectangle(q_box, fill=(255, 255, 255), outline=(200, 200, 200), width=3)
        draw.text((100, 380), question, fill=(20, 20, 20))

        # Options buttons
        opt_start_y = 700
        btn_height = 160
        gap = 50

        for i, opt in enumerate(options):
            y1 = opt_start_y + i * (btn_height + gap)
            y2 = y1 + btn_height
            draw.rectangle([(80, y1), (w - 80, y2)], fill=(255, 255, 255), outline=(66, 133, 244), width=4)
            draw.text((120, y1 + 60), opt, fill=(30, 30, 30))

        return img
