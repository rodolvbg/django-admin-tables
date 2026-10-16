"""Real-browser end-to-end tests: the JS module and the server-side
validation are unit-tested elsewhere (tests/js/, test_formsets.py); this
file is about the two only working together, through an actual browser,
against a real running Django server.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from gallery.models import Album, Image
from playwright.sync_api import Page, expect


class _AdminE2ETestCase(StaticLiveServerTestCase):
    """Shared setup for browser tests against the example admin: log in
    once per test and build the Album/Image fixtures most of them start
    from, instead of each test repeating the same few lines.

    ``StaticLiveServerTestCase`` (a ``TransactionTestCase`` under the
    hood, with static files served too — needed since these tests load
    a real page that pulls in our JS) already runs each test in its own
    transaction the way ``@pytest.mark.django_db(transaction=True)``
    does, so that marker isn't needed here; it also gives
    ``self.live_server_url`` in place of the ``live_server`` fixture.
    pytest-playwright's ``page`` fixture still needs pytest's own
    injection, which doesn't reach unittest-style test methods as an
    extra parameter — so it's grabbed once per test via this autouse
    fixture instead, and stashed on ``self``.
    """

    @pytest.fixture(autouse=True)
    def _inject_page(self, page: Page) -> None:
        self.page = page

    def login(self) -> None:
        get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        self.page.goto(f"{self.live_server_url}/admin/login/")
        self.page.fill('input[name="username"]', "admin")
        self.page.fill('input[name="password"]', "password")
        self.page.click('input[type="submit"]')
        expect(self.page).to_have_url(f"{self.live_server_url}/admin/")

    def create_album(self, *, images: tuple[tuple[str, bool], ...] = ()) -> Album:
        album = Album.objects.create(title="Holiday")
        for title, is_primary in images:
            Image.objects.create(album=album, title=title, is_primary=is_primary)
        return album

    def open_change_page(self, album: Album) -> None:
        self.page.goto(f"{self.live_server_url}/admin/gallery/album/{album.pk}/change/")


class TestInlineExclusivity(_AdminE2ETestCase):
    def test_selecting_one_row_unchecks_the_others_in_the_browser(self):
        album = self.create_album(
            images=(("Beach", True), ("Mountain", False), ("City", False))
        )
        self.login()
        self.open_change_page(album)

        beach = self.page.locator('input[name="images-0-is_primary"]')
        mountain = self.page.locator('input[name="images-1-is_primary"]')
        city = self.page.locator('input[name="images-2-is_primary"]')

        expect(beach).to_be_checked()

        mountain.check()

        expect(mountain).to_be_checked()
        expect(beach).not_to_be_checked()
        expect(city).not_to_be_checked()

    def test_saving_after_switching_the_row_persists(self):
        album = self.create_album(images=(("Beach", True), ("Mountain", False)))
        self.login()
        self.open_change_page(album)

        self.page.locator('input[name="images-1-is_primary"]').check()
        self.page.locator('input[name="_save"]').click()

        expect(self.page).to_have_url(f"{self.live_server_url}/admin/gallery/album/")
        images = {image.title: image.is_primary for image in album.images.all()}
        assert images == {"Beach": False, "Mountain": True}

    def test_dynamically_added_row_joins_the_exclusive_group(self):
        # Not a row we built ourselves: clicking Django admin's own "Add
        # another" button (inlines.js), same as a real user would, to
        # prove the delegated JS listener picks up a node it never saw
        # at load time.
        album = self.create_album(images=(("Beach", True),))
        self.login()
        self.open_change_page(album)

        beach = self.page.locator('input[name="images-0-is_primary"]')
        expect(beach).to_be_checked()

        total_forms = self.page.locator('input[name="images-TOTAL_FORMS"]')
        new_index = int(total_forms.input_value())

        self.page.get_by_role("button", name="Add another Image").click()

        expect(total_forms).to_have_value(str(new_index + 1))
        new_row_title = self.page.locator(f'input[name="images-{new_index}-title"]')
        new_row_primary = self.page.locator(
            f'input[name="images-{new_index}-is_primary"]'
        )
        expect(new_row_title).to_be_visible()

        new_row_title.fill("Sunset")
        new_row_primary.check()

        expect(new_row_primary).to_be_checked()
        expect(beach).not_to_be_checked()

    def test_saving_after_adding_a_new_row_persists_it_as_the_selected_one(self):
        album = self.create_album(images=(("Beach", True),))
        self.login()
        self.open_change_page(album)

        total_forms = self.page.locator('input[name="images-TOTAL_FORMS"]')
        new_index = int(total_forms.input_value())

        self.page.get_by_role("button", name="Add another Image").click()
        self.page.locator(f'input[name="images-{new_index}-title"]').fill("Sunset")
        self.page.locator(f'input[name="images-{new_index}-is_primary"]').check()
        self.page.locator('input[name="_save"]').click()

        expect(self.page).to_have_url(f"{self.live_server_url}/admin/gallery/album/")
        images = {image.title: image.is_primary for image in album.images.all()}
        assert images == {"Beach": False, "Sunset": True}


class TestChangelistExclusivity(_AdminE2ETestCase):
    def test_selecting_one_row_unchecks_the_others_in_the_browser(self):
        Album.objects.create(title="Winter", is_featured=True)
        Album.objects.create(title="Spring", is_featured=False)

        self.login()
        self.page.goto(f"{self.live_server_url}/admin/gallery/album/")

        # Don't assume row order matches creation order (the
        # changelist's own default ordering isn't this package's
        # concern): just track which row is checked by identity.
        group_selector = 'input[data-radio-select-group="form::is_featured"]'
        expect(self.page.locator(group_selector)).to_have_count(2)
        checked = self.page.locator(f"{group_selector}:checked")
        unchecked = self.page.locator(f"{group_selector}:not(:checked)")
        expect(checked).to_have_count(1)
        checked_name_before = checked.get_attribute("name")

        unchecked.check()

        checked_after = self.page.locator(f"{group_selector}:checked")
        expect(checked_after).to_have_count(1)
        assert checked_after.get_attribute("name") != checked_name_before
