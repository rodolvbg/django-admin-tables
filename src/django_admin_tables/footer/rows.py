"""Footer rows: totals, averages… below a table's columns, computed by the
database and laid out as the table's own ``<tfoot>``."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from django.db.models import QuerySet

#: Every row matching the current filters, on every page.
FOOTER_FILTERED = "filtered"
#: Only the rows shown.
FOOTER_PAGE = "page"
FOOTER_SCOPES = (FOOTER_FILTERED, FOOTER_PAGE)

#: ``[(label, {column: aggregate | callable(queryset) | constant}), ...]``
FooterRows: TypeAlias = "Sequence[tuple[Any, Mapping[str, Any]]]"


@dataclass(frozen=True)
class FooterCell:
    #: The column's name, as the admin lists it (``"amount"``).
    column: str
    column_label: str
    #: Formatted for display by ``format_footer_value()``.
    value: str
    #: Machine-readable value (``"1234.5"``) for the page's JS, or ``""`` when
    #: it isn't a number.
    raw: str = ""
    #: The suffix of the column's ``column-``/``field-`` classes, when it
    #: isn't ``column`` (a foreign key link's ``author_link``).
    css_class: str = ""

    @property
    def css(self) -> str:
        return self.css_class or self.column


@dataclass(frozen=True)
class FooterRow:
    label: str
    cells: list[FooterCell]


@dataclass(frozen=True)
class TfootCell:
    """One cell of a footer row in the ``<tfoot>``, under its column."""

    #: The value shown here, or ``None`` for an empty cell.
    cell: FooterCell | None = None
    #: ``"<row index>:<column>"``, as ``data-footer-key``.
    key: str = ""
    #: The row's label goes in this cell, before the value (when the first
    #: value is in the first column, there is no empty column for it).
    label_here: bool = False


@dataclass(frozen=True)
class TfootRow:
    index: int
    label: str
    #: Columns the label spans at the start of the row; ``0`` when it goes
    #: into the first value's cell instead.
    label_colspan: int
    cells: list[TfootCell]
    #: Empty columns after the last value, up to the table's width.
    trailing: int = 0


def raw_number(value: Any) -> str:
    """A footer value as plain digits for JS (``"1234.5"``), ``""`` if not a
    number."""
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        return ""
    return format(value, "f") if isinstance(value, Decimal) else repr(value)


def compute_footer_rows(
    definitions: FooterRows,
    queryset: QuerySet[Any],
    column_label: Callable[[str], str],
    format_value: Callable[[str, Any], Any],
    css_classes: Mapping[str, str] | None = None,
) -> list[FooterRow]:
    """``definitions`` computed on ``queryset``, with every aggregate of every
    row in a single query."""
    aggregates = {
        f"footer_{row}_{column}": value
        for row, (_, cells) in enumerate(definitions)
        for column, value in cells.items()
        if getattr(value, "contains_aggregate", False)
    }
    results = queryset.order_by().aggregate(**aggregates) if aggregates else {}
    rows = []
    for row, (label, cells) in enumerate(definitions):
        values = []
        for column, value in cells.items():
            key = f"footer_{row}_{column}"
            if key in results:
                value = results[key]
            elif callable(value):
                value = value(queryset)
            values.append(
                FooterCell(
                    column=column,
                    column_label=column_label(column),
                    value=str(format_value(column, value)),
                    raw=raw_number(value),
                    css_class=(css_classes or {}).get(column, ""),
                )
            )
        rows.append(FooterRow(label=str(label), cells=values))
    return rows


def empty_footer_rows(
    definitions: FooterRows, column_label: Callable[[str], str]
) -> list[FooterRow]:
    """``definitions`` without values, for an add view: there are no saved
    rows to aggregate yet, but the ``<tfoot>`` keeps its structure and
    ``data-*`` attributes (``data-value=""``) for the page's JS."""
    return [
        FooterRow(
            label=str(label),
            cells=[
                FooterCell(column=column, column_label=column_label(column), value="")
                for column in cells
            ],
        )
        for label, cells in definitions
    ]


def header_columns(html: str) -> tuple[dict[str, int], int]:
    """Position of each column in the table's header row (its
    ``th.column-<name>``), and the row's width, as rendered: the leading and
    trailing columns (the action checkbox, a tabular inline's "original" and
    "delete" ones) vary with the admin, the theme and the permissions.
    Hidden headers take no room."""
    head = re.search(r"<thead.*?</thead>", html, re.S)
    positions: dict[str, int] = {}
    width = 0
    for attrs in re.findall(r"<th\b([^>]*)>", head.group() if head else ""):
        classes = re.search(r'class="([^"]*)"', attrs)
        names = classes.group(1).split() if classes else []
        if "hidden" in names:
            continue
        for name in names:
            if name.startswith("column-"):
                positions.setdefault(name.removeprefix("column-"), width)
        span = re.search(r'colspan="(\d+)"', attrs)
        width += int(span.group(1)) if span else 1
    return positions, width


def layout_tfoot_rows(
    footer_rows: list[FooterRow], positions: dict[str, int], width: int = 0
) -> list[TfootRow] | None:
    """``footer_rows`` laid out in a table ``width`` columns wide whose
    columns are at ``positions`` (0-based, by CSS class), or ``None`` if a
    value's column isn't among them."""
    # Columns before the first named one (the action checkbox, a tabular
    # inline's narrow "original" one).
    leading = min(positions.values(), default=0)
    rows = []
    for index, row in enumerate(footer_rows):
        if any(cell.css not in positions for cell in row.cells):
            return None
        by_position = {positions[cell.css]: cell for cell in row.cells}
        if not by_position:
            continue
        first, last = min(by_position), max(by_position)
        # The leading columns alone don't fit the label: it spans the empty
        # columns before the first value too, or goes into that value's cell.
        label_colspan = first if first > leading else 0
        cells = [] if label_colspan else [TfootCell()] * first
        for position in range(first, last + 1):
            cell = by_position.get(position)
            cells.append(
                TfootCell(
                    cell=cell,
                    key=f"{index}:{cell.column}" if cell else "",
                    label_here=not label_colspan and position == first,
                )
            )
        trailing = max(width - last - 1, 0)
        rows.append(TfootRow(index, row.label, label_colspan, cells, trailing))
    return rows
