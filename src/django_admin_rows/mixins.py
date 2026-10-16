from __future__ import annotations

from .fk_links import ForeignKeyLinkMixin
from .radio_select import ExclusiveRadioFieldsMixin


class AdminRowsMixin(ForeignKeyLinkMixin, ExclusiveRadioFieldsMixin):
    """Every row-level extra in one mixin, for a ``ModelAdmin``,
    ``TabularInline`` or ``StackedInline``::

        class AlbumAdmin(AdminRowsMixin, admin.ModelAdmin):
            list_display = ("title", "owner", "is_featured")
            list_editable = ("is_featured",)
            list_display_foreign_key_links = ("owner",)
            radio_select_exclusive_fields = ("is_featured",)

    Each extra is off until its option is set
    (``list_display_foreign_key_links``, ``radio_select_exclusive_fields``),
    and works as the mixin of its own (``ForeignKeyLinkMixin``,
    ``ExclusiveRadioFieldsMixin``) does. Foreign key links only apply to a
    ``ModelAdmin``'s changelist: an inline has no ``list_display``.
    """
