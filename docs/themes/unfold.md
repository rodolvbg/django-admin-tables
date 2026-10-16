# django-admin-rows with django-unfold

## Usage

Works with [django-unfold](https://unfoldadmin.com/) as it is, on its
`ModelAdmin`, `TabularInline` and `StackedInline`. When `unfold` is in
`INSTALLED_APPS`:

- the exclusive radio fields get Unfold's own radio classes, so they look
  like its other radios;
- the foreign key links get its link colors
  (`text-primary-600 dark:text-primary-500`) — Unfold's reset styles links
  like the text around them. Set `foreign_key_link_class` to use other
  classes, or `""` for none.

Both in light and dark mode. Tested with django-unfold 0.108.

```python
from unfold.admin import ModelAdmin, TabularInline
from django_admin_rows import ExclusiveRadioFieldsMixin, ForeignKeyLinkMixin


class ImageInline(ExclusiveRadioFieldsMixin, TabularInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary",)


class ImageAdmin(ForeignKeyLinkMixin, ModelAdmin):
    list_display = ("title", "album")
    list_display_foreign_key_links = ("album",)
```

## Screenshots

An inline with two exclusive columns:

![Exclusive radios in an Unfold inline](unfold/radio-select-inline.png)

A `list_editable` column on the changelist, in dark mode:

![Exclusive radios on an Unfold changelist, dark mode](unfold/radio-select-changelist-dark.png)

Foreign key links on a changelist, light and dark:

![Foreign key links on an Unfold changelist](unfold/fk-links-changelist.png)

![Foreign key links on an Unfold changelist, dark mode](unfold/fk-links-changelist-dark.png)

## Demo

```bash
cd example
DJANGO_SETTINGS_MODULE=example.settings_unfold python manage.py runserver
```
