from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.utils.html import json_script

if TYPE_CHECKING:
    from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag
def responsive_columns_config(rules: list[dict[str, object]], scope: str) -> SafeString:
    """The ``responsive_columns`` media queries of the table under ``scope``
    (a CSS selector), as JSON for ``columns.js`` to apply: CSS built by a
    script, unlike a ``<style>`` element, needs no ``'unsafe-inline'`` in a
    Content Security Policy's ``style-src``."""
    return json_script(
        {"scope": scope, "rules": rules},
        f"django-admin-tables-responsive-{scope.lstrip('#')}",
    )
