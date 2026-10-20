"""Method-by-method tests for RadioCheckboxInput, one test per scenario.
No database needed.
"""

from unittest import mock

import pytest

from django_admin_tables.radio_select import widgets
from django_admin_tables.radio_select.widgets import RadioCheckboxInput

INSTALLED = "django_admin_tables.radio_select.widgets.apps.is_installed"


def _widget(**kwargs):
    kwargs.setdefault("group", "images::is_primary")
    kwargs.setdefault("field_name", "is_primary")
    return RadioCheckboxInput(**kwargs)


class TestRadioCheckboxInput:
    """The exclusive radio widget."""

    def test_init_sets_the_data_attrs_for_field_name_and_group(self):
        widget = _widget()

        assert widget.attrs["data-radio-select-group"] == "images::is_primary"
        assert widget.attrs["data-radio-select-field"] == "is_primary"

    def test_init_adds_the_exclusive_marker_class(self):
        assert "radio-select-exclusive" in _widget().attrs["class"]

    def test_init_preserves_an_existing_class_attr_instead_of_overwriting_it(self):
        widget = _widget(attrs={"class": "existing"})

        assert widget.attrs["class"] == "existing radio-select-exclusive"

    def test_input_type_is_radio(self):
        assert _widget().input_type == "radio"

    def test_rendered_html_uses_type_radio(self):
        html = _widget().render("is_primary", None)

        assert 'type="radio"' in html
        assert 'type="checkbox"' not in html

    def test_render_reflects_the_checked_state(self):
        widget = _widget()

        assert "checked" in widget.render("is_primary", True)
        assert "checked" not in widget.render("is_primary", False)

    @pytest.mark.parametrize(
        ("data", "expected"),
        [({}, False), ({"is_primary": "on"}, True)],
        ids=["absent means False", "present means True"],
    )
    def test_value_from_datadict(self, data, expected):
        # Present in the POST data => True; absent => False. Exactly
        # what a BooleanField's own default widget (CheckboxInput)
        # does, and what makes this drop-in safe for the field's
        # clean()/validate().
        assert _widget().value_from_datadict(data, {}, "is_primary") is expected

    def test_media(self):
        js_paths = [str(script) for script in _widget().media._js]

        assert any("django_admin_tables/radio-select.js" in p for p in js_paths)


class TestThemeClasses:
    """theme_classes, with and without Unfold."""

    def test_none_without_unfold(self):
        with mock.patch(INSTALLED, return_value=False):
            assert widgets.theme_classes() == []
            assert _widget().attrs["class"] == "radio-select-exclusive"

    def test_unfolds_radio_classes_with_it(self):
        fake = mock.Mock(RADIO_CLASSES=["appearance-none", "rounded-full"])
        with (
            mock.patch(INSTALLED, return_value=True),
            mock.patch.dict("sys.modules", {"unfold.widgets": fake}),
        ):
            assert (
                _widget(attrs={"class": "mine"}).attrs["class"]
                == "mine appearance-none rounded-full radio-select-exclusive"
            )

    def test_none_with_an_unfold_that_has_no_radio_classes(self):
        with (
            mock.patch(INSTALLED, return_value=True),
            mock.patch.dict("sys.modules", {"unfold.widgets": None}),
        ):
            assert widgets.theme_classes() == []
