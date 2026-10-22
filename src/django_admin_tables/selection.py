from __future__ import annotations

import dataclasses
import functools
import re
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.admin import ModelAdmin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db.models import Count, Q
from django.forms import Media
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, ngettext

from .base import TableTemplatesMixin

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest, HttpResponse
    from django.utils.safestring import SafeString

try:  # Django 6.1+: actions of the changelist, or of an object's page.
    from django.contrib.admin.options import ActionLocation

    CHANGE_LIST: Any = ActionLocation.CHANGE_LIST
except ImportError:  # pragma: no cover - older Django
    CHANGE_LIST = None

#: Set on each object of the changelist's page that can't be selected: why
#: not ("" without a reason).
UNSELECTABLE = "_django_admin_tables_unselectable"

#: The class of a checkbox that can't be selected, in place of the admin's
#: ``action-select``: its scripts (the admin's and Unfold's) find the
#: checkboxes by that one, so "select all" and the count leave it out.
UNSELECTABLE_CLASS = "django-admin-tables-unselectable"


class SelectableRowsMixin(TableTemplatesMixin):
    """``ModelAdmin`` mixin deciding, row by row, which objects of the
    changelist can be selected for an action::

        class BookAdmin(SelectableRowsMixin, admin.ModelAdmin):
            def is_row_selectable(self, request, obj):
                return obj.status != Book.Status.ARCHIVED

            def get_row_unselectable_reason(self, request, obj):
                return _("Archived books can't be changed.")

    The checkbox of a row that can't be selected is disabled, with the
    reason as its title; "select all" and the "2 of 25 selected" count
    leave it out. Actions never get those objects: neither through "select
    all 250" nor through a request made by hand. They're left out, with a
    warning saying how many.

    Across many objects ("select all 250"), override
    ``filter_selectable_rows()`` with a filter of the database: by default
    it asks ``is_row_selectable()`` object by object.
    """

    def is_row_selectable(self, request: HttpRequest, obj: Model) -> bool:
        """Whether ``obj`` can be selected for an action."""
        return True

    def get_row_unselectable_reason(
        self, request: HttpRequest, obj: Model
    ) -> str | None:
        """Why ``obj`` can't be selected: the title of its checkbox."""
        return None

    def filter_selectable_rows(
        self, request: HttpRequest, queryset: QuerySet[Any]
    ) -> QuerySet[Any]:
        """The objects of ``queryset`` that can be selected. Override it with
        a filter (``queryset.exclude(status="archived")``): this one loads
        them (in one query, with the admin's ``list_select_related``) to ask
        ``is_row_selectable()`` of each."""
        selectable, _total = self.select_row_by_row(request, queryset)
        return queryset.filter(pk__in=selectable)

    def select_row_by_row(
        self, request: HttpRequest, queryset: QuerySet[Any]
    ) -> tuple[list[Any], int]:
        """The primary keys of the objects of ``queryset`` that
        ``is_row_selectable()`` lets through, and how many there were: one
        query, with the relations of ``list_select_related`` (a rule reading
        ``obj.album`` costs no query per object)."""
        related = self.get_list_select_related(request)  # type: ignore[attr-defined]
        if related is True:
            queryset = queryset.select_related()
        elif related:
            queryset = queryset.select_related(*related)
        objects = list(queryset)
        selectable = [obj.pk for obj in objects if self.is_row_selectable(request, obj)]
        return selectable, len(objects)

    @property
    def uses_selectable_rows(self) -> bool:
        """Whether this admin decides which rows can be selected: it
        overrides ``is_row_selectable()`` or ``filter_selectable_rows()``.
        Otherwise every row can, and nothing costs a query."""
        cls = type(self)
        return (
            cls.is_row_selectable is not SelectableRowsMixin.is_row_selectable
            or cls.filter_selectable_rows
            is not SelectableRowsMixin.filter_selectable_rows
        )

    # The changelist ----------------------------------------------------------

    @property
    def media(self) -> Media:
        media = super().media
        if isinstance(self, ModelAdmin):  # The changelist's, not an inline's.
            media += Media(
                css={"all": ["django_admin_tables/selectable-rows.css"]},
                js=["django_admin_tables/selectable-rows.js"],
            )
        return media

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        response = super().changelist_view(request, extra_context)
        context = getattr(response, "context_data", None) or {}
        cl = context.get("cl")
        if cl is not None and "selection_note" in context:
            # "0 of 25 selected": of those that can be selected.
            selectable = sum(
                getattr(obj, UNSELECTABLE, None) is None for obj in cl.result_list
            )
            context["selection_note"] = gettext("0 of %(cnt)s selected") % {
                "cnt": selectable
            }
        return response

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        # Before the rows are rendered: what each one's checkbox will be.
        for obj in cl.result_list if self.uses_selectable_rows else ():
            if self.is_row_selectable(request, obj):
                setattr(obj, UNSELECTABLE, None)
            else:
                reason = self.get_row_unselectable_reason(request, obj)
                setattr(obj, UNSELECTABLE, str(reason or ""))
        return super().get_changelist_extras(request, cl)

    @property
    def action_checkbox(self) -> Callable[[Model], SafeString]:
        # The admin's (or Unfold's) column, its header included, with the
        # checkboxes of the rows that can't be selected disabled.
        parent = super().action_checkbox  # type: ignore[misc]

        @functools.wraps(parent)
        def action_checkbox(obj: Model) -> SafeString:
            html = parent(obj)
            reason = getattr(obj, UNSELECTABLE, None)
            return html if reason is None else disable_checkbox(html, reason)

        return action_checkbox

    # The actions ---------------------------------------------------------------

    def get_actions(
        self, request: HttpRequest, action_location: Any = CHANGE_LIST
    ) -> dict[str, Any]:
        # Every action, the site's ("delete selected") included, run only on
        # the objects that can be selected.
        if action_location is None:  # Django < 6.1: no locations.
            actions = super().get_actions(request)  # type: ignore[misc]
        else:
            actions = super().get_actions(  # type: ignore[misc]
                request, action_location=action_location
            )
        if not self.uses_selectable_rows:
            return actions
        return {name: self.wrap_action(action) for name, action in actions.items()}

    def wrap_action(self, action: Any) -> Any:
        if dataclasses.is_dataclass(action) and not isinstance(action, type):
            # Django 6.1+: an Action.
            func = self.only_selectable(action.func)  # type: ignore[attr-defined]
            return dataclasses.replace(action, func=func)
        func, name, description = action
        return self.only_selectable(func), name, description

    def only_selectable(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """An action run only on the objects that can be selected."""

        @functools.wraps(func)
        def action(modeladmin: Any, request: HttpRequest, queryset: QuerySet[Any]):
            selectable, total, kept = self.count_selectable(request, queryset)
            skipped = total - kept
            if skipped:
                opts = queryset.model._meta
                self.message_user(  # type: ignore[attr-defined]
                    request,
                    ngettext(
                        "%(count)d %(name)s was left out: it can't be selected.",
                        "%(count)d %(name)s were left out: they can't be selected.",
                        skipped,
                    )
                    % {
                        "count": skipped,
                        "name": (
                            opts.verbose_name
                            if skipped == 1
                            else opts.verbose_name_plural
                        ),
                    },
                    messages.WARNING,
                )
                if not kept:
                    return None  # Nothing left to act on: back to the list.
                queryset = selectable
            return func(modeladmin, request, queryset)

        return action

    def count_selectable(
        self, request: HttpRequest, queryset: QuerySet[Any]
    ) -> tuple[QuerySet[Any], int, int]:
        """The objects of ``queryset`` an action may get, how many there
        were and how many of them it may: one query. With
        ``filter_selectable_rows()``, a count by the database; else the
        objects themselves, asked row by row."""
        if (
            type(self).filter_selectable_rows
            is SelectableRowsMixin.filter_selectable_rows
        ):
            pks, total = self.select_row_by_row(request, queryset)
            return queryset.filter(pk__in=pks), total, len(pks)
        selectable = self.filter_selectable_rows(request, queryset)
        counts = queryset.aggregate(
            total=Count("pk", distinct=True),
            selectable=Count(
                "pk", distinct=True, filter=Q(pk__in=selectable.values("pk"))
            ),
        )
        return selectable, counts["total"], counts["selectable"]


CLASS = re.compile(r'\bclass="([^"]*)"')


def disable_checkbox(html: str, reason: str) -> SafeString:
    """The checkbox of a row that can't be selected: disabled, with the
    reason as its title, out of the admin's selection (no ``action-select``
    class, no name to send)."""

    def classes(match: re.Match[str]) -> str:
        names = [
            UNSELECTABLE_CLASS if name == "action-select" else name
            for name in match.group(1).split()
        ]
        return f'class="{" ".join(names)}"'

    html = CLASS.sub(classes, html, count=1)
    html = html.replace(f' name="{ACTION_CHECKBOX_NAME}"', "", 1)
    title = f' title="{escape(reason)}"' if reason else ""
    return mark_safe(html.replace("<input", f"<input disabled{title}", 1))
