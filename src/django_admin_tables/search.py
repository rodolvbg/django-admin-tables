from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.admin import ModelAdmin
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import quote
from django.core.exceptions import PermissionDenied
from django.forms import Media
from django.http import JsonResponse
from django.urls import NoReverseMatch, path, reverse
from django.utils.translation import gettext

from .base import TableTemplatesMixin

if TYPE_CHECKING:
    from django.contrib.admin.views.main import ChangeList
    from django.db.models import Model, QuerySet
    from django.http import HttpRequest
    from django.urls import URLPattern


class SearchSuggestionsMixin(TableTemplatesMixin):
    """``ModelAdmin`` mixin: the changelist's search box suggests the
    objects it finds as one types, and choosing one opens its change page::

        class BookAdmin(SearchSuggestionsMixin, admin.ModelAdmin):
            search_fields = ("title", "author__name")
            search_suggestions = True

    The suggestions are what the changelist's search would find: its
    ``get_search_results()`` (``search_fields``, their ``^``, ``=`` and
    ``@`` prefixes, and anything that overrides it), on
    ``get_queryset(request)``, in the changelist's order. One query, of
    ``search_suggestions_limit`` objects at most. Enter without choosing one
    searches as always.

    ``get_search_suggestion_label()`` and ``get_search_suggestion_url()``
    say how each one shows and where it leads; ``get_search_suggestions()``
    which they are.
    """

    #: Whether the search box suggests objects.
    search_suggestions = False
    #: How many, at most.
    search_suggestions_limit = 8
    #: The characters typed before it suggests any.
    search_suggestions_min_length = 2

    @property
    def uses_search_suggestions(self) -> bool:
        return bool(self.search_suggestions) and isinstance(self, ModelAdmin)

    def get_search_suggestions(self, request: HttpRequest, term: str) -> QuerySet[Any]:
        """The objects suggested for ``term``: those the changelist's search
        finds, in its order."""
        queryset = self.get_queryset(request)
        found, may_have_duplicates = self.get_search_results(  # type: ignore[attr-defined]
            request, queryset, term
        )
        if may_have_duplicates:
            # As the changelist does: each object once, whatever it joined.
            found = queryset.filter(pk__in=found.values("pk"))
        ordering = self.get_ordering(request)
        if ordering:
            found = found.order_by(*ordering)
        return found[: self.search_suggestions_limit]

    def get_search_suggestion_label(self, request: HttpRequest, obj: Model) -> str:
        """How a suggestion shows: the object, as the admin names it."""
        return str(obj)

    def get_search_suggestion_url(self, request: HttpRequest, obj: Model) -> str | None:
        """Where choosing it leads: its change page (read-only, for those who
        may only view it). None: it isn't suggested."""
        if not self.has_view_or_change_permission(request, obj):
            return None
        opts = self.model._meta
        name = f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_change"
        try:
            return reverse(name, args=(quote(obj.pk),))
        except NoReverseMatch:
            return None

    # The endpoint ------------------------------------------------------------

    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()  # type: ignore[misc]
        if not self.uses_search_suggestions:
            return urls
        opts = self.model._meta
        return [
            path(
                "search-suggestions/",
                self.admin_site.admin_view(self.search_suggestions_view),
                name=f"{opts.app_label}_{opts.model_name}_search_suggestions",
            ),
            *urls,
        ]

    def search_suggestions_view(self, request: HttpRequest) -> JsonResponse:
        """``?q=``: the suggestions, as ``{"results": [{id, text, url}]}``."""
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        term = request.GET.get("q", "").strip()
        if len(term) < self.search_suggestions_min_length or not (
            self.get_search_fields(request)  # type: ignore[attr-defined]
        ):
            return JsonResponse({"results": []})
        results = []
        for obj in self.get_search_suggestions(request, term):
            url = self.get_search_suggestion_url(request, obj)
            if url:
                results.append(
                    {
                        "id": str(obj.pk),
                        "text": self.get_search_suggestion_label(request, obj),
                        "url": url,
                    }
                )
        return JsonResponse({"results": results})

    # The changelist ----------------------------------------------------------

    @property
    def media(self) -> Media:
        media = super().media
        if self.uses_search_suggestions:
            # The look of the admin's autocomplete fields: Select2's (minified
            # unless DEBUG, as the admin's own widgets load it).
            extra = "" if settings.DEBUG else ".min"
            media += Media(
                css={
                    "all": [
                        f"admin/css/vendor/select2/select2{extra}.css",
                        "admin/css/autocomplete.css",
                        "django_admin_tables/search-suggestions.css",
                    ]
                },
                js=["django_admin_tables/search-suggestions.js"],
            )
        return media

    def get_changelist_extras(
        self, request: HttpRequest, cl: ChangeList
    ) -> dict[str, Any]:
        extras = super().get_changelist_extras(request, cl)
        # Not in a popup: there, choosing an object picks it for a field.
        if (
            self.uses_search_suggestions
            and cl.search_fields
            and IS_POPUP_VAR not in request.GET
        ):
            opts = self.model._meta
            extras["search"] = {
                "url": reverse(
                    f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_search_suggestions"
                ),
                "minLength": self.search_suggestions_min_length,
                "texts": {
                    "label": gettext("Suggestions"),
                    "empty": gettext("Nothing found."),
                },
            }
        return extras
