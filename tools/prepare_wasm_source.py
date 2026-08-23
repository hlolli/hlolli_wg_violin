#!/usr/bin/env python3
"""Derive the bounded browser-compiler source from the canonical C file."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile


SOURCE_LIMIT = 256 * 1024
TEST_CONDITION = re.compile(
    r"^\s*#\s*if\s+(!?)defined\s*\(HLOLLI_WG_VIOLIN_TEST_API\)\s*$"
)
IF_DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b")
ELSE_DIRECTIVE = re.compile(r"^\s*#\s*(else|elif)\b")
ENDIF_DIRECTIVE = re.compile(r"^\s*#\s*endif\b")


def strip_test_sections(source: str) -> str:
    output: list[str] = []
    stack: list[dict[str, object]] = []
    active = True
    for line in source.splitlines(keepends=True):
        test_match = TEST_CONDITION.match(line.rstrip("\r\n"))
        if test_match:
            condition = bool(test_match.group(1))
            stack.append(
                {
                    "parent": active,
                    "targeted": True,
                    "condition": condition,
                    "else": False,
                }
            )
            active = active and condition
            continue
        if IF_DIRECTIVE.match(line):
            stack.append(
                {
                    "parent": active,
                    "targeted": False,
                    "condition": True,
                    "else": False,
                }
            )
            if active:
                output.append(line)
            continue
        if ELSE_DIRECTIVE.match(line):
            if not stack:
                raise ValueError("unmatched preprocessor else")
            frame = stack[-1]
            if frame["targeted"]:
                if frame["else"]:
                    raise ValueError("duplicate test preprocessor else")
                frame["else"] = True
                active = bool(frame["parent"]) and not bool(frame["condition"])
            else:
                active = bool(frame["parent"])
                if active:
                    output.append(line)
            continue
        if ENDIF_DIRECTIVE.match(line):
            if not stack:
                raise ValueError("unmatched preprocessor endif")
            frame = stack.pop()
            active = bool(frame["parent"])
            if not frame["targeted"] and active:
                output.append(line)
            continue
        if active:
            output.append(line)
    if stack:
        raise ValueError("unterminated preprocessor condition")
    return "".join(output)


def strip_comments(source: str) -> str:
    output: list[str] = []
    index = 0
    state = "code"
    while index < len(source):
        character = source[index]
        if state == "code":
            if source.startswith("/*", index):
                state = "block"
                index += 2
            elif source.startswith("//", index):
                state = "line"
                index += 2
            else:
                output.append(character)
                index += 1
                if character == '"':
                    state = "string"
                elif character == "'":
                    state = "character"
        elif state == "block":
            if source.startswith("*/", index):
                state = "code"
                index += 2
            else:
                if character == "\n":
                    output.append("\n")
                index += 1
        elif state == "line":
            index += 1
            if character == "\n":
                output.append("\n")
                state = "code"
        else:
            output.append(character)
            index += 1
            if character == "\\" and index < len(source):
                output.append(source[index])
                index += 1
            elif state == "string" and character == '"':
                state = "code"
            elif state == "character" and character == "'":
                state = "code"
    if state in ("block", "string", "character"):
        raise ValueError("unterminated C token")
    return "".join(output)


def compact(source: str) -> str:
    lines: list[str] = []
    operator = re.compile(
        r"\s*(->|==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|<<=|>>=|"
        r"<<|>>|[+*/%=<>&|^!])\s*"
    )
    delimiter = re.compile(r"\s*([{},;:?()\[\]])\s*")
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"[ \t]+", " ", line)
        if not line.startswith("#"):
            line = delimiter.sub(r"\1", line)
            line = operator.sub(r"\1", line)
        lines.append(line)
    return "\n".join(lines) + "\n"


def prepare(source: str) -> str:
    return compact(strip_comments(strip_test_sections(source)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    options = parser.parse_args()
    if not options.source.is_file():
        parser.error(f"missing source file: {options.source}")
    if options.source.resolve() == options.output.resolve():
        parser.error("source and output must name different files")
    prepared = prepare(options.source.read_text(encoding="utf-8"))
    byte_count = len(prepared.encode("utf-8"))
    if byte_count > SOURCE_LIMIT:
        parser.error(
            f"prepared source is {byte_count} bytes; limit is {SOURCE_LIMIT}"
        )
    options.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=options.output.parent,
        prefix=f".{options.output.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(prepared)
    temporary.replace(options.output)
    print(f"prepared WASM source: {byte_count} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
