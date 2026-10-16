"""Extras for the Django admin's tables: changelists and inlines."""

from .columns import HideableColumnsMixin
from .fk_links import ForeignKeyLinkMixin
from .footer import FooterRowsMixin
from .mixins import AdminTablesMixin
from .radio_select import ExclusiveRadioFieldsMixin
from .row_actions import RowActionsMixin, row_action
from .unsaved import UnsavedChangesMixin

__all__ = [
    "AdminTablesMixin",
    "ExclusiveRadioFieldsMixin",
    "FooterRowsMixin",
    "ForeignKeyLinkMixin",
    "HideableColumnsMixin",
    "RowActionsMixin",
    "UnsavedChangesMixin",
    "row_action",
]

__version__ = "0.1.0"
