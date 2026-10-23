from __future__ import annotations

import re
from functools import partial
from typing import TYPE_CHECKING, Any

from django.contrib.admin import ModelAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import Media
from django.forms.models import modelform_factory
from django.http import JsonResponse, QueryDict
from django.urls import path, reverse
from django.utils.translation import gettext
from django.views.decorators.http import require_POST

from .base import TableTemplatesMixin

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.admin.views.main import ChangeList
    from django.forms import ModelForm
    from django.http import HttpRequest
    from django.urls import URLPattern

#: The changelist's forms: Django's formset prefix ("form"), and a row's.
PREFIX = re.compile(r"^form-\d+$")


class ListEditableAutosaveMixin(TableTemplatesMixin):
    """``ModelAdmin`` mixin: the changelist's ``list_editable`` fields in
    ``list_editable_autosave`` save themselves as they change, one row and
    one field at a time, without the "Save" button::

        class ServiceAdmin(ListEditableAutosaveMixin, admin.ModelAdmin):
            list_editable = ("active", "price")
            list_editable_autosave = ("active",)  # or True: all of them

    A switch or a select saves at once; a text, when it's left (or on
    Enter). Each save is validated by the changelist's own form (its field
    only), checked against ``has_change_permission(request, obj)``, saved
    through ``save_model()`` and ``save_related()``, and logged as the
    changelist's saves are. If someone changed the field meanwhile, it isn't
    overwritten: the field goes back, and says so.

    With every ``list_editable`` field saving itself, the "Save" button
    isn't shown, and leaving the page asks nothing for them. Exclusive radio
    fields (``radio_select_exclusive_fields``) don't save themselves: one
    changes two rows.
    """

    #: The ``list_editable`` fields that save themselves; ``True``: all.
    list_editable_autosave: bool | Sequence[str] = ()

    def get_list_editable_autosave(self, request: HttpRequest) -> list[str]:
        """The fields that save themselves, for this request. Not the
        exclusive radio fields (``radio_select_exclusive_fields``): checking
        one row unchecks another, which is the changelist's save."""
        exclusive = set(getattr(self, "radio_select_exclusive_fields", ()) or ())
        editable = [
            name
            for name in getattr(self, "list_editable", ()) or ()
            if name not in exclusive
        ]
        wanted = self.list_editable_autosave
        if wanted is True:
            return editable
        if not wanted:
            return []
        return [name for name in wanted if name in editable]

    @property
    def uses_list_editable_autosave(self) -> bool:
        return bool(self.list_editable_autosave) and isinstance(self, ModelAdmin)

    # The endpoint --------------------------------------------------------------

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()  # type: ignore[misc]
        if not self.uses_list_editable_autosave:
            return urls
        opts = self.model._meta
        return [
            path(
                "autosave/",
                self.admin_site.admin_view(require_POST(self.autosave_view)),
                name=f"{opts.app_label}_{opts.model_name}_autosave",
            ),
            *urls,
        ]

    def get_autosave_form(self, request: HttpRequest, field: str) -> type[ModelForm]:
        """The changelist's form (``get_changelist_form()``), with only
        ``field``: what isn't sent isn't touched."""
        return modelform_factory(
            self.model,
            form=self.get_changelist_form(request),  # type: ignore[attr-defined]
            fields=[field],
            formfield_callback=partial(self.formfield_for_dbfield, request=request),
        )

    def autosave_view(self, request: HttpRequest) -> JsonResponse:
        """Save one field of one row: ``prefix`` (its form's, ``form-3``),
        ``field``, ``pk``, the field's inputs as the changelist sends them,
        and, with ``check``, ``previous-<input>``: what they were when last
        saved (none: an unchecked checkbox)."""
        prefix = request.POST.get("prefix", "")
        field = request.POST.get("field", "")
        if not PREFIX.match(prefix) or field not in self.get_list_editable_autosave(
            request
        ):
            return JsonResponse({"error": gettext("Unknown field.")}, status=400)
        try:
            obj = self.get_queryset(request).filter(pk=request.POST.get("pk")).first()
        except (ValueError, TypeError, ValidationError):
            obj = None
        if obj is None:
            return JsonResponse(
                {"error": gettext("It doesn't exist any more.")}, status=404
            )
        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        form_class = self.get_autosave_form(request, field)
        # Changed by someone else since: what was there isn't what's there.
        previous = QueryDict(mutable=True)
        for name, values in request.POST.lists():
            if name.startswith("previous-"):
                previous.setlist(name.removeprefix("previous-"), values)
        if request.POST.get("check"):
            before = form_class(previous, instance=obj, prefix=prefix)
            if field in before.changed_data:
                return JsonResponse(
                    {
                        "error": gettext(
                            "Someone else changed it meanwhile: reload the page."
                        ),
                        "conflict": True,
                    },
                    status=409,
                )
        form = form_class(request.POST, request.FILES, instance=obj, prefix=prefix)
        if not form.is_valid():
            errors = [str(error) for error in form.errors.get(field, [])]
            errors += [str(error) for error in form.non_field_errors()]
            return JsonResponse(
                {"error": " ".join(errors) or gettext("It can't be saved.")},
                status=400,
            )
        if form.has_changed():
            obj = self.save_form(request, form, change=True)  # type: ignore[attr-defined]
            self.save_model(request, obj, form, change=True)  # type: ignore[attr-defined]
            self.save_related(request, form, formsets=[], change=True)  # type: ignore[attr-defined]
            message = self.construct_change_message(request, form, None)  # type: ignore[attr-defined]
            self.log_change(request, obj, message)  # type: ignore[attr-defined]
        return JsonResponse({"saved": True})

    # The changelist ------------------------------------------------------------

    @property
    def media(self) -> Media:
        media = super().media
        if self.uses_list_editable_autosave:
            media += Media(
                css={"all": ["django_admin_tables/autosave.css"]},
                js=["django_admin_tables/autosave.js"],
            )
        return media

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        extras = super().get_changelist_extras(request, cl)
        fields = self.get_list_editable_autosave(request) if cl.formset else []
        if self.uses_list_editable_autosave and fields:
            opts = self.model._meta
            extras["autosave"] = {
                "url": reverse(
                    f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_autosave"
                ),
                "fields": fields,
                "pk": opts.pk.name,
                # Nothing left for the "Save" button.
                "all": set(fields) >= set(cl.list_editable),
                "texts": {
                    "saving": gettext("Saving…"),
                    "saved": gettext("Saved"),
                    "failed": gettext("Not saved"),
                },
            }
        return extras
