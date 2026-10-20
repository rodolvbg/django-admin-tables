from django.contrib import admin
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from gallery.models import Album

from django_admin_tables import UnsavedChangesMixin

SCRIPT = "django_admin_tables/unsaved-changes.js"


class Editable(UnsavedChangesMixin, admin.ModelAdmin):
    list_display = ("title", "is_featured")
    list_editable = ("is_featured",)


class TestUnsavedChangesMixin(TestCase):
    """Loading the unsaved-changes script on the changelist."""

    def test_with_list_editable(self):
        assert SCRIPT in str(Editable(Album, admin.site).media)

    def test_without_list_editable(self):
        class Admin(UnsavedChangesMixin, admin.ModelAdmin):
            list_display = ("title", "is_featured")

        assert SCRIPT not in str(Admin(Album, admin.site).media)

    def test_turned_off(self):
        class Admin(Editable):
            list_editable_unsaved_warning = False

        assert SCRIPT not in str(Admin(Album, admin.site).media)

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "a@example.com", "x")

    def setUp(self):
        self.client.force_login(self.user)

    def test_on_the_changelist(self):
        response = self.client.get(reverse("admin:gallery_album_changelist"))
        assert SCRIPT in response.content.decode()
