import pytest

from time_scheduler.hermes import extract_json


def test_extract_json_accepts_plain_or_fenced_objects():
    assert extract_json('{"tasks": []}') == {"tasks": []}
    assert extract_json('```json\n{"tasks": []}\n```') == {"tasks": []}


def test_extract_json_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        extract_json("[]")

