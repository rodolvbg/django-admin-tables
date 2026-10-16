"""Method-by-method tests for RadioCheckboxInput, split into subTests
for the different scenarios each method has to handle. No database
needed, so this uses SimpleTestCase.
"""

from django.test import SimpleTestCase

from django_admin_tables.radio_select.widgets import RadioCheckboxInput


def _widget(**kwargs):
    kwargs.setdefault("group", "images::is_primary")
    kwargs.setdefault("field_name", "is_primary")
    return RadioCheckboxInput(**kwargs)


class RadioCheckboxInputTests(SimpleTestCase):
    def test_init(self):
        with self.subTest("sets the data attrs for field name and group"):
            widget = _widget()
            self.assertEqual(
                widget.attrs["data-radio-select-group"], "images::is_primary"
            )
            self.assertEqual(widget.attrs["data-radio-select-field"], "is_primary")

        with self.subTest("adds the exclusive marker class"):
            widget = _widget()
            self.assertIn("radio-select-exclusive", widget.attrs["class"])

        with self.subTest("preserves an existing class attr instead of overwriting it"):
            widget = _widget(attrs={"class": "existing"})
            self.assertEqual(widget.attrs["class"], "existing radio-select-exclusive")

    def test_renders_as_radio_not_checkbox(self):
        widget = _widget()

        with self.subTest("input_type is radio"):
            self.assertEqual(widget.input_type, "radio")

        with self.subTest("rendered HTML uses type=radio"):
            html = widget.render("is_primary", None)
            self.assertIn('type="radio"', html)
            self.assertNotIn('type="checkbox"', html)

    def test_render_reflects_the_checked_state(self):
        widget = _widget()

        with self.subTest("value=True renders checked"):
            self.assertIn("checked", widget.render("is_primary", True))

        with self.subTest("value=False does not render checked"):
            self.assertNotIn("checked", widget.render("is_primary", False))

    def test_value_from_datadict(self):
        # Present in the POST data => True; absent => False. Exactly
        # what a BooleanField's own default widget (CheckboxInput)
        # does, and what makes this drop-in safe for the field's
        # clean()/validate().
        widget = _widget()

        with self.subTest("absent from the data means False"):
            self.assertIs(widget.value_from_datadict({}, {}, "is_primary"), False)

        with self.subTest("present in the data means True"):
            self.assertIs(
                widget.value_from_datadict({"is_primary": "on"}, {}, "is_primary"), True
            )

    def test_media(self):
        js_paths = [str(script) for script in _widget().media._js]

        self.assertTrue(
            any("django_admin_tables/radio-select.js" in p for p in js_paths)
        )


class ThemeClassesTests(SimpleTestCase):
    def test_theme_classes(self):
        from unittest import mock

        from django_admin_tables.radio_select import widgets

        installed = "django_admin_tables.radio_select.widgets.apps.is_installed"

        with self.subTest("none without Unfold"):
            with mock.patch(installed, return_value=False):
                self.assertEqual(widgets.theme_classes(), [])
                self.assertEqual(_widget().attrs["class"], "radio-select-exclusive")

        with self.subTest("Unfold's radio classes with it"):
            fake = mock.Mock(RADIO_CLASSES=["appearance-none", "rounded-full"])
            with (
                mock.patch(installed, return_value=True),
                mock.patch.dict("sys.modules", {"unfold.widgets": fake}),
            ):
                self.assertEqual(
                    _widget(attrs={"class": "mine"}).attrs["class"],
                    "mine appearance-none rounded-full radio-select-exclusive",
                )

        with self.subTest("none with an Unfold that has no radio classes"):
            with (
                mock.patch(installed, return_value=True),
                mock.patch.dict("sys.modules", {"unfold.widgets": None}),
            ):
                self.assertEqual(widgets.theme_classes(), [])
