import re
from decimal import Decimal
from unittest import mock

from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Max, Q
from django.template import Template, TemplateSyntaxError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.safestring import mark_safe
from gallery.models import Album, Image

from django_admin_tables import FooterRowsMixin
from django_admin_tables.footer.rows import (
    FooterCell,
    FooterRow,
    TfootCell,
    compute_footer_rows,
    empty_footer_rows,
    header_columns,
    layout_tfoot_rows,
    raw_number,
)

INSTALLED = "django_admin_tables.footer.mixins.apps.is_installed"


def get(user, path="/", **params):
    request = RequestFactory().get(path, params)
    request.user = user
    return request


def tfoot(content):
    assert "<tfoot" in content
    return content.split('<tfoot class="django-admin-tables-tfoot">')[1].split(
        "</tfoot>"
    )[0]


def values(html):
    """{data-column: data-value} of the footer cells in ``html``."""
    return dict(re.findall(r'data-column="([^"]+)" data-value="([^"]*)"', html))


class TestRows(TestCase):
    """Footer rows computation and layout."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.alps = Album.objects.create(title="Alps")
        cls.coast = Album.objects.create(title="Coast")
        Image.objects.create(album=cls.alps, title="Peak", is_primary=True)
        Image.objects.create(album=cls.alps, title="Lake", is_featured=True)
        Image.objects.create(album=cls.coast, title="Harbor", is_primary=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_raw_number(self):
        assert raw_number(3) == "3"
        assert raw_number(2.5) == "2.5"
        assert raw_number(Decimal("1234.50")) == "1234.50"
        assert raw_number(True) == ""
        assert raw_number(None) == ""
        assert raw_number("3") == ""

    def test_compute_runs_every_aggregate_in_one_query(self):
        definitions = [
            ("Total", {"title": Count("pk"), "album": lambda qs: qs.count() * 10}),
            ("Max", {"title": Max("title"), "is_primary": "n/a"}),
        ]
        with self.assertNumQueries(2):  # One for the aggregates, one callable.
            rows = compute_footer_rows(
                definitions,
                Image.objects.all(),
                str.upper,
                lambda column, value: f"<{value}>",
                {"album": "album_link"},
            )

        assert rows == [
            FooterRow(
                "Total",
                [
                    FooterCell("title", "TITLE", "<3>", "3"),
                    FooterCell("album", "ALBUM", "<30>", "30", "album_link"),
                ],
            ),
            FooterRow(
                "Max",
                [
                    FooterCell("title", "TITLE", "<Peak>", ""),
                    FooterCell("is_primary", "IS_PRIMARY", "<n/a>", ""),
                ],
            ),
        ]
        assert rows[0].cells[1].css == "album_link"
        assert rows[0].cells[0].css == "title"

    def test_compute_without_aggregates(self):
        with self.assertNumQueries(0):
            rows = compute_footer_rows(
                [("Note", {"title": "-"})], Image.objects.all(), str, lambda c, v: v
            )
        assert rows[0].cells[0].value == "-"

    def test_empty_rows(self):
        rows = empty_footer_rows([("Total", {"title": Count("pk")})], str.title)
        assert rows == [FooterRow("Total", [FooterCell("title", "Title", "")])]

    def test_header_columns(self):
        html = """<table><thead><tr>
            <th class="action-checkbox-column"></th>
            <th class="column-title sortable"></th>
            <th class="column-pk hidden"></th>
            <th colspan="2" class="column-album"></th>
            <th class="column-amount"></th>
        </tr></thead><tbody><tr><th class="column-nope"></th></tr></tbody></table>"""

        assert header_columns(html) == ({"title": 1, "album": 2, "amount": 4}, 5)
        assert header_columns("<table></table>") == ({}, 0)

    def test_layout(self):
        rows = [
            FooterRow(
                "Total",
                [FooterCell("amount", "Amount", "9"), FooterCell("tax", "Tax", "1")],
            ),
            FooterRow("First", [FooterCell("title", "Title", "3")]),
            FooterRow("Nothing", []),
        ]

        laid_out = layout_tfoot_rows(
            rows, {"title": 1, "amount": 2, "x": 3, "tax": 4}, 6
        )

        total, first = laid_out
        # The label spans the columns before the first value.
        assert (total.label_colspan, total.trailing) == (2, 1)
        assert [slot.key for slot in total.cells] == ["0:amount", "", "0:tax"]
        assert total.cells[1] == TfootCell()
        # The first value is in the first named column: the label goes in it.
        assert first.label_colspan == 0
        assert first.cells[0] == TfootCell()
        assert first.cells[1].label_here
        assert first.trailing == 4

    def test_layout_without_a_values_column(self):
        rows = [FooterRow("Total", [FooterCell("gone", "Gone", "1")])]
        assert layout_tfoot_rows(rows, {"title": 0}, 1) is None


class TestChangelist(TestCase):
    """The footer on the changelist."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.alps = Album.objects.create(title="Alps")
        cls.coast = Album.objects.create(title="Coast")
        Image.objects.create(album=cls.alps, title="Peak", is_primary=True)
        Image.objects.create(album=cls.alps, title="Lake", is_featured=True)
        Image.objects.create(album=cls.coast, title="Harbor", is_primary=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_tfoot_under_the_columns(self):
        response = self.client.get(reverse("admin:gallery_image_changelist"))

        content = response.content.decode()
        footer = tfoot(content)
        assert values(footer) == {"title": "3", "is_primary": "2", "is_featured": "1"}
        assert 'class="django-admin-tables-footer-value field-title"' in footer
        # In the results' own table, after its body.
        assert content.index("<tfoot") > content.index('<table id="result_list"')
        assert "django_admin_tables/footer.css" in content

    def test_filtered_scope_follows_the_search_and_filters(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_filter = ("is_primary",)
            list_per_page = 1
            footer_rows = [("Total", {"title": Count("pk")})]

        response = ImageAdmin(Image, admin.site).changelist_view(
            get(self.user, is_primary__exact="1")
        )
        response.render()

        # Two primary images, on two pages: both are counted.
        assert values(tfoot(response.content.decode())) == {"title": "2"}

    def test_page_scope(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_per_page = 2
            footer_rows = [("Total", {"title": Count("pk")})]
            footer_scope = "page"

        response = ImageAdmin(Image, admin.site).changelist_view(get(self.user, p="2"))
        response.render()

        assert values(tfoot(response.content.decode())) == {"title": "1"}

    def test_summary_when_a_column_isnt_in_the_table(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title",)

            def get_footer_rows(self, request, obj=None):
                return [
                    ("Primary", {"is_primary": Count("pk", filter=Q(is_primary=True))})
                ]

        response = ImageAdmin(Image, admin.site).changelist_view(get(self.user))
        response.render()

        content = response.content.decode()
        assert "<tfoot" not in content
        assert 'class="django-admin-tables-footer-summary"' in content
        assert values(content) == {"is_primary": "2"}
        assert (
            '<span class="django-admin-tables-footer-column">Is primary</span>'
            in content
        )

    def test_format_footer_value(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            footer_rows = [
                ("A", {"title": Decimal("1234.567"), "album": None}),
                ("B", {"title": 2.0, "album": mark_safe("<b>x</b>")}),
            ]

        response = ImageAdmin(Image, admin.site).changelist_view(get(self.user))
        response.render()

        footer = tfoot(response.content.decode())
        assert ">1234.57</span>" in footer
        assert ">2</span>" in footer
        assert "<b>x</b>" in footer

    def test_changelist_without_footer_rows_is_untouched(self):
        response = self.client.get(reverse("admin:gallery_album_changelist"))
        assert "<tfoot" not in response.content.decode()
        assert "django_admin_tables_footer" not in response.context_data

    def test_footer_column_label_of_an_unknown_column(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            pass

        image_admin = ImageAdmin(Image, admin.site)
        assert image_admin.footer_column_label("is_primary") == "Is primary"
        assert image_admin.footer_column_label("nope") == "nope"


class TestInline(TestCase):
    """The footer on inlines."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.alps = Album.objects.create(title="Alps")
        cls.coast = Album.objects.create(title="Coast")
        Image.objects.create(album=cls.alps, title="Peak", is_primary=True)
        Image.objects.create(album=cls.alps, title="Lake", is_featured=True)
        Image.objects.create(album=cls.coast, title="Harbor", is_primary=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_tabular_tfoot(self):
        response = self.client.get(
            reverse("admin:gallery_album_change", args=[self.alps.pk])
        )

        content = response.content.decode()
        footer = tfoot(content)
        # The album's own images only.
        assert values(footer) == {"title": "2", "is_primary": "1", "is_featured": "1"}
        assert content.index("<tfoot") > content.index('id="images-group"')

    def test_add_view_keeps_the_structure_without_values(self):
        response = self.client.get(reverse("admin:gallery_album_add"))

        footer = tfoot(response.content.decode())
        assert values(footer) == {"title": "", "is_primary": "", "is_featured": ""}

    def test_stacked_inline_summary(self):
        response = self.client.get(
            reverse("admin:gallery_albumstacked_change", args=[self.alps.pk])
        )

        content = response.content.decode()
        assert "<tfoot" not in content
        summary = content.split('class="django-admin-tables-footer-summary"')[1]
        assert values(summary.split("</div>")[0] + "</div>") == {"title": "2"}

    def test_footer_queryset_hook(self):
        class Inline(FooterRowsMixin, admin.TabularInline):
            model = Image
            footer_rows = [("Total", {"title": Count("pk")})]

            def get_inline_footer_queryset(self, request, formset, scope):
                return formset.get_queryset().filter(is_primary=True)

        inline = Inline(Album, admin.site)
        request = get(self.user)
        formset = inline.get_formset(request, self.alps)(instance=self.alps)

        rows = inline.inline_footer_rows(request, self.alps, formset)

        assert rows[0].cells[0].raw == "1"
        assert inline.template == "django_admin_tables/edit_inline.html"
        assert inline.django_admin_tables_inline["footer"] == {
            "request": request,
            "obj": self.alps,
        }

    def test_inline_without_footer_rows_is_untouched(self):
        class Inline(FooterRowsMixin, admin.TabularInline):
            model = Image

        inline = Inline(Album, admin.site)
        inline.get_formset(get(self.user))
        assert inline.template == "admin/edit_inline/tabular.html"

    def test_inline_with_responsive_columns_only(self):
        """The inline's own template, untouched but for the media queries."""
        from gallery.admin import AlbumAdmin, ImageTabularInline

        class Inline(ImageTabularInline):
            footer_rows = ()

        with mock.patch.object(AlbumAdmin, "inlines", [Inline]):
            response = self.client.get(
                reverse("admin:gallery_album_change", args=[self.alps.pk])
            )

        content = response.content.decode()
        assert "django-admin-tables-responsive-images-group" in content
        assert "<tfoot" not in content
        assert 'id="images-group"' in content


class TestFooterTag(SimpleTestCase):
    """The footer template tag."""

    def test_footer_tag_takes_the_rows(self):
        with self.assertRaisesRegex(TemplateSyntaxError, "takes the footer rows"):
            Template(
                "{% load django_admin_tables %}"
                "{% django_admin_tables_footer %}{% end_django_admin_tables_footer %}"
            )


class TestMedia(SimpleTestCase):
    """The footer's CSS."""

    def test_css_only_with_footer_rows(self):
        class With(FooterRowsMixin, admin.ModelAdmin):
            footer_rows = [("Total", {"title": Count("pk")})]

        class Dynamic(FooterRowsMixin, admin.ModelAdmin):
            def get_footer_rows(self, request, obj=None):
                return ()

        class Without(FooterRowsMixin, admin.ModelAdmin):
            pass

        assert "footer.css" in str(With(Image, admin.site).media)
        assert "footer.css" in str(Dynamic(Image, admin.site).media)
        assert "footer.css" not in str(Without(Image, admin.site).media)

    def test_unfold_css(self):
        class With(FooterRowsMixin, admin.ModelAdmin):
            footer_rows = [("Total", {"title": Count("pk")})]

        with mock.patch(INSTALLED, side_effect=lambda app: app == "unfold"):
            media = str(With(Image, admin.site).media)
        assert "footer-unfold.css" in media


class TestChecks(SimpleTestCase):
    """The mixin's system checks."""

    def test_valid(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            footer_rows = [("Total", {"title": Count("pk")})]
            footer_scope = "page"

        assert ImageAdmin(Image, admin.site).check() == []

    def test_scope(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            footer_scope = "all"

        errors = ImageAdmin(Image, admin.site).check()
        assert [e.id for e in errors] == ["django_admin_tables.E005"]

    def test_row_shape(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            footer_rows = [("Total", "title"), "Total", ("A", {}, "x")]

        errors = ImageAdmin(Image, admin.site).check()
        assert [e.id for e in errors] == ["django_admin_tables.E006"] * 3

    def test_changelist_columns(self):
        class ImageAdmin(FooterRowsMixin, admin.ModelAdmin):
            list_display = ("title",)
            footer_rows = [("Total", {"title": Count("pk"), "album": Count("album")})]

        errors = ImageAdmin(Image, admin.site).check()
        assert [e.id for e in errors] == ["django_admin_tables.E007"]
        assert "'album'" in errors[0].msg

    def test_inline_columns_are_not_checked(self):
        class Inline(FooterRowsMixin, admin.TabularInline):
            model = Image
            footer_rows = [("Total", {"anything": Count("pk")})]

        assert Inline(Album, admin.site).check() == []


class TestWithInlineControls(TestCase):
    """django-admin-inline-controls, recognized by its attributes: no
    dependency either way."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        cls.alps = Album.objects.create(title="Alps")
        cls.coast = Album.objects.create(title="Coast")
        Image.objects.create(album=cls.alps, title="Peak", is_primary=True)
        Image.objects.create(album=cls.alps, title="Lake", is_featured=True)
        Image.objects.create(album=cls.coast, title="Harbor", is_primary=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_querysets_follow_its_filters_and_page(self):
        from types import SimpleNamespace

        class Inline(FooterRowsMixin, admin.TabularInline):
            model = Image

        inline = Inline(Album, admin.site)
        filtered = Image.objects.filter(is_primary=True)
        shown = filtered[:1]
        formset = SimpleNamespace(
            inline_controls=SimpleNamespace(
                filtered_queryset=filtered, shown_queryset=shown
            ),
            get_queryset=Image.objects.all,
        )

        assert inline.get_inline_footer_queryset(None, formset, "filtered") is filtered
        assert inline.get_inline_footer_queryset(None, formset, "page") is shown

        # Its add view: no controls.
        formset.inline_controls = None
        assert inline.get_inline_footer_queryset(None, formset, "filtered").count() == 3

    def test_wraps_the_inline_template_inside_its_wrapper(self):
        class Inline(FooterRowsMixin, admin.TabularInline):
            model = Image
            footer_rows = [("Total", {"title": Count("pk")})]

            def __init__(self, *args, **kwargs):
                # What InlineControlsMixin does.
                super().__init__(*args, **kwargs)
                self.inline_controls_inner_template = self.template
                self.template = "django_admin_inline_controls/inline.html"

        inline = Inline(Album, admin.site)
        inline.get_formset(get(self.user))

        assert inline.template == "django_admin_inline_controls/inline.html"
        assert inline.inline_controls_inner_template == (
            "django_admin_tables/edit_inline.html"
        )
        parent = inline.django_admin_tables_inline["parent"]
        assert parent.template.name == "admin/edit_inline/tabular.html"
