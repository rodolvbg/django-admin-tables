from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django import template
from django.utils.html import json_script
from django.utils.safestring import mark_safe

from ..footer.rows import header_columns, layout_tfoot_rows

if TYPE_CHECKING:
    from django.template.base import NodeList, Parser, Token
    from django.utils.safestring import SafeString

    from ..footer.rows import FooterRow

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


def with_footer_rows(
    context: template.Context,
    html: str,
    footer_rows: list[FooterRow],
    tfoot_template: str,
    summary_template: str,
) -> SafeString:
    """``html`` with ``footer_rows`` as the ``<tfoot>`` of its (last) table —
    no JS, and no copy of the admin's template to keep in sync — or, when a
    value's column isn't a column of that table, a summary after it."""
    engine = context.template.engine  # type: ignore[union-attr]
    # Last in the table: if it has its own <tfoot> (Unfold's "Add another"),
    # that one stays the table's footer and these rows show above it.
    position = html.rfind("</table>")
    rows = (
        layout_tfoot_rows(footer_rows, *header_columns(html))
        if position != -1
        else None
    )
    if rows is None:
        with context.push(footer_rows=footer_rows):
            summary = engine.get_template(summary_template).render(context)
        # Inside the element that wraps it all (an inline's group), last.
        html = html.rstrip()
        end = len(html) - len("</div>") if html.endswith("</div>") else len(html)
        return mark_safe(html[:end] + summary + html[end:])
    with context.push(tfoot_rows=rows):
        tfoot = engine.get_template(tfoot_template).render(context)
    return mark_safe(html[:position] + tfoot + html[position:])


class FooterRowsNode(template.Node):
    def __init__(self, nodelist: NodeList, footer: template.base.FilterExpression):
        self.nodelist = nodelist
        self.footer = footer

    def render(self, context: template.Context) -> str:
        html = self.nodelist.render(context)
        footer_rows = self.footer.resolve(context, ignore_failures=True)
        model_admin = getattr(context.get("cl"), "model_admin", None)
        if not footer_rows or model_admin is None:
            return html
        return with_footer_rows(
            context,
            html,
            footer_rows,
            model_admin.footer_tfoot_template,
            model_admin.footer_summary_template,
        )


@register.tag("django_admin_tables_footer")
def do_footer_rows(parser: Parser, token: Token) -> FooterRowsNode:
    """``{% django_admin_tables_footer rows %}…{% end_django_admin_tables_footer %}``:
    the changelist's results (the admin's ``result_list`` block) with the
    footer rows in their table."""
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(f"{bits[0]} takes the footer rows.")
    nodelist = parser.parse(("end_django_admin_tables_footer",))
    parser.delete_first_token()
    return FooterRowsNode(nodelist, parser.compile_filter(bits[1]))


@register.simple_tag(takes_context=True)
def django_admin_tables_inline(context: template.Context) -> SafeString:
    """The inline's own template, with its footer rows."""
    formset = context["inline_admin_formset"]
    inline: Any = formset.opts
    extras = inline.django_admin_tables_inline
    # The inline's own template (a backend template's engine template),
    # rendered in this same context, as {% include %} would.
    html = extras["parent"].template.render(context)
    footer = extras.get("footer")
    if not footer:
        return mark_safe(html)
    footer_rows = inline.inline_footer_rows(
        footer["request"], footer["obj"], formset.formset
    )
    return with_footer_rows(
        context,
        html,
        footer_rows,
        inline.footer_tfoot_template,
        inline.footer_summary_template,
    )
