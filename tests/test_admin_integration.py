import pytest
from django.test import Client
from django.urls import reverse
from gallery.models import Album, Image

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(django_user_model):
    django_user_model.objects.create_superuser("admin", "admin@example.com", "password")
    client = Client()
    client.login(username="admin", password="password")
    return client


@pytest.fixture
def album():
    album = Album.objects.create(title="Holiday")
    Image.objects.create(album=album, title="A", is_primary=True)
    Image.objects.create(album=album, title="B", is_primary=False)
    return album


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


def test_change_form_renders_radio_inputs(admin_client, album):
    url = reverse("admin:gallery_album_change", args=[album.pk])
    response = admin_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'type="radio"' in content
    assert "radio-select-exclusive" in content
    assert 'data-radio-select-group="images::is_primary"' in content


def test_switching_the_primary_row_and_saving_persists_through_the_admin_view(
    admin_client, album
):
    url = reverse("admin:gallery_album_change", args=[album.pk])
    data = _base_post_data(album)
    # Switch: unselect row 0 (A), select row 1 (B) — as JS would leave
    # the form after a user clicks B's radio.
    del data["images-0-is_primary"]
    data["images-1-is_primary"] = "on"
    data["_save"] = "Save"

    response = admin_client.post(url, data)

    assert response.status_code == 302
    primaries = {image.title: image.is_primary for image in album.images.all()}
    assert primaries == {"A": False, "B": True}


def test_posting_two_true_rows_is_rejected_by_the_admin_view(admin_client, album):
    url = reverse("admin:gallery_album_change", args=[album.pk])
    data = _base_post_data(album)
    data["images-1-is_primary"] = "on"  # A is already primary; now B too
    data["_save"] = "Save"

    response = admin_client.post(url, data)

    assert response.status_code == 200  # re-rendered with errors, not redirected
    assert not Image.objects.get(title="B").is_primary
    content = response.content.decode()
    assert "is_primary" in content
