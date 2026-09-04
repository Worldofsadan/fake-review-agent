"""
AI Agent — Fake Review Classifier
----------------------------------
Supports:
- Claude API mode
- Free offline demo mode

Demo mode is used when DEMO_MODE=true.
"""

import os
import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import (
    MODEL_VERSION,
    PROMPT_VERSION,
    get_confidence_level,
    needs_human_review,
)

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() == "true"

# Keep a default client so tests can still monkeypatch _client.
_client = anthropic.Anthropic(api_key=API_KEY)
_DEFAULT_CLIENT = _client

# Load system prompt
_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"

with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATE = f.read()

VALID_LABELS = {"Fake", "Genuine"}


class AgentResponseError(Exception):
    """Raised when the AI agent response is invalid."""
    pass


def build_prompt(review_text: str, rating: int | None = None) -> str:
    """Fill the system prompt template with review details."""
    return PROMPT_TEMPLATE.format(
        review_text=review_text.strip(),
        rating=rating if rating is not None else "Not provided",
    )


def validate_agent_output(raw: dict) -> dict:
    """
    Strictly validates the agent output.
    """

    if not isinstance(raw, dict):
        raise AgentResponseError(
            f"Agent response is not a JSON object: {raw!r}"
        )

    label = raw.get("label")

    if not isinstance(label, str) or label not in VALID_LABELS:
        raise AgentResponseError(
            f"Invalid or missing 'label': {label!r} "
            f"(must be Fake or Genuine)"
        )

    confidence = raw.get("confidence")

    if isinstance(confidence, bool) or not isinstance(
        confidence, (int, float)
    ):
        raise AgentResponseError(
            f"Invalid 'confidence': {confidence!r} "
            f"(must be numeric)"
        )

    if not (0 <= confidence <= 100):
        raise AgentResponseError(
            f"'confidence' out of range: {confidence!r} "
            f"(must be 0-100)"
        )

    confidence = int(round(confidence))

    reasoning = raw.get("reasoning")

    if not isinstance(reasoning, str) or not reasoning.strip():
        raise AgentResponseError(
            "Invalid or missing 'reasoning' "
            "(must be a non-empty string)"
        )

    indicators = raw.get("indicators", [])

    if indicators is None:
        indicators = []

    if not isinstance(indicators, list) or not all(
        isinstance(i, str) for i in indicators
    ):
        raise AgentResponseError(
            f"Invalid 'indicators': {indicators!r} "
            f"(must be a list of strings)"
        )

    return {
        "label": label,
        "confidence": confidence,
        "reasoning": reasoning.strip(),
        "indicators": indicators,
        "confidence_level": get_confidence_level(confidence),
        "needs_human_review": needs_human_review(confidence),
    }


def _demo_classify(
    review_text: str,
    rating: int | None = None,
) -> dict:
    """
    Free offline demo classifier.

    This does NOT call Anthropic.
    It uses simple linguistic signals for demonstration.
    """

    text = review_text.strip()
    lower = text.lower()

    indicators = []
    score = 0

    # Excessive exclamation marks
    if text.count("!") >= 3:
        score += 30
        indicators.append("Excessive promotional language")

    # Strong promotional words
    promotional_words = [
        "best",
        "amazing",
        "perfect",
        "awesome",
        "excellent",
        "incredible",
        "love",
        "must buy",
        "changed my life",
        "everyone",
    ]

    found_words = [
        word for word in promotional_words
        if word in lower
    ]

    if len(found_words) >= 2:
        score += 30
        indicators.append("Multiple promotional expressions")

    # Repeated superlative language
    if lower.count("best") >= 2:
        score += 20
        indicators.append("Repeated superlative wording")

    # Very short review
    if len(text) < 40:
        score += 10
        indicators.append("Very short review")

    # Extreme rating + hype
    if rating == 5 and len(found_words) >= 2:
        score += 10
        indicators.append("Highly positive rating with promotional wording")

    if score >= 60:
        label = "Fake"
        confidence = min(95, 60 + score // 2)
    else:
        label = "Genuine"
        confidence = 72

    reasoning = (
        "Free demo mode: the review was analyzed using "
        "linguistic and promotional-language patterns. "
        "No external AI API was used."
    )

    return validate_agent_output(
        {
            "label": label,
            "confidence": confidence,
            "reasoning": reasoning,
            "indicators": indicators,
        }
    )


def classify_review(
    review_text: str,
    rating: int | None = None,
) -> dict:
    """
    Classifies a review using either:

    1. Free offline demo mode
    2. Claude API mode
    """

    # FREE OFFLINE MODE
    #
    # The _client check keeps compatibility with tests that
    # monkeypatch the Anthropic client.
    if DEMO_MODE and _client is _DEFAULT_CLIENT:
        return _demo_classify(review_text, rating)

    # CLAUDE API MODE
    prompt = build_prompt(review_text, rating)

    response = _client.messages.create(
        model=MODEL_VERSION,
        max_tokens=350,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    raw_text = response.content[0].text.strip()

    # Defensive cleanup for markdown JSON fences
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise AgentResponseError(
            f"Could not parse agent response as JSON: {raw_text}"
        ) from exc

    return validate_agent_output(parsed)


if __name__ == "__main__":

    sample_review = (
        "This product changed my life!!! "
        "Best purchase EVER, 10/10 would recommend "
        "to everyone!!!"
    )

    sample_rating = 5

    print("Testing review classifier...\n")

    try:
        output = classify_review(
            sample_review,
            sample_rating,
        )

        print(json.dumps(output, indent=2))

    except AgentResponseError as e:
        print(f"Agent error: {e}")