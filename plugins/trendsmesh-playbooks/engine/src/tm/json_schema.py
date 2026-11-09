"""A small JSON Schema check for the playbooks' own data files (PB04's report.json; PB02's and PB03's
schemas use the same keywords). No dependency.

    problems(data, schema, name="data") -> ["<where> <what is wrong>", ...], empty when it holds

Checked: `type` (one or a list), `required`, `const`, `enum` (`true` and `1` differ), `pattern`,
`minItems`, `maxItems`, through `properties`, `items` (a schema), `additionalProperties` (a schema,
or `false`: no other key) and `$ref` (a JSON pointer into the schema itself, so `#/definitions/x`
and `#/$defs/x` both work). A schema that uses a keyword that changes what holds and is not checked
here (`anyOf`, `oneOf`, `allOf`, `not`, `if`/`then`/`else`, `patternProperties`, `prefixItems`,
`items` as a list ...) is refused with a ValueError, never passed silently; so is a `pattern` that is
not a valid regular expression. Annotations and the
remaining assertions (`format`, `minimum`, `default`, descriptions ...) are ignored.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_TYPES = {"object": dict, "array": list, "string": str, "null": type(None), "boolean": bool}
UNSUPPORTED = ("anyOf", "oneOf", "allOf", "not", "if", "then", "else", "patternProperties", "prefixItems",
               "dependentSchemas", "dependentRequired", "dependencies", "contains", "unevaluatedProperties",
               "unevaluatedItems")


def _equal(a: object, b: object) -> bool:
    """JSON equality: true and 1 differ (Python says True == 1); 1 and 1.0 are the same number."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    return a == b


def load(path: Path) -> dict:
    """A schema file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _is(value: object, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES.get(kind, ()))


def resolve(root: dict, ref: str) -> dict:
    """The schema a local `$ref` points to (`#/definitions/x`, `#/$defs/x`, `#`); ValueError for any
    other reference."""
    if not isinstance(ref, str) or not ref.startswith("#"):
        raise ValueError(f"The schema refers to {ref!r}; only references inside the schema (#/...) are supported.")
    node: object = root
    for part in [p for p in ref[1:].split("/") if p]:
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise ValueError(f"The schema's reference {ref!r} points to nothing.")
        node = node[part]
    if not isinstance(node, dict):
        raise ValueError(f"The schema's reference {ref!r} does not point to a schema.")
    return node


def _short(value: object) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _refuse_unsupported(node: object, where: str = "#") -> None:
    """ValueError when a schema, or any schema inside it, uses a keyword this check does not support,
    or a `pattern` that is not a valid regular expression."""
    if not isinstance(node, dict):
        return
    found = [k for k in UNSUPPORTED if k in node] + (["items (a list)"] if isinstance(node.get("items"), list) else [])
    if found:
        raise ValueError(f"The schema uses {', '.join(found)} at {where}, which this check does not support; it refuses "
                         "the schema rather than pass every file.")
    if isinstance(node.get("pattern"), str):
        try:
            re.compile(node["pattern"])
        except re.error as exc:
            raise ValueError(f"The schema's pattern {node['pattern']!r} at {where} is not a valid regular expression "
                             f"({exc}); fix the schema.") from None
    for group in ("properties", "definitions", "$defs"):
        for k, sub in (node.get(group) or {}).items() if isinstance(node.get(group), dict) else ():
            _refuse_unsupported(sub, f"{where}/{group}/{k}")
    for key in ("items", "additionalProperties"):
        _refuse_unsupported(node.get(key), f"{where}/{key}")


def problems(data: object, schema: dict, name: str = "data") -> list[str]:
    """What in `data` breaks `schema` (see the module docstring); empty when it holds. ValueError
    for a schema this check cannot read in full."""
    _refuse_unsupported(schema)
    out: list[str] = []

    def walk(value: object, s: dict, where: str, refs: int = 0) -> None:
        if "$ref" in s:
            if refs > 50:                      # $ref to $ref ... without reaching a schema
                raise ValueError(f"The schema's reference {s['$ref']!r} never reaches a schema.")
            walk(value, resolve(schema, s["$ref"]), where, refs + 1)
            return
        if "const" in s and not _equal(value, s["const"]):
            out.append(f"{where} is {_short(value)}, not {s['const']!r}")
        if "enum" in s and not any(_equal(value, e) for e in s["enum"]):
            out.append(f"{where} is {_short(value)}, not one of {', '.join(map(repr, s['enum']))}")
        if isinstance(value, str) and isinstance(s.get("pattern"), str) and not re.search(s["pattern"], value):
            out.append(f"{where} is {_short(value)}, which does not match {s['pattern']!r}")
        if "type" in s:
            kinds = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_is(value, k) for k in kinds):
                out.append(f"{where} is {type(value).__name__}, not {' or '.join(kinds)}")
                return
        if isinstance(value, dict):
            out.extend(f"{where} lacks {k}" for k in s.get("required", []) if k not in value)
            props = s.get("properties") or {}
            for k, sub in props.items():
                if k in value and isinstance(sub, dict):
                    walk(value[k], sub, f"{where}.{k}")
            extra = s.get("additionalProperties")
            if isinstance(extra, dict):
                for k, v in value.items():
                    if k not in props:
                        walk(v, extra, f"{where}.{k}")
            elif extra is False:
                out.extend(f"{where} has {k}, which the schema does not allow" for k in value if k not in props)
        if isinstance(value, list):
            if isinstance(s.get("minItems"), int) and len(value) < s["minItems"]:
                out.append(f"{where} has {len(value)} items, fewer than {s['minItems']}")
            if isinstance(s.get("maxItems"), int) and len(value) > s["maxItems"]:
                out.append(f"{where} has {len(value)} items, more than {s['maxItems']}")
            if isinstance(s.get("items"), dict):
                for i, v in enumerate(value):
                    walk(v, s["items"], f"{where}[{i}]")

    walk(data, schema, name)
    return out
