from __future__ import annotations

from django.contrib.admin.options import BaseModelAdmin
from django.forms import Media


class UnsavedChangesMixin(BaseModelAdmin):
    """``ModelAdmin`` mixin warning before the changelist's unsaved
    ``list_editable`` changes are lost: leaving the page by its page links,
    filters, sorting, search, or any other way, asks first (the browser's
    own "Leave site?" prompt). Saving the changelist, or running an action
    on it, doesn't."""

    #: ``False`` to leave without asking.
    list_editable_unsaved_warning = True

    @property
    def media(self) -> Media:
        media = super().media
        if self.list_editable_unsaved_warning and getattr(self, "list_editable", None):
            media += Media(js=["django_admin_tables/unsaved-changes.js"])
        return media
