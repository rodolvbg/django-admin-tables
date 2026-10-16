# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

First release: django-admin-radio-select and django-admin-fk-links,
together, with hideable and responsive columns.

### Added

- `ExclusiveRadioFieldsMixin` (`django_admin_tables.radio_select`), from
  django-admin-radio-select 0.1.2: `BooleanField` columns shown as radio
  buttons, exclusive across the rows of an inline or of the changelist's
  `list_editable`, checked on the server too.
- `ForeignKeyLinkMixin` (`django_admin_tables.fk_links`), from
  django-admin-fk-links 0.1.4: foreign keys in `list_display` as links to
  their change view, with `get_foreign_key_link()`,
  `foreign_key_link_template` and `foreign_key_link_class`. It inherits
  from `BaseModelAdmin` instead of `ModelAdmin`, so it can be combined on
  an inline too: use it before `admin.ModelAdmin` in the bases.
- `HideableColumnsMixin` (`django_admin_tables.columns`): a "Columns" menu
  on the changelist to hide or show the columns in `list_display_hideable`
  (`list_display_hidden` start hidden), remembered per user and model in
  the browser. System checks `django_admin_tables.E001` and `E002`.
- `responsive_columns` (same mixin): columns hidden below a viewport width
  (`"sm"`…`"2xl"` or pixels), with CSS media queries, on the changelist
  and in tabular inlines; disabled in the "Columns" menu while hidden.
  System checks `django_admin_tables.E003` and `E004`.
- Hideable and responsive columns work under a strict Content Security
  Policy: their CSS is set from a script, as constructed stylesheets, with
  no inline `<style>`.
- `AdminTablesMixin`: every extra in one mixin, on a `ModelAdmin`, a
  `TabularInline` or a `StackedInline`, each off until its option is set.
- django-unfold support: Unfold's radio and checkbox classes, link colors,
  and the "Columns" menu next to its "Filters" button.
- Django 4.2 – 6.1, Python 3.10+.
