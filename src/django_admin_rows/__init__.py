"""Row-level extras for the Django admin: on changelist and inline rows."""

from .fk_links import ForeignKeyLinkMixin
from .mixins import AdminRowsMixin
from .radio_select import ExclusiveRadioFieldsMixin

__all__ = ["AdminRowsMixin", "ExclusiveRadioFieldsMixin", "ForeignKeyLinkMixin"]

__version__ = "0.1.0"
