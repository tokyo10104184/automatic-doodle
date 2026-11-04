"""End-to-end simulation runner for demonstration and offline testing."""
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.device.mock_driver import MockDeviceDriver
from src.solver.gemini_solver import GeminiQuizSolver
from src.quiz_bot import QuizBot


def create_quiz_image(question: str, options: list[str]) -> Image.Image:
    w, h = 1080, 2400
    img = Image.new("RGB", (w, h), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)

    # App Header
    draw.rectangle([(0, 0), (w, 180)], fill=(41, 98, 255))
    draw.text((60, 70), "クイズ選手権 (Quiz Contest)", fill=(255, 255, 255))

    # Question Box
    draw.rectangle([(60, 300), (w - 60, 750)], fill=(255, 255, 255), outline=(220, 224, 230), width=3)
    draw.text((100, 480), f"Q. {question}", fill=(30, 30, 30))

    # 4 Option buttons
    start_y = 850
    btn_h = 180
    gap = 60
    for i, opt in enumerate(options):
        y1 = start_y + i * (btn_h + gap)
        y2 = y1 + btn_h
        draw.rectangle([(80, y1), (w - 80, y2)], fill=(255, 255, 255), outline=(66, 133, 244), width=4)
        draw.text((130, y1 + 70), opt, fill=(20, 20, 20))

    return img


def run_offline_simulation():
    print("=== Running Offline QuizBot Simulation ===")
    mock_device = MockDeviceDriver(screen_size=(1080, 2400))

    # Add 2 sample quiz questions
    img1 = create_quiz_image(
        question="日本で一番高い山は？",
        options=["1. 北岳", "2. 富士山", "3. 槍ヶ岳", "4. 穂高岳"],
    )
    img2 = create_quiz_image(
        question="1年は何日？（平年）",
        options=["1. 364日", "2. 365日", "3. 366日", "4. 360日"],
    )
    mock_device.add_preset_image(img1)
    mock_device.add_preset_image(img2)

    # Mock solver for simulation without live API key
    class MockGeminiQuizSolver(GeminiQuizSolver):
        def __init__(self):
            super().__init__(api_key=None)
            self.call_count = 0

        def analyze_and_solve(self, image: Image.Image):
            self.call_count += 1
            if self.call_count == 1:
                return self._parse_gemini_response(
                    """{
                        "is_quiz_screen": true,
                        "question": "日本で一番高い山は？",
                        "options": [
                            {"index": 1, "text": "北岳", "box_norm": [354, 74, 429, 925]},
                            {"index": 2, "text": "富士山", "box_norm": [454, 74, 529, 925]},
                            {"index": 3, "text": "槍ヶ岳", "box_norm": [554, 74, 629, 925]},
                            {"index": 4, "text": "穂高岳", "box_norm": [654, 74, 729, 925]}
                        ],
                        "correct_option_index": 2,
                        "confidence": 1.0,
                        "reasoning": "富士山が標高3776mで日本一です。",
                        "tap_target_norm": [491, 500]
                    }""",
                    1080,
                    2400,
                )
            else:
                return self._parse_gemini_response(
                    """{
                        "is_quiz_screen": true,
                        "question": "1年は何日？（平年）",
                        "options": [
                            {"index": 1, "text": "364日", "box_norm": [354, 74, 429, 925]},
                            {"index": 2, "text": "365日", "box_norm": [454, 74, 529, 925]},
                            {"index": 3, "text": "366日", "box_norm": [554, 74, 629, 925]},
                            {"index": 4, "text": "360日", "box_norm": [654, 74, 729, 925]}
                        ],
                        "correct_option_index": 2,
                        "confidence": 1.0,
                        "reasoning": "平年は365日です。",
                        "tap_target_norm": [491, 500]
                    }""",
                    1080,
                    2400,
                )

    solver = MockGeminiQuizSolver()
    bot = QuizBot(device=mock_device, solver=solver, loop_interval=0.1, dry_run=False, save_debug=False)

    bot.run_continuous_loop(max_iterations=2)

    print("=== Simulation Results ===")
    print(f"Total simulated questions: {solver.call_count}")
    print(f"Recorded taps: {mock_device.tapped_coordinates}")
    assert len(mock_device.tapped_coordinates) == 2
    assert mock_device.tapped_coordinates[0] == (540, 1178)
    assert mock_device.tapped_coordinates[1] == (540, 1178)
    print("Simulation completed successfully!")


if __name__ == "__main__":
    run_offline_simulation()
