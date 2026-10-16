# django-admin-rows

[![Python tests](https://github.com/rodolvbg/django-admin-rows/actions/workflows/pytest.yml/badge.svg)](https://github.com/rodolvbg/django-admin-rows/actions/workflows/pytest.yml)
[![JavaScript tests](https://github.com/rodolvbg/django-admin-rows/actions/workflows/js-tests.yml/badge.svg)](https://github.com/rodolvbg/django-admin-rows/actions/workflows/js-tests.yml)
[![Current version on PyPI](https://img.shields.io/pypi/v/django-admin-rows.svg)](https://pypi.org/project/django-admin-rows/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/django-admin-rows)](https://pypi.org/project/django-admin-rows/)
[![PyPI - Django Version](https://img.shields.io/pypi/djversions/django-admin-rows)](https://pypi.org/project/django-admin-rows/)
[![Downloads](https://static.pepy.tech/personalized-badge/django-admin-rows?period=month&units=international_system&left_color=black&right_color=blue&left_text=Downloads/month)](https://pepy.tech/project/django-admin-rows)

Row-level extras for the Django admin, on changelists and inlines:

- **[Exclusive radio fields](#exclusive-radio-fields)** — a `BooleanField`
  column where only one row can be true, shown as radio buttons.
- **[Foreign key links](#foreign-key-links)** — foreign keys in
  `list_display` as links to their change view.

It brings together, and replaces,
[django-admin-radio-select](https://pypi.org/project/django-admin-radio-select/)
and [django-admin-fk-links](https://pypi.org/project/django-admin-fk-links/)
— see [Migrating](#migrating-from-django-admin-radio-select-or-django-admin-fk-links).

## Install

```bash
uv add django-admin-rows
# or
pip install django-admin-rows
```

Add it to `INSTALLED_APPS` (so `django.contrib.staticfiles` finds the
exclusive radio fields' JS):

```python
INSTALLED_APPS = [
    ...,
    "django_admin_rows",
]
```

## Exclusive radio fields

An inline `BooleanField` column renders as independent checkboxes:

```text
Image A    [ ]
Image B    [x]
Image C    [ ]
```

Nothing stops you from checking more than one — but often only one row
should ever be true (the primary image, the default address, the featured
item). `ExclusiveRadioFieldsMixin` renders that column as radio buttons
instead:

```text
Image A    ( )
Image B    (•)
Image C    ( )
```

Selecting one clears the others, with a small vanilla JS module. Every row
still POSTs under its own Django-generated field name (`images-0-is_primary`,
`images-1-is_primary`…), and a formset-level check on the server rejects a
handcrafted POST setting more than one row true, so the guarantee doesn't
depend on JavaScript running.

Inline formset, before and after clicking a different row's radio — note
`is_primary` switches from "Snowy Peak" to "Frozen Lake" while the
independent `is_featured` column ("Cabin") is untouched:

![Inline radio-select columns](docs/screenshots/inline-radio-select.png)
![Inline radio-select columns after clicking a different row](docs/screenshots/inline-radio-select-after-click.png)

```python
from django.contrib import admin
from django_admin_rows import ExclusiveRadioFieldsMixin

from .models import Album, Image


class ImageInline(ExclusiveRadioFieldsMixin, admin.TabularInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary",)


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    inlines = [ImageInline]
```

It works the same way with `StackedInline`, and several fields are
independent groups:

```python
class ImageInline(ExclusiveRadioFieldsMixin, admin.StackedInline):
    model = Image
    radio_select_exclusive_fields = ("is_primary", "is_featured")
```

Compute the field list per request (and, for an inline or a change form,
per object) instead of the class attribute:

```python
class ImageInline(ExclusiveRadioFieldsMixin, admin.TabularInline):
    model = Image

    def get_radio_select_exclusive_fields(self, request, obj=None):
        return ("is_primary",) if request.user.is_superuser else ()
```

Whatever `get_radio_select_exclusive_fields` returns is filtered against
`get_readonly_fields(request, obj)`: a readonly field isn't an editable
widget, so there's nothing to turn into a radio button — which matters for
a field that's only readonly for some requests.

Each configured name must be a `BooleanField` present on the **form** —
anything else raises `ImproperlyConfigured` when the admin builds the
formset. Only the form is inspected: a field declared on a custom form
(not on the model), or a form field overriding the model field's type,
works the same.

### On the changelist (`list_editable`)

The same mixin works on a `ModelAdmin`, for a `BooleanField` column made
editable in the changelist with `list_editable` (the field must be in
`list_display` too, as Django requires):

```python
@admin.register(Album)
class AlbumAdmin(ExclusiveRadioFieldsMixin, admin.ModelAdmin):
    list_display = ("title", "is_featured")
    list_editable = ("is_featured",)
    radio_select_exclusive_fields = ("is_featured",)
```

Only one `Album` in the whole changelist can be featured at a time — same
client-side sync, same server-side check on save:

![Changelist radio-select column](docs/screenshots/changelist-radio-select.png)

## Foreign key links

`ForeignKeyLinkMixin` turns the foreign keys you list into links to the
related object's change view:

```python
from django.contrib import admin
from django_admin_rows import ForeignKeyLinkMixin


@admin.register(Book)
class BookAdmin(ForeignKeyLinkMixin, admin.ModelAdmin):
    list_display = ("title", "author")
    list_display_foreign_key_links = ("author",)
```

**Before** — `author` as plain text:

![Book changelist without the mixin](docs/screenshots/fk-links-changelist-before.png)

**After** — `author` as a link to its change view:

![Book changelist with the mixin](docs/screenshots/fk-links-changelist.png)

The listed fields keep their column's header and sorting, and the links
point at the change view of the `AdminSite` the `ModelAdmin` belongs to
(custom sites included). Override `get_list_display_foreign_key_links(request)`
to choose them per request.

### Customizing the link

Override `get_foreign_key_link()` to change the markup — return safe HTML
(`format_html()`), since the admin escapes plain strings:

```python
from django.utils.html import format_html


class BookAdmin(ForeignKeyLinkMixin, admin.ModelAdmin):
    list_display = ("title", "author")
    list_display_foreign_key_links = ("author",)

    def get_foreign_key_link(self, obj, field_name, related, url):
        return format_html('<a class="button" target="_blank" href="{}">{}</a>', url, related)
```

Or render it from a template, with `obj`, `related`, `url`, `field_name`
and `link_class` in its context:

```python
class BookAdmin(ForeignKeyLinkMixin, admin.ModelAdmin):
    list_display = ("title", "author")
    list_display_foreign_key_links = ("author",)
    foreign_key_link_template = "admin/book_author_link.html"
```

```django
{# templates/admin/book_author_link.html #}
<a class="fk-link" href="{{ url }}" title="{{ obj }}">{{ related }}</a>
```

To only add a CSS class, set `foreign_key_link_class = "my-link"`.

## Themes

- [django-unfold](docs/themes/unfold.md): works as it is, with Unfold's
  radios and link colors.

## Migrating from django-admin-radio-select or django-admin-fk-links

Replace the package and the imports; the classes, options and behavior are
the same:

| Before | After |
|---|---|
| `pip install django-admin-radio-select` / `django-admin-fk-links` | `pip install django-admin-rows` |
| `"django_admin_radio_select"` in `INSTALLED_APPS` | `"django_admin_rows"` |
| `from django_admin_radio_select import ExclusiveRadioFieldsMixin` | `from django_admin_rows import ExclusiveRadioFieldsMixin` |
| `from django_admin_fk_links import ForeignKeyLinkMixin` | `from django_admin_rows import ForeignKeyLinkMixin` |
| `django_admin_radio_select.widgets` / `.formsets` / `.mixins` | `django_admin_rows.radio_select.widgets` / `.formsets` / `.mixins` |
| `django_admin_fk_links.admin_mixins` | `django_admin_rows.fk_links.mixins` |

Their last releases depend on django-admin-rows and keep the old imports
working, with a `DeprecationWarning`. django-admin-fk-links didn't need
`INSTALLED_APPS`; django-admin-rows does, for the radios' JS. Its floor is
Django 4.2 and Python 3.10 (django-admin-fk-links declared Django 2.2+).

## Supported versions

Django 4.2 – 6.1, Python 3.10+.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, running the example
project, and the test/lint/type-check commands.
