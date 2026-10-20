import json
from unittest import mock

from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.contrib.messages.storage.cookie import CookieStorage
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from gallery.admin import AlbumAdmin, ImageAdmin, ImageTabularInline
from gallery.models import Album, Image
from unittest_parametrize import ParametrizedTestCase, parametrize

from django_admin_tables import RowActionsMixin, row_action
from django_admin_tables.row_actions.actions import (
    RowActionSpec,
    delete,
    row_action_spec,
    run_row_action,
    view,
)

INSTALLED = "django_admin_tables.row_actions.mixins.apps.is_installed"


def get(user, **attrs):
    request = RequestFactory().get("/")
    request.user = user
    request._messages = CookieStorage(request)
    for name, value in attrs.items():
        setattr(request, name, value)
    return request


def action_url(obj, action):
    return reverse("admin:gallery_image_row_action", args=[obj.pk, action])


def inline_url(album, row, action, inline=0):
    return reverse(
        "admin:gallery_album_inline_row_action",
        args=[album.pk, inline, row.pk, action],
    )


class TestSpecs(ParametrizedTestCase, TestCase):
    """Building and running the row action specs."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        # Staff that may only view images and albums.
        cls.viewer = User.objects.create_user("viewer", password="password")
        cls.viewer.is_staff = True
        cls.viewer.save()
        cls.viewer.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_image", "view_album"])
        )
        cls.album = Album.objects.create(title="Alps")
        cls.peak = Image.objects.create(album=cls.album, title="Peak", is_primary=True)
        Image.objects.create(album=cls.album, title="Lake")

    def setUp(self):
        self.client.force_login(self.user)

    def test_label_css_attrs_and_confirmation(self):
        @row_action(
            description="Publish %(object)s",
            confirmation="Publish “%(object)s” (%(verbose_name)s)?",
        )
        def publish(model_admin, request, obj):
            pass

        publish.css_classes = "danger"
        publish.attribute_properties = {"title": "Go"}
        image_admin = ImageAdmin(Image, admin.site)

        spec = row_action_spec(image_admin, "publish", publish, self.peak)

        assert spec.label == "Publish Peak"
        assert spec.css_classes == "danger"
        assert spec.attrs == 'title="Go"'
        assert spec.confirmation == "Publish “Peak” (image)?"
        assert spec.url is None

    def test_hooks_per_row(self):
        def publish(model_admin, request, obj):
            pass

        class Admin(RowActionsMixin, admin.ModelAdmin):
            def get_publish_label(self, obj):
                return f"Publish {obj}!"

            def get_publish_css(self, obj):
                return "big"

            def get_publish_attrs(self, obj):
                return 'data-x="1"'

        spec = row_action_spec(Admin(Image, admin.site), "publish", publish, self.peak)

        assert (spec.label, spec.css_classes, spec.attrs) == (
            "Publish Peak!",
            "big",
            'data-x="1"',
        )

    def test_label_from_the_name(self):
        def mark_as_seen(model_admin, request, obj):
            pass

        spec = row_action_spec(
            ImageAdmin(Image, admin.site), "mark_as_seen", mark_as_seen, self.peak
        )
        assert spec.label == "Mark as seen"

    def test_view_is_a_link(self):
        spec = row_action_spec(ImageAdmin(Image, admin.site), "view", view, self.peak)
        assert spec.url == reverse("admin:gallery_image_change", args=[self.peak.pk])

    def test_a_link_from_its_hook(self):
        @row_action(link=True, description="Site")
        def site(model_admin, request, obj):
            pass

        class Admin(RowActionsMixin, admin.ModelAdmin):
            def get_site_url(self, obj):
                return f"/images/{obj.pk}/"

        spec = row_action_spec(Admin(Image, admin.site), "site", site, self.peak)
        assert spec.url == f"/images/{self.peak.pk}/"

    def test_permissions_and_links_without_a_url(self):
        @row_action(link=True)
        def nowhere(model_admin, request, obj):
            pass

        class Admin(RowActionsMixin, admin.ModelAdmin):
            row_actions = ["view", "toggle", "delete", nowhere, "custom"]

            @row_action(permissions=["change"])
            def toggle(self, request, obj):
                pass

            @row_action(permissions=["publish"])
            def custom(self, request, queryset):
                pass

            def has_publish_permission(self, request):
                return request.user.is_superuser

        image_admin = Admin(Image, admin.site)

        assert list(image_admin.get_row_action_specs(get(self.user), self.peak)) == [
            "view",
            "toggle",
            "delete",
            "custom",
        ]
        assert list(image_admin.get_row_action_specs(get(self.viewer), self.peak)) == [
            "view"
        ]
        assert image_admin.get_row_action_specs(get(self.user), None) == {}
        assert image_admin.get_row_action_specs(get(self.user), Image()) == {}

    @parametrize(
        ("kind", "expected"),
        [
            ("one", lambda admin_, peak, album: [("one", peak)]),
            ("with_parent", lambda admin_, peak, album: [("with_parent", peak, album)]),
            ("many", lambda admin_, peak, album: [("many", [peak])]),
            ("plain", lambda admin_, peak, album: [("plain", admin_, peak)]),
            ("bound", lambda admin_, peak, album: [("one", peak)]),
        ],
        ids=["one", "with_parent", "many", "plain", "bound"],
    )
    def test_run_each_form(self, kind, expected):
        calls = []

        class Admin(RowActionsMixin, admin.ModelAdmin):
            def one(self, request, obj):
                calls.append(("one", obj))

            def with_parent(self, request, obj, parent_obj=None):
                calls.append(("with_parent", obj, parent_obj))

            def many(self, request, queryset):
                calls.append(("many", list(queryset)))

        def plain(model_admin, request, obj):
            calls.append(("plain", model_admin, obj))

        image_admin = Admin(Image, admin.site)
        function = {
            "one": Admin.one,
            "with_parent": Admin.with_parent,
            "many": Admin.many,
            "plain": plain,
            "bound": image_admin.one,
        }[kind]
        spec = RowActionSpec(kind, function, kind, "", "", None)

        run_row_action(image_admin, get(self.user), spec, self.peak, self.album)

        assert calls == expected(image_admin, self.peak, self.album)


class TestChangelist(TestCase):
    """Row actions on the changelist."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        # Staff that may only view images and albums.
        cls.viewer = User.objects.create_user("viewer", password="password")
        cls.viewer.is_staff = True
        cls.viewer.save()
        cls.viewer.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_image", "view_album"])
        )
        cls.album = Album.objects.create(title="Alps")
        cls.peak = Image.objects.create(album=cls.album, title="Peak", is_primary=True)
        Image.objects.create(album=cls.album, title="Lake")

    def setUp(self):
        self.client.force_login(self.user)

    def test_column_with_the_buttons(self):
        response = self.client.get(reverse("admin:gallery_image_changelist"))

        content = response.content.decode()
        assert 'class="column-row_actions"' in content
        assert (
            f'href="{reverse("admin:gallery_image_change", args=[self.peak.pk])}"'
            in content
        )
        url = action_url(self.peak, "toggle_featured")
        assert f'data-django-admin-tables-row-action="{url}"' in content
        assert 'data-confirmation="Delete “Peak”? This cannot be undone."' in content
        assert ">Feature</button>" in content
        assert "django_admin_tables/row-actions.js" in content

    def test_placed_where_listed(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            list_display = ("row_actions", "title")
            row_actions = ["view"]

        list_display = Admin(Image, admin.site).get_list_display(get(self.user))

        assert getattr(list_display[0], "__name__", "") == "row_actions"
        assert list_display[1] == "title"

    def test_no_column_without_actions(self):
        response = self.client.get(reverse("admin:gallery_album_changelist"))
        assert "column-row_actions" not in response.content.decode()
        assert "row-actions.js" not in response.content.decode()

    def test_run_and_go_back(self):
        back = reverse("admin:gallery_image_changelist") + "?q=Peak"

        response = self.client.post(
            action_url(self.peak, "toggle_featured"), {"next": back}, follow=True
        )

        assert response.redirect_chain == [(back, 302)]
        self.peak.refresh_from_db()
        assert self.peak.is_featured
        assert [str(m) for m in response.context["messages"]] == [
            "“Peak” is featured now."
        ]

    def test_unsafe_next_goes_to_the_changelist(self):
        response = self.client.post(
            action_url(self.peak, "toggle_featured"), {"next": "https://evil.example/"}
        )
        assert response.url == reverse("admin:gallery_image_changelist")

    def test_ajax_gets_the_outcome(self):
        response = self.client.post(
            action_url(self.peak, "toggle_featured"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        assert json.loads(response.content) == {
            "status": "done",
            "message": "“Peak” is featured now.",
        }

    def test_ajax_error_status(self):
        with mock.patch.object(
            Image, "delete", side_effect=ProtectedError("no", [self.peak.album])
        ):
            response = self.client.post(
                action_url(self.peak, "delete"),
                headers={"x-requested-with": "XMLHttpRequest"},
            )
        result = json.loads(response.content)
        assert result["status"] == "error"
        assert "Cannot delete “Peak”: Alps depend on it." == result["message"]

    def test_delete(self):
        self.client.post(action_url(self.peak, "delete"))
        assert not Image.objects.filter(pk=self.peak.pk).exists()

    def test_the_action_own_response(self):
        def export(model_admin, request, queryset):
            return HttpResponse(",".join(obj.title for obj in queryset))

        with mock.patch.object(ImageAdmin, "row_actions", [export]):
            response = self.client.post(action_url(self.peak, "export"))
        assert response.content == b"Peak"

    def test_errors(self):
        assert self.client.post(action_url(self.peak, "nope")).status_code == 400
        # A link isn't run.
        assert self.client.post(action_url(self.peak, "view")).status_code == 400
        missing = reverse("admin:gallery_image_row_action", args=[0, "delete"])
        assert self.client.post(missing).status_code == 404
        assert self.client.get(action_url(self.peak, "delete")).status_code == 405

        self.client.force_login(self.viewer)
        assert self.client.post(action_url(self.peak, "delete")).status_code == 400
        assert Image.objects.filter(pk=self.peak.pk).exists()

    def test_needs_the_view_permission(self):
        user = User.objects.create_user("staff", password="x")
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        assert self.client.post(action_url(self.peak, "delete")).status_code == 403


class TestInline(TestCase):
    """Row actions on inlines."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        # Staff that may only view images and albums.
        cls.viewer = User.objects.create_user("viewer", password="password")
        cls.viewer.is_staff = True
        cls.viewer.save()
        cls.viewer.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_image", "view_album"])
        )
        cls.album = Album.objects.create(title="Alps")
        cls.peak = Image.objects.create(album=cls.album, title="Peak", is_primary=True)
        Image.objects.create(album=cls.album, title="Lake")

    def setUp(self):
        self.client.force_login(self.user)

    def test_column_in_the_change_view(self):
        response = self.client.get(
            reverse("admin:gallery_album_change", args=[self.album.pk])
        )

        content = response.content.decode()
        url = inline_url(self.album, self.peak, "toggle_featured")
        assert f'data-django-admin-tables-row-action="{url}"' in content
        assert "row-actions.js" in content

    def test_not_in_the_add_view(self):
        response = self.client.get(reverse("admin:gallery_album_add"))
        assert "django-admin-tables-row-actions" not in response.content.decode()

    def test_run_and_go_back(self):
        change = reverse("admin:gallery_album_change", args=[self.album.pk])

        response = self.client.post(
            inline_url(self.album, self.peak, "toggle_featured")
        )

        assert response.url == change
        self.peak.refresh_from_db()
        assert self.peak.is_featured

    def test_delete_is_logged_on_the_parent(self):
        self.client.post(inline_url(self.album, self.peak, "delete"))

        assert not Image.objects.filter(pk=self.peak.pk).exists()
        entry = LogEntry.objects.get()
        assert entry.object_id == str(self.album.pk)
        assert "Peak" in entry.get_change_message()

    def test_errors(self):
        other = Album.objects.create(title="Other")
        stranger = Image.objects.create(album=other, title="Stranger")
        assert (
            self.client.post(inline_url(self.album, stranger, "delete")).status_code
            == 400
        )
        assert (
            self.client.post(
                inline_url(self.album, self.peak, "delete", inline=5)
            ).status_code
            == 404
        )
        missing = reverse(
            "admin:gallery_album_inline_row_action", args=[0, 0, self.peak.pk, "delete"]
        )
        assert self.client.post(missing).status_code == 404

    def test_inline_without_row_actions(self):
        class Plain(admin.TabularInline):
            model = Image

        with mock.patch.object(AlbumAdmin, "inlines", [Plain]):
            response = self.client.post(inline_url(self.album, self.peak, "delete"))
        assert response.status_code == 404

    def test_needs_the_view_permission(self):
        user = User.objects.create_user("staff", password="x")
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        assert (
            self.client.post(inline_url(self.album, self.peak, "delete")).status_code
            == 403
        )

    def test_render_without_its_request(self):
        inline = ImageTabularInline(Album, admin.site)
        assert inline.render_row_actions(self.peak) == ""

    def test_parent_admin_without_the_mixin(self):
        site = admin.AdminSite(name="plain")
        site.register(Album, admin.ModelAdmin, inlines=[ImageTabularInline])
        inline = ImageTabularInline(Album, site)
        inline.get_formset(get(self.user), self.album)
        assert inline.render_row_actions(self.peak) == ""

        errors = inline.check()
        assert [e.id for e in errors] == ["django_admin_tables.E009"]

    def test_fieldsets(self):
        class Inline(RowActionsMixin, admin.StackedInline):
            model = Image
            fieldsets = [(None, {"fields": ["title"]})]
            row_actions = ["delete"]

        inline = Inline(Album, admin.site)
        request = get(self.user)
        assert inline.get_fieldsets(request, self.album) == [
            (None, {"fields": ["title", "render_row_actions"]})
        ]
        assert "render_row_actions" in inline.get_readonly_fields(request, self.album)
        assert inline.get_fieldsets(request, None) == [(None, {"fields": ["title"]})]

    def test_message_user(self):
        inline = ImageTabularInline(Album, admin.site)
        request = get(self.user)
        inline.message_user(request, "Hi", messages.WARNING)
        assert [(m.level, str(m)) for m in request._messages] == [
            (messages.WARNING, "Hi")
        ]


class TestMedia(SimpleTestCase):
    """The row actions' assets."""

    def test_only_with_row_actions(self):
        assert "row-actions.js" in str(ImageAdmin(Image, admin.site).media)
        assert "row-actions.js" not in str(AlbumAdmin(Album, admin.site).media)

    def test_unfold(self):
        with mock.patch(INSTALLED, side_effect=lambda app: app == "unfold"):
            media = str(ImageAdmin(Image, admin.site).media)
        assert "row-actions-unfold.css" in media

    def test_overridden_get_row_actions(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            def get_row_actions(self, request, obj):
                return ["view"]

        assert Admin(Image, admin.site).has_row_actions


class TestChecks(SimpleTestCase):
    """The mixin's system checks."""

    def test_unknown_action(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            row_actions = ["view", "nope", delete]

        errors = Admin(Image, admin.site).check()
        assert [e.id for e in errors] == ["django_admin_tables.E008"]
        assert "'nope'" in errors[0].msg

    def test_valid(self):
        assert ImageAdmin(Image, admin.site).check() == []
        assert AlbumAdmin(Album, admin.site).check() == []


class TestRowActionsMixin(TestCase):
    """The mixin's edge cases."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        # Staff that may only view images and albums.
        cls.viewer = User.objects.create_user("viewer", password="password")
        cls.viewer.is_staff = True
        cls.viewer.save()
        cls.viewer.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_image", "view_album"])
        )
        cls.album = Album.objects.create(title="Alps")
        cls.peak = Image.objects.create(album=cls.album, title="Peak", is_primary=True)
        Image.objects.create(album=cls.album, title="Lake")

    def setUp(self):
        self.client.force_login(self.user)

    def test_view_without_a_change_view_is_left_out(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            row_actions = ["view"]

        other_site = admin.AdminSite(name="other")
        image_admin = Admin(Image, other_site)

        assert image_admin.get_row_action_specs(get(self.user), self.peak) == {}
        # Run anyway, it goes to its change view (none here).
        assert view(image_admin, get(self.user), self.peak).url == ""

    def test_a_row_without_actions_has_an_empty_cell(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            row_actions = ["delete"]

        cell = Admin(Image, admin.site).render_row_actions_cell(
            get(self.viewer), self.peak, lambda action: "/"
        )
        assert cell == ""

    def test_inline_listing_the_column_itself(self):
        class Inline(RowActionsMixin, admin.TabularInline):
            model = Image
            fields = ["title", "render_row_actions"]
            row_actions = ["delete"]

        inline = Inline(Album, admin.site)
        assert inline.get_fields(get(self.user), self.album) == [
            "title",
            "render_row_actions",
        ]

        # Declared without it: added last.
        Inline.fields = ["title"]
        assert inline.get_fields(get(self.user), self.album) == [
            "title",
            "render_row_actions",
        ]
