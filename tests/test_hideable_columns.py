import json
import sys
import types
from unittest import mock

import pytest
from django.contrib import admin
from django.core import checks
from django.template.response import TemplateResponse
from django.test import Client, RequestFactory
from django.urls import reverse
from gallery.models import Album, Image

from django_admin_tables import HideableColumnsMixin

pytestmark = pytest.mark.django_db

INSTALLED = "django_admin_tables.columns.mixins.apps.is_installed"


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
def images():
    album = Album.objects.create(title="Holiday")
    return [
        Image.objects.create(album=album, title="Beach", is_primary=True),
        Image.objects.create(album=album, title="City"),
    ]


def changelist(model_admin, superuser, **attrs):
    request = RequestFactory().get("/")
    request.user = superuser
    for name, value in attrs.items():
        setattr(request, name, value)
    response = model_admin.changelist_view(request)
    response.render()
    return response


def config_of(response):
    return response.context_data["django_admin_tables_columns"]


def template_names(response):
    return [t.name for t in response.templates]


class TestHideableColumnsMixin:
    """The columns menu on the changelist."""

    def test_changelist_gets_the_columns_menu(self, admin_client, images):
        response = admin_client.get(reverse("admin:gallery_image_changelist"))

        assert "django_admin_tables/change_list.html" in template_names(response)
        assert "admin/change_list.html" in template_names(response)
        content = response.content.decode()
        assert 'class="django-admin-tables-columns"' in content
        assert (
            'data-django-admin-tables-column="album_link"'
            ' data-django-admin-tables-max-width="767.98" checked'
        ) in content
        assert 'data-django-admin-tables-column="is_primary" checked' in content
        assert 'data-django-admin-tables-column="is_featured">' in content
        assert "django_admin_tables/columns.js" in content
        assert "django_admin_tables/columns.css" in content

    def test_config_lists_the_hideable_columns_in_list_display_order(
        self, admin_client, images
    ):
        response = admin_client.get(reverse("admin:gallery_image_changelist"))

        columns = config_of(response)
        assert [c["name"] for c in columns["columns"]] == [
            "album",
            "is_primary",
            "is_featured",
        ]
        assert [c["label"] for c in columns["columns"]] == [
            "Album",
            "Is primary",
            "Is featured",
        ]
        assert columns["config"] == {
            "storageKey": "django-admin-tables:admin:gallery.image:hidden-columns",
            "hidden": ["is_featured"],
            "columns": ["album_link", "is_primary", "is_featured"],
        }
        script = response.content.decode().split(
            '<script id="django-admin-tables-columns" type="application/json">'
        )[1]
        assert json.loads(script.split("</script>")[0]) == columns["config"]

    def test_changelist_without_hideable_columns_is_untouched(self, admin_client):
        response = admin_client.get(reverse("admin:gallery_album_changelist"))

        assert "django_admin_tables/change_list.html" not in template_names(response)
        assert "django_admin_tables_columns" not in response.context_data

    def test_hideable_columns_can_depend_on_the_request(self, superuser, images):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album", "is_primary")

            def get_list_display_hideable(self, request):
                return ("album",) if getattr(request, "hideable", False) else ()

            def get_list_display_hidden(self, request):
                return ("album",)

        image_admin = ImageAdmin(Image, admin.site)

        assert (
            "django_admin_tables_columns"
            not in changelist(image_admin, superuser).context_data
        )
        config = config_of(changelist(image_admin, superuser, hideable=True))["config"]
        assert config["columns"] == ["album"]
        assert config["hidden"] == ["album"]

    def test_callables_get_the_admin_column_classes(self, superuser, images):
        def shout(obj):
            return obj.title.upper()

        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", shout, lambda obj: obj.pk, "upper_title")
            list_display_hideable = ("shout", "upper_title", "<lambda>")

            @admin.display(description="Loud")
            def upper_title(self, obj):
                return obj.title.upper()

        response = changelist(ImageAdmin(Image, admin.site), superuser)

        columns = config_of(response)["columns"]
        assert [(c["class"], c["label"]) for c in columns] == [
            ("shout", "Shout"),
            ("lambda3", "--"),
            ("upper_title", "Loud"),
        ]
        content = response.content.decode()
        assert all(
            f'class="{prefix}-{css_class}"' in content
            for css_class in ("shout", "lambda3", "upper_title")
            for prefix in ("column", "field")
        )

    def test_custom_change_list_template_is_extended(self, superuser, images):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_display_hideable = ("album",)
            change_list_template = "admin/custom_change_list.html"

        response = changelist(ImageAdmin(Image, admin.site), superuser)

        assert response.template_name == "django_admin_tables/change_list.html"
        parent = response.context_data["django_admin_tables_parent"]
        assert parent.template.name == "admin/custom_change_list.html"
        content = response.content.decode()
        assert 'id="custom-change-list"' in content
        assert "django-admin-tables-columns" in content

    def test_responses_without_a_changelist_are_untouched(self, superuser):
        """A ModelAdmin earlier in the MRO may render something else."""

        class Other(admin.ModelAdmin):
            def changelist_view(self, request, extra_context=None):
                return TemplateResponse(request, "admin/base.html", {})

        class ImageAdmin(HideableColumnsMixin, Other):
            list_display = ("title", "album")
            list_display_hideable = ("album",)

        request = RequestFactory().get("/")
        request.user = superuser
        response = ImageAdmin(Image, admin.site).changelist_view(request)

        assert response.template_name == "admin/base.html"

    def test_redirects_are_untouched(self, superuser, images):
        """Saving list_editable redirects: there's no template to swap."""

        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "is_primary")
            list_editable = ("is_primary",)
            list_display_hideable = ("is_primary",)

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(images[0].pk),
            "form-1-id": str(images[1].pk),
            "form-1-is_primary": "on",
            "_save": "Save",
        }
        request = RequestFactory().post("/", data)
        request.user = superuser
        request._dont_enforce_csrf_checks = True
        with mock.patch("django.contrib.admin.options.ModelAdmin.message_user"):
            response = ImageAdmin(Image, admin.site).changelist_view(request)

        assert response.status_code == 302
        images[1].refresh_from_db()
        assert images[1].is_primary

    def test_unfold_menu(self, superuser, images):
        fake = types.ModuleType("unfold.widgets")
        fake.CHECKBOX_CLASSES = ["appearance-none", "w-4"]

        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_display_hideable = ("album",)

        with (
            mock.patch(INSTALLED, side_effect=lambda app: app == "unfold"),
            mock.patch.dict(sys.modules, {"unfold.widgets": fake}),
        ):
            response = changelist(ImageAdmin(Image, admin.site), superuser)

        content = response.content.decode()
        assert "django-admin-tables-columns--unfold" in content
        assert 'class="appearance-none w-4" checked' in content
        assert "view_column" in content


class TestChecks:
    def test_valid(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_display_hideable = ("album",)
            list_display_hidden = ("album",)

        assert ImageAdmin(Image, admin.site).check() == []

    def test_hideable_must_be_in_list_display(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title",)
            list_display_hideable = ("album",)

        errors = ImageAdmin(Image, admin.site).check()

        assert [e.id for e in errors] == ["django_admin_tables.E001"]
        assert isinstance(errors[0], checks.Error)
        assert "'album'" in errors[0].msg

    def test_hidden_must_be_hideable(self):
        class ImageAdmin(HideableColumnsMixin, admin.ModelAdmin):
            list_display = ("title", "album")
            list_display_hidden = ("album",)

        errors = ImageAdmin(Image, admin.site).check()

        assert [e.id for e in errors] == ["django_admin_tables.E002"]

    def test_inlines_are_not_checked(self):
        class ImageInline(HideableColumnsMixin, admin.TabularInline):
            model = Image
            list_display_hideable = ("album",)

        assert ImageInline(Album, admin.site).check() == []
