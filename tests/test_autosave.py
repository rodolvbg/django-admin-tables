"""ListEditableAutosaveMixin: list_editable fields that save themselves."""

import json
import re

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from gallery.models import Album, AlbumStacked

from django_admin_tables import AdminTablesMixin, ListEditableAutosaveMixin

CHANGELIST = "/admin/gallery/albumstacked/"
URL = "/admin/gallery/albumstacked/autosave/"


def config(html):
    match = re.search(
        r'<script id="django-admin-tables-autosave" type="application/json">'
        r"(.*?)</script>",
        html,
    )
    return json.loads(match.group(1)) if match else None


class TestAutosave(TestCase):
    """The example's AlbumStackedAdmin: its title and is_featured save
    themselves."""

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.album = Album.objects.create(title="Winter")

    def setUp(self):
        self.client.force_login(self.user)

    def save(self, field, data, previous=None, pk=None):
        body = {"prefix": "form-0", "field": field, "pk": pk or self.album.pk}
        body.update({f"form-0-{name}": value for name, value in data.items()})
        if previous is not None:
            body["check"] = "1"
            body.update(
                {f"previous-form-0-{name}": value for name, value in previous.items()}
            )
        return self.client.post(URL, body)

    def test_its_page_has_its_configuration_and_no_save_button(self):
        html = self.client.get(CHANGELIST).content.decode()
        assert config(html) == {
            "url": URL,
            "fields": ["title", "is_featured"],
            "pk": "id",
            "all": True,
            "texts": {"saving": "Saving…", "saved": "Saved", "failed": "Not saved"},
        }
        assert "django_admin_tables/autosave.js" in html
        assert "django_admin_tables/autosave.css" in html
        assert "django_admin_tables/autosave-all.css" in html

    def test_a_switch_saves_itself(self):
        response = self.save("is_featured", {"is_featured": "on"}, previous={})
        assert response.status_code == 200
        assert response.json() == {"saved": True}
        self.album.refresh_from_db()
        assert self.album.is_featured is True
        # The title, not sent, is as it was; and the change is in its history.
        assert self.album.title == "Winter"
        entry = LogEntry.objects.get()
        assert "Is featured" in entry.get_change_message()
        # Unchecked: no value sent.
        assert self.save("is_featured", {}, previous={"is_featured": "on"}).json() == {
            "saved": True
        }
        self.album.refresh_from_db()
        assert self.album.is_featured is False

    def test_a_text_saves_itself_valid_or_not(self):
        self.save("title", {"title": "Summer"}, previous={"title": "Winter"})
        self.album.refresh_from_db()
        assert self.album.title == "Summer"
        response = self.save("title", {"title": ""}, previous={"title": "Summer"})
        assert response.status_code == 400
        assert response.json()["error"] == "This field is required."
        self.album.refresh_from_db()
        assert self.album.title == "Summer"

    def test_nothing_changed_nothing_saved(self):
        response = self.save("title", {"title": "Winter"})
        assert response.json() == {"saved": True}
        assert not LogEntry.objects.exists()

    def test_what_someone_else_changed_isnt_overwritten(self):
        Album.objects.filter(pk=self.album.pk).update(title="Changed")
        response = self.save("title", {"title": "Mine"}, previous={"title": "Winter"})
        assert response.status_code == 409
        assert response.json()["conflict"] is True
        self.album.refresh_from_db()
        assert self.album.title == "Changed"

    def test_what_it_doesnt_save(self):
        assert self.save("id", {"id": "5"}).status_code == 400
        response = self.client.post(URL, {"prefix": "x", "field": "title"})
        assert response.status_code == 400
        assert self.save("title", {"title": "x"}, pk=9999).status_code == 404
        assert self.save("title", {"title": "x"}, pk="nope").status_code == 404
        assert self.client.get(URL).status_code == 405

    def test_only_for_who_may_change_it(self):
        clerk = User.objects.create_user("clerk", password="pw", is_staff=True)
        clerk.user_permissions.add(Permission.objects.get(codename="view_album"))
        self.client.force_login(clerk)
        assert self.save("title", {"title": "x"}).status_code == 403


class Some(AdminTablesMixin, admin.ModelAdmin):
    """Only some fields save themselves; the exclusive one never."""

    list_display = ("id", "title", "is_featured")
    list_editable = ("title", "is_featured")
    list_editable_autosave = ("is_featured", "nope")


class Exclusive(AdminTablesMixin, admin.ModelAdmin):
    list_display = ("id", "title", "is_featured")
    list_editable = ("title", "is_featured")
    radio_select_exclusive_fields = ("is_featured",)
    list_editable_autosave = True


class Plain(ListEditableAutosaveMixin, admin.ModelAdmin):
    list_display = ("id", "title")
    list_editable = ("title",)


class TestOptions(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        Album.objects.create(title="Winter")

    def changelist_extras(self, model_admin):
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        request.user = self.user
        cl = model_admin.get_changelist_instance(request)
        cl.formset = model_admin.get_changelist_formset(request)(
            queryset=cl.result_list
        )
        return model_admin.get_changelist_extras(request, cl)

    def test_some_fields(self):
        extras = self.changelist_extras(Some(AlbumStacked, admin.site))
        assert extras["autosave"]["fields"] == ["is_featured"]
        assert extras["autosave"]["all"] is False

    def test_not_the_exclusive_radio_fields(self):
        extras = self.changelist_extras(Exclusive(AlbumStacked, admin.site))
        assert extras["autosave"]["fields"] == ["title"]

    def test_off_by_default(self):
        model_admin = Plain(AlbumStacked, admin.site)
        assert model_admin.uses_list_editable_autosave is False
        assert "autosave" not in str(model_admin.media)
        names = [getattr(url, "name", None) for url in model_admin.get_urls()]
        assert "gallery_albumstacked_autosave" not in names
        assert "autosave" not in self.changelist_extras(model_admin)
