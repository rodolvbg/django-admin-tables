"""Row-level extras for the Django admin: on changelist and inline rows."""

from .fk_links import ForeignKeyLinkMixin
from .radio_select import ExclusiveRadioFieldsMixin

__all__ = ["ExclusiveRadioFieldsMixin", "ForeignKeyLinkMixin"]

__version__ = "0.1.0"
