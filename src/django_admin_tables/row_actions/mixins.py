from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.contrib import messages
from django.contrib.admin.options import InlineModelAdmin
from django.contrib.admin.utils import quote, unquote
from django.core import checks
from django.core.exceptions import PermissionDenied
from django.forms import Media
from django.forms.models import _get_foreign_key
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseRedirect,
    JsonResponse,
)
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, path, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from ..base import TableTemplatesMixin
from .actions import BUILTIN_ROW_ACTIONS, row_action_spec, run_row_action

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from django.db.models import Model
    from django.forms.models import BaseInlineFormSet
    from django.http import HttpRequest
    from django.urls import URLPattern
    from django.utils.functional import _StrOrPromise as StrOrPromise
    from django.utils.safestring import SafeString

    from .actions import RowActionSpec

#: The changelist column of the actions, in ``list_display``: put it there to
#: place it, else it's the last column.
COLUMN = "row_actions"


class RowActionsMixin(TableTemplatesMixin):
    """Mixin adding buttons to each row, for a ``ModelAdmin`` (its changelist)
    or an inline::

        class BookAdmin(RowActionsMixin, admin.ModelAdmin):
            list_display = ("title", "author", "row_actions")
            row_actions = ["view", "feature", "delete"]

            @row_action(permissions=["change"], description="Feature")
            def feature(self, request, obj):
                ...

    ``"view"`` (a link to the row's change view) and ``"delete"`` are built
    in; other actions are methods or callables (see ``actions``). Each
    button posts to the ``ModelAdmin``'s ``row-action`` URL, which runs the
    action and goes back to the page. An inline's buttons post to its parent
    ``ModelAdmin``, which needs this mixin too (``django_admin_tables.E009``).
    With django-admin-inline-controls on the inline, only the inline is
    refreshed, in place.
    """

    row_actions: Sequence[str | Callable[..., Any]] = ()
    row_actions_template = "django_admin_tables/row_actions.html"

    # Which actions ---------------------------------------------------------

    def get_row_actions(
        self, request: HttpRequest, obj: Model
    ) -> Sequence[str | Callable[..., Any]]:
        """The actions of the row ``obj``. Override to offer some only on
        some rows ("Unpublish" on the published ones, say)."""
        return self.row_actions

    @property
    def has_row_actions(self) -> bool:
        return bool(self.row_actions) or (
            type(self).get_row_actions is not RowActionsMixin.get_row_actions
        )

    def _resolve_row_action(
        self, action: str | Callable[..., Any]
    ) -> tuple[str, Callable[..., Any]]:
        if callable(action):
            return action.__name__, action
        if hasattr(type(self), action):
            return action, getattr(type(self), action)
        if action in BUILTIN_ROW_ACTIONS:
            return action, BUILTIN_ROW_ACTIONS[action]
        raise AttributeError(action)

    def _has_permission(self, request: HttpRequest, permission: str, obj: Any) -> bool:
        method = getattr(self, f"has_{permission}_permission")
        # Django's take the object; an admin action's own ones may not.
        if "obj" in inspect.signature(method).parameters:
            return bool(method(request, obj))
        return bool(method(request))

    def get_row_action_specs(
        self, request: HttpRequest, obj: Model | None, parent: Model | None = None
    ) -> dict[str, RowActionSpec]:
        """The actions of the saved row ``obj`` this user may run, by name.
        Their permissions are checked for the row, or on an inline for the
        object being edited (``parent``)."""
        if obj is None or obj.pk is None:
            return {}
        target = obj if parent is None else parent
        specs = {}
        for action in self.get_row_actions(request, obj):
            name, function = self._resolve_row_action(action)
            permissions = getattr(function, "allowed_permissions", ())
            if not all(self._has_permission(request, p, target) for p in permissions):
                continue
            spec = row_action_spec(self, name, function, obj)
            if getattr(function, "row_action_link", False) and spec.url is None:
                continue  # Nowhere to link to.
            specs[name] = spec
        return specs

    # Rendering -------------------------------------------------------------

    def render_row_actions_cell(
        self,
        request: HttpRequest,
        obj: Model,
        url: Callable[[str], str],
        parent: Model | None = None,
    ) -> SafeString:
        """The buttons of the row ``obj``, posting to ``url(action)``."""
        actions = [
            (spec, None if spec.url else url(spec.name))
            for spec in self.get_row_action_specs(request, obj, parent).values()
        ]
        if not actions:
            return mark_safe("")
        return mark_safe(
            render_to_string(
                self.row_actions_template,
                {"actions": actions, "obj": obj},
                request,
            )
        )

    def get_list_display(self, request: HttpRequest) -> Any:
        list_display = list(super().get_list_display(request))  # type: ignore[misc]
        if not self.has_row_actions:
            return list_display
        opts = self.model._meta
        name = f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_row_action"

        def row_actions(obj: Model) -> SafeString:
            return self.render_row_actions_cell(
                request,
                obj,
                lambda action: reverse(name, args=[quote(obj.pk), action]),
            )

        row_actions.short_description = _("Actions")  # type: ignore[attr-defined]
        if COLUMN in list_display:
            list_display[list_display.index(COLUMN)] = row_actions
        else:
            list_display.append(row_actions)
        return list_display

    # An inline: a read-only column, rendered with the request and object it
    # was built for (the admin creates the inlines for each request).

    def _inline_row_actions(self, obj: Model | None) -> bool:
        return (
            isinstance(self, InlineModelAdmin)
            and self.has_row_actions
            and obj is not None
            and obj.pk is not None
        )

    def get_formset(
        self, request: HttpRequest, obj: Model | None = None, **kwargs: Any
    ) -> type[BaseInlineFormSet]:
        if self._inline_row_actions(obj):
            self._row_actions_request = request
            self._row_actions_parent = obj
        return super().get_formset(request, obj, **kwargs)

    def get_readonly_fields(
        self, request: HttpRequest, obj: Model | None = None
    ) -> Any:
        fields = super().get_readonly_fields(request, obj)
        if self._inline_row_actions(obj) and "render_row_actions" not in fields:
            fields = [*fields, "render_row_actions"]
        return fields

    def get_fields(self, request: HttpRequest, obj: Model | None = None) -> Any:
        fields = super().get_fields(request, obj)
        if self._inline_row_actions(obj) and "render_row_actions" not in fields:
            fields = [*fields, "render_row_actions"]
        return fields

    def get_fieldsets(self, request: HttpRequest, obj: Model | None = None) -> Any:
        fieldsets = list(super().get_fieldsets(request, obj))
        if self._inline_row_actions(obj) and fieldsets:
            name, options = fieldsets[-1]
            fields = list(options.get("fields") or ())
            if "render_row_actions" not in fields:
                fieldsets[-1] = (
                    name,
                    {**options, "fields": [*fields, "render_row_actions"]},
                )
        return fieldsets

    def render_row_actions(self, obj: Model | None = None) -> SafeString:
        """An inline's row actions: its read-only "Actions" column."""
        request = getattr(self, "_row_actions_request", None)
        parent = getattr(self, "_row_actions_parent", None)
        if request is None or parent is None or obj is None or obj.pk is None:
            return mark_safe("")
        parent_opts = parent._meta
        name = (
            f"{self.admin_site.name}:{parent_opts.app_label}_"
            f"{parent_opts.model_name}_inline_row_action"
        )
        index = self._inline_index(request, parent)
        try:
            reverse(name, args=[quote(parent.pk), index, quote(obj.pk), "x"])
        except NoReverseMatch:  # The parent admin hasn't the mixin (E009).
            return mark_safe("")
        return self.render_row_actions_cell(
            request,
            obj,
            lambda action: reverse(
                name, args=[quote(parent.pk), index, quote(obj.pk), action]
            ),
            parent,
        )

    render_row_actions.short_description = _("Actions")  # type: ignore[attr-defined]

    def _inline_index(self, request: HttpRequest, parent: Model) -> int:
        """This inline's position among its parent admin's inlines: the URL's
        way to find it again (``-1``, which matches no URL, if it isn't
        there)."""
        if not hasattr(self, "_row_actions_index"):
            parent_admin = self.admin_site._registry[type(parent)]
            inlines = parent_admin.get_inline_instances(request, parent)
            self._row_actions_index = next(
                (
                    index
                    for index, inline in enumerate(inlines)
                    if type(inline) is type(self)
                ),
                -1,
            )
        return self._row_actions_index

    @property
    def media(self) -> Media:
        media = super().media
        if self.has_row_actions:
            css = ["django_admin_tables/row-actions.css"]
            if apps.is_installed("unfold"):
                css.append("django_admin_tables/row-actions-unfold.css")
            media += Media(js=["django_admin_tables/row-actions.js"], css={"all": css})
        return media

    def message_user(
        self,
        request: HttpRequest,
        message: StrOrPromise,
        level: int | str = messages.INFO,
        extra_tags: str = "",
        fail_silently: bool = False,
    ) -> None:
        """``ModelAdmin.message_user()``, for an inline's actions too."""
        parent = getattr(super(), "message_user", None)
        if parent is not None:
            parent(request, message, level, extra_tags, fail_silently)
            return
        messages.add_message(
            request,
            level,  # type: ignore[arg-type]
            message,
            extra_tags=extra_tags,
            fail_silently=fail_silently,
        )

    # The ModelAdmin's URLs -------------------------------------------------

    def get_urls(self) -> list[URLPattern]:
        opts = self.model._meta
        name = f"{opts.app_label}_{opts.model_name}"
        return [
            path(
                "<path:object_id>/row-action/<str:action>/",
                self.admin_site.admin_view(require_POST(self.row_action_view)),
                name=f"{name}_row_action",
            ),
            path(
                "<path:object_id>/inline-row-action/<int:inline>/<str:row_id>/<str:action>/",
                self.admin_site.admin_view(require_POST(self.inline_row_action_view)),
                name=f"{name}_inline_row_action",
            ),
            *super().get_urls(),  # type: ignore[misc]
        ]

    def row_action_view(
        self, request: HttpRequest, object_id: str, action: str
    ) -> HttpResponseBase:
        """Run ``action`` on the changelist's row ``object_id``."""
        obj = self.get_object(request, unquote(object_id))  # type: ignore[attr-defined]
        if obj is None:
            raise Http404
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        spec = self.get_row_action_specs(request, obj).get(action)
        if spec is None or spec.url:
            return HttpResponseBadRequest("Unknown or forbidden action.")
        response = run_row_action(self, request, spec, obj)
        opts = self.model._meta
        default = reverse(
            f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_changelist"
        )
        return self._row_action_response(request, response, default)

    def inline_row_action_view(
        self,
        request: HttpRequest,
        object_id: str,
        inline: int,
        row_id: str,
        action: str,
    ) -> HttpResponseBase:
        """Run ``action`` on the row ``row_id`` of the object's ``inline``-th
        inline."""
        parent = self.get_object(request, unquote(object_id))  # type: ignore[attr-defined]
        if parent is None:
            raise Http404
        if not self.has_view_or_change_permission(request, parent):
            raise PermissionDenied
        inlines = self.get_inline_instances(request, parent)  # type: ignore[attr-defined]
        if not 0 <= inline < len(inlines) or not isinstance(
            inlines[inline], RowActionsMixin
        ):
            raise Http404
        instance: Any = inlines[inline]
        fk = _get_foreign_key(self.model, instance.model, fk_name=instance.fk_name)
        row = (
            instance.get_queryset(request)
            .filter(**{fk.name: parent}, pk=unquote(row_id))
            .first()
        )
        spec = instance.get_row_action_specs(request, row, parent).get(action)
        if spec is None or spec.url:
            return HttpResponseBadRequest("Unknown or forbidden action.")
        response = run_row_action(instance, request, spec, row, parent)
        opts = self.model._meta
        default = reverse(
            f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_change",
            args=[quote(parent.pk)],
        )
        return self._row_action_response(request, response, default)

    def _row_action_response(
        self, request: HttpRequest, response: Any, default: str
    ) -> HttpResponseBase:
        """The action's own response, or back to the page: a redirect, or
        for the page's script (refreshing an inline in place) the outcome."""
        if isinstance(response, HttpResponseBase):
            return response
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            sent = list(messages.get_messages(request))
            return JsonResponse(
                {
                    "status": "error"
                    if any(message.level >= messages.ERROR for message in sent)
                    else "done",
                    "message": " ".join(str(message) for message in sent),
                }
            )
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = default
        return HttpResponseRedirect(next_url)

    # Checks ----------------------------------------------------------------

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        return [*super().check(**kwargs), *self._check_row_actions()]

    def _check_row_actions(self) -> list[checks.CheckMessage]:
        errors: list[checks.CheckMessage] = []
        for action in self.row_actions:
            try:
                self._resolve_row_action(action)
            except AttributeError:
                errors.append(
                    checks.Error(
                        f"row_actions: '{action}' isn't a method of "
                        f"{type(self).__name__} nor a built-in action "
                        f"({', '.join(BUILTIN_ROW_ACTIONS)}).",
                        obj=self.__class__,
                        id="django_admin_tables.E008",
                    )
                )
        if isinstance(self, InlineModelAdmin) and self.has_row_actions:
            parent_admin = self.admin_site._registry.get(self.parent_model)
            if parent_admin is not None and not isinstance(
                parent_admin, RowActionsMixin
            ):
                errors.append(
                    checks.Error(
                        f"{type(self).__name__} has row actions, which run on "
                        f"its parent admin: {type(parent_admin).__name__} needs "
                        "RowActionsMixin (or AdminTablesMixin) too.",
                        obj=self.__class__,
                        id="django_admin_tables.E009",
                    )
                )
        return errors
