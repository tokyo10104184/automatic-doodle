"""Gemini Vision based 4-choice quiz solver supporting both google-genai and google-generativeai."""
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)

# Try newer google.genai SDK first, fallback to google.generativeai
HAVE_NEW_GENAI = False
HAVE_OLD_GENAI = False

try:
    from google import genai
    from google.genai import types
    HAVE_NEW_GENAI = True
except ImportError:
    pass

if not HAVE_NEW_GENAI:
    try:
        import google.generativeai as old_genai
        HAVE_OLD_GENAI = True
    except ImportError:
        pass


@dataclass
class QuizOption:
    index: int  # 1 to 4
    text: str
    box_2d: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] normalized 0-1000
    center_x: Optional[int] = None      # Pixel coordinate
    center_y: Optional[int] = None      # Pixel coordinate


@dataclass
class QuizAnalysisResult:
    is_quiz_screen: bool
    question: Optional[str] = None
    options: Optional[List[QuizOption]] = None
    correct_option_index: Optional[int] = None  # 1 to 4
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    tap_x: Optional[int] = None  # Final target tap coordinates
    tap_y: Optional[int] = None
    raw_response: Optional[str] = None


SOLVER_SYSTEM_PROMPT = """You are an expert quiz solver specialized in Android mobile quiz games.
Analyze the provided Android screenshot.

Determine if this screen is currently displaying a 4-choice quiz question.
If it is NOT a quiz screen (e.g. ad, loading screen, result screen, home menu), set "is_quiz_screen": false.

If it IS a 4-choice quiz screen:
1. Extract the question text accurately.
2. Extract the 4 options (ordered 1 to 4 from top to bottom or designated numbers).
3. Determine the single correct answer based on world knowledge and trivia facts.
4. For each option, determine its bounding box coordinates on the screen normalized from 0 to 1000:
   [ymin, xmin, ymax, xmax], where (0,0) is top-left and (1000, 1000) is bottom-right.
5. Identify the center coordinates [tap_y_normalized, tap_x_normalized] (0-1000) of the CORRECT option button so it can be tapped.

Respond strictly in valid JSON format matching this schema:
{
  "is_quiz_screen": true,
  "question": "string question text",
  "options": [
    {"index": 1, "text": "Option 1", "box_norm": [ymin, xmin, ymax, xmax]},
    {"index": 2, "text": "Option 2", "box_norm": [ymin, xmin, ymax, xmax]},
    {"index": 3, "text": "Option 3", "box_norm": [ymin, xmin, ymax, xmax]},
    {"index": 4, "text": "Option 4", "box_norm": [ymin, xmin, ymax, xmax]}
  ],
  "correct_option_index": 1,
  "confidence": 0.95,
  "reasoning": "brief explanation why this option is correct",
  "tap_target_norm": [y_center_norm, x_center_norm]
}
"""


class GeminiQuizSolver:
    """Uses Gemini Multimodal Vision to identify and solve 4-choice quizzes from screenshots."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._new_client = None
        self._old_model = None

        if self.api_key:
            if HAVE_NEW_GENAI:
                self._new_client = genai.Client(api_key=self.api_key)
            elif HAVE_OLD_GENAI:
                old_genai.configure(api_key=self.api_key)
                self._old_model = old_genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=SOLVER_SYSTEM_PROMPT,
                    generation_config={"response_mime_type": "application/json"},
                )

    def analyze_and_solve(self, image: Image.Image) -> QuizAnalysisResult:
        """Analyzes screen image and calculates correct answer and tap coordinates."""
        if not self._new_client and not self._old_model:
            raise RuntimeError(
                "Gemini API client is not initialized. Please set GEMINI_API_KEY environment variable or pass api_key."
            )

        width, height = image.size
        if image.mode != "RGB":
            image = image.convert("RGB")

        prompt = "Analyze this Android screenshot, solve the quiz, and return the coordinates to tap."

        try:
            if self._new_client:
                # Use official new google.genai SDK
                response = self._new_client.models.generate_content(
                    model=self.model_name,
                    contents=[image, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=SOLVER_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text or ""
            else:
                # Fallback to old SDK
                response = self._old_model.generate_content([image, prompt])
                raw_text = response.text or ""

            return self._parse_gemini_response(raw_text, width, height)
        except Exception as e:
            logger.error("Error calling Gemini API: %s", e)
            raise

    def _parse_gemini_response(self, text: str, screen_width: int, screen_height: int) -> QuizAnalysisResult:
        """Parses the JSON response from Gemini Vision into QuizAnalysisResult with pixel coordinates."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("Failed to decode JSON directly from Gemini: %s. Response was: %s", e, text)
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                return QuizAnalysisResult(
                    is_quiz_screen=False,
                    reasoning=f"Failed to parse Gemini output: {e}",
                    raw_response=text,
                )

        is_quiz = data.get("is_quiz_screen", False)
        if not is_quiz:
            return QuizAnalysisResult(
                is_quiz_screen=False,
                reasoning=data.get("reasoning", "Not a quiz screen"),
                raw_response=text,
            )

        question = data.get("question", "")
        correct_idx = data.get("correct_option_index")
        confidence = data.get("confidence", 1.0)
        reasoning = data.get("reasoning", "")

        options_list: List[QuizOption] = []
        for opt_data in data.get("options", []):
            idx = opt_data.get("index", 0)
            opt_text = opt_data.get("text", "")
            box = opt_data.get("box_norm")
            cx, cy = None, None
            if box and len(box) == 4:
                ymin, xmin, ymax, xmax = box
                cx = int(((xmin + xmax) / 2.0 / 1000.0) * screen_width)
                cy = int(((ymin + ymax) / 2.0 / 1000.0) * screen_height)
            options_list.append(
                QuizOption(index=idx, text=opt_text, box_2d=box, center_x=cx, center_y=cy)
            )

        # Calculate tap coordinates
        tap_x, tap_y = None, None
        tap_norm = data.get("tap_target_norm")
        if tap_norm and len(tap_norm) == 2:
            norm_y, norm_x = tap_norm
            tap_x = int((norm_x / 1000.0) * screen_width)
            tap_y = int((norm_y / 1000.0) * screen_height)
        elif correct_idx is not None:
            for opt in options_list:
                if opt.index == correct_idx and opt.center_x and opt.center_y:
                    tap_x = opt.center_x
                    tap_y = opt.center_y
                    break

        return QuizAnalysisResult(
            is_quiz_screen=True,
            question=question,
            options=options_list,
            correct_option_index=correct_idx,
            confidence=confidence,
            reasoning=reasoning,
            tap_x=tap_x,
            tap_y=tap_y,
            raw_response=text,
        )
