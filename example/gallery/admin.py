from django.contrib import admin
from django.db.models import Count, Q

from django_admin_tables import AdminTablesMixin, row_action

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
    row_actions = ["toggle_featured", "delete"]

    @row_action(permissions=["change"])
    def toggle_featured(self, request, obj):
        obj.is_featured = not obj.is_featured
        obj.save(update_fields=["is_featured"])
        self.message_user(
            request,
            f"“{obj}” is featured now."
            if obj.is_featured
            else f"“{obj}” isn't featured now.",
        )

    def get_toggle_featured_label(self, obj):
        return "Unfeature" if obj.is_featured else "Feature"


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
class AlbumStackedAdmin(AdminTablesMixin, admin.ModelAdmin):
    inlines = [ImageStackedInline]
    # Its changelist's fields save themselves as they change: no "Save".
    list_display = ("id", "title", "is_featured")
    list_editable = ("title", "is_featured")
    list_editable_autosave = True


@admin.register(Image)
class ImageAdmin(AdminTablesMixin, admin.ModelAdmin):
    """Each image's album, as a link to the album's change view."""

    list_display = ("title", "album", "is_primary", "is_featured")
    # The search box suggests images as one types; choosing one opens it.
    search_fields = ("title", "album__title")
    search_suggestions = True
    list_display_foreign_key_links = ("album",)
    list_display_hideable = ("album", "is_primary", "is_featured")
    list_display_hidden = ("is_featured",)
    responsive_columns = {"album": "md"}
    row_actions = ["view", "toggle_featured", "delete"]
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

    # An album's primary image can't be selected for an action (deleted,
    # say): choose another one first.
    def is_row_selectable(self, request, obj):
        return not obj.is_primary

    def get_row_unselectable_reason(self, request, obj):
        return "The album's primary image: choose another one first."

    def filter_selectable_rows(self, request, queryset):
        return queryset.filter(is_primary=False)

    @row_action(permissions=["change"])
    def toggle_featured(self, request, obj):
        obj.is_featured = not obj.is_featured
        obj.save(update_fields=["is_featured"])
        self.message_user(
            request,
            f"“{obj}” is featured now."
            if obj.is_featured
            else f"“{obj}” isn't featured now.",
        )

    def get_toggle_featured_label(self, obj):
        return "Unfeature" if obj.is_featured else "Feature"
