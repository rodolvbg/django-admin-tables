from django.contrib import admin

from django_admin_rows import ExclusiveRadioFieldsMixin, ForeignKeyLinkMixin

from .models import Album, AlbumStacked, Image


class ImageTabularInline(ExclusiveRadioFieldsMixin, admin.TabularInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")


class ImageStackedInline(ExclusiveRadioFieldsMixin, admin.StackedInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")


@admin.register(Album)
class AlbumAdmin(ExclusiveRadioFieldsMixin, admin.ModelAdmin):
    inlines = [ImageTabularInline]
    list_display = ("title", "is_featured")
    list_editable = ("is_featured",)
    radio_select_exclusive_fields = ("is_featured",)


@admin.register(AlbumStacked)
class AlbumStackedAdmin(admin.ModelAdmin):
    inlines = [ImageStackedInline]


@admin.register(Image)
class ImageAdmin(ForeignKeyLinkMixin, admin.ModelAdmin):
    """Each image's album, as a link to the album's change view."""

    list_display = ("title", "album", "is_primary")
    list_display_foreign_key_links = ("album",)
