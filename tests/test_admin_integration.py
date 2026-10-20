from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from gallery.models import Album, Image


def _base_post_data(album):
    images = list(album.images.all())
    data = {
        "title": album.title,
        "images-TOTAL_FORMS": str(len(images)),
        "images-INITIAL_FORMS": str(len(images)),
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }
    for index, image in enumerate(images):
        data[f"images-{index}-id"] = str(image.pk)
        data[f"images-{index}-album"] = str(album.pk)
        data[f"images-{index}-title"] = image.title
        if image.is_primary:
            data[f"images-{index}-is_primary"] = "on"
    return data


class TestInlineRadioIntegration(TestCase):
    """Exclusive radios through the inline admin views."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.album = Album.objects.create(title="Holiday")
        Image.objects.create(album=cls.album, title="A", is_primary=True)
        Image.objects.create(album=cls.album, title="B", is_primary=False)

    def setUp(self):
        self.client.force_login(self.user)

    def test_change_form_renders_radio_inputs(self):
        url = reverse("admin:gallery_album_change", args=[self.album.pk])
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        assert 'type="radio"' in content
        assert "radio-select-exclusive" in content
        assert 'data-radio-select-group="images::is_primary"' in content

    def test_switching_the_primary_row_and_saving_persists(self):
        url = reverse("admin:gallery_album_change", args=[self.album.pk])
        data = _base_post_data(self.album)
        # Switch: unselect row 0 (A), select row 1 (B) — as JS would leave
        # the form after a user clicks B's radio.
        del data["images-0-is_primary"]
        data["images-1-is_primary"] = "on"
        data["_save"] = "Save"

        response = self.client.post(url, data)

        assert response.status_code == 302
        primaries = {image.title: image.is_primary for image in self.album.images.all()}
        assert primaries == {"A": False, "B": True}

    def test_posting_two_true_rows_is_rejected_by_the_admin_view(self):
        url = reverse("admin:gallery_album_change", args=[self.album.pk])
        data = _base_post_data(self.album)
        data["images-1-is_primary"] = "on"  # A is already primary; now B too
        data["_save"] = "Save"

        response = self.client.post(url, data)

        assert response.status_code == 200  # re-rendered with errors, not redirected
        assert not Image.objects.get(title="B").is_primary
        content = response.content.decode()
        assert "is_primary" in content
