from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.apps import apps
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.utils import label_for_field
from django.core import checks
from django.template.loader import select_template
from django.template.response import TemplateResponse
from django.utils.text import capfirst

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.admin.views.main import ChangeList
    from django.http import HttpRequest, HttpResponse

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


class HideableColumnsMixin(BaseModelAdmin):
    """``ModelAdmin`` mixin adding a "Columns" menu to the changelist, to
    hide or show the columns listed in ``list_display_hideable``.

    The choice is per user and per model, kept in the browser's
    ``localStorage``: hiding is done client-side, on the ``column-<name>``
    and ``field-<name>`` classes the admin gives each column's cells, so
    sorting, actions and ``list_editable`` work as they do without it.

    The changelist is rendered with ``hideable_columns_template``, which
    extends the template the admin would use (``change_list_template``
    included) and adds the menu to its blocks. The ``# type: ignore[misc]``
    on ``super().changelist_view()`` is because only the concrete
    ``ModelAdmin`` declares it.
    """

    #: ``list_display`` entries the user can hide: field names, or the
    #: name of a method or callable.
    list_display_hideable: Sequence[str] = ()
    #: Entries of ``list_display_hideable`` hidden until the user shows them.
    list_display_hidden: Sequence[str] = ()
    hideable_columns_template = "django_admin_tables/change_list.html"

    def get_list_display_hideable(self, request: HttpRequest) -> Sequence[str]:
        return self.list_display_hideable

    def get_list_display_hidden(self, request: HttpRequest) -> Sequence[str]:
        return self.list_display_hidden

    def get_hideable_columns(
        self, request: HttpRequest, cl: ChangeList
    ) -> list[dict[str, Any]]:
        """The hideable columns of ``cl``, in ``list_display`` order."""
        hideable = set(self.get_list_display_hideable(request))
        if not hideable:
            return []
        hidden = set(self.get_list_display_hidden(request))
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
                }
            )
        return columns

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        response = super().changelist_view(request, extra_context)  # type: ignore[misc]
        if not isinstance(response, TemplateResponse) or response.is_rendered:
            return response
        context = response.context_data or {}
        cl = context.get("cl")
        if cl is None:
            return response
        columns = self.get_hideable_columns(request, cl)
        if not columns:
            return response

        opts = cl.model._meta
        # The admin's changelist_view() renders a name or a list of names.
        template_name = cast("str | Sequence[str]", response.template_name)
        context["django_admin_tables_columns"] = {
            "parent": select_template(
                [template_name] if isinstance(template_name, str) else template_name
            ),
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
        response.template_name = self.hideable_columns_template
        return response

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        return [*super().check(**kwargs), *self._check_hideable_columns()]

    def _check_hideable_columns(self) -> list[checks.CheckMessage]:
        list_display = getattr(self, "list_display", None)
        if list_display is None:  # An inline: there's no changelist.
            return []
        listed = {column_name(item) for item in list_display}
        errors: list[checks.CheckMessage] = [
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
