from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.contrib.admin.utils import label_for_field
from django.core import checks
from django.forms import Media
from django.template.defaultfilters import floatformat
from django.utils.safestring import SafeString
from django.utils.text import capfirst

from ..base import TableTemplatesMixin
from ..columns.mixins import column_class, column_name
from .rows import (
    FOOTER_FILTERED,
    FOOTER_PAGE,
    FOOTER_SCOPES,
    FooterRow,
    FooterRows,
    compute_footer_rows,
    empty_footer_rows,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model, QuerySet
    from django.forms.models import BaseInlineFormSet
    from django.http import HttpRequest


class FooterRowsMixin(TableTemplatesMixin):
    """Mixin adding rows of totals, averages… below a table's columns, for a
    ``ModelAdmin`` (its changelist) or an inline::

        class OrderAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("number", "customer", "amount")
            footer_rows = [
                ("Total", {"amount": Sum("amount")}),
                ("Average", {"amount": Avg("amount")}),
            ]

    Each row is a label and ``{column: value}``: an aggregate (``Sum``,
    ``Avg``, ``Count``…), a ``callable(queryset)``, or a constant; every
    aggregate of every row runs in one query. ``footer_scope`` says what is
    added up: ``"filtered"``, every row matching the changelist's filters
    and search, on every page; or ``"page"``, the rows shown. In an inline,
    the rows of its formset (``get_inline_footer_queryset()``).

    The rows are the table's own ``<tfoot>``, rendered by the server, each
    value under its column; the label spans the columns before the first
    value. When a value's column isn't a column of the table (a stacked
    inline, say), they're a summary line below it instead.
    """

    footer_rows: FooterRows = ()
    #: ``"filtered"`` or ``"page"``.
    footer_scope: str = FOOTER_FILTERED
    footer_tfoot_template = "django_admin_tables/tfoot.html"
    footer_summary_template = "django_admin_tables/footer_summary.html"

    def get_footer_rows(
        self, request: HttpRequest, obj: Model | None = None
    ) -> FooterRows:
        """The rows: of the changelist (``obj`` is ``None``), or of an inline
        of ``obj`` (``None`` in the add view)."""
        return self.footer_rows

    def format_footer_value(self, column: str, value: Any) -> Any:
        """Text (or safe HTML) of a footer cell. Override for currencies,
        units, localized numbers…; the default is the plain value, floats and
        decimals rounded to 2 decimals at most (``1234.5``)."""
        if value is None:
            return ""
        if isinstance(value, SafeString):
            return value
        if isinstance(value, float | Decimal):
            return floatformat(value, "-2u")
        return str(value)

    def footer_column_label(self, column: str) -> str:
        try:
            label = label_for_field(column, self.model, self, return_attr=False)
            return str(capfirst(label))
        except AttributeError:
            return column

    def get_changelist_footer_queryset(
        self, request: HttpRequest, cl: ChangeList, scope: str
    ) -> QuerySet[Any]:
        """What the changelist's footer rows add up."""
        if scope == FOOTER_PAGE:
            return cl.queryset.filter(pk__in=[obj.pk for obj in cl.result_list])
        return cl.queryset

    def get_inline_footer_queryset(
        self, request: HttpRequest, formset: BaseInlineFormSet, scope: str
    ) -> QuerySet[Any]:
        """What an inline's footer rows add up: its formset's rows, which are
        every row of the parent object (django-admin-inline-controls narrows
        them to its filters, or its page)."""
        return formset.get_queryset()

    def inline_footer_rows(
        self, request: HttpRequest, obj: Model | None, formset: BaseInlineFormSet
    ) -> list[FooterRow]:
        """An inline's footer rows, computed on its formset's rows."""
        definitions = self.get_footer_rows(request, obj)
        if obj is None:
            return empty_footer_rows(definitions, self.footer_column_label)
        return compute_footer_rows(
            definitions,
            self.get_inline_footer_queryset(request, formset, self.footer_scope),
            self.footer_column_label,
            self.format_footer_value,
        )

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        extras = super().get_changelist_extras(request, cl)
        definitions = self.get_footer_rows(request)
        if definitions:
            css_classes: Mapping[str, str] = {
                column_name(item): column_class(item, index)
                for index, item in enumerate(cl.list_display)
            }
            extras["footer"] = compute_footer_rows(
                definitions,
                self.get_changelist_footer_queryset(request, cl, self.footer_scope),
                self.footer_column_label,
                self.format_footer_value,
                css_classes,
            )
        return extras

    def get_inline_extras(
        self, request: HttpRequest, obj: Model | None
    ) -> dict[str, Any]:
        extras = super().get_inline_extras(request, obj)
        if self.get_footer_rows(request, obj):
            # Computed when the inline renders: it needs the formset.
            extras["footer"] = {"request": request, "obj": obj}
        return extras

    @property
    def media(self) -> Media:
        media = super().media
        if (
            self.footer_rows
            or type(self).get_footer_rows is not FooterRowsMixin.get_footer_rows
        ):
            css = ["django_admin_tables/footer.css"]
            if apps.is_installed("unfold"):
                css.append("django_admin_tables/footer-unfold.css")
            media += Media(css={"all": css})
        return media

    def check(self, **kwargs: Any) -> list[checks.CheckMessage]:
        return [*super().check(**kwargs), *self._check_footer_rows()]

    def _check_footer_rows(self) -> list[checks.CheckMessage]:
        errors: list[checks.CheckMessage] = []
        if self.footer_scope not in FOOTER_SCOPES:
            errors.append(
                checks.Error(
                    f"footer_scope must be one of {', '.join(FOOTER_SCOPES)}, "
                    f"not {self.footer_scope!r}.",
                    obj=self.__class__,
                    id="django_admin_tables.E005",
                )
            )
        for row in self.footer_rows:
            if (
                not isinstance(row, tuple | list)
                or len(row) != 2
                or not hasattr(row[1], "items")
            ):
                errors.append(
                    checks.Error(
                        f"footer_rows: {row!r} isn't a "
                        "(label, {column: value}) pair.",
                        obj=self.__class__,
                        id="django_admin_tables.E006",
                    )
                )
                continue
            list_display = getattr(self, "list_display", None)
            if list_display is None:  # An inline: its columns are its fields.
                continue
            listed = {column_name(item) for item in list_display}
            errors += [
                checks.Error(
                    f"footer_rows: '{column}' isn't in list_display.",
                    obj=self.__class__,
                    id="django_admin_tables.E007",
                )
                for column in row[1]
                if column not in listed
            ]
        return errors
