"""Full HTTP-level integration for the ModelAdmin changelist path: real
GET/POST requests through a logged-in admin client, hitting the actual
URLs. Direct, method-level tests for ExclusiveRadioFieldsMixin's own
methods (including get_changelist_formset) live in
test_exclusive_radio_fields_mixin.py instead.
"""

import pytest
from django.test import Client
from django.urls import reverse
from gallery.models import Album

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(django_user_model):
    django_user_model.objects.create_superuser("admin", "admin@example.com", "password")
    client = Client()
    client.login(username="admin", password="password")
    return client


@pytest.fixture
def albums():
    return [
        Album.objects.create(title="Winter", is_featured=True),
        Album.objects.create(title="Spring", is_featured=False),
        Album.objects.create(title="Summer", is_featured=False),
    ]


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


def test_changelist_renders_radio_inputs(admin_client, albums):
    response = admin_client.get(reverse("admin:gallery_album_changelist"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'type="radio"' in content
    assert 'data-radio-select-group="form::is_featured"' in content


def test_switching_the_featured_album_and_saving_persists_through_the_admin_view(
    admin_client, albums
):
    data = _base_post_data(albums)
    del data["form-0-is_featured"]  # Winter was featured
    data["form-1-is_featured"] = "on"  # Spring becomes featured

    response = admin_client.post(reverse("admin:gallery_album_changelist"), data)

    assert response.status_code == 302
    featured = {album.title: album.is_featured for album in Album.objects.all()}
    assert featured == {"Winter": False, "Spring": True, "Summer": False}


def test_posting_two_featured_albums_is_rejected_by_the_admin_view(
    admin_client, albums
):
    data = _base_post_data(albums)
    data["form-1-is_featured"] = "on"  # Winter already featured; now Spring too

    response = admin_client.post(reverse("admin:gallery_album_changelist"), data)

    assert response.status_code == 200  # re-rendered with errors, not redirected
    assert not Album.objects.get(title="Spring").is_featured
