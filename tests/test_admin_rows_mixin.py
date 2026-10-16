import pytest
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from gallery.models import Album, Image

from django_admin_rows import (
    AdminRowsMixin,
    ExclusiveRadioFieldsMixin,
    ForeignKeyLinkMixin,
)
from django_admin_rows.radio_select import RadioCheckboxInput

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_():
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    return request


class ImageAdmin(AdminRowsMixin, admin.ModelAdmin):
    list_display = ("title", "album", "is_primary")
    list_editable = ("is_primary",)
    list_display_foreign_key_links = ("album",)
    radio_select_exclusive_fields = ("is_primary",)


class ImageInline(AdminRowsMixin, admin.TabularInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary",)


def test_combines_both_mixins():
    assert issubclass(AdminRowsMixin, ForeignKeyLinkMixin)
    assert issubclass(AdminRowsMixin, ExclusiveRadioFieldsMixin)


def test_model_admin_gets_links_and_radios(request_):
    image_admin = ImageAdmin(Image, admin.site)

    list_display = image_admin.get_list_display(request_)
    assert list_display[0] == "title"
    assert getattr(list_display[1], "__name__", "") == "album_link"
    assert list_display[2] == "is_primary"

    formset = image_admin.get_changelist_formset(request_)
    assert isinstance(formset.form.base_fields["is_primary"].widget, RadioCheckboxInput)


def test_model_admin_keeps_list_editable_fields_as_fields(request_):
    class Admin(ImageAdmin):
        list_display_foreign_key_links = ("album", "is_primary")

    assert Admin(Image, admin.site).get_list_display(request_)[2] == "is_primary"


def test_inline_gets_radios(request_):
    inline = ImageInline(Album, admin.site)

    assert isinstance(inline, admin.TabularInline)
    formset = inline.get_formset(request_)
    assert isinstance(formset.form.base_fields["is_primary"].widget, RadioCheckboxInput)
