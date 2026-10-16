from __future__ import annotations

from typing import TYPE_CHECKING

from django.apps import apps
from django.forms.widgets import CheckboxInput

if TYPE_CHECKING:
    from typing import Any


def theme_classes() -> list[str]:
    """CSS classes of the admin theme's own radios: django-unfold's, when it
    is installed (its styles only cover the classes it uses itself)."""
    if not apps.is_installed("unfold"):
        return []
    try:
        from unfold.widgets import RADIO_CLASSES
    except ImportError:  # an Unfold without them: the browser's radio
        return []
    return list(RADIO_CLASSES)


class RadioCheckboxInput(CheckboxInput):
    """A :class:`~django.forms.CheckboxInput` rendered with
    ``type="radio"`` instead of ``type="checkbox"``.

    ``CheckboxInput`` already POSTs exactly the way a radio-per-row needs
    to: present in the data means checked, absent means unchecked/False.
    Only ``input_type`` changes here, which is all Django's widget
    templates key off of for the rendered ``type`` attribute — so a
    ``BooleanField`` using this widget round-trips through a normal
    Django form/formset completely unchanged; only the rendered control
    (and therefore its default browser styling and grouping semantics)
    is different.

    ``media`` lives here rather than on the admin mixin on purpose: a
    widget only exists once a field is actually radioized, and only ever
    gets *rendered* as part of the specific form/formset that uses it —
    Django aggregates a rendered page's media from exactly the
    forms/widgets it renders. So this script only ever loads on a
    changelist that actually has a ``list_editable`` radio column, or a
    change view that actually has a radioized inline — never anywhere
    else — with no extra request- or view-awareness needed here. An
    admin-level ``media`` property couldn't do this: Django computes
    ``ModelAdmin.media``/``InlineModelAdmin.media`` the same way
    regardless of which view asked for it, so it can't tell "changelist"
    from "change form" apart.
    """

    class Media:
        js = ("django_admin_tables/radio-select.js",)

    input_type = "radio"

    def __init__(
        self, group: str, field_name: str, attrs: dict[str, Any] | None = None
    ) -> None:
        attrs = dict(attrs or {})
        classes = [attrs.get("class", ""), *theme_classes(), "radio-select-exclusive"]
        attrs["class"] = " ".join(name for name in classes if name)
        attrs["data-radio-select-group"] = group
        attrs["data-radio-select-field"] = field_name
        super().__init__(attrs=attrs)
