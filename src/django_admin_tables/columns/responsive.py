"""Columns hidden below a viewport width, with CSS media queries."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

#: Named breakpoints, in pixels: Tailwind's, which django-unfold uses.
BREAKPOINTS = {"sm": 640, "md": 768, "lg": 1024, "xl": 1280, "2xl": 1536}

Breakpoint = str | int


def max_width(breakpoint: Breakpoint) -> float:
    """The ``max-width`` of the media query hiding a column below
    ``breakpoint`` (a name of ``BREAKPOINTS``, or pixels)."""
    if isinstance(breakpoint, str) and breakpoint in BREAKPOINTS:
        pixels = BREAKPOINTS[breakpoint]
    elif isinstance(breakpoint, int) and not isinstance(breakpoint, bool):
        pixels = breakpoint
    else:
        raise ValueError(f"Unknown breakpoint: {breakpoint!r}.")
    if pixels <= 0:
        raise ValueError(f"Unknown breakpoint: {breakpoint!r}.")
    # Just under the breakpoint: at exactly its width, the column shows.
    return pixels - 0.02


def css_identifier(name: str) -> str:
    """``name`` escaped for a class selector."""
    return re.sub(r"[^\w-]", lambda match: f"\\{match.group()}", name)


def media_rules(
    breakpoints: Mapping[str, Breakpoint], classes: Iterable[tuple[str, str]]
) -> list[dict[str, object]]:
    """The media queries hiding each column below its breakpoint.

    ``classes`` pairs each column's name (a key of ``breakpoints``) with
    the suffix of its ``column-``/``field-`` classes. Returns one rule per
    width, widest first: ``{"max_width": 767.98, "classes": [...]}``.
    """
    by_width: dict[float, list[str]] = {}
    for name, css_class in classes:
        if name in breakpoints:
            width = max_width(breakpoints[name])
            by_width.setdefault(width, []).append(css_identifier(css_class))
    return [
        {"max_width": width, "classes": by_width[width]}
        for width in sorted(by_width, reverse=True)
    ]
