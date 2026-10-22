"""Method-by-method tests for ExclusiveRadioFieldsMixin: one test class
per area, one test per scenario. Full HTTP-level integration (real
GET/POST through the admin views) lives in test_inline_integration.py and
test_changelist_integration.py instead — this file only calls the mixin's own methods
directly.
"""

from django import forms
from django.contrib import admin as djadmin
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.forms.models import inlineformset_factory
from django.test import RequestFactory, SimpleTestCase, TestCase
from gallery.admin import AlbumAdmin, ImageStackedInline, ImageTabularInline
from gallery.models import Album, Image
from unittest_parametrize import ParametrizedTestCase, parametrize

from django_admin_tables import ExclusiveRadioFieldsMixin
from django_admin_tables.radio_select.widgets import RadioCheckboxInput

RADIO_SELECT_JS = "django_admin_tables/radio-select.js"


class PartlyReadonlyInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary", "is_featured")
    readonly_fields = ("is_primary",)


class PlainInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
    model = Image
    radio_select_exclusive_fields = ()


def js_paths(media):
    return [str(script) for script in media._js]


class TestGetRadioSelectExclusiveFields(SimpleTestCase):
    """get_radio_select_exclusive_fields."""

    def setUp(self):
        self.site = djadmin.AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = AnonymousUser()

    def test_returns_the_class_attribute_unchanged_by_default(self):
        inline = ImageTabularInline(Album, self.site)

        assert inline.get_radio_select_exclusive_fields(self.request) == (
            "is_primary",
            "is_featured",
        )

    def test_does_not_filter_readonly_fields_itself(self):
        inline = PartlyReadonlyInline(Album, self.site)

        assert inline.get_radio_select_exclusive_fields(self.request) == (
            "is_primary",
            "is_featured",
        )

    def test_can_be_overridden_per_request_and_obj(self):
        class DynamicInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            radio_select_exclusive_fields = ("title",)  # would raise if actually used

            def get_radio_select_exclusive_fields(self, request, obj=None):
                return ("is_primary",)

        formset_class = DynamicInline(Album, self.site).get_formset(self.request)

        assert isinstance(
            formset_class.form.base_fields["is_primary"].widget, RadioCheckboxInput
        )


class TestGetEffectiveRadioSelectExclusiveFields(SimpleTestCase):
    """_get_effective_radio_select_exclusive_fields."""

    def setUp(self):
        self.site = djadmin.AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = AnonymousUser()

    def test_drops_fields_that_are_currently_readonly(self):
        inline = PartlyReadonlyInline(Album, self.site)

        assert inline._get_effective_radio_select_exclusive_fields(self.request) == (
            "is_featured",
        )

    def test_still_filters_when_the_getter_is_overridden(self):
        class DynamicInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            readonly_fields = ("is_primary",)

            def get_radio_select_exclusive_fields(self, request, obj=None):
                return ("is_primary", "is_featured")

        inline = DynamicInline(Album, self.site)

        assert inline._get_effective_radio_select_exclusive_fields(self.request) == (
            "is_featured",
        )

    def test_a_readonly_field_does_not_crash_get_formset(self):
        # Without the filter this would raise ImproperlyConfigured
        # for a field the admin class itself excluded from the form
        # (Django never puts a readonly field in form.base_fields).
        formset_class = PartlyReadonlyInline(Album, self.site).get_formset(self.request)

        assert "is_primary" not in formset_class.form.base_fields
        assert isinstance(
            formset_class.form.base_fields["is_featured"].widget, RadioCheckboxInput
        )


class TestRadioizeFormFields(ParametrizedTestCase, SimpleTestCase):
    """_radioize_form_fields (staticmethod)."""

    def test_converts_a_configured_boolean_field_to_a_radio_widget(self):
        class Form(forms.ModelForm):
            class Meta:
                model = Image
                fields = ["title", "is_primary"]

        ExclusiveRadioFieldsMixin._radioize_form_fields(Form, ("is_primary",), "images")

        field = Form.base_fields["is_primary"]
        assert isinstance(field.widget, RadioCheckboxInput)
        assert not field.required
        assert field.widget.attrs["data-radio-select-group"] == "images::is_primary"

    @parametrize("field_name", [("does_not_exist",), ("title",)])
    def test_raises_improperly_configured_for_a_missing_or_non_boolean_field(
        self, field_name
    ):
        class TitleOnlyForm(forms.ModelForm):
            class Meta:
                model = Image
                fields = ["title"]

        with self.assertRaisesRegex(ImproperlyConfigured, field_name):
            ExclusiveRadioFieldsMixin._radioize_form_fields(
                TitleOnlyForm, (field_name,), "images"
            )


class TestWrapFormset(SimpleTestCase):
    """_wrap_formset (staticmethod)."""

    def test_returns_the_formset_unchanged_when_no_fields_are_configured(self):
        formset_class = inlineformset_factory(
            Album, Image, fields=["title", "is_primary"]
        )

        wrapped = ExclusiveRadioFieldsMixin._wrap_formset(formset_class, ())

        assert wrapped is formset_class

    def test_radioizes_the_field_and_wraps_it_with_exclusivity_validation(self):
        formset_class = inlineformset_factory(
            Album, Image, fields=["title", "is_primary"]
        )

        wrapped = ExclusiveRadioFieldsMixin._wrap_formset(
            formset_class, ("is_primary",)
        )

        assert isinstance(
            wrapped.form.base_fields["is_primary"].widget, RadioCheckboxInput
        )
        assert issubclass(wrapped, formset_class)
        assert wrapped is not formset_class


class TestGetFormset(ParametrizedTestCase, TestCase):
    """get_formset (inline)."""

    @classmethod
    def setUpTestData(cls):
        cls.album_with_images = Album.objects.create(title="Holiday")
        Image.objects.create(album=cls.album_with_images, title="A", is_primary=True)
        Image.objects.create(album=cls.album_with_images, title="B", is_primary=False)
        Image.objects.create(album=cls.album_with_images, title="C", is_primary=False)

    def setUp(self):
        self.site = djadmin.AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = AnonymousUser()

    @parametrize(
        ("inline_class", "field_name"),
        [
            (ImageTabularInline, "is_primary"),
            (ImageTabularInline, "is_featured"),
            (ImageStackedInline, "is_primary"),
            (ImageStackedInline, "is_featured"),
        ],
        ids=[
            "tabular_is_primary",
            "tabular_is_featured",
            "stacked_is_primary",
            "stacked_is_featured",
        ],
    )
    def test_radioizes_configured_boolean_fields(self, inline_class, field_name):
        formset_class = inline_class(Album, self.site).get_formset(self.request)

        field = formset_class.form.base_fields[field_name]
        assert isinstance(field.widget, RadioCheckboxInput)
        assert not field.required

    def test_initial_selected_state_renders_checked_on_the_right_row(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)
        formset = formset_class(instance=self.album_with_images)

        rows = {form.instance.title: form for form in formset.forms}
        assert "checked" in str(rows["A"]["is_primary"])
        assert "checked" not in str(rows["B"]["is_primary"])
        assert "checked" not in str(rows["C"]["is_primary"])

    def test_rows_keep_independent_post_names(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)

        html = str(formset_class(instance=self.album_with_images))

        assert 'name="images-0-is_primary"' in html
        assert 'name="images-1-is_primary"' in html
        assert 'name="images-0-is_featured"' in html

    def test_multiple_configured_fields_get_independent_group_keys(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)
        base_fields = formset_class.form.base_fields

        primary_group = base_fields["is_primary"].widget.attrs[
            "data-radio-select-group"
        ]
        featured_group = base_fields["is_featured"].widget.attrs[
            "data-radio-select-group"
        ]

        assert primary_group != featured_group
        assert primary_group.endswith("::is_primary")
        assert featured_group.endswith("::is_featured")

    def test_group_key_is_derived_from_the_formset_prefix(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)

        group = formset_class.form.base_fields["is_primary"].widget.attrs[
            "data-radio-select-group"
        ]

        assert group == f"{formset_class.get_default_prefix()}::is_primary"

    def test_empty_form_template_shares_the_group_key_with_real_rows(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)
        formset = formset_class(instance=self.album_with_images)

        bound_group = (
            formset.forms[0]
            .fields["is_primary"]
            .widget.attrs["data-radio-select-group"]
        )
        empty_group = formset.empty_form.fields["is_primary"].widget.attrs[
            "data-radio-select-group"
        ]

        assert bound_group == empty_group

    def test_leaves_an_unconfigured_field_alone(self):
        formset_class = PlainInline(Album, self.site).get_formset(self.request)

        assert not isinstance(
            formset_class.form.base_fields["is_primary"].widget, RadioCheckboxInput
        )

    def test_propagates_improperly_configured_from_a_misconfigured_field(self):
        class BadInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            radio_select_exclusive_fields = ("does_not_exist",)

        with self.assertRaises(ImproperlyConfigured):
            BadInline(Album, self.site).get_formset(self.request)

    def test_field_not_on_the_model_but_declared_on_the_form_is_radioized(self):
        class ExtraFieldForm(forms.ModelForm):
            approved = forms.BooleanField(required=False)

            class Meta:
                model = Image
                fields = ["title", "is_primary", "approved"]

        class ExtraFieldInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            form = ExtraFieldForm
            radio_select_exclusive_fields = ("approved",)

        formset_class = ExtraFieldInline(Album, self.site).get_formset(self.request)

        assert isinstance(
            formset_class.form.base_fields["approved"].widget, RadioCheckboxInput
        )

    def test_form_field_type_overriding_the_models_is_radioized(self):
        class BooleanTitleForm(forms.ModelForm):
            title = forms.BooleanField(required=False)

            class Meta:
                model = Image
                fields = ["title", "is_primary"]

        class BooleanTitleInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            form = BooleanTitleForm
            radio_select_exclusive_fields = ("title",)

        formset_class = BooleanTitleInline(Album, self.site).get_formset(self.request)

        assert isinstance(
            formset_class.form.base_fields["title"].widget, RadioCheckboxInput
        )


class TestGetChangelistFormset(TestCase):
    """get_changelist_formset (ModelAdmin)."""

    @classmethod
    def setUpTestData(cls):
        cls.albums = [
            Album.objects.create(title="Winter", is_featured=True),
            Album.objects.create(title="Spring", is_featured=False),
            Album.objects.create(title="Summer", is_featured=False),
        ]

    def setUp(self):
        self.site = djadmin.AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = AnonymousUser()

    def test_radioizes_the_configured_list_editable_boolean_field(self):
        formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )

        field = formset_class.form.base_fields["is_featured"]
        assert isinstance(field.widget, RadioCheckboxInput)
        assert not field.required

    def test_group_key_uses_the_plain_form_formset_prefix(self):
        formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )

        group = formset_class.form.base_fields["is_featured"].widget.attrs[
            "data-radio-select-group"
        ]
        assert formset_class.get_default_prefix() == "form"
        assert group == "form::is_featured"

    def test_rows_keep_independent_names_and_initial_state(self):
        formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )
        formset = formset_class(queryset=Album.objects.order_by("pk"))

        html = str(formset)
        assert 'name="form-0-is_featured"' in html
        assert 'name="form-1-is_featured"' in html
        rows = {form.instance.title: form for form in formset.forms}
        assert "checked" in str(rows["Winter"]["is_featured"])
        assert "checked" not in str(rows["Spring"]["is_featured"])

    def test_leaves_an_unconfigured_model_admin_alone(self):
        class PlainAlbumAdmin(ExclusiveRadioFieldsMixin, djadmin.ModelAdmin):
            list_display = ("title", "is_featured")
            list_editable = ("is_featured",)
            radio_select_exclusive_fields = ()

        formset_class = PlainAlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )

        assert not isinstance(
            formset_class.form.base_fields["is_featured"].widget, RadioCheckboxInput
        )

    def test_improperly_configured_for_a_field_missing_from_list_editable(self):
        class BadAlbumAdmin(ExclusiveRadioFieldsMixin, djadmin.ModelAdmin):
            list_display = ("title",)
            list_editable = ()
            radio_select_exclusive_fields = ("is_featured",)

        with self.assertRaisesRegex(ImproperlyConfigured, "is_featured"):
            BadAlbumAdmin(Album, self.site).get_changelist_formset(self.request)

    def test_field_declared_on_the_changelist_form_only_is_radioized(self):
        class ExtraFieldForm(forms.ModelForm):
            approved = forms.BooleanField(required=False)

            class Meta:
                model = Album
                fields = ["title", "is_featured"]

        class ExtraFieldAlbumAdmin(ExclusiveRadioFieldsMixin, djadmin.ModelAdmin):
            list_display = ("title", "is_featured", "approved")
            list_editable = ("is_featured",)
            radio_select_exclusive_fields = ("approved",)

            def get_changelist_form(self, request, **kwargs):
                return ExtraFieldForm

        formset_class = ExtraFieldAlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )

        assert isinstance(
            formset_class.form.base_fields["approved"].widget, RadioCheckboxInput
        )


class TestMedia(TestCase):
    """RadioCheckboxInput.media, pulled in via a rendered form."""

    def setUp(self):
        self.site = djadmin.AdminSite()
        self.request = RequestFactory().get("/admin/")
        self.request.user = AnonymousUser()

    def test_pulled_in_by_the_rendered_inline_formset_when_a_field_is_radioized(self):
        formset_class = ImageTabularInline(Album, self.site).get_formset(self.request)

        assert any(RADIO_SELECT_JS in p for p in js_paths(formset_class().media))

    def test_absent_from_the_inline_formset_when_no_field_is_radioized(self):
        formset_class = PlainInline(Album, self.site).get_formset(self.request)

        assert not any(RADIO_SELECT_JS in p for p in js_paths(formset_class().media))

    def test_pulled_in_by_the_changelist_formset_when_a_field_is_radioized(self):
        formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(
            self.request
        )
        media = formset_class(queryset=Album.objects.none()).media

        assert any(RADIO_SELECT_JS in p for p in js_paths(media))

    def test_absent_from_the_plain_model_admin_media(self):
        assert not any(
            RADIO_SELECT_JS in p for p in js_paths(AlbumAdmin(Album, self.site).media)
        )
