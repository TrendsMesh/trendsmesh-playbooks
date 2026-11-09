"""tm.json_schema: the small schema check shared by the playbooks' data files (PB04's report.json,
PB02's brief pack), tried on the handoff's own schemas and examples."""

import copy
import json
import re
from pathlib import Path

import pytest

from tm import json_schema

REPO = Path(__file__).resolve().parents[4]
PB04 = REPO / "handoff" / "trend-research_v01"
PB02 = REPO / "handoff" / "creative-brief_v02"
REPORT_SCHEMA = PB04 / "playbook-04-trend-research" / "schema" / "report.schema.json"
BRIEF_SCHEMA = PB02 / "playbook-02-creative-brief" / "schema" / "brief.schema.json"
BRIEF_PACK = PB02 / "examples" / "ld-en-dry-run" / "04_final" / "brief_pack_v01.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.private_data
def test_pb04_report_holds_and_breaks():
    schema = json_schema.load(REPORT_SCHEMA)
    report = _read(PB04 / "examples" / "beauty-dry-run" / "04_final" / "report_v05" / "report.json")
    assert json_schema.problems(report, schema, "report") == []
    bad = copy.deepcopy(report)
    bad["outputs"] = ["report", "slides"]                                   # enum
    bad["act_now"][0]["trend"]["bucket"] = "soon"                           # enum through #/definitions/...
    bad["moves"][0].pop("why")
    assert json_schema.problems(bad, schema, "report") == [
        "report.outputs[1] is 'slides', not one of 'report', 'digest', 'paid'",
        "report.act_now[0].trend.bucket is 'soon', not one of 'act_now', 'still_rising', 'too_late', 'past_peak'",
        "report.moves[0] lacks why"]


@pytest.mark.private_data
def test_pb02_brief_pack_holds_and_breaks():
    schema = json_schema.load(BRIEF_SCHEMA)
    pack = _read(BRIEF_PACK)
    assert "$defs" in schema and json_schema.problems(pack, schema, "brief") == []
    bad = copy.deepcopy(pack)
    del bad["meta"]["title"]
    bad["meta"]["recipients"] = ["decision", "intern"]                     # enum without a type
    bad["concepts"] = []                                                    # minItems 1
    problems = json_schema.problems(bad, schema, "brief")
    assert "brief.meta lacks title" in problems
    assert any(p.startswith("brief.meta.recipients[1] is 'intern', not one of") for p in problems)
    assert "brief.concepts has 0 items, fewer than 1" in problems
    # a concept is checked through #/$defs/concept
    bad = copy.deepcopy(pack)
    bad["concepts"][0] = "C1"
    assert json_schema.problems(bad, schema, "brief") == ["brief.concepts[0] is str, not object"]


def test_max_items_refs_and_bad_refs():
    schema = {"type": "object", "properties": {"tags": {"type": "array", "maxItems": 2, "items": {"$ref": "#/$defs/tag"}}},
              "$defs": {"tag": {"type": "string"}, "a~/b": {"const": 1}}}
    assert json_schema.problems({"tags": ["a", "b", 3]}, schema) == [
        "data.tags has 3 items, more than 2", "data.tags[2] is int, not string"]
    assert json_schema.resolve(schema, "#/$defs/a~0~1b") == {"const": 1}            # JSON pointer escapes
    with pytest.raises(ValueError, match="points to nothing"):
        json_schema.problems(1, {"$ref": "#/definitions/none"})
    with pytest.raises(ValueError, match="only references inside the schema"):
        json_schema.problems(1, {"$ref": "other.json#/x"})
    with pytest.raises(ValueError, match="never reaches a schema"):
        json_schema.problems(1, {"$ref": "#"})


def test_additional_properties_false_and_pattern_are_checked():
    schema = {"type": "object", "required": ["id"], "additionalProperties": False,
              "properties": {"id": {"type": "string", "pattern": "^[0-9a-f]{4}$"}, "n": {"type": "integer"}}}
    assert json_schema.problems({"id": "ab12", "n": 1}, schema) == []
    assert json_schema.problems({"id": "AB12", "n": 1, "x": 2}, schema) == [
        "data.id is 'AB12', which does not match '^[0-9a-f]{4}$'",
        "data has x, which the schema does not allow"]



def test_an_invalid_pattern_is_a_plain_value_error():
    """A broken regular expression in the schema is the schema's fault: a plain ValueError naming it."""
    schema = {"type": "object", "properties": {"id": {"type": "string", "pattern": "^[0-9"}}}
    with pytest.raises(ValueError, match=r"pattern '\^\[0-9' at #/properties/id is not a valid regular expression") as got:
        json_schema.problems({"id": "1"}, schema)
    assert not isinstance(got.value, re.error)
    with pytest.raises(ValueError, match="not a valid regular expression"):
        json_schema.problems({}, schema)                    # refused even where the data never reaches it

def test_enum_and_const_tell_true_from_one():
    schema = {"type": "object", "properties": {"flag": {"enum": [1, 2]}, "on": {"const": True},
                                               "f": {"enum": [1.0]}}}
    assert json_schema.problems({"flag": 1, "on": True, "f": 1}, schema) == []
    assert json_schema.problems({"flag": True, "on": 1}, schema) == [
        "data.flag is True, not one of 1, 2", "data.on is 1, not True"]
    assert json_schema.problems({"x": [True]}, {"properties": {"x": {"const": [1]}}}) == ["data.x is [True], not [1]"]


@pytest.mark.parametrize("keyword, sub", [
    ("anyOf", [{"type": "string"}, {"type": "null"}]), ("oneOf", [{"type": "string"}]), ("allOf", [{"type": "string"}]),
    ("not", {"type": "string"}), ("items", [{"type": "string"}]), ("patternProperties", {"^x": {"type": "string"}})])
def test_unsupported_keywords_refuse_the_schema(keyword, sub):
    """Refused even where the data never reaches them: an unchecked keyword never passes a file."""
    schema = {"type": "object", "definitions": {"d": {keyword: sub}},
              "properties": {"a": {"type": "object", "properties": {"b": {keyword: sub}}}}}
    with pytest.raises(ValueError, match=f"uses {keyword}"):
        json_schema.problems({}, schema)
    # a property merely named like a keyword is not one
    assert json_schema.problems({"not": 1}, {"properties": {"not": {"type": "integer"}}}) == []
