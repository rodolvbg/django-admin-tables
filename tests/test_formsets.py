from django.contrib import admin as djadmin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from gallery.admin import ImageTabularInline
from gallery.models import Album, Image

from django_admin_tables import ExclusiveRadioFieldsMixin


def management_data(album, rows=None, extra_forms=0):
    """Build the POST management-form + row data a formset expects,
    mimicking exactly what real browser submission (JS-managed or not)
    produces: every row keeps its own numbered field name.

    ``rows`` maps row index -> {"is_primary": bool, "is_featured": bool,
    "delete": bool}.
    """
    rows = rows or {}
    images = list(album.images.all())
    data = {
        "images-TOTAL_FORMS": str(len(images) + extra_forms),
        "images-INITIAL_FORMS": str(len(images)),
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }
    for index, image in enumerate(images):
        data[f"images-{index}-id"] = str(image.pk)
        data[f"images-{index}-album"] = str(album.pk)
        data[f"images-{index}-title"] = image.title
        row = rows.get(index, {})
        if row.get("is_primary"):
            data[f"images-{index}-is_primary"] = "on"
        if row.get("is_featured"):
            data[f"images-{index}-is_featured"] = "on"
        if row.get("delete"):
            data[f"images-{index}-DELETE"] = "on"
    return data


def build_formset(request_, site, album, data):
    inline = ImageTabularInline(Album, site)
    formset_class = inline.get_formset(request_)
    return formset_class(data, instance=album)


class TestExclusiveRadioFormSet(TestCase):
    """Exactly-one-selected validation of the exclusive formset."""

    @classmethod
    def setUpTestData(cls):
        # A real superuser, not AnonymousUser: Django admin's own
        # DeleteProtectedModelForm.has_changed() and the formset's
        # can_delete flag are both gated on has_change_permission() /
        # has_delete_permission(), so an unprivileged user silently makes
        # saves and deletions no-ops regardless of what our mixin does.
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.album = Album.objects.create(title="Holiday")
        Image.objects.create(album=cls.album, title="A", is_primary=False)
        Image.objects.create(album=cls.album, title="B", is_primary=False)

    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        self.site = djadmin.AdminSite()

    def test_single_selected_row_is_valid(self):
        data = management_data(self.album, rows={0: {"is_primary": True}})
        formset = build_formset(self.request, self.site, self.album, data)

        assert formset.is_valid(), formset.errors

    def test_no_selected_row_is_valid(self):
        data = management_data(self.album)
        formset = build_formset(self.request, self.site, self.album, data)

        assert formset.is_valid(), formset.errors

    def test_malformed_post_with_two_true_rows_is_rejected(self):
        data = management_data(
            self.album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        formset = build_formset(self.request, self.site, self.album, data)

        assert not formset.is_valid()
        assert any("is_primary" in str(error) for error in formset.non_form_errors())

    def test_two_true_rows_on_different_fields_is_valid(self):
        # is_primary and is_featured are independent groups: one True each
        # is fine even though it's the same two rows.
        data = management_data(
            self.album, rows={0: {"is_primary": True}, 1: {"is_featured": True}}
        )
        formset = build_formset(self.request, self.site, self.album, data)

        assert formset.is_valid(), formset.errors

    def test_row_marked_for_deletion_is_excluded_from_the_count(self):
        data = management_data(
            self.album,
            rows={0: {"is_primary": True, "delete": True}, 1: {"is_primary": True}},
        )
        formset = build_formset(self.request, self.site, self.album, data)

        assert formset.is_valid(), formset.errors

    def test_saving_a_valid_formset_persists_exactly_one_true_row(self):
        data = management_data(self.album, rows={1: {"is_primary": True}})
        formset = build_formset(self.request, self.site, self.album, data)

        assert formset.is_valid(), formset.errors
        formset.save()

        images = {image.title: image.is_primary for image in self.album.images.all()}
        assert images == {"A": False, "B": True}

    def test_dynamically_added_row_can_be_submitted_and_becomes_the_selected_one(self):
        # What Django admin's "Add another" produces client-side: an extra
        # form beyond INITIAL_FORMS, with no "id" (new row) and a title.
        data = management_data(self.album, extra_forms=1)
        data["images-2-id"] = ""
        data["images-2-album"] = str(self.album.pk)
        data["images-2-title"] = "C"
        data["images-2-is_primary"] = "on"

        formset = build_formset(self.request, self.site, self.album, data)
        assert formset.is_valid(), formset.errors
        formset.save()

        images = {image.title: image.is_primary for image in self.album.images.all()}
        assert images == {"A": False, "B": False, "C": True}

    def test_exclusivity_check_is_skipped_when_a_row_already_has_field_errors(self):
        # If a row's own fields are invalid, our formset-level clean() must
        # not layer a second, more confusing error on top of it.
        data = management_data(
            self.album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        data["images-0-title"] = ""  # title is required: this row is already invalid

        formset = build_formset(self.request, self.site, self.album, data)

        assert not formset.is_valid()
        assert formset.errors[0].get("title")
        assert formset.non_form_errors() == []

    def test_user_supplied_formset_clean_is_preserved(self):
        from django.forms.models import BaseInlineFormSet

        calls = []

        class CustomFormSet(BaseInlineFormSet):
            def clean(self):
                super().clean()
                calls.append("custom-clean-ran")

        class CustomInline(ExclusiveRadioFieldsMixin, djadmin.TabularInline):
            model = Image
            formset = CustomFormSet
            radio_select_exclusive_fields = ("is_primary",)

        inline = CustomInline(Album, self.site)
        formset_class = inline.get_formset(self.request)

        data = management_data(
            self.album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        formset = formset_class(data, instance=self.album)

        assert not formset.is_valid()
        assert calls == ["custom-clean-ran"]
