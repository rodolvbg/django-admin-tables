"""Extras for the Django admin's tables: changelists and inlines."""

from .autosave import ListEditableAutosaveMixin
from .columns import HideableColumnsMixin
from .fk_links import ForeignKeyLinkMixin
from .footer import FooterRowsMixin
from .mixins import AdminTablesMixin
from .radio_select import ExclusiveRadioFieldsMixin
from .row_actions import RowActionsMixin, row_action
from .search import SearchSuggestionsMixin
from .selection import SelectableRowsMixin
from .unsaved import UnsavedChangesMixin

__all__ = [
    "AdminTablesMixin",
    "ExclusiveRadioFieldsMixin",
    "FooterRowsMixin",
    "ForeignKeyLinkMixin",
    "HideableColumnsMixin",
    "ListEditableAutosaveMixin",
    "RowActionsMixin",
    "SearchSuggestionsMixin",
    "SelectableRowsMixin",
    "UnsavedChangesMixin",
    "row_action",
]

__version__ = "0.1.0"
