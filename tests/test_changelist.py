"""Full HTTP-level integration for the ModelAdmin changelist path: real
GET/POST requests through a logged-in admin client, hitting the actual
URLs. Direct, method-level tests for ExclusiveRadioFieldsMixin's own
methods (including get_changelist_formset) live in
test_exclusive_radio_fields_mixin.py instead.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from gallery.models import Album


def _base_post_data(albums):
    data = {
        "form-TOTAL_FORMS": str(len(albums)),
        "form-INITIAL_FORMS": str(len(albums)),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "_save": "Save",
    }
    for index, album in enumerate(albums):
        data[f"form-{index}-id"] = str(album.pk)
        if album.is_featured:
            data[f"form-{index}-is_featured"] = "on"
    return data


class TestChangelistRadioIntegration(TestCase):
    """Exclusive radios through the changelist admin view."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.albums = [
            Album.objects.create(title="Winter", is_featured=True),
            Album.objects.create(title="Spring", is_featured=False),
            Album.objects.create(title="Summer", is_featured=False),
        ]

    def setUp(self):
        self.client.force_login(self.user)

    def test_changelist_renders_radio_inputs(self):
        response = self.client.get(reverse("admin:gallery_album_changelist"))

        assert response.status_code == 200
        content = response.content.decode()
        assert 'type="radio"' in content
        assert 'data-radio-select-group="form::is_featured"' in content

    def test_switching_the_featured_album_and_saving_persists(self):
        data = _base_post_data(self.albums)
        del data["form-0-is_featured"]  # Winter was featured
        data["form-1-is_featured"] = "on"  # Spring becomes featured

        response = self.client.post(reverse("admin:gallery_album_changelist"), data)

        assert response.status_code == 302
        featured = {album.title: album.is_featured for album in Album.objects.all()}
        assert featured == {"Winter": False, "Spring": True, "Summer": False}

    def test_posting_two_featured_albums_is_rejected_by_the_admin_view(self):
        data = _base_post_data(self.albums)
        data["form-1-is_featured"] = "on"  # Winter already featured; now Spring too

        response = self.client.post(reverse("admin:gallery_album_changelist"), data)

        assert response.status_code == 200  # re-rendered with errors, not redirected
        assert not Album.objects.get(title="Spring").is_featured
