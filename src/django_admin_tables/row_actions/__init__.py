"""Buttons on each row of a changelist or an inline."""

from .actions import RowActionSpec, row_action
from .mixins import RowActionsMixin

__all__ = ["RowActionSpec", "RowActionsMixin", "row_action"]
