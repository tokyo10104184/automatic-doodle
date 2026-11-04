"""Unit and integration tests for Quiz Bot."""
import json
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

from src.device.mock_driver import MockDeviceDriver
from src.solver.gemini_solver import GeminiQuizSolver, QuizAnalysisResult, QuizOption
from src.quiz_bot import QuizBot, load_config


def test_mock_device_driver():
    driver = MockDeviceDriver(screen_size=(1080, 2400))
    assert driver.connect() is True
    assert driver.is_connected() is True
    assert driver.get_screen_size() == (1080, 2400)

    img = driver.take_screenshot()
    assert isinstance(img, Image.Image)
    assert img.size == (1080, 2400)

    # Tap simulation
    assert driver.tap(500, 1000) is True
    assert (500, 1000) in driver.tapped_coordinates


def test_gemini_solver_parse_quiz_screen():
    solver = GeminiQuizSolver(api_key=None)
    response_payload = {
        "is_quiz_screen": True,
        "question": "太陽系で最も太陽に近い惑星は？",
        "options": [
            {"index": 1, "text": "金星", "box_norm": [600, 100, 680, 900]},
            {"index": 2, "text": "水星", "box_norm": [700, 100, 780, 900]},
            {"index": 3, "text": "火星", "box_norm": [800, 100, 880, 900]},
            {"index": 4, "text": "木星", "box_norm": [900, 100, 980, 900]},
        ],
        "correct_option_index": 2,
        "confidence": 0.99,
        "reasoning": "水星（Mercury）が太陽に最も近い惑星です。",
        "tap_target_norm": [740, 500],
    }

    raw_json = f"```json\n{json.dumps(response_payload)}\n```"
    result = solver._parse_gemini_response(raw_json, screen_width=1080, screen_height=2400)

    assert result.is_quiz_screen is True
    assert result.question == "太陽系で最も太陽に近い惑星は？"
    assert len(result.options) == 4
    assert result.correct_option_index == 2
    assert result.tap_x == 540  # 500 / 1000 * 1080
    assert result.tap_y == 1776  # 740 / 1000 * 2400


def test_gemini_solver_parse_non_quiz_screen():
    solver = GeminiQuizSolver(api_key=None)
    raw_json = json.dumps({
        "is_quiz_screen": False,
        "reasoning": "This is a home menu screen or loading screen.",
    })
    result = solver._parse_gemini_response(raw_json, screen_width=1080, screen_height=2400)

    assert result.is_quiz_screen is False
    assert result.tap_x is None
    assert result.tap_y is None


def test_gemini_solver_fallback_to_option_center():
    solver = GeminiQuizSolver(api_key=None)
    response_payload = {
        "is_quiz_screen": True,
        "question": "テスト問題",
        "options": [
            {"index": 1, "text": "選択肢A", "box_norm": [500, 200, 600, 800]},
            {"index": 2, "text": "選択肢B", "box_norm": [650, 200, 750, 800]},
        ],
        "correct_option_index": 1,
        # No tap_target_norm provided
    }
    result = solver._parse_gemini_response(json.dumps(response_payload), screen_width=1000, screen_height=1000)
    assert result.is_quiz_screen is True
    assert result.correct_option_index == 1
    # Bounding box center for index 1: y = (500+600)/2 = 550, x = (200+800)/2 = 500
    assert result.tap_x == 500
    assert result.tap_y == 550


def test_quiz_bot_process_screen_and_tap():
    mock_device = MockDeviceDriver(screen_size=(1080, 2400))
    mock_solver = MagicMock(spec=GeminiQuizSolver)

    # Mock return value from solver
    mock_solver.analyze_and_solve.return_value = QuizAnalysisResult(
        is_quiz_screen=True,
        question="日本の最高峰は？",
        options=[
            QuizOption(index=1, text="富士山"),
            QuizOption(index=2, text="北岳"),
            QuizOption(index=3, text="奥穂高岳"),
            QuizOption(index=4, text="間ノ岳"),
        ],
        correct_option_index=1,
        confidence=1.0,
        reasoning="富士山（3,776m）が日本で最も高い山です。",
        tap_x=540,
        tap_y=800,
    )

    bot = QuizBot(device=mock_device, solver=mock_solver, dry_run=False, save_debug=False)
    res = bot.process_one_screen()

    assert res.is_quiz_screen is True
    assert (540, 800) in mock_device.tapped_coordinates


def test_quiz_bot_dry_run():
    mock_device = MockDeviceDriver(screen_size=(1080, 2400))
    mock_solver = MagicMock(spec=GeminiQuizSolver)
    mock_solver.analyze_and_solve.return_value = QuizAnalysisResult(
        is_quiz_screen=True,
        question="日本の最高峰は？",
        options=[],
        correct_option_index=1,
        tap_x=540,
        tap_y=800,
    )

    bot = QuizBot(device=mock_device, solver=mock_solver, dry_run=True, save_debug=False)
    bot.process_one_screen()

    # Dry-run should not tap
    assert len(mock_device.tapped_coordinates) == 0


def test_quiz_bot_continuous_loop_max_iterations():
    mock_device = MockDeviceDriver()
    mock_solver = MagicMock(spec=GeminiQuizSolver)
    mock_solver.analyze_and_solve.return_value = QuizAnalysisResult(
        is_quiz_screen=True,
        question="ループテスト",
        options=[],
        correct_option_index=1,
        tap_x=100,
        tap_y=200,
    )

    bot = QuizBot(device=mock_device, solver=mock_solver, loop_interval=0.01, save_debug=False)
    bot.run_continuous_loop(max_iterations=3)

    assert mock_solver.analyze_and_solve.call_count == 3
    assert len(mock_device.tapped_coordinates) == 3


def test_load_config_env_precedence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env_test_key_12345")
    cfg = load_config(None)
    assert cfg["gemini_api_key"] == "env_test_key_12345"
