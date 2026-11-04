"""Main Quiz Bot runner supporting continuous loop and single-shot modes."""
import argparse
import datetime
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional
import yaml

# Support both relative execution and module import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.device.base import DeviceController
from src.device.termux_driver import TermuxAdbDriver
from src.device.mock_driver import MockDeviceDriver
from src.solver.gemini_solver import GeminiQuizSolver, QuizAnalysisResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("QuizBot")


class QuizBot:
    """Orchestrates screen capture, Gemini Vision reasoning, and automated tapping."""

    def __init__(
        self,
        device: DeviceController,
        solver: GeminiQuizSolver,
        loop_interval: float = 2.5,
        dry_run: bool = False,
        debug_dir: Optional[str] = "debug_captures",
        save_debug: bool = True,
    ):
        self.device = device
        self.solver = solver
        self.loop_interval = loop_interval
        self.dry_run = dry_run
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self.save_debug = save_debug

        if self.save_debug and self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def process_one_screen(self) -> Optional[QuizAnalysisResult]:
        """Captures current screen, analyzes with Gemini, and taps the correct option if detected."""
        logger.info("Capturing screenshot...")
        screenshot = self.device.take_screenshot()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.save_debug and self.debug_dir:
            save_path = self.debug_dir / f"screen_{timestamp}.png"
            screenshot.save(save_path)
            logger.debug("Saved debug screenshot to %s", save_path)

        logger.info("Analyzing screenshot with Gemini Vision...")
        result = self.solver.analyze_and_solve(screenshot)

        if not result.is_quiz_screen:
            logger.info("Screen does not contain an active quiz question: %s", result.reasoning)
            return result

        logger.info("==========================================")
        logger.info("Question: %s", result.question)
        if result.options:
            for opt in result.options:
                marker = " [★ TARGET]" if opt.index == result.correct_option_index else ""
                logger.info("  %d. %s%s", opt.index, opt.text, marker)
        logger.info("Selected Correct Option: #%s", result.correct_option_index)
        logger.info("Confidence: %s", result.confidence)
        logger.info("Reasoning: %s", result.reasoning)
        logger.info("Target Coordinate: (%s, %s)", result.tap_x, result.tap_y)
        logger.info("==========================================")

        if result.tap_x is not None and result.tap_y is not None:
            if self.dry_run:
                logger.info("[DRY RUN] Would tap at (%d, %d)", result.tap_x, result.tap_y)
            else:
                logger.info("Executing tap at (%d, %d)...", result.tap_x, result.tap_y)
                success = self.device.tap(result.tap_x, result.tap_y)
                if success:
                    logger.info("Tap executed successfully.")
                else:
                    logger.warning("Tap execution reported failure.")
        else:
            logger.warning("Could not determine tap coordinates for correct answer.")

        return result

    def run_continuous_loop(self, max_iterations: int = 0):
        """Runs the quiz bot continuously until interrupted or max_iterations reached."""
        logger.info("Starting Continuous Loop Mode (interval: %.1fs, dry_run: %s)...", self.loop_interval, self.dry_run)
        logger.info("Press Ctrl+C to stop.")

        iteration = 0
        try:
            while True:
                iteration += 1
                logger.info("--- Loop iteration #%d ---", iteration)

                try:
                    self.process_one_screen()
                except Exception as e:
                    logger.error("Error during iteration #%d: %s", iteration, e, exc_info=True)

                if 0 < max_iterations <= iteration:
                    logger.info("Reached maximum iterations (%d). Stopping.", max_iterations)
                    break

                logger.info("Waiting %.1f seconds before next check...", self.loop_interval)
                time.sleep(self.loop_interval)
        except KeyboardInterrupt:
            logger.info("Loop interrupted by user.")


def load_config(config_path: Optional[str]) -> dict:
    """Loads configuration from YAML file and merges with environment variables."""
    cfg = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "model_name": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "device_mode": "termux_adb",
        "adb_host": "127.0.0.1",
        "adb_port": 5555,
        "loop_interval_sec": 2.5,
        "max_iterations": 0,
        "dry_run": False,
        "debug_screenshot_dir": "debug_captures",
        "save_debug_screenshots": True,
    }

    path_to_try = config_path or "config.yaml"
    if os.path.exists(path_to_try):
        try:
            with open(path_to_try, "r", encoding="utf-8") as f:
                file_cfg = yaml.safe_load(f) or {}
                cfg.update(file_cfg)
        except Exception as e:
            logger.warning("Could not load config file %s: %s", path_to_try, e)

    # Environment variables have highest precedence for API key
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        cfg["gemini_api_key"] = env_key

    return cfg


def main():
    parser = argparse.ArgumentParser(description="Android 4-Choice Quiz Auto-Solver (Termux & Gemini Vision)")
    parser.add_argument("--config", "-c", type=str, default=None, help="Path to YAML config file")
    parser.add_argument("--once", action="store_true", help="Run once (single-shot mode) instead of continuous loop")
    parser.add_argument("--dry-run", action="store_true", help="Analyze and display answer without sending tap")
    parser.add_argument("--interval", "-i", type=float, default=None, help="Polling interval in seconds (default: 2.5)")
    parser.add_argument("--max-count", "-n", type=int, default=None, help="Max questions to solve (0 = infinite)")
    parser.add_argument("--mock", action="store_true", help="Use mock device driver for offline testing")
    parser.add_argument("--port", "-p", type=int, default=None, help="ADB wireless debugging port (default: 5555)")
    parser.add_argument("--model", "-m", type=str, default=None, help="Gemini model name (default: gemini-2.5-flash)")
    parser.add_argument("--api-key", "-k", type=str, default=None, help="Gemini API Key")

    args = parser.parse_args()
    config = load_config(args.config)

    # CLI args override config
    if args.interval is not None:
        config["loop_interval_sec"] = args.interval
    if args.max_count is not None:
        config["max_iterations"] = args.max_count
    if args.dry_run:
        config["dry_run"] = True
    if args.port:
        config["adb_port"] = args.port
    if args.model:
        config["model_name"] = args.model
    if args.api_key:
        config["gemini_api_key"] = args.api_key

    # Initialize Device
    if args.mock or config.get("device_mode") == "mock":
        logger.info("Initializing MockDeviceDriver (testing mode)...")
        device = MockDeviceDriver()
    else:
        logger.info("Initializing TermuxAdbDriver on %s:%d...", config["adb_host"], config["adb_port"])
        device = TermuxAdbDriver(host=config["adb_host"], port=config["adb_port"])

    # Initialize Gemini Solver
    api_key = config.get("gemini_api_key")
    if not api_key and not args.mock:
        logger.error(
            "GEMINI_API_KEY is not set! Please set it in config.yaml, command-line --api-key, or export GEMINI_API_KEY='your_key'."
        )
        sys.exit(1)

    solver = GeminiQuizSolver(api_key=api_key, model_name=config["model_name"])

    # Initialize Quiz Bot
    bot = QuizBot(
        device=device,
        solver=solver,
        loop_interval=config["loop_interval_sec"],
        dry_run=config["dry_run"],
        debug_dir=config["debug_screenshot_dir"],
        save_debug=config["save_debug_screenshots"],
    )

    if args.once:
        logger.info("Running single-shot mode...")
        bot.process_one_screen()
    else:
        bot.run_continuous_loop(max_iterations=config["max_iterations"])


if __name__ == "__main__":
    main()
