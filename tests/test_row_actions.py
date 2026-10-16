import json
from unittest import mock

import pytest
from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.cookie import CookieStorage
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse
from gallery.admin import AlbumAdmin, ImageAdmin, ImageTabularInline
from gallery.models import Album, Image

from django_admin_tables import RowActionsMixin, row_action
from django_admin_tables.row_actions.actions import (
    RowActionSpec,
    delete,
    row_action_spec,
    run_row_action,
    view,
)

pytestmark = pytest.mark.django_db

INSTALLED = "django_admin_tables.row_actions.mixins.apps.is_installed"


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
def viewer(django_user_model):
    """Staff that may only view images and albums."""
    user = django_user_model.objects.create_user("viewer", password="password")
    user.is_staff = True
    user.save()
    user.user_permissions.add(
        *Permission.objects.filter(codename__in=["view_image", "view_album"])
    )
    return user


@pytest.fixture
def album():
    album = Album.objects.create(title="Alps")
    Image.objects.create(album=album, title="Peak", is_primary=True)
    Image.objects.create(album=album, title="Lake")
    return album


@pytest.fixture
def peak(album):
    return album.images.get(title="Peak")


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


class TestSpecs:
    def test_label_css_attrs_and_confirmation(self, peak):
        @row_action(
            description="Publish %(object)s",
            confirmation="Publish “%(object)s” (%(verbose_name)s)?",
        )
        def publish(model_admin, request, obj):
            pass

        publish.css_classes = "danger"
        publish.attribute_properties = {"title": "Go"}
        image_admin = ImageAdmin(Image, admin.site)

        spec = row_action_spec(image_admin, "publish", publish, peak)

        assert spec.label == "Publish Peak"
        assert spec.css_classes == "danger"
        assert spec.attrs == 'title="Go"'
        assert spec.confirmation == "Publish “Peak” (image)?"
        assert spec.url is None

    def test_hooks_per_row(self, peak):
        def publish(model_admin, request, obj):
            pass

        class Admin(RowActionsMixin, admin.ModelAdmin):
            def get_publish_label(self, obj):
                return f"Publish {obj}!"

            def get_publish_css(self, obj):
                return "big"

            def get_publish_attrs(self, obj):
                return 'data-x="1"'

        spec = row_action_spec(Admin(Image, admin.site), "publish", publish, peak)

        assert (spec.label, spec.css_classes, spec.attrs) == (
            "Publish Peak!",
            "big",
            'data-x="1"',
        )

    def test_label_from_the_name(self, peak):
        def mark_as_seen(model_admin, request, obj):
            pass

        spec = row_action_spec(
            ImageAdmin(Image, admin.site), "mark_as_seen", mark_as_seen, peak
        )
        assert spec.label == "Mark as seen"

    def test_view_is_a_link(self, peak):
        spec = row_action_spec(ImageAdmin(Image, admin.site), "view", view, peak)
        assert spec.url == reverse("admin:gallery_image_change", args=[peak.pk])

    def test_a_link_from_its_hook(self, peak):
        @row_action(link=True, description="Site")
        def site(model_admin, request, obj):
            pass

        class Admin(RowActionsMixin, admin.ModelAdmin):
            def get_site_url(self, obj):
                return f"/images/{obj.pk}/"

        spec = row_action_spec(Admin(Image, admin.site), "site", site, peak)
        assert spec.url == f"/images/{peak.pk}/"

    def test_permissions_and_links_without_a_url(self, superuser, viewer, peak):
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

        assert list(image_admin.get_row_action_specs(get(superuser), peak)) == [
            "view",
            "toggle",
            "delete",
            "custom",
        ]
        assert list(image_admin.get_row_action_specs(get(viewer), peak)) == ["view"]
        assert image_admin.get_row_action_specs(get(superuser), None) == {}
        assert image_admin.get_row_action_specs(get(superuser), Image()) == {}

    def test_run_each_form(self, superuser, album, peak):
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
        request = get(superuser)
        for name, function in [
            ("one", Admin.one),
            ("with_parent", Admin.with_parent),
            ("many", Admin.many),
            ("plain", plain),
            ("bound", image_admin.one),
        ]:
            spec = RowActionSpec(name, function, name, "", "", None)
            run_row_action(image_admin, request, spec, peak, album)

        assert calls == [
            ("one", peak),
            ("with_parent", peak, album),
            ("many", [peak]),
            ("plain", image_admin, peak),
            ("one", peak),
        ]


class TestChangelist:
    def test_column_with_the_buttons(self, admin_client, peak):
        response = admin_client.get(reverse("admin:gallery_image_changelist"))

        content = response.content.decode()
        assert 'class="column-row_actions"' in content
        assert (
            f'href="{reverse("admin:gallery_image_change", args=[peak.pk])}"' in content
        )
        url = action_url(peak, "toggle_featured")
        assert f'data-django-admin-tables-row-action="{url}"' in content
        assert 'data-confirmation="Delete “Peak”? This cannot be undone."' in content
        assert ">Feature</button>" in content
        assert "django_admin_tables/row-actions.js" in content

    def test_placed_where_listed(self, superuser, peak):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            list_display = ("row_actions", "title")
            row_actions = ["view"]

        list_display = Admin(Image, admin.site).get_list_display(get(superuser))

        assert getattr(list_display[0], "__name__", "") == "row_actions"
        assert list_display[1] == "title"

    def test_no_column_without_actions(self, admin_client):
        response = admin_client.get(reverse("admin:gallery_album_changelist"))
        assert "column-row_actions" not in response.content.decode()
        assert "row-actions.js" not in response.content.decode()

    def test_run_and_go_back(self, admin_client, peak):
        back = reverse("admin:gallery_image_changelist") + "?q=Peak"

        response = admin_client.post(
            action_url(peak, "toggle_featured"), {"next": back}, follow=True
        )

        assert response.redirect_chain == [(back, 302)]
        peak.refresh_from_db()
        assert peak.is_featured
        assert [str(m) for m in response.context["messages"]] == [
            "“Peak” is featured now."
        ]

    def test_unsafe_next_goes_to_the_changelist(self, admin_client, peak):
        response = admin_client.post(
            action_url(peak, "toggle_featured"), {"next": "https://evil.example/"}
        )
        assert response.url == reverse("admin:gallery_image_changelist")

    def test_ajax_gets_the_outcome(self, admin_client, peak):
        response = admin_client.post(
            action_url(peak, "toggle_featured"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        assert json.loads(response.content) == {
            "status": "done",
            "message": "“Peak” is featured now.",
        }

    def test_ajax_error_status(self, admin_client, peak):
        with mock.patch.object(
            Image, "delete", side_effect=ProtectedError("no", [peak.album])
        ):
            response = admin_client.post(
                action_url(peak, "delete"),
                headers={"x-requested-with": "XMLHttpRequest"},
            )
        result = json.loads(response.content)
        assert result["status"] == "error"
        assert "Cannot delete “Peak”: Alps depend on it." == result["message"]

    def test_delete(self, admin_client, peak):
        admin_client.post(action_url(peak, "delete"))
        assert not Image.objects.filter(pk=peak.pk).exists()

    def test_the_action_own_response(self, admin_client, peak):
        def export(model_admin, request, queryset):
            return HttpResponse(",".join(obj.title for obj in queryset))

        with mock.patch.object(ImageAdmin, "row_actions", [export]):
            response = admin_client.post(action_url(peak, "export"))
        assert response.content == b"Peak"

    def test_errors(self, admin_client, client, viewer, peak):
        assert admin_client.post(action_url(peak, "nope")).status_code == 400
        # A link isn't run.
        assert admin_client.post(action_url(peak, "view")).status_code == 400
        missing = reverse("admin:gallery_image_row_action", args=[0, "delete"])
        assert admin_client.post(missing).status_code == 404
        assert admin_client.get(action_url(peak, "delete")).status_code == 405

        client.force_login(viewer)
        assert client.post(action_url(peak, "delete")).status_code == 400
        assert Image.objects.filter(pk=peak.pk).exists()

    def test_needs_the_view_permission(self, django_user_model, client, peak):
        user = django_user_model.objects.create_user("staff", password="x")
        user.is_staff = True
        user.save()
        client.force_login(user)
        assert client.post(action_url(peak, "delete")).status_code == 403


class TestInline:
    def test_column_in_the_change_view(self, admin_client, album, peak):
        response = admin_client.get(
            reverse("admin:gallery_album_change", args=[album.pk])
        )

        content = response.content.decode()
        url = inline_url(album, peak, "toggle_featured")
        assert f'data-django-admin-tables-row-action="{url}"' in content
        assert "row-actions.js" in content

    def test_not_in_the_add_view(self, admin_client):
        response = admin_client.get(reverse("admin:gallery_album_add"))
        assert "django-admin-tables-row-actions" not in response.content.decode()

    def test_run_and_go_back(self, admin_client, album, peak):
        change = reverse("admin:gallery_album_change", args=[album.pk])

        response = admin_client.post(inline_url(album, peak, "toggle_featured"))

        assert response.url == change
        peak.refresh_from_db()
        assert peak.is_featured

    def test_delete_is_logged_on_the_parent(self, admin_client, album, peak):
        admin_client.post(inline_url(album, peak, "delete"))

        assert not Image.objects.filter(pk=peak.pk).exists()
        entry = LogEntry.objects.get()
        assert entry.object_id == str(album.pk)
        assert "Peak" in entry.get_change_message()

    def test_errors(self, admin_client, album, peak):
        other = Album.objects.create(title="Other")
        stranger = Image.objects.create(album=other, title="Stranger")
        assert (
            admin_client.post(inline_url(album, stranger, "delete")).status_code == 400
        )
        assert (
            admin_client.post(inline_url(album, peak, "delete", inline=5)).status_code
            == 404
        )
        missing = reverse(
            "admin:gallery_album_inline_row_action", args=[0, 0, peak.pk, "delete"]
        )
        assert admin_client.post(missing).status_code == 404

    def test_inline_without_row_actions(self, admin_client, album, peak):
        class Plain(admin.TabularInline):
            model = Image

        with mock.patch.object(AlbumAdmin, "inlines", [Plain]):
            response = admin_client.post(inline_url(album, peak, "delete"))
        assert response.status_code == 404

    def test_needs_the_view_permission(self, django_user_model, client, album, peak):
        user = django_user_model.objects.create_user("staff", password="x")
        user.is_staff = True
        user.save()
        client.force_login(user)
        assert client.post(inline_url(album, peak, "delete")).status_code == 403

    def test_render_without_its_request(self, peak):
        inline = ImageTabularInline(Album, admin.site)
        assert inline.render_row_actions(peak) == ""

    def test_parent_admin_without_the_mixin(self, superuser, album, peak):
        site = admin.AdminSite(name="plain")
        site.register(Album, admin.ModelAdmin, inlines=[ImageTabularInline])
        inline = ImageTabularInline(Album, site)
        inline.get_formset(get(superuser), album)
        assert inline.render_row_actions(peak) == ""

        errors = inline.check()
        assert [e.id for e in errors] == ["django_admin_tables.E009"]

    def test_fieldsets(self, superuser, album):
        class Inline(RowActionsMixin, admin.StackedInline):
            model = Image
            fieldsets = [(None, {"fields": ["title"]})]
            row_actions = ["delete"]

        inline = Inline(Album, admin.site)
        request = get(superuser)
        assert inline.get_fieldsets(request, album) == [
            (None, {"fields": ["title", "render_row_actions"]})
        ]
        assert "render_row_actions" in inline.get_readonly_fields(request, album)
        assert inline.get_fieldsets(request, None) == [(None, {"fields": ["title"]})]

    def test_message_user(self, superuser):
        inline = ImageTabularInline(Album, admin.site)
        request = get(superuser)
        inline.message_user(request, "Hi", messages.WARNING)
        assert [(m.level, str(m)) for m in request._messages] == [
            (messages.WARNING, "Hi")
        ]


class TestMedia:
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


class TestChecks:
    def test_unknown_action(self):
        class Admin(RowActionsMixin, admin.ModelAdmin):
            row_actions = ["view", "nope", delete]

        errors = Admin(Image, admin.site).check()
        assert [e.id for e in errors] == ["django_admin_tables.E008"]
        assert "'nope'" in errors[0].msg

    def test_valid(self):
        assert ImageAdmin(Image, admin.site).check() == []
        assert AlbumAdmin(Album, admin.site).check() == []


def test_view_without_a_change_view_is_left_out(superuser, peak):
    class Admin(RowActionsMixin, admin.ModelAdmin):
        row_actions = ["view"]

    other_site = admin.AdminSite(name="other")
    image_admin = Admin(Image, other_site)

    assert image_admin.get_row_action_specs(get(superuser), peak) == {}
    # Run anyway, it goes to its change view (none here).
    assert view(image_admin, get(superuser), peak).url == ""


def test_a_row_without_actions_has_an_empty_cell(viewer, peak):
    class Admin(RowActionsMixin, admin.ModelAdmin):
        row_actions = ["delete"]

    cell = Admin(Image, admin.site).render_row_actions_cell(
        get(viewer), peak, lambda action: "/"
    )
    assert cell == ""


def test_inline_listing_the_column_itself(superuser, album):
    class Inline(RowActionsMixin, admin.TabularInline):
        model = Image
        fields = ["title", "render_row_actions"]
        row_actions = ["delete"]

    inline = Inline(Album, admin.site)
    assert inline.get_fields(get(superuser), album) == ["title", "render_row_actions"]

    # Declared without it: added last.
    Inline.fields = ["title"]
    assert inline.get_fields(get(superuser), album) == ["title", "render_row_actions"]
