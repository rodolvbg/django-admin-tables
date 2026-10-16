import json

import pytest
from django.contrib import admin
from django.test import Client, RequestFactory
from django.urls import reverse
from gallery.models import Album, Image

from django_admin_tables import HideableColumnsMixin
from django_admin_tables.columns.responsive import (
    BREAKPOINTS,
    css_identifier,
    max_width,
    media_rules,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser(django_user_model):
    return django_user_model.objects.create_superuser(
        "admin", "admin@example.com", "password"
    )


@pytest.fixture
def admin_client(superuser):
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def album():
    album = Album.objects.create(title="Holiday")
    Image.objects.create(album=album, title="Beach", is_primary=True)
    return album


def responsive_config(content, table):
    """The JSON columns.js reads for ``table``'s media queries."""
    start = (
        f'<script id="django-admin-tables-responsive-{table}" type="application/json">'
    )
    assert start in content
    return json.loads(content.split(start)[1].split("</script>")[0])


def get(superuser):
    request = RequestFactory().get("/")
    request.user = superuser
    return request


class TestBreakpoints:
    @pytest.mark.parametrize(
        ("breakpoint", "expected"),
        [
            ("sm", 639.98),
            ("md", 767.98),
            ("lg", 1023.98),
            ("2xl", 1535.98),
            (900, 899.98),
        ],
    )
    def test_max_width(self, breakpoint, expected):
        assert max_width(breakpoint) == pytest.approx(expected)

    @pytest.mark.parametrize("breakpoint", ["huge", 0, -10, True, 7.5, None])
    def test_unknown(self, breakpoint):
        with pytest.raises(ValueError, match="Unknown breakpoint"):
            max_width(breakpoint)

    def test_names(self):
        assert list(BREAKPOINTS) == ["sm", "md", "lg", "xl", "2xl"]

    def test_css_identifier(self):
        assert css_identifier("is_primary") == "is_primary"
        assert css_identifier("a.b c") == "a\\.b\\ c"

    def test_media_rules_group_by_width_widest_first(self):
        rules = media_rules(
            {"album": "md", "title": "lg", "pk": "md"},
            [("title", "title"), ("album", "album_link"), ("pk", "pk"), ("x", "x")],
        )

        assert rules == [
            {"max_width": pytest.approx(1023.98), "classes": ["title"]},
            {"max_width": pytest.approx(767.98), "classes": ["album_link", "pk"]},
        ]


class TestChangelist:
    def test_media_queries_for_list_display_columns(self, admin_client, album):
        response = admin_client.get(reverse("admin:gallery_image_changelist"))

        content = response.content.decode()
        assert responsive_config(content, "result_list") == {
            "scope": "#result_list",
            "rules": [{"max_width": 767.98, "classes": ["album_link"]}],
        }
        assert "django_admin_tables/columns.js" in content
        # No <style>: a Content Security Policy needn't allow inline styles.
        assert "<style" not in content

    def test_only_responsive_columns_skip_the_menu(self, superuser, album):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            responsive_columns = {"album": 900}

        response = ImageAdmin(Image, admin.site).changelist_view(get(superuser))
        response.render()

        content = response.content.decode()
        rules = responsive_config(content, "result_list")["rules"]
        assert rules == [{"max_width": 899.98, "classes": ["album"]}]
        assert "django_admin_tables/columns.js" in content
        assert 'id="django-admin-tables-columns"' not in content
        assert "columns.css" not in content

    def test_responsive_columns_can_depend_on_the_request(self, superuser, album):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")

            def get_responsive_columns(self, request, obj=None):
                return {"album": "lg"} if request.user.is_superuser else {}

        response = ImageAdmin(Image, admin.site).changelist_view(get(superuser))

        rules = response.context_data["django_admin_tables_responsive"]
        assert [rule["classes"] for rule in rules] == [["album"]]


class ImageInline(HideableColumnsMixin, admin.TabularInline):
    model = Image
    responsive_columns = {"is_featured": "md", "is_primary": "lg"}


class TestInline:
    def test_media_queries_scoped_to_the_inline(self, admin_client, album):
        response = admin_client.get(
            reverse("admin:gallery_album_change", args=[album.pk])
        )

        content = response.content.decode()
        assert responsive_config(content, "images-group") == {
            "scope": "#images-group",
            "rules": [{"max_width": 767.98, "classes": ["is_featured"]}],
        }
        # The config and the script come first, then the inline's own
        # template: the columns are hidden before it's painted.
        config = content.index("django-admin-tables-responsive-images-group")
        script = content.index("django_admin_tables/columns.js", config)
        assert config < script < content.index('id="images-group"')
        assert 'class="field-is_featured"' in content
        assert "<style" not in content

    def test_template_is_swapped_once(self, superuser):
        inline = ImageInline(Album, admin.site)
        request = get(superuser)

        inline.get_formset(request)
        inline.get_formset(request)

        assert inline.template == "django_admin_tables/edit_inline.html"
        columns = inline.django_admin_tables_inline
        assert columns["parent"].template.name == "admin/edit_inline/tabular.html"
        assert [rule["classes"] for rule in columns["responsive"]] == [
            ["is_primary"],
            ["is_featured"],
        ]

    def test_custom_inline_template_is_included(self, superuser):
        class Inline(ImageInline):
            template = "admin/edit_inline/stacked.html"

        inline = Inline(Album, admin.site)
        inline.get_formset(get(superuser))

        parent = inline.django_admin_tables_inline["parent"]
        assert parent.template.name == "admin/edit_inline/stacked.html"

    def test_inline_without_responsive_columns_is_untouched(self, superuser):
        class Inline(HideableColumnsMixin, admin.TabularInline):
            model = Image

        inline = Inline(Album, admin.site)
        inline.get_formset(get(superuser))

        assert inline.template == "admin/edit_inline/tabular.html"
        assert not hasattr(inline, "django_admin_tables_inline")


class TestChecks:
    def test_valid(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            responsive_columns = {"album": "md", "title": 500}

        assert ImageAdmin(Image, admin.site).check() == []

    def test_unknown_breakpoint(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            responsive_columns = {"album": "tablet"}

        errors = ImageAdmin(Image, admin.site).check()

        assert [e.id for e in errors] == ["django_admin_tables.E003"]
        assert "'tablet'" in errors[0].msg
        assert "sm, md, lg, xl, 2xl" in errors[0].msg

    def test_column_must_be_in_list_display(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title",)
            responsive_columns = {"album": "md"}

        errors = ImageAdmin(Image, admin.site).check()

        assert [e.id for e in errors] == ["django_admin_tables.E004"]

    def test_inline_breakpoints_are_checked(self):
        class Inline(ImageInline):
            responsive_columns = {"is_featured": "phone"}

        errors = Inline(Album, admin.site).check()

        assert [e.id for e in errors] == ["django_admin_tables.E003"]
