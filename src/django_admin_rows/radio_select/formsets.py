from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from django import forms

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.forms.models import BaseModelFormSet

_FormSetT = TypeVar("_FormSetT", bound="BaseModelFormSet")


def make_radio_select_exclusive_formset(
    formset_class: type[_FormSetT], field_names: Sequence[str]
) -> type[_FormSetT]:
    """Return a subclass of ``formset_class`` whose ``clean()`` rejects
    more than one non-deleted form having any of ``field_names`` set to
    ``True``.

    Works the same for an inline's formset and for a ``ModelAdmin``
    changelist's ``list_editable`` formset — both are ``BaseModelFormSet``
    subclasses. This is the server-side backstop for the client-side
    radio behavior: JS keeps at most one row checked interactively, but a
    handcrafted POST could still submit several. The check runs *after*
    ``formset_class``'s own ``clean()`` (via ``super()``), so whatever
    validation a user-supplied ``InlineModelAdmin.formset`` (or
    ``ModelAdmin.get_changelist_formset``) already does keeps running
    unchanged; this only adds to it.
    """

    class RadioSelectExclusiveFormSet(formset_class):  # type: ignore[misc,valid-type]
        def clean(self) -> None:
            super().clean()
            if any(self.errors):
                return

            for field_name in field_names:
                selected = [
                    form
                    for form in self.forms
                    if not self._should_delete_form(form)
                    and form.cleaned_data.get(field_name)
                ]
                if len(selected) > 1:
                    raise forms.ValidationError(
                        "Only one row may have '%(field)s' selected.",
                        code="radio-select-exclusive",
                        params={"field": field_name},
                    )

    RadioSelectExclusiveFormSet.__name__ = formset_class.__name__
    RadioSelectExclusiveFormSet.__qualname__ = formset_class.__qualname__
    return RadioSelectExclusiveFormSet
