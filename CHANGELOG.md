# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-10-28

### Removed

- `SearchSuggestionsMixin` and its `search_suggestions*` options (also out
  of `AdminTablesMixin`): they're their own package now,
  [django-admin-suggest](https://github.com/rodolvbg/django-admin-suggest),
  with the same options — `SearchSuggestionsMixin` from
  `django_admin_suggest`, and `"django_admin_suggest"` in
  `INSTALLED_APPS`.

## [0.1.2] - 2026-10-28

### Added

- `search_suggestions_add`: when the search box's suggestions find nothing,
  their last option adds it — the add page, with what was typed in a field
  (the first of `search_fields` of the model, or the one named). Only for
  those who may add; `get_search_suggestion_add_url()` to change it.
  Spanish translation of its text.

## [0.1.1] - 2026-10-24

### Added

- `ListEditableAutosaveMixin` (also in `AdminTablesMixin`, with
  `list_editable_autosave`): `list_editable` fields that save themselves as
  they change, one row and one field at a time, through the changelist's
  form, permissions and `save_model()`; what someone else changed meanwhile
  isn't overwritten. With every editable field saving itself, no "Save"
  button. Spanish translation of its texts.
- `SelectableRowsMixin` (also in `AdminTablesMixin`): which rows of the
  changelist can be selected for an action, with `is_row_selectable()`,
  `get_row_unselectable_reason()` and `filter_selectable_rows()`. Their
  checkboxes are disabled, "select all" and the counter leave them out,
  and actions never get them, "Select all" across pages included. It costs
  nothing unless used, and then one query per action.
- `SearchSuggestionsMixin` (also in `AdminTablesMixin`, with
  `search_suggestions = True`): the changelist's search box suggests the
  objects its search finds as one types, and choosing one opens its change
  page. One query per suggestion request; `get_search_suggestions()`,
  `get_search_suggestion_label()` and `get_search_suggestion_url()` to
  customize it. Its suggestions look like the admin's autocomplete fields
  (Select2's dropdown, in Django's admin and in Unfold). Spanish translation
  of its texts.

## [0.1.0] - 2026-10-17

First release.

### Added

- `ExclusiveRadioFieldsMixin` (`django_admin_tables.radio_select`):
  `BooleanField` columns shown as radio
  buttons, exclusive across the rows of an inline or of the changelist's
  `list_editable`, checked on the server too.
- `ForeignKeyLinkMixin` (`django_admin_tables.fk_links`): foreign keys in
  `list_display` as links to their change view, with
  `get_foreign_key_link()`, `foreign_key_link_template` and
  `foreign_key_link_class`.
- `HideableColumnsMixin` (`django_admin_tables.columns`): a "Columns" menu
  on the changelist to hide or show the columns in `list_display_hideable`
  (`list_display_hidden` start hidden), remembered per user and model in
  the browser. System checks `django_admin_tables.E001` and `E002`.
- `responsive_columns` (same mixin): columns hidden below a viewport width
  (`"sm"`…`"2xl"` or pixels), with CSS media queries, on the changelist
  and in tabular inlines; disabled in the "Columns" menu while hidden.
  System checks `django_admin_tables.E003` and `E004`.
- `FooterRowsMixin`: rows of totals, averages… (`footer_rows`) below the
  columns of the changelist and of inlines, as the table's own `<tfoot>`
  (a summary line on stacked inlines). Aggregates run in one query, on
  the filtered rows (`footer_scope = "filtered"`, every page) or the page
  shown (`"page"`). On django-admin-inline-controls' inlines they follow
  its filters, paging and refreshes, without depending on it. System
  checks `django_admin_tables.E005` to
  `E007`.
- `RowActionsMixin`: buttons on each row (`row_actions`), on the
  changelist (an "Actions" column) and in inlines, with `"view"` and
  `"delete"` built in, `@row_action` for permissions, labels and
  confirmations, and per-row hooks. Each one posts to the `ModelAdmin`
  (`<pk>/row-action/<action>/`) and comes back to the page; on
  django-admin-inline-controls' inlines only the inline is refreshed,
  without depending on it. System checks `django_admin_tables.E008` and
  `E009`.
- `UnsavedChangesMixin`: a changelist with `list_editable` asks before
  its unsaved edits are lost (pages, filters, sorting, search…), but not
  when it's saved or an action runs (`list_editable_unsaved_warning`).
- Hideable and responsive columns and row actions work under a strict
  Content Security Policy: no inline `<style>` nor script.
- `AdminTablesMixin`: every extra in one mixin, on a `ModelAdmin`, a
  `TabularInline` or a `StackedInline`, each off until its option is set.
- django-unfold support: Unfold's radio and checkbox classes, link colors,
  and the "Columns" menu next to its "Filters" button.
- Spanish translation.
- Django 4.2 – 6.1, Python 3.10+.
