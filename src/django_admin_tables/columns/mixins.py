from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.contrib.admin.utils import label_for_field
from django.core import checks
from django.utils.text import capfirst

from ..base import TableTemplatesMixin
from .responsive import BREAKPOINTS, Breakpoint, max_width, media_rules

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model
    from django.http import HttpRequest

#: Attribute naming the field behind a generated ``list_display`` callable
#: (``ForeignKeyLinkMixin``'s links), so it can be listed by that name.
FIELD_NAME_ATTR = "_django_admin_tables_field"


def column_name(item: Any) -> str:
    """The name ``item`` (a ``list_display`` entry) is listed by."""
    if isinstance(item, str):
        return item
    return str(getattr(item, FIELD_NAME_ATTR, None) or getattr(item, "__name__", ""))


def column_class(item: Any, index: int) -> str:
    """The suffix of the ``column-``/``field-`` classes the admin gives
    ``item``'s cells (``_coerce_field_name()`` in ``admin_list``)."""
    if isinstance(item, str):
        return item
    if item.__name__ == "<lambda>":
        return f"lambda{index}"
    return item.__name__


def checkbox_classes() -> str:
    if not apps.is_installed("unfold"):
        return ""
    from unfold.widgets import CHECKBOX_CLASSES

    return " ".join(CHECKBOX_CLASSES)


class HideableColumnsMixin(TableTemplatesMixin):
    """Mixin hiding columns, for a ``ModelAdmin`` or a ``TabularInline``:

    - ``list_display_hideable``: a "Columns" menu on the changelist, to
      hide or show those columns. The choice is per user and per model,
      kept in the browser's ``localStorage``.
    - ``responsive_columns``: columns hidden below a viewport width, on the
      changelist (``list_display`` names) or in a tabular inline (field
      names), with CSS media queries.

    Both hide on the ``column-<name>`` and ``field-<name>`` classes the
    admin gives each column's cells, so sorting, actions, ``list_editable``
    and the inline's form work as they do without it.

    They're added by the changelist's and the inline's templates (see
    ``TableTemplatesMixin``).
    """

    #: ``list_display`` entries the user can hide: field names, or the
    #: name of a method or callable.
    list_display_hideable: Sequence[str] = ()
    #: Entries of ``list_display_hideable`` hidden until the user shows them.
    list_display_hidden: Sequence[str] = ()
    #: Columns hidden below a viewport width: ``{"album": "md"}``. Widths
    #: are a name of ``BREAKPOINTS`` (``"sm"``, ``"md"``, ``"lg"``, ``"xl"``,
    #: ``"2xl"``) or pixels.
    responsive_columns: Mapping[str, Breakpoint] = {}

    def get_list_display_hideable(self, request: HttpRequest) -> Sequence[str]:
        return self.list_display_hideable

    def get_list_display_hidden(self, request: HttpRequest) -> Sequence[str]:
        return self.list_display_hidden

    def get_responsive_columns(
        self, request: HttpRequest, obj: Model | None = None
    ) -> Mapping[str, Breakpoint]:
        return self.responsive_columns

    def get_hideable_columns(
        self, request: HttpRequest, cl: ChangeList
    ) -> list[dict[str, Any]]:
        """The hideable columns of ``cl``, in ``list_display`` order."""
        hideable = set(self.get_list_display_hideable(request))
        if not hideable:
            return []
        hidden = set(self.get_list_display_hidden(request))
        responsive = self.get_responsive_columns(request)
        columns = []
        for index, item in enumerate(cl.list_display):
            name = column_name(item)
            if name not in hideable:
                continue
            columns.append(
                {
                    "name": name,
                    "class": column_class(item, index),
                    "label": capfirst(
                        str(label_for_field(item, cl.model, model_admin=self))
                    ),
                    "hidden": name in hidden,
                    "max_width": (
                        max_width(responsive[name]) if name in responsive else None
                    ),
                }
            )
        return columns

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        extras = super().get_changelist_extras(request, cl)
        columns = self.get_hideable_columns(request, cl)
        if columns:
            opts = cl.model._meta
            extras["columns"] = {
                "columns": columns,
                "unfold": apps.is_installed("unfold"),
                "checkbox_classes": checkbox_classes(),
                "config": {
                    "storageKey": (
                        f"django-admin-tables:{self.admin_site.name}:"
                        f"{opts.app_label}.{opts.model_name}:hidden-columns"
                    ),
                    "hidden": [c["class"] for c in columns if c["hidden"]],
                    "columns": [c["class"] for c in columns],
                },
            }
        extras["responsive"] = media_rules(
            self.get_responsive_columns(request),
            (
                (column_name(item), column_class(item, index))
                for index, item in enumerate(cl.list_display)
            ),
        )
        return extras

    def get_inline_extras(
        self, request: HttpRequest, obj: Model | None
    ) -> dict[str, Any]:
        extras = super().get_inline_extras(request, obj)
        responsive = self.get_responsive_columns(request, obj)
        extras["responsive"] = media_rules(
            responsive, ((name, name) for name in responsive)
        )
        return extras

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        return [*super().check(**kwargs), *self._check_hideable_columns()]

    def _check_hideable_columns(self) -> list[checks.CheckMessage]:
        errors: list[checks.CheckMessage] = []
        for name, breakpoint in self.responsive_columns.items():
            try:
                max_width(breakpoint)
            except ValueError:
                errors.append(
                    checks.Error(
                        f"'{name}' in responsive_columns has an unknown "
                        f"breakpoint, {breakpoint!r}: use one of "
                        f"{', '.join(BREAKPOINTS)}, or pixels.",
                        obj=self.__class__,
                        id="django_admin_tables.E003",
                    )
                )
        list_display = getattr(self, "list_display", None)
        if list_display is None:  # An inline: there's no changelist.
            return errors
        listed = {column_name(item) for item in list_display}
        errors += [
            checks.Error(
                f"'{name}' in responsive_columns isn't in list_display.",
                obj=self.__class__,
                id="django_admin_tables.E004",
            )
            for name in self.responsive_columns
            if name not in listed
        ]
        errors += [
            checks.Error(
                f"'{name}' in list_display_hideable isn't in list_display.",
                obj=self.__class__,
                id="django_admin_tables.E001",
            )
            for name in self.list_display_hideable
            if name not in listed
        ]
        errors += [
            checks.Error(
                f"'{name}' in list_display_hidden isn't in list_display_hideable.",
                obj=self.__class__,
                id="django_admin_tables.E002",
            )
            for name in self.list_display_hidden
            if name not in self.list_display_hideable
        ]
        return errors
