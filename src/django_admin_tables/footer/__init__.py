"""Totals, averages… below a table's columns: the changelist's, an inline's."""

from .mixins import FooterRowsMixin
from .rows import FOOTER_FILTERED, FOOTER_PAGE

__all__ = ["FOOTER_FILTERED", "FOOTER_PAGE", "FooterRowsMixin"]
