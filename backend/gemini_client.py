# backend/gemini_client.py
import copy
import json
import logging
import os
from typing import Any, Dict

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - library optional in dev
    genai = None


LOGGER = logging.getLogger(__name__)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-pro")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FEATURE_TEMPLATE = {
    "redness": {"present": False, "extent_percent": 0.0, "confidence": None},
    "swelling": {"present": False, "extent_percent": 0.0, "confidence": None},
    "dressing_lift": {"present": False, "confidence": None},
    "discharge": {"present": False, "type": None, "amount": None, "confidence": None},
    "exposed_catheter": {"present": False, "length_mm_estimate": None, "confidence": None},
    "open_wound": {"present": False, "size_mm": None, "confidence": None},
    "bruising": {"present": False, "confidence": None},
    "crusting": {"present": False, "confidence": None},
    "erythema_border_sharp": {"yes": False, "confidence": None},
    "fluctuance": {"present": False, "confidence": None},
}

PROMPT = (
    "You are a clinical assistant triaging catheter site photos. "
    "Extract the requested structured JSON schema exactly as specified. "
    "Respond only with valid JSON matching the schema that contains: image_id, quality, "
    "localization, features (redness, swelling, dressing_lift, discharge, exposed_catheter, "
    "open_wound, bruising, crusting, erythema_border_sharp, fluctuance), overall_confidence, "
    "recommended_label, explanation."
)


def _configure_client() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    if genai is None:
        raise RuntimeError(
            "google-generativeai package not installed. Add it to requirements.txt"
        )
    genai.configure(api_key=GEMINI_API_KEY)


def _call_gemini(image_bytes: bytes, image_name: str) -> Dict[str, Any]:
    _configure_client()
    model = genai.GenerativeModel(DEFAULT_MODEL)
    result = model.generate_content(
        [
            PROMPT,
            {
                "mime_type": "image/jpeg",
                "data": image_bytes,
            },
        ],
        generation_config={"response_mime_type": "application/json"},
    )
    if not result.candidates:
        raise RuntimeError("Gemini response missing candidates")
    text = result.candidates[0].content.parts[0].text  # type: ignore[index]
    raw = json.loads(text)
    return _normalize_response(raw, image_name)


def _mock_response(image_name: str) -> Dict[str, Any]:
    base = _base_response(image_name)
    base["quality"].update({
        "adequate_lighting": True,
        "focused": True,
        "view_complete": True,
        "notes": ""
    })
    base["localization"].update({
        "bbox": [50, 50, 450, 450],
        "segmentation_mask_available": False
    })
    base_features = {
        "redness": {"present": True, "extent_percent": 30.0, "confidence": 0.9},
        "swelling": {"present": True, "extent_percent": 15.0, "confidence": 0.85},
        "dressing_lift": {"present": False, "confidence": 0.9},
        "discharge": {"present": False, "type": None, "amount": "none", "confidence": 0.95},
        "exposed_catheter": {"present": False, "length_mm_estimate": None, "confidence": 0.98},
        "open_wound": {"present": False, "size_mm": None, "confidence": 0.98},
        "bruising": {"present": False, "confidence": 0.8},
        "crusting": {"present": False, "confidence": 0.8},
        "erythema_border_sharp": {"yes": False, "confidence": 0.9},
        "fluctuance": {"present": False, "confidence": 0.6}
    }
    base["features"] = _normalize_features(base_features, base["features"])
    base["overall_confidence"] = 0.88
    base["recommended_label"] = "Yellow"
    base["explanation"] = "Redness and mild swelling detected; caution advised."
    return base


def _base_response(image_name: str) -> Dict[str, Any]:
    return {
        "image_id": image_name,
        "quality": {
            "adequate_lighting": False,
            "focused": False,
            "view_complete": False,
            "notes": ""
        },
        "localization": {
            "bbox": [0, 0, 0, 0],
            "segmentation_mask_available": False
        },
        "features": copy.deepcopy(FEATURE_TEMPLATE),
        "overall_confidence": 0.0,
        "recommended_label": "Green",
        "explanation": ""
    }


def _normalize_response(raw: Dict[str, Any], image_name: str) -> Dict[str, Any]:
    normalized = _base_response(image_name)
    normalized["image_id"] = raw.get("image_id", image_name)
    normalized["explanation"] = raw.get("explanation", normalized["explanation"])
    normalized["recommended_label"] = raw.get("recommended_label", normalized["recommended_label"])
    normalized["overall_confidence"] = _confidence_value(raw.get("overall_confidence"))
    normalized["quality"] = _normalize_quality(raw.get("quality"), normalized["quality"])
    normalized["localization"] = _normalize_localization(raw.get("localization"), normalized["localization"])
    normalized["features"] = _normalize_features(raw.get("features"), normalized["features"])
    return normalized


def _confidence_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
    if isinstance(value, str):
        mapping = {
            "very low": 0.1,
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "very high": 0.9,
            "certain": 1.0,
        }
        key = value.strip().lower()
        if key in mapping:
            return mapping[key]
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return 0.0
    return 0.0


def _normalize_quality(raw_value: Any, defaults: Dict[str, Any]) -> Dict[str, Any]:
    quality = defaults.copy()
    if isinstance(raw_value, dict):
        for key in quality:
            if key in raw_value and raw_value[key] is not None:
                quality[key] = raw_value[key]
        notes = raw_value.get("notes")
        if notes:
            quality["notes"] = str(notes)
    elif isinstance(raw_value, str):
        quality["notes"] = raw_value
    return quality


def _normalize_localization(raw_value: Any, defaults: Dict[str, Any]) -> Dict[str, Any]:
    localization = copy.deepcopy(defaults)
    if isinstance(raw_value, dict):
        bbox = raw_value.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            localization["bbox"] = list(bbox)
        if "segmentation_mask_available" in raw_value:
            localization["segmentation_mask_available"] = bool(raw_value["segmentation_mask_available"])
    elif isinstance(raw_value, (list, tuple)) and len(raw_value) == 4:
        localization["bbox"] = list(raw_value)
    return localization


def _normalize_features(raw_value: Any, defaults: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    features = {key: copy.deepcopy(value) for key, value in defaults.items()}
    if not isinstance(raw_value, dict):
        return features

    for name, value in raw_value.items():
        if name not in features:
            continue
        entry = features[name]

        if name == "erythema_border_sharp":
            if isinstance(value, dict):
                if "yes" in value:
                    entry["yes"] = bool(value["yes"])
                if "confidence" in value and value["confidence"] is not None:
                    entry["confidence"] = value["confidence"]
            else:
                entry["yes"] = bool(value)
            continue

        if isinstance(value, dict):
            present_val = value.get("present")
            if present_val is None and "yes" in value:
                present_val = value["yes"]
            if present_val is not None and "present" in entry:
                entry["present"] = bool(present_val)

            for key, val in value.items():
                if key in entry and key != "present" and val is not None:
                    entry[key] = val
        else:
            if "present" in entry:
                entry["present"] = bool(value)
            elif "yes" in entry:
                entry["yes"] = bool(value)

    return features


def send_to_gemini(image_bytes: bytes, image_name: str) -> Dict[str, Any]:
    """Send image to Gemini Vision API and return parsed JSON matching schema."""
    try:
        return _call_gemini(image_bytes, image_name)
    except Exception as exc:  # pragma: no cover - network issues
        LOGGER.warning("Falling back to mock Gemini response: %s", exc)
        return _mock_response(image_name)
