import pytest
from django.contrib import admin as djadmin
from django.test import RequestFactory
from gallery.admin import ImageTabularInline
from gallery.models import Album, Image

from django_admin_tables import ExclusiveRadioFieldsMixin

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_(rf: RequestFactory, django_user_model):
    # A real staff/superuser, not AnonymousUser: Django admin's own
    # DeleteProtectedModelForm.has_changed() and the formset's
    # can_delete flag are both gated on has_change_permission() /
    # has_delete_permission(), so an unprivileged user silently makes
    # saves and deletions no-ops regardless of what our mixin does.
    user = django_user_model.objects.create_superuser(
        "admin", "admin@example.com", "password"
    )
    request = rf.get("/admin/")
    request.user = user
    return request


@pytest.fixture
def site():
    return djadmin.AdminSite()


@pytest.fixture
def album():
    album = Album.objects.create(title="Holiday")
    Image.objects.create(album=album, title="A", is_primary=False)
    Image.objects.create(album=album, title="B", is_primary=False)
    return album


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


class TestExclusiveRadioFormSet:
    """Exactly-one-selected validation of the exclusive formset."""

    def test_single_selected_row_is_valid(self, request_, site, album):
        data = management_data(album, rows={0: {"is_primary": True}})
        formset = build_formset(request_, site, album, data)

        assert formset.is_valid(), formset.errors

    def test_no_selected_row_is_valid(self, request_, site, album):
        data = management_data(album)
        formset = build_formset(request_, site, album, data)

        assert formset.is_valid(), formset.errors

    def test_malformed_post_with_two_true_rows_is_rejected(self, request_, site, album):
        data = management_data(
            album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        formset = build_formset(request_, site, album, data)

        assert not formset.is_valid()
        assert any("is_primary" in str(error) for error in formset.non_form_errors())

    def test_two_true_rows_on_different_fields_is_valid(self, request_, site, album):
        # is_primary and is_featured are independent groups: one True each
        # is fine even though it's the same two rows.
        data = management_data(
            album, rows={0: {"is_primary": True}, 1: {"is_featured": True}}
        )
        formset = build_formset(request_, site, album, data)

        assert formset.is_valid(), formset.errors

    def test_row_marked_for_deletion_is_excluded_from_the_count(
        self, request_, site, album
    ):
        data = management_data(
            album,
            rows={0: {"is_primary": True, "delete": True}, 1: {"is_primary": True}},
        )
        formset = build_formset(request_, site, album, data)

        assert formset.is_valid(), formset.errors

    def test_saving_a_valid_formset_persists_exactly_one_true_row(
        self, request_, site, album
    ):
        data = management_data(album, rows={1: {"is_primary": True}})
        formset = build_formset(request_, site, album, data)

        assert formset.is_valid(), formset.errors
        formset.save()

        images = {image.title: image.is_primary for image in album.images.all()}
        assert images == {"A": False, "B": True}

    def test_dynamically_added_row_can_be_submitted_and_becomes_the_selected_one(
        self, request_, site, album
    ):
        # What Django admin's "Add another" produces client-side: an extra
        # form beyond INITIAL_FORMS, with no "id" (new row) and a title.
        data = management_data(album, extra_forms=1)
        data["images-2-id"] = ""
        data["images-2-album"] = str(album.pk)
        data["images-2-title"] = "C"
        data["images-2-is_primary"] = "on"

        formset = build_formset(request_, site, album, data)
        assert formset.is_valid(), formset.errors
        formset.save()

        images = {image.title: image.is_primary for image in album.images.all()}
        assert images == {"A": False, "B": False, "C": True}

    def test_exclusivity_check_is_skipped_when_a_row_already_has_field_errors(
        self, request_, site, album
    ):
        # If a row's own fields are invalid, our formset-level clean() must
        # not layer a second, more confusing error on top of it.
        data = management_data(
            album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        data["images-0-title"] = ""  # title is required: this row is already invalid

        formset = build_formset(request_, site, album, data)

        assert not formset.is_valid()
        assert formset.errors[0].get("title")
        assert formset.non_form_errors() == []

    def test_user_supplied_formset_clean_is_preserved(self, request_, site, album):
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

        inline = CustomInline(Album, site)
        formset_class = inline.get_formset(request_)

        data = management_data(
            album, rows={0: {"is_primary": True}, 1: {"is_primary": True}}
        )
        formset = formset_class(data, instance=album)

        assert not formset.is_valid()
        assert calls == ["custom-clean-ran"]
