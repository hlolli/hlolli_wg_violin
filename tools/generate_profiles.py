#!/usr/bin/env python3
"""Validate violin profile JSON and emit the fixed C profile table."""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import math
import os
import re
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, NoReturn, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "profiles" / "manifest.json"
DEFAULT_SOURCE = ROOT / "src" / "hlolli_wg_violin.c"
SCHEMA_FILE = "schema/violin-profile-v1.schema.json"
BEGIN_MARKER = "/* BEGIN GENERATED VIOLIN PROFILE DATA */"
END_MARKER = "/* END GENERATED VIOLIN PROFILE DATA */"
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class ProfileError(ValueError):
    """Raised when source data or generated output breaks the profile contract."""


def fail(message: str) -> NoReturn:
    raise ProfileError(message)


def unique_object(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail("duplicate JSON key: " + key)
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    fail("non-finite JSON number: " + token)


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_float=Decimal,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail("cannot read {}: {}".format(path, error))


def schema_ref(root: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    if not ref.startswith("#/"):
        fail("unsupported schema reference: " + ref)
    value: Any = root
    for part in ref[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or key not in value:
            fail("unresolved schema reference: " + ref)
        value = value[key]
    if not isinstance(value, dict):
        fail("schema reference is not an object: " + ref)
    return value


def is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float, Decimal))


def json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def c_double(value: Any, path: str) -> float:
    if not is_number(value):
        fail(path + " is not a C number")
    result = float(value)
    if not math.isfinite(result):
        fail(path + " does not fit a finite binary64 value")
    return result


def quantize_numbers(value: Any, path: str = "$") -> Any:
    if is_number(value):
        return c_double(value, path)
    if isinstance(value, list):
        return [quantize_numbers(item, "{}[{}]".format(path, index)) for index, item in enumerate(value)]
    if isinstance(value, dict):
        return {key: quantize_numbers(item, path + "." + key) for key, item in value.items()}
    return value


def validate_schema(
    value: Any,
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    path: str = "$",
) -> None:
    """Validate the JSON Schema subset used by profile schema version 1."""
    if "$ref" in schema:
        validate_schema(value, schema_ref(root, schema["$ref"]), root, path)
    if "const" in schema and not json_equal(value, schema["const"]):
        fail("{} must equal {!r}".format(path, schema["const"]))
    if "enum" in schema and not any(json_equal(value, item) for item in schema["enum"]):
        fail("{} is not one of {!r}".format(path, schema["enum"]))

    kind = schema.get("type")
    if kind == "object" and not isinstance(value, dict):
        fail(path + " must be an object")
    if kind == "array" and not isinstance(value, list):
        fail(path + " must be an array")
    if kind == "string" and not isinstance(value, str):
        fail(path + " must be a string")
    if kind == "number" and not is_number(value):
        fail(path + " must be a number")

    object_rule = kind == "object" or "properties" in schema or "required" in schema
    if object_rule:
        if not isinstance(value, dict):
            fail(path + " must be an object")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            fail("{} lacks required keys: {}".format(path, ", ".join(missing)))
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                fail("{} has unknown keys: {}".format(path, ", ".join(extra)))
        for key, child_schema in properties.items():
            if key in value:
                validate_schema(value[key], child_schema, root, path + "." + key)

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            fail("{} has too few items".format(path))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            fail("{} has too many items".format(path))
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], root, "{}[{}]".format(path, index))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            fail(path + " is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            fail(path + " is too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            fail(path + " does not match " + schema["pattern"])

    if is_number(value):
        if isinstance(value, float) and not math.isfinite(value):
            fail(path + " must be finite")
        if isinstance(value, Decimal) and not value.is_finite():
            fail(path + " must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            fail("{} is below {}".format(path, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            fail("{} is above {}".format(path, schema["maximum"]))
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            fail("{} must exceed {}".format(path, schema["exclusiveMinimum"]))
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            fail("{} must be below {}".format(path, schema["exclusiveMaximum"]))

    for child_schema in schema.get("allOf", []):
        validate_schema(value, child_schema, root, path)
    if "if" in schema:
        try:
            validate_schema(value, schema["if"], root, path)
            matched = True
        except ProfileError:
            matched = False
        branch = "then" if matched else "else"
        if branch in schema:
            validate_schema(value, schema[branch], root, path)


def validate_profile(
    profile: Mapping[str, Any],
    schema: Mapping[str, Any],
    expected_id: Optional[str] = None,
) -> None:
    validate_schema(profile, schema, schema)
    profile_id = profile["id"]
    if expected_id is not None and profile_id != expected_id:
        fail("profile id {!r} does not match {}.json".format(profile_id, expected_id))
    try:
        display_bytes = profile["display_name"].encode("ascii")
    except UnicodeEncodeError:
        fail(profile_id + ": display_name must use printable ASCII")
    if not 1 <= len(display_bytes) <= 127 or any(byte < 32 or byte > 126 for byte in display_bytes):
        fail(profile_id + ": display_name must use 1 to 127 printable ASCII bytes")

    friction = profile["bow"]["friction"]
    if friction["floor_mu"] + friction["slow_gain"] + friction["fast_gain"] > Decimal("2.5"):
        fail(profile_id + ": bow friction sum exceeds 2.5")
    force_map = profile["bow"]["force_map"]
    if force_map["control_low"] >= force_map["control_high"]:
        fail(profile_id + ": force-map control_low must be below control_high")
    if force_map["control_high"] - force_map["control_low"] < Decimal("0.000001"):
        fail(profile_id + ": force-map middle span is below 0.000001")
    if force_map["extreme_max_scale"] < force_map["normal_max_scale"]:
        fail(profile_id + ": extreme_max_scale must be at least normal_max_scale")
    gestures = profile["gestures"]
    if gestures["detache"]["stroke_seconds"] < gestures["detache"]["onset_seconds"]:
        fail(profile_id + ": detache stroke must be at least its onset")
    martele = gestures["martele"]
    if martele["stroke_seconds"] < martele["preload_seconds"] + martele["acceleration_seconds"]:
        fail(profile_id + ": martele stroke must include preload and acceleration")
    spiccato = gestures["spiccato"]
    if spiccato["stroke_slow_seconds"] - spiccato["stroke_fast_seconds"] < Decimal("0.00001"):
        fail(profile_id + ": spiccato stroke range is below 0.00001")
    if gestures["tremolo"]["rate_min_hz"] > gestures["tremolo"]["rate_max_hz"]:
        fail(profile_id + ": tremolo rate_min_hz exceeds rate_max_hz")

    exciters = profile["exciters"]
    windows = [
        ("pizzicato_right", "pulse_min_seconds", "pulse_range_seconds"),
        ("pizzicato_left", "pulse_min_seconds", "pulse_range_seconds"),
        ("bartok", "pulse_min_seconds", "pulse_range_seconds"),
        ("bartok", "impact_delay_min_seconds", "impact_delay_range_seconds"),
        ("bartok", "impact_min_seconds", "impact_range_seconds"),
    ]
    for group, minimum, spread in windows:
        if exciters[group][minimum] + exciters[group][spread] > Decimal("0.004"):
            fail("{}: exciters.{} {} window exceeds 0.004".format(profile_id, group, minimum))

    matrix = profile["coupling"]["bridge_coefficients"]
    for row in range(4):
        if matrix[row][row] != 0:
            fail(profile_id + ": bridge matrix diagonal must be exact zero")
        for column in range(row + 1, 4):
            if matrix[row][column] != matrix[column][row]:
                fail(profile_id + ": bridge matrix must be symmetric")

    body = profile["body"]
    if body["body_decay_base"] <= body["body_decay_range"]:
        fail(profile_id + ": body_decay_base must exceed body_decay_range")
    previous = Decimal("0")
    for index, mode in enumerate(body["modes"]):
        if mode["frequency_hz"] <= previous:
            fail("{}: body mode frequencies must increase at {}".format(profile_id, index))
        if mode["bandwidth_hz"] > Decimal("2") * mode["frequency_hz"]:
            fail("{}: body mode {} bandwidth is too wide".format(profile_id, index))
        previous = mode["frequency_hz"]

    runtime = quantize_numbers(profile)
    validate_schema(runtime, schema, schema)
    runtime_friction = runtime["bow"]["friction"]
    static_mu = c_double(
        friction["floor_mu"] + friction["slow_gain"] + friction["fast_gain"],
        profile_id + ": derived static_mu",
    )
    component_static_mu = (
        runtime_friction["floor_mu"]
        + runtime_friction["slow_gain"]
        + runtime_friction["fast_gain"]
    )
    if abs(static_mu - component_static_mu) > 1.0e-12:
        fail(profile_id + ": derived static_mu differs after binary64 conversion")

    runtime_force = runtime["bow"]["force_map"]
    middle_span = c_double(
        force_map["control_high"] - force_map["control_low"],
        profile_id + ": derived control_middle_span",
    )
    high_span = c_double(
        Decimal("1") - force_map["control_high"],
        profile_id + ": derived control_high_span",
    )
    if not 0.000001 <= middle_span <= 1.0 or not 0.000001 <= high_span <= 1.0:
        fail(profile_id + ": derived force-map span is outside the C range")
    if abs(runtime_force["control_low"] + middle_span - runtime_force["control_high"]) > 1.0e-12:
        fail(profile_id + ": derived middle span differs after binary64 conversion")
    if abs(runtime_force["control_high"] + high_span - 1.0) > 1.0e-12:
        fail(profile_id + ": derived high span differs after binary64 conversion")
    if runtime_force["extreme_max_scale"] < runtime_force["normal_max_scale"]:
        fail(profile_id + ": binary64 extreme force scale is below normal scale")

    runtime_gestures = runtime["gestures"]
    if runtime_gestures["detache"]["stroke_seconds"] < runtime_gestures["detache"]["onset_seconds"]:
        fail(profile_id + ": binary64 detache stroke is shorter than its onset")
    runtime_martele = runtime_gestures["martele"]
    if runtime_martele["stroke_seconds"] < runtime_martele["preload_seconds"] + runtime_martele["acceleration_seconds"]:
        fail(profile_id + ": binary64 martele stroke omits preload or acceleration")
    runtime_spiccato = runtime_gestures["spiccato"]
    stroke_range = c_double(
        spiccato["stroke_slow_seconds"] - spiccato["stroke_fast_seconds"],
        profile_id + ": derived stroke_range_seconds",
    )
    if not 0.00001 <= stroke_range <= 2.0:
        fail(profile_id + ": binary64 spiccato stroke range is outside the C range")
    if runtime_spiccato["stroke_slow_seconds"] < runtime_spiccato["stroke_fast_seconds"]:
        fail(profile_id + ": binary64 spiccato slow stroke is shorter than fast")
    if abs(runtime_spiccato["stroke_fast_seconds"] + stroke_range - runtime_spiccato["stroke_slow_seconds"]) > 1.0e-12:
        fail(profile_id + ": derived spiccato range differs after binary64 conversion")
    if runtime_gestures["tremolo"]["rate_min_hz"] > runtime_gestures["tremolo"]["rate_max_hz"]:
        fail(profile_id + ": binary64 tremolo rate bounds are reversed")

    runtime_exciters = runtime["exciters"]
    for group, minimum, spread in windows:
        if runtime_exciters[group][minimum] + runtime_exciters[group][spread] > 0.004:
            fail("{}: binary64 exciters.{} window exceeds 0.004".format(profile_id, group))
    runtime_matrix = runtime["coupling"]["bridge_coefficients"]
    for row in range(4):
        if runtime_matrix[row][row] != 0.0:
            fail(profile_id + ": binary64 bridge matrix diagonal must be zero")
        for column in range(row + 1, 4):
            if runtime_matrix[row][column] != runtime_matrix[column][row]:
                fail(profile_id + ": binary64 bridge matrix must be symmetric")

    runtime_body = runtime["body"]
    if runtime_body["body_decay_range"] >= runtime_body["body_decay_base"]:
        fail(profile_id + ": binary64 body decay range must stay below its base")
    previous_frequency = 0.0
    for index, mode in enumerate(runtime_body["modes"]):
        if mode["frequency_hz"] <= previous_frequency:
            fail("{}: binary64 body mode frequencies do not increase at {}".format(profile_id, index))
        if mode["bandwidth_hz"] > 2.0 * mode["frequency_hz"]:
            fail("{}: binary64 body mode {} bandwidth is too wide".format(profile_id, index))
        previous_frequency = mode["frequency_hz"]


def validate_manifest(manifest: Any) -> List[str]:
    keys = {"schema_version", "default_profile", "profiles"}
    if not isinstance(manifest, dict) or set(manifest) != keys:
        fail("manifest must contain only schema_version, default_profile, and profiles")
    if isinstance(manifest["schema_version"], bool) or manifest["schema_version"] != 1:
        fail("manifest schema_version must be 1")
    if manifest["default_profile"] != "generic_violin":
        fail("manifest default_profile must be generic_violin")
    names = manifest["profiles"]
    if not isinstance(names, list) or not names:
        fail("manifest profiles must be a non-empty array")
    for name in names:
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".json"):
            fail("manifest profile names must be plain .json filenames")
    if len(names) != len(set(names)):
        fail("manifest repeats a profile filename")
    return names


def load_profiles(
    manifest_path: Path,
) -> Tuple[Mapping[str, Any], List[Dict[str, Any]]]:
    manifest = load_json(manifest_path)
    names = validate_manifest(manifest)

    schema_path = manifest_path.parent / SCHEMA_FILE
    schema = load_json(schema_path)
    if not isinstance(schema, dict):
        fail("profile schema must be an object")
    listed = set(names)
    found = {path.name for path in manifest_path.parent.glob("*.json") if path.name != manifest_path.name}
    if found != listed:
        fail("manifest/profile files differ; unlisted={} missing={}".format(sorted(found - listed), sorted(listed - found)))

    profiles: List[Dict[str, Any]] = []
    ids: Set[str] = set()
    displays: Set[str] = set()
    for name in names:
        path = manifest_path.parent / name
        raw = path.read_bytes()
        profile = load_json(path)
        if not isinstance(profile, dict):
            fail(str(path) + " must contain an object")
        validate_profile(profile, schema, Path(name).stem)
        if profile["id"] in ids:
            fail("profile id repeats: " + profile["id"])
        if profile["display_name"] in displays:
            fail("profile display_name repeats: " + profile["display_name"])
        ids.add(profile["id"])
        displays.add(profile["display_name"])
        profiles.append(
            {
                "path": path,
                "data": profile,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    if manifest["default_profile"] not in ids:
        fail("manifest default_profile does not name a profile id")

    return manifest, profiles


def c_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def c_number(value: Any) -> str:
    if not is_number(value):
        fail("cannot emit non-number {!r}".format(value))
    binary_value = c_double(value, "generated C number")
    if isinstance(value, Decimal):
        text = format(value, "f")
    elif isinstance(value, int):
        text = str(value)
    else:
        text = repr(value)
    if float(text) != binary_value:
        text = repr(binary_value)
    if "." not in text and "e" not in text.lower():
        text += ".0"
    if Decimal(text) == 0:
        return "0.0"
    return text


def values(item: Mapping[str, Any], names: Sequence[str]) -> str:
    return ", ".join(c_number(item[name]) for name in names)


def render_profile(item: Mapping[str, Any]) -> List[str]:
    profile = item["data"]
    name = "wg_profile_" + profile["id"]
    bow = profile["bow"]
    gestures = profile["gestures"]
    exciters = profile["exciters"]
    body = profile["body"]
    lines = [
        "static const WG_VIOLIN_PROFILE {} = {{".format(name),
        "    .schema_version = WG_VIOLIN_PROFILE_SCHEMA_VERSION,",
        "    .id = {},".format(c_string(profile["id"])),
        "    .display_name = {},".format(c_string(profile["display_name"])),
        "    .source_sha256 =",
        "        {},".format(c_string(item["sha256"])),
        "    .strings = {",
    ]
    string_names = (
        "characteristic_impedance_kg_per_second",
        "loss_time_constant_seconds",
        "nut_cutoff_hz",
        "bridge_cutoff_hz",
        "nut_loss_fraction",
    )
    for string in profile["strings"]:
        lines.append("        {{{}, {}}},".format(
            values(string, string_names), c_number(string.get("stopped_finger_loss", 0))))
    lines.extend(
        [
            "    },",
            "    .bow = {",
            "        .speed_scale = {},".format(c_number(bow["speed_scale"])),
            "        .friction = {{{}, {}}},".format(
                values(bow["friction"], ("floor_mu", "slow_gain", "slow_speed", "fast_gain", "fast_speed")),
                c_number(bow["friction"]["floor_mu"] + bow["friction"]["slow_gain"] + bow["friction"]["fast_gain"]),
            ),
            "        .force_map = {{{}, {}, {}, {}, {}}},".format(
                values(bow["force_map"], ("mu_drop_floor", "minimum_divisor", "control_low", "control_high")),
                c_number(bow["force_map"]["control_high"] - bow["force_map"]["control_low"]),
                c_number(Decimal("1") - bow["force_map"]["control_high"]),
                c_number(bow["force_map"]["normal_max_scale"]),
                c_number(bow["force_map"]["extreme_max_scale"]),
            ),
            "        .contact = {{{}}},".format(values(bow["contact"], ("stiffness", "damping", "breakaway", "dynamic_mix", "memory_release_seconds", "thermal_attack_seconds", "thermal_release_seconds", "thermal_drop", "thermal_work_scale", "hair_stiffness", "hair_damping", "hair_contact_mix"))),
            "    },",
            "    .gestures = {",
            "        .transition_seconds = {},".format(c_number(gestures["transition_seconds"])),
            "        .bow_change_seconds = {},".format(c_number(gestures["bow_change_seconds"])),
            "        .bow_change_contact_dip = {},".format(c_number(gestures["bow_change_contact_dip"])),
            "        .bow_change_force_floor = {},".format(c_number(gestures["bow_change_force_floor"])),
            "        .detache = {{{}}},".format(values(gestures["detache"], ("onset_seconds", "stroke_seconds", "force_base", "force_attack", "force_settle", "speed_base", "speed_attack", "speed_settle", "contact_attack_scale"))),
            "        .martele = {{{}}},".format(values(gestures["martele"], ("preload_seconds", "acceleration_seconds", "stroke_seconds", "force_base", "force_preload", "force_acceleration", "force_settle", "speed_preload", "speed_acceleration", "speed_settle", "contact_preload_scale"))),
            "        .spiccato = {{{}, {}, {}}},".format(
                values(gestures["spiccato"], ("stroke_fast_seconds", "stroke_slow_seconds")),
                c_number(gestures["spiccato"]["stroke_slow_seconds"] - gestures["spiccato"]["stroke_fast_seconds"]),
                values(gestures["spiccato"], ("force_base", "force_bounce", "speed_base", "speed_bounce")),
            ),
            "        .tremolo = {{{}}},".format(values(gestures["tremolo"], ("onset_seconds", "rate_min_hz", "rate_max_hz", "force_base", "force_motion", "contact_base", "contact_motion"))),
            "    },",
            "    .release_t60_seconds = {{{}}},".format(values(profile["release_t60_seconds"], ("arco", "detache", "martele", "spiccato", "tremolo", "pizzicato_right", "pizzicato_left", "bartok", "battuto", "tratto"))),
            "    .harmonics = {",
            "        .touch_level = {{{}}},".format(", ".join(c_number(value) for value in profile["harmonics"]["touch_level"])),
            "        .attack_seconds = {},".format(c_number(profile["harmonics"]["attack_seconds"])),
            "        .release_seconds = {},".format(c_number(profile["harmonics"]["release_seconds"])),
            "        .order_transition_seconds = {},".format(c_number(profile["harmonics"]["order_transition_seconds"])),
            "    },",
            "    .exciters = {",
            "        .noise_highpass = {},".format(c_number(exciters["noise_highpass"])),
            "        .contact_attack_seconds = {},".format(c_number(exciters["contact_attack_seconds"])),
            "        .contact_release_seconds = {},".format(c_number(exciters["contact_release_seconds"])),
            "        .speed_smooth_seconds = {},".format(c_number(exciters["speed_smoothing_seconds"])),
            "        .pizzicato_right = {{{}}},".format(values(exciters["pizzicato_right"], ("pulse_min_seconds", "pulse_range_seconds", "amplitude", "noise_gain"))),
            "        .pizzicato_left = {{{}}},".format(values(exciters["pizzicato_left"], ("pulse_min_seconds", "pulse_range_seconds", "amplitude", "noise_gain"))),
            "        .bartok = {{{}}},".format(values(exciters["bartok"], ("pulse_min_seconds", "pulse_range_seconds", "impact_delay_min_seconds", "impact_delay_range_seconds", "impact_min_seconds", "impact_range_seconds", "amplitude", "noise_gain", "impact_gain", "impact_alternating_mix"))),
            "        .battuto = {{{}}},".format(values(exciters["battuto"], ("collision_seconds", "noise_gain", "speed_base", "speed_force", "stiffness_base", "stiffness_force", "damping_base", "damping_force", "mass_kg"))),
            "        .tratto = {{{}}},".format(values(exciters["tratto"], ("speed_scale", "transition_min", "transition_range", "force_gain", "grain_gain"))),
            "    },",
            "    .coupling = {",
            "        .bridge_coefficients = {",
        ]
    )
    for row in profile["coupling"]["bridge_coefficients"]:
        lines.append("            {{{}}},".format(", ".join(c_number(value) for value in row)))
    lines.extend(
        [
            "        },",
            "        .sympathetic_open_scale = {},".format(c_number(profile["coupling"]["sympathetic_open_scale"])),
            "    },",
            "    .body = {",
        ]
    )
    for field in (
        "wet_gain",
        "gain_smoothing_seconds",
        "body_decay_base",
        "body_decay_range",
        "mute_decay_scale",
        "body_tone_depth",
        "mute_low_attenuation",
        "mute_high_attenuation",
        "mute_level_attenuation",
    ):
        lines.append("        .{} = {},".format(field, c_number(body[field])))
    lines.append("        .modes = {")
    for mode in body["modes"]:
        mode_values = values(mode, ("frequency_hz", "bandwidth_hz", "gain", "pan"))
        source_gains = mode.get("source_gains", (1, 1, 1, 1))
        lines.append("            {{{}, {{{}}}}},".format(
            mode_values, ", ".join(c_number(gain) for gain in source_gains)))
    lines.extend(["        },", "    },", "};"])
    return lines


def render_block(manifest: Mapping[str, Any], profiles: Sequence[Mapping[str, Any]]) -> str:
    lines = [BEGIN_MARKER, "/* Generated violin profile data. Do not edit by hand. */"]
    for item in profiles:
        lines.extend(render_profile(item))
        lines.append("")
    lines.append("static const WG_VIOLIN_PROFILE *const wg_violin_profiles[] = {")
    for item in profiles:
        lines.append("    &wg_profile_{},".format(item["data"]["id"]))
    lines.extend(
        [
            "};",
            "",
            "static const WG_VIOLIN_PROFILE *const wg_default_violin_profile =",
            "    &wg_profile_{};".format(manifest["default_profile"]),
            END_MARKER,
        ]
    )
    return "\n".join(lines)


def replace_generated_block(source: str, block: str, profile_count: int) -> str:
    if source.count(BEGIN_MARKER) != 1 or source.count(END_MARKER) != 1:
        fail("C source must contain one begin marker and one end marker")
    begin = source.index(BEGIN_MARKER)
    end = source.index(END_MARKER)
    if begin >= end:
        fail("C profile markers are out of order")
    count_pattern = r"#define WG_VIOLIN_PROFILE_COUNT\s+{}U\b".format(profile_count)
    if re.search(count_pattern, source) is None:
        fail("WG_VIOLIN_PROFILE_COUNT does not match the manifest")
    end += len(END_MARKER)
    return source[:begin] + block + source[end:]


def write_atomic(path: Path, text: str) -> None:
    mode = path.stat().st_mode
    temporary: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=str(path.parent), delete=False
        ) as output:
            temporary = output.name
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def expect_failure(label: str, action: Any) -> None:
    try:
        action()
    except ProfileError:
        return
    fail("self-test did not reject " + label)


def run_self_tests(
    schema: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> None:
    cases: List[Tuple[str, Any]] = []

    def changed(path: Sequence[Any], value: Any) -> Any:
        sample = copy.deepcopy(profile)
        target = sample
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return sample

    unknown = copy.deepcopy(profile)
    unknown["unknown"] = 1
    def checked(sample: Mapping[str, Any]) -> None:
        validate_profile(sample, schema)

    cases.append(("unknown field", lambda: checked(unknown)))
    cases.append(("schema version", lambda: checked(changed(("schema_version",), 2))))
    cases.append(("profile id", lambda: validate_profile(profile, schema, "wrong_id")))
    cases.append(("non-ASCII display name", lambda: checked(changed(("display_name",), "Violín"))))
    cases.append(("long display name", lambda: checked(changed(("display_name",), "V" * 128))))
    cases.append(("zero contact damping", lambda: checked(changed(("bow", "contact", "damping"), Decimal("0")))))
    cases.append(("short friction speed", lambda: checked(changed(("bow", "friction", "slow_speed"), Decimal("0.000001")))))
    cases.append(("friction sum", lambda: checked(changed(("bow", "friction", "fast_gain"), Decimal("2.0")))))
    cases.append(("extreme force scale", lambda: checked(changed(("bow", "force_map", "extreme_max_scale"), Decimal("0.5")))))
    cases.append(("short detache stroke", lambda: checked(changed(("gestures", "detache", "stroke_seconds"), Decimal("0.005")))))
    cases.append(("short martele stroke", lambda: checked(changed(("gestures", "martele", "stroke_seconds"), Decimal("0.010")))))
    cases.append(("zero spiccato range", lambda: checked(changed(("gestures", "spiccato", "stroke_slow_seconds"), Decimal("0.032")))))
    cases.append(("zero matrix diagonal", lambda: checked(changed(("coupling", "bridge_coefficients", 0, 0), Decimal("0.001")))))
    cases.append(("matrix symmetry", lambda: checked(changed(("coupling", "bridge_coefficients", 0, 1), Decimal("0.001")))))
    cases.append(("mode order", lambda: checked(changed(("body", "modes", 1, "frequency_hz"), Decimal("200")))))
    cases.append(("binary64 mode collision", lambda: checked(changed(("body", "modes", 1, "frequency_hz"), Decimal("265.0000000000000000001")))))
    cases.append(("body mode source count", lambda: checked(changed(("body", "modes", 0, "source_gains"), [1, 1, 1]))))
    cases.append(("body mode source gain range", lambda: checked(changed(("body", "modes", 0, "source_gains"), [1, 1, 1, -1]))))
    for label, action in cases:
        expect_failure(label, action)
    expect_failure("duplicate JSON key", lambda: unique_object((("x", 1), ("x", 2))))
    expect_failure("non-finite binary64", lambda: c_number(Decimal("1e9999")))
    expect_failure(
        "non-generic default",
        lambda: validate_manifest(
            {
                "schema_version": 1,
                "default_profile": "other_violin",
                "profiles": ["generic_violin.json", "other_violin.json"],
            }
        ),
    )
    valid_source = "#define WG_VIOLIN_PROFILE_COUNT 1U\n{}\n{}\n".format(BEGIN_MARKER, END_MARKER)
    replace_generated_block(valid_source, BEGIN_MARKER + "\n" + END_MARKER, 1)
    expect_failure("missing marker", lambda: replace_generated_block("", "", 1))
    expect_failure("duplicate marker", lambda: replace_generated_block(valid_source + BEGIN_MARKER, "", 1))
    expect_failure("wrong profile count", lambda: replace_generated_block(valid_source, "", 2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail if the C block is stale")
    mode.add_argument("--self-test", action="store_true", help="run focused rejection tests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest, profiles = load_profiles(args.manifest)
        if args.self_test:
            schema = load_json(args.manifest.parent / SCHEMA_FILE)
            run_self_tests(schema, profiles[0]["data"])
            print("profile generator self-test passed")
            return 0
        block = render_block(manifest, profiles)
        source = args.source.read_text(encoding="utf-8")
        expected = replace_generated_block(source, block, len(profiles))
        if args.check:
            if expected != source:
                diff = difflib.unified_diff(
                    source.splitlines(), expected.splitlines(),
                    fromfile=str(args.source), tofile="generated", lineterm="",
                )
                print("\n".join(list(diff)[:120]))
                fail("generated C profile data is stale")
            print("profile generation check passed for {} profiles".format(len(profiles)))
            return 0
        write_atomic(args.source, expected)
        print("generated {} profiles in {}".format(len(profiles), args.source))
        return 0
    except (OSError, UnicodeError, ProfileError) as error:
        print("generate_profiles.py: {}".format(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
