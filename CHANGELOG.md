# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `AdminRowsMixin`: every row-level extra in one mixin, on a `ModelAdmin`,
  a `TabularInline` or a `StackedInline`. Each extra is off until its
  option is set; foreign key links only apply to a `ModelAdmin`'s
  changelist.

### Changed

- `ForeignKeyLinkMixin` inherits from `BaseModelAdmin` instead of
  `ModelAdmin`, like `ExclusiveRadioFieldsMixin`, so both can be combined
  on an inline. Use it before `admin.ModelAdmin` in the bases, as
  documented: on its own it's no longer a complete `ModelAdmin`.

## [0.1.0] - 2026-10-16

First release: django-admin-radio-select and django-admin-fk-links, together.

### Added

- `ExclusiveRadioFieldsMixin` (`django_admin_rows.radio_select`), from
  django-admin-radio-select 0.1.2: `BooleanField` columns shown as radio
  buttons, exclusive across the rows of an inline or of the changelist's
  `list_editable`, checked on the server too.
- `ForeignKeyLinkMixin` (`django_admin_rows.fk_links`), from
  django-admin-fk-links 0.1.4: foreign keys in `list_display` as links to
  their change view, with `get_foreign_key_link()`,
  `foreign_key_link_template` and `foreign_key_link_class`.
- django-unfold support for both: Unfold's radio classes and link colors.
- Django 4.2 – 6.1, Python 3.10+.
