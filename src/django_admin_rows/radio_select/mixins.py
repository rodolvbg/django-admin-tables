from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from django import forms
from django.contrib.admin.options import BaseModelAdmin
from django.core.exceptions import ImproperlyConfigured

from .formsets import make_radio_select_exclusive_formset
from .widgets import RadioCheckboxInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import Model
    from django.forms.models import BaseInlineFormSet, BaseModelFormSet
    from django.http import HttpRequest

_FormSetT = TypeVar("_FormSetT", bound="BaseModelFormSet")


class ExclusiveRadioFieldsMixin(BaseModelAdmin):
    """Mixin for ``ModelAdmin``, ``TabularInline``, or ``StackedInline``
    that renders the ``BooleanField``\\ s named in
    ``radio_select_exclusive_fields`` as radio buttons, synchronized
    client-side so selecting one clears the others in the same column —
    while every row keeps its own Django-generated field name, so the
    formset POST is completely unaffected.

    - On an inline, this applies to every row of that inline's formset.
    - On a ``ModelAdmin``, it applies to the changelist's
      ``list_editable`` formset — the field must be in both
      ``list_display`` and ``list_editable`` for Django to render it as
      an editable column at all; ``radio_select_exclusive_fields`` only
      controls how that column renders and is validated, same as inline.

    Meant to sit before ``admin.ModelAdmin``/``admin.TabularInline``/
    ``admin.StackedInline`` in a subclass's bases, e.g.
    ``class ImageInline(ExclusiveRadioFieldsMixin, admin.TabularInline)``.
    Inheriting from ``BaseModelAdmin`` — the common base of both
    ``ModelAdmin`` and ``InlineModelAdmin`` — rather than staying a bare
    mixin gives ``self``/``super()`` their real types for free; the
    ``# type: ignore[misc]`` on each ``super()`` call below is only
    because ``BaseModelAdmin`` itself doesn't declare ``get_formset``/
    ``get_changelist_formset`` (only the concrete ``InlineModelAdmin``/
    ``ModelAdmin`` a using class also inherits from do), so a type
    checker can't confirm they'll exist until the two are combined.

    See ``RadioCheckboxInput.media`` for how the JS gets loaded — not
    from a ``media`` property here, since ``ModelAdmin.media`` /
    ``InlineModelAdmin.media`` are computed the same way no matter which
    view is asking, so a property here couldn't tell a changelist render
    apart from a change-form render.
    """

    radio_select_exclusive_fields: Sequence[str] = ()

    def get_radio_select_exclusive_fields(
        self, request: HttpRequest, obj: Model | None = None
    ) -> Sequence[str]:
        return tuple(self.radio_select_exclusive_fields)

    def _get_effective_radio_select_exclusive_fields(
        self, request: HttpRequest, obj: Model | None = None
    ) -> Sequence[str]:
        # A readonly field is never part of form.base_fields as an
        # editable widget (Django renders it as plain text instead), so
        # radioizing it would either be a no-op or, if it's also missing
        # from the form for that reason, raise ImproperlyConfigured for
        # something the caller didn't really misconfigure — e.g. a field
        # only made readonly for some requests via get_readonly_fields.
        # Kept separate from get_radio_select_exclusive_fields() so this
        # filtering applies whether or not that method is overridden.
        readonly_fields = set(self.get_readonly_fields(request, obj))
        return tuple(
            field_name
            for field_name in self.get_radio_select_exclusive_fields(request, obj)
            if field_name not in readonly_fields
        )

    def get_formset(
        self, request: HttpRequest, obj: Model | None = None, **kwargs: Any
    ) -> type[BaseInlineFormSet]:
        formset_class = super().get_formset(request, obj, **kwargs)  # type: ignore[misc]
        field_names = self._get_effective_radio_select_exclusive_fields(request, obj)
        return self._wrap_formset(formset_class, field_names)

    def get_changelist_formset(
        self, request: HttpRequest, **kwargs: Any
    ) -> type[BaseModelFormSet]:
        formset_class = super().get_changelist_formset(request, **kwargs)  # type: ignore[misc]
        field_names = self._get_effective_radio_select_exclusive_fields(request)
        return self._wrap_formset(formset_class, field_names)

    @staticmethod
    def _wrap_formset(
        formset_class: type[_FormSetT], field_names: Sequence[str]
    ) -> type[_FormSetT]:
        if not field_names:
            return formset_class

        prefix = formset_class.get_default_prefix()
        ExclusiveRadioFieldsMixin._radioize_form_fields(
            formset_class.form, field_names, prefix
        )
        return make_radio_select_exclusive_formset(formset_class, field_names)

    @staticmethod
    def _radioize_form_fields(
        form_class: type[forms.ModelForm], field_names: Sequence[str], prefix: str
    ) -> None:
        for field_name in field_names:
            field = form_class.base_fields.get(field_name)
            if not isinstance(field, forms.BooleanField):
                raise ImproperlyConfigured(
                    f"{form_class.__name__}: radio_select_exclusive_fields references "
                    f"'{field_name}', which must be a BooleanField on the form "
                    f"(got {field.__class__.__name__ if field else 'nothing'})."
                )
            field.widget = RadioCheckboxInput(
                group=f"{prefix}::{field_name}", field_name=field_name
            )
            # A "must be checked" BooleanField can't represent the "this
            # row isn't the selected one" (False) state, which is a
            # completely valid, expected state for every row but one.
            field.required = False
