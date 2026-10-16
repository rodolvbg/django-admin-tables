"""Method-by-method tests for ExclusiveRadioFieldsMixin: one test
method per public/internal method, split into subTests for the
different scenarios that method has to handle. Full HTTP-level
integration (real GET/POST through the admin views) lives in
test_admin_integration.py and the tail of test_changelist.py instead —
this file only calls the mixin's own methods directly.
"""

from django import forms
from django.contrib import admin as djadmin
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured
from django.forms.models import inlineformset_factory
from django.test import RequestFactory, TestCase
from gallery.admin import AlbumAdmin, ImageStackedInline, ImageTabularInline
from gallery.models import Album, Image

from django_admin_tables import ExclusiveRadioFieldsMixin
from django_admin_tables.radio_select.widgets import RadioCheckboxInput


class ExclusiveRadioFieldsMixinTests(TestCase):
    def setUp(self):
        self.site = djadmin.AdminSite()
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.get("/admin/")
        request.user = AnonymousUser()
        return request

    def _album_with_images(self):
        album = Album.objects.create(title="Holiday")
        Image.objects.create(album=album, title="A", is_primary=True)
        Image.objects.create(album=album, title="B", is_primary=False)
        Image.objects.create(album=album, title="C", is_primary=False)
        return album

    def _albums(self):
        return [
            Album.objects.create(title="Winter", is_featured=True),
            Album.objects.create(title="Spring", is_featured=False),
            Album.objects.create(title="Summer", is_featured=False),
        ]

    # -- get_radio_select_exclusive_fields --------------------------------

    def test_get_radio_select_exclusive_fields(self):
        request = self._request()

        with self.subTest("returns the class attribute unchanged by default"):
            inline = ImageTabularInline(Album, self.site)
            self.assertEqual(
                inline.get_radio_select_exclusive_fields(request),
                ("is_primary", "is_featured"),
            )

        with self.subTest("does not filter readonly fields itself"):

            class PartlyReadonlyInline(
                ExclusiveRadioFieldsMixin, djadmin.TabularInline
            ):
                model = Image
                radio_select_exclusive_fields = ("is_primary", "is_featured")
                readonly_fields = ("is_primary",)

            inline = PartlyReadonlyInline(Album, self.site)
            self.assertEqual(
                inline.get_radio_select_exclusive_fields(request),
                ("is_primary", "is_featured"),
            )

        with self.subTest("can be overridden per request/obj"):

            class DynamicInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                radio_select_exclusive_fields = (
                    "title",
                )  # would raise if actually used

                def get_radio_select_exclusive_fields(self, request, obj=None):
                    return ("is_primary",)

            formset_class = DynamicInline(Album, self.site).get_formset(request)
            self.assertIsInstance(
                formset_class.form.base_fields["is_primary"].widget, RadioCheckboxInput
            )

    # -- _get_effective_radio_select_exclusive_fields ----------------------

    def test_get_effective_radio_select_exclusive_fields(self):
        request = self._request()

        class PartlyReadonlyInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            radio_select_exclusive_fields = ("is_primary", "is_featured")
            readonly_fields = ("is_primary",)

        with self.subTest("drops fields that are currently readonly"):
            inline = PartlyReadonlyInline(Album, self.site)
            self.assertEqual(
                inline._get_effective_radio_select_exclusive_fields(request),
                ("is_featured",),
            )

        with self.subTest(
            "still filters when get_radio_select_exclusive_fields is overridden"
        ):

            class DynamicInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                readonly_fields = ("is_primary",)

                def get_radio_select_exclusive_fields(self, request, obj=None):
                    return ("is_primary", "is_featured")

            inline = DynamicInline(Album, self.site)
            self.assertEqual(
                inline._get_effective_radio_select_exclusive_fields(request),
                ("is_featured",),
            )

        with self.subTest("a readonly field does not crash get_formset"):
            # Without the filter this would raise ImproperlyConfigured
            # for a field the admin class itself excluded from the form
            # (Django never puts a readonly field in form.base_fields).
            inline = PartlyReadonlyInline(Album, self.site)
            formset_class = inline.get_formset(request)
            self.assertNotIn("is_primary", formset_class.form.base_fields)
            self.assertIsInstance(
                formset_class.form.base_fields["is_featured"].widget, RadioCheckboxInput
            )

    # -- _radioize_form_fields (staticmethod) ------------------------------

    def test_radioize_form_fields(self):
        with self.subTest("converts a configured boolean field to a radio widget"):

            class Form(forms.ModelForm):
                class Meta:
                    model = Image
                    fields = ["title", "is_primary"]

            ExclusiveRadioFieldsMixin._radioize_form_fields(
                Form, ("is_primary",), "images"
            )
            field = Form.base_fields["is_primary"]
            self.assertIsInstance(field.widget, RadioCheckboxInput)
            self.assertFalse(field.required)
            self.assertEqual(
                field.widget.attrs["data-radio-select-group"], "images::is_primary"
            )

        with self.subTest("raises ImproperlyConfigured for a missing field"):

            class MissingFieldForm(forms.ModelForm):
                class Meta:
                    model = Image
                    fields = ["title"]

            with self.assertRaisesMessage(ImproperlyConfigured, "does_not_exist"):
                ExclusiveRadioFieldsMixin._radioize_form_fields(
                    MissingFieldForm, ("does_not_exist",), "images"
                )

        with self.subTest("raises ImproperlyConfigured for a non-boolean field"):

            class NonBooleanForm(forms.ModelForm):
                class Meta:
                    model = Image
                    fields = ["title"]

            with self.assertRaisesMessage(ImproperlyConfigured, "title"):
                ExclusiveRadioFieldsMixin._radioize_form_fields(
                    NonBooleanForm, ("title",), "images"
                )

    # -- _wrap_formset (staticmethod) ---------------------------------------

    def test_wrap_formset(self):
        with self.subTest(
            "returns the formset unchanged when no fields are configured"
        ):
            formset_class = inlineformset_factory(
                Album, Image, fields=["title", "is_primary"]
            )
            wrapped = ExclusiveRadioFieldsMixin._wrap_formset(formset_class, ())
            self.assertIs(wrapped, formset_class)

        with self.subTest(
            "radioizes the field and wraps it with exclusivity validation"
        ):
            formset_class = inlineformset_factory(
                Album, Image, fields=["title", "is_primary"]
            )
            wrapped = ExclusiveRadioFieldsMixin._wrap_formset(
                formset_class, ("is_primary",)
            )
            self.assertIsInstance(
                wrapped.form.base_fields["is_primary"].widget, RadioCheckboxInput
            )
            self.assertTrue(issubclass(wrapped, formset_class))
            self.assertIsNot(wrapped, formset_class)

    # -- get_formset (inline) -----------------------------------------------

    def test_get_formset(self):
        request = self._request()

        with self.subTest("radioizes configured boolean fields (TabularInline)"):
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            for field_name in ("is_primary", "is_featured"):
                field = formset_class.form.base_fields[field_name]
                self.assertIsInstance(field.widget, RadioCheckboxInput)
                self.assertFalse(field.required)

        with self.subTest("radioizes configured boolean fields (StackedInline)"):
            formset_class = ImageStackedInline(Album, self.site).get_formset(request)
            for field_name in ("is_primary", "is_featured"):
                self.assertIsInstance(
                    formset_class.form.base_fields[field_name].widget,
                    RadioCheckboxInput,
                )

        with self.subTest("initial selected state renders checked on the right row"):
            album = self._album_with_images()
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            formset = formset_class(instance=album)
            rows = {form.instance.title: form for form in formset.forms}
            self.assertIn("checked", str(rows["A"]["is_primary"]))
            self.assertNotIn("checked", str(rows["B"]["is_primary"]))
            self.assertNotIn("checked", str(rows["C"]["is_primary"]))

        with self.subTest("rows keep independent POST names"):
            album = self._album_with_images()
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            html = str(formset_class(instance=album))
            self.assertIn('name="images-0-is_primary"', html)
            self.assertIn('name="images-1-is_primary"', html)
            self.assertIn('name="images-0-is_featured"', html)

        with self.subTest("multiple configured fields get independent group keys"):
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            base_fields = formset_class.form.base_fields
            primary_group = base_fields["is_primary"].widget.attrs[
                "data-radio-select-group"
            ]
            featured_group = base_fields["is_featured"].widget.attrs[
                "data-radio-select-group"
            ]
            self.assertNotEqual(primary_group, featured_group)
            self.assertTrue(primary_group.endswith("::is_primary"))
            self.assertTrue(featured_group.endswith("::is_featured"))

        with self.subTest("group key is derived from the formset prefix"):
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            group = formset_class.form.base_fields["is_primary"].widget.attrs[
                "data-radio-select-group"
            ]
            self.assertEqual(group, f"{formset_class.get_default_prefix()}::is_primary")

        with self.subTest("empty_form template shares the group key with real rows"):
            album = self._album_with_images()
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            formset = formset_class(instance=album)
            bound_group = (
                formset.forms[0]
                .fields["is_primary"]
                .widget.attrs["data-radio-select-group"]
            )
            empty_group = formset.empty_form.fields["is_primary"].widget.attrs[
                "data-radio-select-group"
            ]
            self.assertEqual(bound_group, empty_group)

        with self.subTest("leaves an unconfigured field alone"):

            class PlainInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                radio_select_exclusive_fields = ()

            formset_class = PlainInline(Album, self.site).get_formset(request)
            self.assertNotIsInstance(
                formset_class.form.base_fields["is_primary"].widget, RadioCheckboxInput
            )

        with self.subTest("propagates ImproperlyConfigured from a misconfigured field"):

            class BadInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                radio_select_exclusive_fields = ("does_not_exist",)

            with self.assertRaises(ImproperlyConfigured):
                BadInline(Album, self.site).get_formset(request)

        with self.subTest(
            "field not on the model but declared on the form is radioized"
        ):

            class ExtraFieldForm(forms.ModelForm):
                approved = forms.BooleanField(required=False)

                class Meta:
                    model = Image
                    fields = ["title", "is_primary", "approved"]

            class ExtraFieldInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                form = ExtraFieldForm
                radio_select_exclusive_fields = ("approved",)

            formset_class = ExtraFieldInline(Album, self.site).get_formset(request)
            self.assertIsInstance(
                formset_class.form.base_fields["approved"].widget, RadioCheckboxInput
            )

        with self.subTest("form field type overriding the model's is radioized"):

            class BooleanTitleForm(forms.ModelForm):
                title = forms.BooleanField(required=False)

                class Meta:
                    model = Image
                    fields = ["title", "is_primary"]

            class BooleanTitleInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                form = BooleanTitleForm
                radio_select_exclusive_fields = ("title",)

            formset_class = BooleanTitleInline(Album, self.site).get_formset(request)
            self.assertIsInstance(
                formset_class.form.base_fields["title"].widget, RadioCheckboxInput
            )

    # -- get_changelist_formset (ModelAdmin) --------------------------------

    def test_get_changelist_formset(self):
        request = self._request()

        with self.subTest("radioizes the configured list_editable boolean field"):
            formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(request)
            field = formset_class.form.base_fields["is_featured"]
            self.assertIsInstance(field.widget, RadioCheckboxInput)
            self.assertFalse(field.required)

        with self.subTest("group key uses the plain 'form' formset prefix"):
            formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(request)
            group = formset_class.form.base_fields["is_featured"].widget.attrs[
                "data-radio-select-group"
            ]
            self.assertEqual(formset_class.get_default_prefix(), "form")
            self.assertEqual(group, "form::is_featured")

        with self.subTest("rows keep independent names and initial state"):
            self._albums()
            formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(request)
            formset = formset_class(queryset=Album.objects.order_by("pk"))
            html = str(formset)
            self.assertIn('name="form-0-is_featured"', html)
            self.assertIn('name="form-1-is_featured"', html)
            rows = {form.instance.title: form for form in formset.forms}
            self.assertIn("checked", str(rows["Winter"]["is_featured"]))
            self.assertNotIn("checked", str(rows["Spring"]["is_featured"]))

        with self.subTest("leaves an unconfigured ModelAdmin alone"):

            class PlainAlbumAdmin(ExclusiveRadioFieldsMixin, djadmin.ModelAdmin):
                list_display = ("title", "is_featured")
                list_editable = ("is_featured",)
                radio_select_exclusive_fields = ()

            formset_class = PlainAlbumAdmin(Album, self.site).get_changelist_formset(
                request
            )
            self.assertNotIsInstance(
                formset_class.form.base_fields["is_featured"].widget, RadioCheckboxInput
            )

        with self.subTest(
            "propagates ImproperlyConfigured for a field missing from list_editable"
        ):

            class BadAlbumAdmin(ExclusiveRadioFieldsMixin, djadmin.ModelAdmin):
                list_display = ("title",)
                list_editable = ()
                radio_select_exclusive_fields = ("is_featured",)

            with self.assertRaisesMessage(ImproperlyConfigured, "is_featured"):
                BadAlbumAdmin(Album, self.site).get_changelist_formset(request)

        with self.subTest(
            "field not on the model but declared on the changelist form is radioized"
        ):

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

            formset_class = ExtraFieldAlbumAdmin(
                Album, self.site
            ).get_changelist_formset(request)
            self.assertIsInstance(
                formset_class.form.base_fields["approved"].widget, RadioCheckboxInput
            )

    # -- media (RadioCheckboxInput.media, pulled in via a rendered form) ---

    def test_media(self):
        request = self._request()

        with self.subTest(
            "pulled in by the rendered inline formset when a field is radioized"
        ):
            formset_class = ImageTabularInline(Album, self.site).get_formset(request)
            js_paths = [str(s) for s in formset_class().media._js]
            self.assertTrue(
                any("django_admin_tables/radio-select.js" in p for p in js_paths)
            )

        with self.subTest("absent from the inline formset when no field is radioized"):

            class PlainInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
                model = Image
                radio_select_exclusive_fields = ()

            formset_class = PlainInline(Album, self.site).get_formset(request)
            js_paths = [str(s) for s in formset_class().media._js]
            self.assertFalse(
                any("django_admin_tables/radio-select.js" in p for p in js_paths)
            )

        with self.subTest(
            "pulled in by the rendered changelist formset when a field is radioized"
        ):
            formset_class = AlbumAdmin(Album, self.site).get_changelist_formset(request)
            js_paths = [
                str(s) for s in formset_class(queryset=Album.objects.none()).media._js
            ]
            self.assertTrue(
                any("django_admin_tables/radio-select.js" in p for p in js_paths)
            )

        with self.subTest(
            "absent from the plain ModelAdmin.media (used on every page)"
        ):
            js_paths = [str(s) for s in AlbumAdmin(Album, self.site).media._js]
            self.assertFalse(
                any("django_admin_tables/radio-select.js" in p for p in js_paths)
            )
