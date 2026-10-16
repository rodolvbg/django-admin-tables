from __future__ import annotations

from .columns import HideableColumnsMixin
from .fk_links import ForeignKeyLinkMixin
from .footer import FooterRowsMixin
from .radio_select import ExclusiveRadioFieldsMixin


class AdminTablesMixin(
    ForeignKeyLinkMixin,
    HideableColumnsMixin,
    FooterRowsMixin,
    ExclusiveRadioFieldsMixin,
):
    """Every extra in one mixin, for a ``ModelAdmin``, ``TabularInline`` or
    ``StackedInline``::

        class ImageAdmin(AdminTablesMixin, admin.ModelAdmin):
            list_display = ("title", "album", "is_primary")
            list_editable = ("is_primary",)
            list_display_foreign_key_links = ("album",)
            list_display_hideable = ("album",)
            footer_rows = [("Total", {"title": Count("pk")})]
            radio_select_exclusive_fields = ("is_primary",)

    Each extra is off until its option is set
    (``list_display_foreign_key_links``, ``list_display_hideable``,
    ``responsive_columns``, ``footer_rows``, ``radio_select_exclusive_fields``),
    and works as the mixin of its own (``ForeignKeyLinkMixin``,
    ``HideableColumnsMixin``, ``FooterRowsMixin``,
    ``ExclusiveRadioFieldsMixin``) does. Foreign key links and hideable
    columns only apply to a ``ModelAdmin``'s changelist: an inline has no
    ``list_display``.
    """
