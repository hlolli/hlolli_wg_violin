#!/usr/bin/env python3
"""Rebuild the measured low body modes used by the violin profiles."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, NoReturn, Optional, Sequence, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MEASUREMENTS = (
    ROOT / "profiles" / "measurements" / "holm_valimaki_2000_table1.json"
)
EXPECTED_TOP_KEYS = {
    "schema_version",
    "id",
    "units",
    "gain_normalization",
    "rows",
    "profile_targets",
}
EXPECTED_ROW_KEYS = {"generic"}
EXPECTED_MODE_KEYS = {"frequency_hz", "bandwidth_hz", "magnitude_db"}
FORMULA = "10 ** ((magnitude_db - row_maximum_db) / 20)"


class FitError(ValueError):
    """Raised when source or profile data breaks the fit contract."""


def fail(message: str) -> NoReturn:
    raise FitError(message)


def unique_object(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(token: str) -> NoReturn:
    fail(f"non-finite JSON number: {token}")


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        fail(f"cannot read {path}: {error}")


def require_keys(value: Any, keys: Set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    found = set(value)
    if found != keys:
        missing = sorted(keys - found)
        extra = sorted(found - keys)
        fail(f"{path} has wrong keys; missing={missing}, extra={extra}")
    return value


def finite_number(value: Any, path: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{path} must be a number")
    result = float(value)
    if not math.isfinite(result):
        fail(f"{path} must be finite")
    if positive and result <= 0.0:
        fail(f"{path} must be positive")
    return result


def validate_measurements(
    data: Any,
) -> Mapping[str, Any]:
    top = require_keys(data, EXPECTED_TOP_KEYS, "measurement source")
    if isinstance(top["schema_version"], bool) or top["schema_version"] != 1:
        fail("measurement source schema_version must be 1")
    if top["id"] != "holm_valimaki_2000_table1":
        fail("measurement source id does not match the supported table")
    if top["gain_normalization"] != FORMULA:
        fail("measurement source has an unsupported gain formula")

    units = require_keys(top["units"], {"frequency", "bandwidth", "magnitude"}, "units")
    if units != {"frequency": "Hz", "bandwidth": "Hz", "magnitude": "dB"}:
        fail("measurement units must be Hz, Hz, and dB")

    rows = require_keys(top["rows"], EXPECTED_ROW_KEYS, "rows")
    for row_id, row_value in rows.items():
        row = require_keys(row_value, {"modes"}, f"rows.{row_id}")
        modes = row["modes"]
        if not isinstance(modes, list) or len(modes) != 5:
            fail(f"rows.{row_id}.modes must contain five modes")
        previous_frequency = 0.0
        for index, mode_value in enumerate(modes):
            path = f"rows.{row_id}.modes[{index}]"
            mode = require_keys(mode_value, EXPECTED_MODE_KEYS, path)
            frequency = finite_number(mode["frequency_hz"], path + ".frequency_hz", positive=True)
            finite_number(mode["bandwidth_hz"], path + ".bandwidth_hz", positive=True)
            finite_number(mode["magnitude_db"], path + ".magnitude_db")
            if frequency <= previous_frequency:
                fail(f"{path}.frequency_hz must increase")
            previous_frequency = frequency

    targets = top["profile_targets"]
    if not isinstance(targets, list) or not targets:
        fail("profile_targets must be a non-empty array")
    profile_ids: Set[str] = set()
    for index, target_value in enumerate(targets):
        path = f"profile_targets[{index}]"
        target = require_keys(
            target_value,
            {"profile_id", "row", "gain_decimal_places"},
            path,
        )
        profile_id = target["profile_id"]
        if not isinstance(profile_id, str) or not profile_id:
            fail(f"{path}.profile_id must be a non-empty string")
        if profile_id in profile_ids:
            fail(f"profile target repeats {profile_id}")
        profile_ids.add(profile_id)
        if target["row"] not in rows:
            fail(f"{path}.row does not name a source row")
        places = target["gain_decimal_places"]
        if places is not None and (
            isinstance(places, bool) or not isinstance(places, int) or not 0 <= places <= 15
        ):
            fail(f"{path}.gain_decimal_places must be null or an integer from 0 to 15")
    return top


def fit_row(
    row: Mapping[str, Any], gain_decimal_places: Optional[int]
) -> List[Dict[str, float]]:
    modes: Sequence[Mapping[str, Any]] = row["modes"]
    maximum_db = max(float(mode["magnitude_db"]) for mode in modes)
    fitted: List[Dict[str, float]] = []
    for mode in modes:
        gain = 10.0 ** ((float(mode["magnitude_db"]) - maximum_db) / 20.0)
        if gain_decimal_places is not None:
            gain = round(gain, gain_decimal_places)
        fitted.append(
            {
                "frequency_hz": float(mode["frequency_hz"]),
                "bandwidth_hz": float(mode["bandwidth_hz"]),
                "gain": gain,
            }
        )
    return fitted


def fitted_profiles(data: Mapping[str, Any]) -> Dict[str, List[Dict[str, float]]]:
    rows: Mapping[str, Mapping[str, Any]] = data["rows"]
    result: Dict[str, List[Dict[str, float]]] = {}
    for target in data["profile_targets"]:
        result[target["profile_id"]] = fit_row(
            rows[target["row"]], target["gain_decimal_places"]
        )
    return result


def check_profiles(
    fits: Mapping[str, Sequence[Mapping[str, float]]],
) -> None:
    for profile_id, expected_modes in fits.items():
        path = ROOT / "profiles" / f"{profile_id}.json"
        profile = load_json(path)
        if not isinstance(profile, dict) or profile.get("id") != profile_id:
            fail(f"{path} has the wrong profile id")
        try:
            modes = profile["body"]["modes"]
        except (KeyError, TypeError):
            fail(f"{path} has no body mode array")
        if not isinstance(modes, list) or len(modes) != 17:
            fail(f"{path} must contain seventeen body modes")
        for index, expected in enumerate(expected_modes):
            actual = modes[index]
            for key in ("frequency_hz", "bandwidth_hz", "gain"):
                actual_value = finite_number(actual.get(key), f"{path}: body.modes[{index}].{key}")
                if actual_value != expected[key]:
                    fail(
                        f"{path}: body.modes[{index}].{key} is {actual_value!r}; "
                        f"expected {expected[key]!r}"
                    )


def run_self_test(data: Mapping[str, Any]) -> None:
    cases: List[Tuple[str, Mapping[str, Any]]] = []
    bad_schema = copy.deepcopy(data)
    bad_schema["schema_version"] = True
    cases.append(("a Boolean schema version", bad_schema))
    bad_formula = copy.deepcopy(data)
    bad_formula["gain_normalization"] = "linear"
    cases.append(("an unknown gain formula", bad_formula))
    bad_order = copy.deepcopy(data)
    bad_order["rows"]["generic"]["modes"][1]["frequency_hz"] = 100.0
    cases.append(("unordered mode frequencies", bad_order))
    for label, sample in cases:
        try:
            validate_measurements(sample)
        except FitError:
            continue
        fail("self-test did not reject " + label)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--measurements",
        type=Path,
        default=DEFAULT_MEASUREMENTS,
        help="measurement source JSON (default: repository Table 1 source)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="check the committed profile rows instead of printing fitted rows",
    )
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="run the focused measurement-source rejection test",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = validate_measurements(load_json(args.measurements))
        if args.self_test:
            run_self_test(data)
            print("body mode fitter self-test passed")
            return 0
        fits = fitted_profiles(data)
        if args.check:
            check_profiles(fits)
            print(f"body mode fit check passed for {len(fits)} profiles")
        else:
            print(json.dumps(fits, indent=2, sort_keys=True) + "\n", end="")
        return 0
    except FitError as error:
        print(f"fit_body_modes.py: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
