from django.contrib import admin
from django.db.models import Count, Q

from django_admin_tables import AdminTablesMixin

from .models import Album, AlbumStacked, Image


class ImageTabularInline(AdminTablesMixin, admin.TabularInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")
    responsive_columns = {"is_featured": "md"}
    footer_rows = [
        (
            "Total",
            {
                "title": Count("pk"),
                "is_primary": Count("pk", filter=Q(is_primary=True)),
                "is_featured": Count("pk", filter=Q(is_featured=True)),
            },
        ),
    ]


class ImageStackedInline(AdminTablesMixin, admin.StackedInline):
    model = Image
    extra = 3
    radio_select_exclusive_fields = ("is_primary", "is_featured")
    footer_rows = [("Total", {"title": Count("pk")})]


@admin.register(Album)
class AlbumAdmin(AdminTablesMixin, admin.ModelAdmin):
    inlines = [ImageTabularInline]
    list_display = ("title", "is_featured")
    list_editable = ("is_featured",)
    radio_select_exclusive_fields = ("is_featured",)


@admin.register(AlbumStacked)
class AlbumStackedAdmin(admin.ModelAdmin):
    inlines = [ImageStackedInline]


@admin.register(Image)
class ImageAdmin(AdminTablesMixin, admin.ModelAdmin):
    """Each image's album, as a link to the album's change view."""

    list_display = ("title", "album", "is_primary", "is_featured")
    list_display_foreign_key_links = ("album",)
    list_display_hideable = ("album", "is_primary", "is_featured")
    list_display_hidden = ("is_featured",)
    responsive_columns = {"album": "md"}
    footer_rows = [
        (
            "Total",
            {
                "title": Count("pk"),
                "is_primary": Count("pk", filter=Q(is_primary=True)),
                "is_featured": Count("pk", filter=Q(is_featured=True)),
            },
        ),
    ]
