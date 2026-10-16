"""Row actions: buttons on each row of a changelist or an inline.

An action is a method of the admin (or a callable) in one of two forms:

- for one row: ``action(model_admin, request, obj)`` — on an inline it may
  also take ``parent_obj``, the object being edited, as in
  django-inline-actions;
- for a queryset: ``action(model_admin, request, queryset)``, the form of the
  admin's own actions, run on a queryset with only that row — so existing
  admin actions work as row actions too.

Both return ``None`` to go back to the page, with the messages sent through
``message_user()``, or an ``HttpResponse`` (a file download, a redirect, an
intermediate page). ``@row_action`` (or ``@admin.action``) sets its
permissions and label; per row, ``get_<action>_label(obj)``,
``get_<action>_css(obj)`` and ``get_<action>_attrs(obj)`` on the admin
change them.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib import admin, messages
from django.contrib.admin.utils import model_format_dict, quote
from django.db import router, transaction
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html_join
from django.utils.safestring import SafeString, mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext, pgettext_lazy
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.http import HttpRequest
    from django.utils.functional import _StrOrPromise as StrOrPromise


def row_action(
    function: Callable[..., Any] | None = None,
    *,
    permissions: Sequence[str] | None = None,
    description: StrOrPromise | None = None,
    confirmation: StrOrPromise | None = None,
    link: bool = False,
) -> Any:
    """``@admin.action`` for a row action, plus a confirmation prompt::

        @row_action(
            permissions=["change"],
            description="Feature",
            confirmation="Feature “%(object)s”?",
        )
        def feature(self, request, obj):
            obj.featured = True
            obj.save()

    ``permissions`` are checked with the admin's ``has_<permission>_permission()``
    for the row (on an inline, for the object being edited). ``description``
    and ``confirmation`` may use ``%(object)s``, ``%(verbose_name)s`` and
    ``%(verbose_name_plural)s``. ``link=True`` renders the action as a link
    to the URL it returns from ``get_<action>_url(obj)`` on the admin,
    without running it (``"view"``).
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func = admin.action(permissions=permissions, description=description)(func)
        if confirmation is not None:
            func.confirmation = confirmation  # type: ignore[attr-defined]
        if link:
            func.row_action_link = True  # type: ignore[attr-defined]
        return func

    return decorator if function is None else decorator(function)


def change_url(model_admin: Any, obj: Any) -> str | None:
    """The change view of ``obj`` in the admin's site, if it has one."""
    opts = obj._meta
    try:
        return reverse(
            f"{model_admin.admin_site.name}:{opts.app_label}_{opts.model_name}_change",
            args=[quote(obj.pk)],
        )
    except NoReverseMatch:
        return None


# Their own context: the admin's catalog has other words for "View".
@row_action(
    permissions=["view"], description=pgettext_lazy("row action", "View"), link=True
)
def view(model_admin: Any, request: HttpRequest, obj: Any) -> Any:
    """Open the row's change view (its own ``ModelAdmin``)."""
    return HttpResponseRedirect(change_url(model_admin, obj) or "")


@row_action(
    permissions=["delete"],
    description=pgettext_lazy("row action", "Delete"),
    confirmation=_("Delete “%(object)s”? This cannot be undone."),
)
def delete(
    model_admin: Any, request: HttpRequest, obj: Any, parent_obj: Any = None
) -> None:
    """Delete the row (its ``delete()`` and signals run), recorded in the
    history: the row's own on a changelist, the parent's on an inline."""
    opts = obj._meta
    name = str(obj)
    try:
        with transaction.atomic(using=router.db_for_write(type(obj))):
            obj.delete()
    except ProtectedError as error:
        model_admin.message_user(
            request,
            gettext("Cannot delete “%(object)s”: %(objects)s depend on it.")
            % {
                "object": name,
                "objects": ", ".join(str(item) for item in error.protected_objects),
            },
            messages.ERROR,
        )
        return None
    parent_admin = parent_obj is not None and model_admin.admin_site._registry.get(
        type(parent_obj)
    )
    if parent_admin:
        parent_admin.log_change(
            request,
            parent_obj,
            [{"deleted": {"name": str(opts.verbose_name), "object": name}}],
        )
    model_admin.message_user(
        request,
        gettext("Deleted “%(object)s”.") % {"object": name},
        messages.SUCCESS,
    )
    return None


#: Row actions that can be listed by name in ``row_actions``.
BUILTIN_ROW_ACTIONS: dict[str, Callable[..., Any]] = {"delete": delete, "view": view}


def takes_one_row(function: Callable[..., Any]) -> bool:
    """Whether ``function`` acts on one row (``obj``) rather than a queryset."""
    try:
        return "obj" in inspect.signature(function).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins, C functions
        return False


@dataclass(frozen=True)
class RowActionSpec:
    """A row action as offered for one row."""

    name: str
    function: Callable[..., Any]
    label: str
    css_classes: str
    #: Extra HTML attributes of the button.
    attrs: SafeString
    confirmation: str | None
    #: A link to this URL instead of a button (``"view"``).
    url: str | None = None


def row_action_spec(
    model_admin: Any, name: str, function: Callable[..., Any], obj: Any
) -> RowActionSpec:
    """``function`` as ``name``'s action for the row ``obj``."""
    names = {**model_format_dict(model_admin.model._meta), "object": obj}

    def hook(kind: str) -> Any:
        method = getattr(model_admin, f"get_{name}_{kind}", None)
        return method(obj) if callable(method) else None

    label = hook("label")
    if label is None:
        description = getattr(function, "short_description", None)
        label = (
            str(description) % names
            if description is not None
            else capfirst(name.replace("_", " "))
        )
    css = hook("css")
    if css is None:
        css = getattr(function, "css_classes", "")
    attrs = hook("attrs")
    if attrs is None:
        attrs = getattr(function, "attribute_properties", {})
    attrs = (
        format_html_join(" ", '{}="{}"', attrs.items())
        if isinstance(attrs, dict)
        else mark_safe(attrs)  # noqa: S308 - the admin's own markup
    )
    confirmation = getattr(function, "confirmation", None)
    url = None
    if getattr(function, "row_action_link", False):
        url = hook("url")
        if url is None and function is view:
            url = change_url(model_admin, obj)
    return RowActionSpec(
        name=name,
        function=function,
        label=str(label),
        css_classes=str(css),
        attrs=attrs,
        confirmation=None if confirmation is None else str(confirmation) % names,
        url=url,
    )


def run_row_action(
    model_admin: Any,
    request: HttpRequest,
    action: RowActionSpec,
    obj: Any,
    parent: Any = None,
) -> Any:
    """Call the action on the row ``obj`` in the form it was written for."""
    function = action.function
    # A method listed by name is unbound: it gets the admin first, like a
    # plain function; a bound one (from getattr()) already has it.
    call = (
        function
        if inspect.ismethod(function)
        else lambda *args, **kwargs: function(model_admin, *args, **kwargs)
    )
    if takes_one_row(function):
        parameters = inspect.signature(function).parameters
        if "parent_obj" in parameters:
            return call(request, obj, parent_obj=parent)
        return call(request, obj)
    return call(request, type(obj)._default_manager.filter(pk=obj.pk))


__all__ = [
    "BUILTIN_ROW_ACTIONS",
    "RowActionSpec",
    "delete",
    "row_action",
    "view",
]
