"""Foreign keys in ``list_display`` shown as links to their change view."""

from .mixins import UNFOLD_LINK_CLASS, ForeignKeyLinkMixin

__all__ = ["UNFOLD_LINK_CLASS", "ForeignKeyLinkMixin"]
