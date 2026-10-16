from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.contrib.admin.options import BaseModelAdmin
from django.template.loader import select_template
from django.template.response import TemplateResponse

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model
    from django.forms.models import BaseInlineFormSet
    from django.http import HttpRequest, HttpResponse


class TableTemplatesMixin(BaseModelAdmin):
    """The base of the mixins that add to the admin's tables: renders the
    changelist with ``tables_change_list_template``, and a tabular inline
    with ``tables_inline_template``, when one of them has something to add.

    Each mixin adds its part through ``get_changelist_extras()`` and
    ``get_inline_extras()``, calling ``super()``: their keys end up in the
    template's context (``django_admin_tables_<key>``) for the changelist,
    and in the inline's ``django_admin_tables_inline`` for an inline.

    The changelist template extends the one the admin would use
    (``change_list_template`` included); the inline one includes the
    inline's own ``template``. The ``# type: ignore[misc]`` on ``super()``
    calls is because only the concrete ``ModelAdmin``/``InlineModelAdmin``
    declare them.
    """

    tables_change_list_template = "django_admin_tables/change_list.html"
    tables_inline_template = "django_admin_tables/edit_inline.html"

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        return {}

    def get_inline_extras(
        self, request: HttpRequest, obj: Model | None
    ) -> dict[str, Any]:
        return {}

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
        extras = {
            key: value
            for key, value in self.get_changelist_extras(request, cl).items()
            if value
        }
        if not extras:
            return response
        # The admin's changelist_view() renders a name or a list of names.
        template_name = cast("str | Sequence[str]", response.template_name)
        context["django_admin_tables_parent"] = select_template(
            [template_name] if isinstance(template_name, str) else template_name
        )
        for key, value in extras.items():
            context[f"django_admin_tables_{key}"] = value
        response.template_name = self.tables_change_list_template
        return response

    def get_formset(
        self, request: HttpRequest, obj: Model | None = None, **kwargs: Any
    ) -> type[BaseInlineFormSet]:
        formset_class = super().get_formset(request, obj, **kwargs)  # type: ignore[misc]
        template: str = getattr(self, "template", "")
        # The admin builds its inlines for each request: their template can
        # change with the request. get_formset() may be called more than once.
        if template != self.tables_inline_template:
            extras = {
                key: value
                for key, value in self.get_inline_extras(request, obj).items()
                if value
            }
            if extras:
                self.django_admin_tables_inline = {
                    "parent": select_template([template]),
                    **extras,
                }
                self.template = self.tables_inline_template
        return formset_class
