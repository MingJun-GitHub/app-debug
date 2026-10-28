"""Lightweight build, test, and log analysis for persisted debug sessions."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


_SOURCE_PATTERN = re.compile(
    r"(?P<file>/?(?:[A-Za-z0-9_.@+-]+/)*[A-Za-z0-9_.@+-]+"
    r"\.(?:swift|m|mm|kt|kts|java|c|cc|cpp|h|hpp)):(?P<line>\d+)"
)
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_LONG_NUMBER_PATTERN = re.compile(r"\b\d{5,}\b")
_TIMESTAMP_PATTERN = re.compile(
    r"^\s*(?:\[?\d{2,4}[-/:]\d{1,2}[-/:]\d{1,2}[ T]\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?\]?\s*)"
)
_ERROR_PATTERN = re.compile(
    r"(?i)(\berror:|\bfatal error\b|\bexception\b|\bfailed\b|\bfailure:|\bwhat went wrong\b|"
    r"\bexecution failed\b|\bcaused by:|^\s*✗|\s[EF](?:/|\s{2,}))"
)
_WARNING_PATTERN = re.compile(
    r"(?i)(^\s*w:|warning:|\bwarn(?:ing)?\b|\sW(?:/|\s{2,})|^\s*!)"
)
_TEST_SUMMARY_PATTERN = re.compile(
    r"(?i)(tests?\s+(?:passed|failed)|test cases?|tests completed|BUILD SUCCESSFUL|"
    r"BUILD FAILED|TEST SUCCEEDED|TEST FAILED|\d+\s+passed|\d+\s+failed)"
)


def is_error_line(line: str) -> bool:
    return bool(_ERROR_PATTERN.search(line))


def is_warning_line(line: str) -> bool:
    return bool(_WARNING_PATTERN.search(line))


def source_locations(lines: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        for match in _SOURCE_PATTERN.finditer(line):
            value = f"{match.group('file')}:{match.group('line')}"
            if value not in seen:
                seen.add(value)
                result.append(value)
    return result


def error_fingerprint(line: str) -> str:
    """Normalize volatile values so repeated failures collapse together."""
    value = _TIMESTAMP_PATTERN.sub("", line.strip())
    value = _UUID_PATTERN.sub("<uuid>", value)
    value = _LONG_NUMBER_PATTERN.sub("<n>", value)
    value = re.sub(r"\s+", " ", value)
    return value[:320]


def error_groups(lines: Iterable[str]) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = {}
    for line in lines:
        if not is_error_line(line):
            continue
        fingerprint = error_fingerprint(line)
        grouped.setdefault(fingerprint, []).append(line)
    result = [
        {
            "fingerprint": fingerprint,
            "count": len(matches),
            "sample": matches[0],
        }
        for fingerprint, matches in grouped.items()
    ]
    result.sort(key=lambda item: (-int(item["count"]), str(item["fingerprint"])))
    return result


def analyze_lines(lines: Iterable[str]) -> dict[str, object]:
    line_list = [str(line) for line in lines]
    errors = [line for line in line_list if is_error_line(line)]
    warnings = [line for line in line_list if is_warning_line(line)]
    summaries = [line for line in line_list if _TEST_SUMMARY_PATTERN.search(line)]
    command_counts = Counter(
        match.group(1)
        for line in line_list
        if (match := re.search(r"(?i)\b(?:BUILD|TEST)\s+(SUCCEEDED|FAILED)\b", line))
    )
    return {
        "lineCount": len(line_list),
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "sourceLocations": source_locations(line_list),
        "errorGroups": error_groups(line_list),
        "summaries": summaries[-20:],
        "outcomes": [
            {"name": name, "count": count}
            for name, count in command_counts.items()
        ],
    }

