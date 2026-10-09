from app.services.stage_scoring import default_mapping, score_transition, validate_mapping
import pytest


def test_defaults_have_valid_terminal_categories():
    rows = [vars(row) for row in default_mapping()]
    assert validate_mapping(rows) == default_mapping()
    assert rows[-2]["probability"] == 100
    assert rows[-1]["probability"] == 0


def test_transition_is_deterministic_and_not_cumulative():
    mapping = default_mapping()
    first = score_transition("New", "Qualified", mapping, 20)
    again = score_transition("Qualified", "Qualified", mapping, 20)
    assert first["stage_score"] == again["stage_score"] == 35
    assert first["changed"] is True
    assert again["changed"] is False
    assert again["engagement_score"] == 20


@pytest.mark.parametrize("field,value", [
    ("probability", 101), ("probability", True), ("stage_score", -1),
    ("record_category", "Unknown"), ("forecast_category", "Unknown"),
])
def test_invalid_mapping_rejected(field, value):
    rows = [vars(default_mapping()[0]).copy()]
    rows[0][field] = value
    with pytest.raises(ValueError):
        validate_mapping(rows)


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        score_transition("New", "Missing", default_mapping())


def test_duplicate_stage_rejected():
    rows = [vars(default_mapping()[0]), vars(default_mapping()[0])]
    with pytest.raises(ValueError, match="Duplicate"):
        validate_mapping(rows)
