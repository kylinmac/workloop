"""Small JSON Schema subset used when the host has no jsonschema package."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationError:
    path: tuple
    message: str

    @property
    def json_path(self) -> str:
        return "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in self.path
        )


class Validator:
    def __init__(self, schema: dict):
        self.schema = schema

    @staticmethod
    def check_schema(schema: dict) -> None:
        if not isinstance(schema, dict):
            raise ValueError("schema must be an object")

    def iter_errors(self, value):
        yield from self._errors(value, self.schema, ())

    def _resolve(self, schema: dict) -> dict:
        reference = schema.get("$ref")
        if not reference:
            return schema
        target = self.schema
        for part in reference.removeprefix("#/").split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return target

    def _valid(self, value, schema: dict) -> bool:
        return not any(self._errors(value, schema, ()))

    def _errors(self, value, raw_schema: dict, path: tuple):
        schema = self._resolve(raw_schema)
        for clause in schema.get("allOf", []):
            yield from self._errors(value, clause, path)
        if "anyOf" in schema and not any(self._valid(value, item) for item in schema["anyOf"]):
            yield ValidationError(path, "does not match any allowed schema")
        if "oneOf" in schema and sum(self._valid(value, item) for item in schema["oneOf"]) != 1:
            yield ValidationError(path, "does not match exactly one allowed schema")
        if "not" in schema and self._valid(value, schema["not"]):
            yield ValidationError(path, "matches a forbidden schema")
        if "if" in schema and self._valid(value, schema["if"]):
            yield from self._errors(value, schema.get("then", {}), path)
        elif "else" in schema:
            yield from self._errors(value, schema["else"], path)

        expected = schema.get("type")
        if expected is not None:
            options = expected if isinstance(expected, list) else [expected]
            if not any(self._is_type(value, item) for item in options):
                yield ValidationError(path, f"{value!r} is not of type {expected!r}")
                return
        if "const" in schema and value != schema["const"]:
            yield ValidationError(path, f"{value!r} is not equal to {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            yield ValidationError(path, f"{value!r} is not one of {schema['enum']!r}")

        if isinstance(value, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in value:
                    yield ValidationError(path, f"{key!r} is a required property")
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            for key, item in value.items():
                if key in properties:
                    yield from self._errors(item, properties[key], path + (key,))
                elif isinstance(additional, dict):
                    yield from self._errors(item, additional, path + (key,))
                elif additional is False:
                    yield ValidationError(path, f"additional property {key!r} is not allowed")
        elif isinstance(value, list):
            if len(value) < schema.get("minItems", 0):
                yield ValidationError(path, "array is shorter than minItems")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                yield ValidationError(path, "array is longer than maxItems")
            if schema.get("uniqueItems"):
                for index, item in enumerate(value):
                    if item in value[:index]:
                        yield ValidationError(path + (index,), "array items are not unique")
            contains = schema.get("contains")
            if contains and not any(self._valid(item, contains) for item in value):
                yield ValidationError(path, "array does not contain a required item")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    yield from self._errors(item, item_schema, path + (index,))
        elif isinstance(value, str):
            if len(value) < schema.get("minLength", 0):
                yield ValidationError(path, "string is shorter than minLength")
            pattern = schema.get("pattern")
            if pattern:
                flags = re.IGNORECASE if pattern.startswith("(?i)") else 0
                expression = pattern[4:] if flags else pattern
                if re.search(expression, value, flags) is None:
                    yield ValidationError(path, f"{value!r} does not match {pattern!r}")
            if schema.get("format") == "date-time":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    yield ValidationError(path, f"{value!r} is not a date-time")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                yield ValidationError(path, f"{value!r} is less than minimum")

    @staticmethod
    def _is_type(value, expected: str) -> bool:
        return {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(expected, True)
