import pytest

from decision_tree import classify_label, compute_risk_score


def _build_gemini(features, confidence=0.9):
    return {
        "features": features,
        "overall_confidence": confidence,
    }


def test_compute_risk_score_caps_at_100():
    features = {
        "discharge": {"present": True, "type": "purulent"},
        "redness": {"present": True, "extent_percent": 80},
        "swelling": {"present": True},
        "dressing_lift": {"present": True},
        "open_wound": {"present": True},
    }
    assert compute_risk_score(features) == 100


def test_classify_label_returns_red_for_purulent():
    features = {
        "discharge": {"present": True, "type": "purulent"},
        "redness": {"present": False},
        "swelling": {"present": False},
    }
    result = classify_label(_build_gemini(features))
    assert result["label"] == "Red"
    assert "Purulent" in result["explanation"]


def test_classify_label_handles_low_confidence():
    features = {
        "discharge": {"present": False},
        "redness": {"present": False},
    }
    result = classify_label(_build_gemini(features, confidence=0.3))
    assert result["label"] == "Uncertain"


def test_classify_label_uses_risk_score_for_yellow():
    features = {
        "discharge": {"present": False},
        "redness": {"present": True, "extent_percent": 60},
        "swelling": {"present": True},
    }
    result = classify_label(_build_gemini(features))
    assert result["label"] == "Yellow"
    assert result["risk_score"] >= 25
