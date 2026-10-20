from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from gallery.models import Album, Image

from django_admin_tables import (
    AdminTablesMixin,
    ExclusiveRadioFieldsMixin,
    ForeignKeyLinkMixin,
)
from django_admin_tables.radio_select import RadioCheckboxInput


class ImageAdmin(AdminTablesMixin, admin.ModelAdmin):
    list_display = ("title", "album", "is_primary")
    list_editable = ("is_primary",)
    list_display_foreign_key_links = ("album",)
    radio_select_exclusive_fields = ("is_primary",)


class ImageInline(AdminTablesMixin, admin.TabularInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary",)


class TestAdminTablesMixin(TestCase):
    """The combined links and radios mixin."""

    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()

    def test_combines_both_mixins(self):
        assert issubclass(AdminTablesMixin, ForeignKeyLinkMixin)
        assert issubclass(AdminTablesMixin, ExclusiveRadioFieldsMixin)

    def test_model_admin_gets_links_and_radios(self):
        image_admin = ImageAdmin(Image, admin.site)

        list_display = image_admin.get_list_display(self.request)
        assert list_display[0] == "title"
        assert getattr(list_display[1], "__name__", "") == "album_link"
        assert list_display[2] == "is_primary"

        formset = image_admin.get_changelist_formset(self.request)
        assert isinstance(
            formset.form.base_fields["is_primary"].widget, RadioCheckboxInput
        )

    def test_model_admin_keeps_list_editable_fields_as_fields(self):
        class Admin(ImageAdmin):
            list_display_foreign_key_links = ("album", "is_primary")

        assert (
            Admin(Image, admin.site).get_list_display(self.request)[2] == "is_primary"
        )

    def test_inline_gets_radios(self):
        inline = ImageInline(Album, admin.site)

        assert isinstance(inline, admin.TabularInline)
        formset = inline.get_formset(self.request)
        assert isinstance(
            formset.form.base_fields["is_primary"].widget, RadioCheckboxInput
        )
