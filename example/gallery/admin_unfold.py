"""The demo's admin on an Unfold site (see ``example.settings_unfold``)."""

from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.sites import UnfoldAdminSite

from django_admin_tables import AdminTablesMixin

from .models import Album, AlbumStacked, Image

site = UnfoldAdminSite(name="admin")


class ImageTabularInline(AdminTablesMixin, TabularInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")
    responsive_columns = {"is_featured": "md"}


class ImageStackedInline(AdminTablesMixin, StackedInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")


class AlbumAdmin(AdminTablesMixin, ModelAdmin):
    inlines = [ImageTabularInline]
    list_display = ("title", "is_featured")
    list_editable = ("is_featured",)
    radio_select_exclusive_fields = ("is_featured",)


class AlbumStackedAdmin(ModelAdmin):
    inlines = [ImageStackedInline]


site.register(Album, AlbumAdmin)
site.register(AlbumStacked, AlbumStackedAdmin)


class ImageAdmin(AdminTablesMixin, ModelAdmin):
    list_display = ("title", "album", "is_primary", "is_featured")
    list_display_foreign_key_links = ("album",)
    list_display_hideable = ("album", "is_primary", "is_featured")
    list_display_hidden = ("is_featured",)
    responsive_columns = {"album": "md"}


site.register(Image, ImageAdmin)
