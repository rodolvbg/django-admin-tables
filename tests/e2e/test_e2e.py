"""Real-browser end-to-end tests: the JS module and the server-side
validation are unit-tested elsewhere (tests/js/, radio_select/test_formsets.py); this
file is about the two only working together, through an actual browser,
against a real running Django server.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from gallery.models import Album, Image
from playwright.sync_api import Error, Page, expect


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

    def tearDown(self) -> None:
        # Close the page before the test database is flushed (after
        # tearDown): a request still in flight, or one the page makes later,
        # would otherwise reach the server once its data, or its database
        # connection, is gone, breaking this test or the next one.
        page = getattr(self, "page", None)
        if page is not None and not page.is_closed():
            # Its routes first (a CSP test adds some): none left mid-request.
            page.unroute_all(behavior="ignoreErrors")
            page.close()
        super().tearDown()

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


class TestHideableColumns(_AdminE2ETestCase):
    def test_hiding_a_column_from_the_menu_is_remembered(self):
        self.create_album(images=(("Beach", True),))
        self.login()
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/")

        album_header = self.page.locator("#result_list th.column-album_link")
        album_cell = self.page.locator("#result_list td.field-album_link")
        featured_header = self.page.locator("#result_list th.column-is_featured")
        # list_display_hidden: hidden until the user shows it.
        expect(featured_header).to_be_hidden()
        expect(album_header).to_be_visible()

        self.page.get_by_text("Columns", exact=True).click()
        self.page.get_by_label("Album").uncheck()

        expect(album_header).to_be_hidden()
        expect(album_cell).to_be_hidden()

        self.page.reload()

        expect(album_header).to_be_hidden()
        expect(featured_header).to_be_hidden()
        self.page.get_by_text("Columns", exact=True).click()
        self.page.get_by_label("Is featured").check()
        expect(featured_header).to_be_visible()


class TestResponsiveColumns(_AdminE2ETestCase):
    def test_changelist_column_hidden_on_narrow_screens(self):
        self.create_album(images=(("Beach", True),))
        self.login()
        self.page.set_viewport_size({"width": 1200, "height": 800})
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/")
        album_header = self.page.locator("#result_list th.column-album_link")
        expect(album_header).to_be_visible()

        self.page.set_viewport_size({"width": 600, "height": 800})

        expect(album_header).to_be_hidden()
        expect(self.page.locator("#result_list td.field-album_link")).to_be_hidden()
        self.page.locator("details.django-admin-tables-columns > summary").click()
        album = self.page.get_by_label("Album")
        expect(album).to_be_disabled()
        expect(album).not_to_be_checked()
        expect(self.page.get_by_text("(narrow screen)")).to_be_visible()

        self.page.set_viewport_size({"width": 1200, "height": 800})

        expect(album_header).to_be_visible()
        expect(album).to_be_enabled()
        expect(album).to_be_checked()

    def test_inline_column_hidden_on_narrow_screens(self):
        album = self.create_album(images=(("Beach", True),))
        self.login()
        self.page.set_viewport_size({"width": 600, "height": 800})
        self.open_change_page(album)

        expect(self.page.locator("#images-group th.column-is_featured")).to_be_hidden()
        expect(self.page.locator("#images-group th.column-is_primary")).to_be_visible()

        self.page.set_viewport_size({"width": 1200, "height": 800})

        expect(self.page.locator("#images-group th.column-is_featured")).to_be_visible()


class TestStrictContentSecurityPolicy(_AdminE2ETestCase):
    """Without 'unsafe-inline' in style-src, a <style> element is blocked:
    the columns' CSS is set from columns.js instead."""

    POLICY = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:"
    )
    # Playwright's route.fetch() may resolve "localhost" to IPv6 (::1),
    # where the test server doesn't listen.
    host = "127.0.0.1"

    def setUp(self) -> None:
        super().setUp()
        self.violations: list[str] = []
        self.page.on(
            "console",
            lambda message: (
                self.violations.append(message.text)
                if "Content Security Policy" in message.text and "style" in message.text
                else None
            ),
        )

        def add_policy(route):
            try:
                response = route.fetch(max_redirects=0)
                route.fulfill(
                    response=response,
                    headers={
                        **response.headers,
                        "content-security-policy": self.POLICY,
                    },
                )
            except Error:
                # The test ended, and its server or page closed, mid-request.
                pass

        self.page.route(f"{self.live_server_url}/**", add_policy)

    def test_menu_and_responsive_columns_still_hide(self):
        album = self.create_album(images=(("Beach", True),))
        self.login()
        self.page.set_viewport_size({"width": 600, "height": 800})
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/")

        expect(self.page.locator("#result_list th.column-album_link")).to_be_hidden()
        expect(self.page.locator("#result_list th.column-is_featured")).to_be_hidden()
        self.page.locator("details.django-admin-tables-columns > summary").click()
        self.page.get_by_label("Is primary").uncheck()
        expect(self.page.locator("#result_list th.column-is_primary")).to_be_hidden()

        self.open_change_page(album)
        expect(self.page.locator("#images-group th.column-is_featured")).to_be_hidden()
        expect(self.page.locator("#images-group th.column-is_primary")).to_be_visible()

        # The row actions' script, too.
        self.page.locator("#images-group").get_by_role("button", name="Feature").click()
        expect(self.page.locator(".messagelist")).to_contain_text("featured now")
        assert self.violations == []


class TestFooterRows(_AdminE2ETestCase):
    def test_totals_follow_their_columns(self):
        self.create_album(images=(("Beach", True), ("City", False)))
        self.login()
        self.page.set_viewport_size({"width": 1200, "height": 800})
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/")

        footer = self.page.locator("#result_list tfoot")
        expect(footer.locator("td.field-title")).to_contain_text("2")
        expect(footer.locator("td.field-is_primary")).to_contain_text("1")
        # Under its column: hidden with it (list_display_hidden here).
        expect(footer.locator("td.field-is_featured")).to_be_hidden()

        self.page.locator("details.django-admin-tables-columns > summary").click()
        self.page.get_by_label("Is primary").uncheck()
        expect(footer.locator("td.field-is_primary")).to_be_hidden()

    def test_inline_totals(self):
        album = self.create_album(images=(("Beach", True), ("City", False)))
        self.login()
        self.open_change_page(album)

        footer = self.page.locator("#images-group tfoot")
        expect(footer.locator("td.field-title")).to_contain_text("2")
        expect(footer.locator("td.field-is_primary")).to_contain_text("1")


class TestRowActions(_AdminE2ETestCase):
    def test_changelist_button_runs_the_action(self):
        self.create_album(images=(("Beach", True),))
        self.login()
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/?q=")

        self.page.get_by_role("button", name="Feature").click()

        expect(self.page).to_have_url(f"{self.live_server_url}/admin/gallery/image/?q=")
        expect(self.page.locator(".messagelist")).to_contain_text(
            "“Beach” is featured now."
        )
        expect(self.page.get_by_role("button", name="Unfeature")).to_be_visible()
        assert Image.objects.get(title="Beach").is_featured

    def test_delete_asks_first(self):
        self.create_album(images=(("Beach", True), ("City", False)))
        self.login()
        self.page.goto(f"{self.live_server_url}/admin/gallery/image/")
        row = self.page.locator("#result_list tbody tr", has_text="City")

        self.page.once("dialog", lambda dialog: dialog.dismiss())
        row.get_by_role("button", name="Delete").click()
        assert Image.objects.filter(title="City").exists()

        self.page.once("dialog", lambda dialog: dialog.accept())
        row.get_by_role("button", name="Delete").click()
        expect(self.page.locator(".messagelist")).to_contain_text("Deleted “City”.")
        assert not Image.objects.filter(title="City").exists()

    def test_inline_button_and_unsaved_changes(self):
        album = self.create_album(images=(("Beach", True),))
        self.login()
        self.open_change_page(album)
        self.page.fill("#id_title", "Edited")
        button = self.page.locator("#images-group").get_by_role(
            "button", name="Feature"
        )

        messages: list[str] = []

        def dismiss(dialog):
            messages.append(dialog.message)
            dialog.dismiss()

        self.page.once("dialog", dismiss)
        button.click()
        assert messages == [
            "You have unsaved changes on this page: they will be lost. Continue?"
        ]
        assert not Image.objects.get(title="Beach").is_featured

        self.page.once("dialog", lambda dialog: dialog.accept())
        button.click()
        expect(self.page.locator(".messagelist")).to_contain_text(
            "“Beach” is featured now."
        )
        expect(self.page.locator("#id_title")).to_have_value("Holiday")
        assert Image.objects.get(title="Beach").is_featured


class TestUnsavedChanges(_AdminE2ETestCase):
    def test_leaving_with_unsaved_list_editable_changes_asks_first(self):
        Album.objects.create(title="Winter", is_featured=True)
        Album.objects.create(title="Spring")
        self.login()
        changelist = f"{self.live_server_url}/admin/gallery/album/"
        self.page.goto(changelist)
        dialogs: list[str] = []

        def answer(accept):
            def handle(dialog):
                dialogs.append(dialog.type)
                dialog.accept() if accept else dialog.dismiss()

            return handle

        # Unchanged: sorting just goes.
        self.page.locator("th.column-title a").first.click()
        expect(self.page).to_have_url(re.compile(r"\?o="))
        assert dialogs == []

        self.page.goto(changelist)
        self.page.locator(
            'input[data-radio-select-group="form::is_featured"]:not(:checked)'
        ).check()
        self.page.once("dialog", answer(False))
        self.page.locator("th.column-title a").first.click()
        expect(self.page).to_have_url(changelist)
        assert dialogs == ["beforeunload"]

        # Saving sends the edits: no question.
        self.page.locator('input[name="_save"]').click()
        expect(self.page.locator(".messagelist")).to_be_visible()
        assert dialogs == ["beforeunload"]
        assert Album.objects.get(title="Spring").is_featured


class TestSelectableRows(_AdminE2ETestCase):
    """The example's ImageAdmin: an album's primary image can't be selected."""

    def test_select_all_leaves_out_the_rows_that_cant_be_selected(self):
        self.create_album(images=(("Cover", True), ("Beach", False), ("City", False)))
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/image/")

        cover = page.locator("tr", has_text="Cover").locator("td.action-checkbox input")
        expect(cover).to_be_disabled()
        expect(cover).to_have_attribute(
            "title", "The album's primary image: choose another one first."
        )

        expect(page.locator(".action-counter")).to_contain_text("0 of 2 selected")
        page.check("#action-toggle")
        expect(page.locator("input.action-select:checked")).to_have_count(2)
        expect(cover).not_to_be_checked()
        expect(page.locator(".action-counter")).to_contain_text("2 of 2 selected")

        page.select_option("select[name=action]", "delete_selected")
        page.click("button[name=index]")
        page.click("input[type=submit]")  # "Yes, I'm sure"
        expect(page.locator(".messagelist")).to_contain_text("Successfully deleted 2")
        assert list(Image.objects.values_list("title", flat=True)) == ["Cover"]


class TestListEditableAutosave(_AdminE2ETestCase):
    """The example's AlbumStackedAdmin: its title and is_featured save
    themselves, without a "Save" button."""

    def test_fields_save_themselves(self):
        from gallery.models import Album

        album = Album.objects.create(title="Winter")
        self.login()
        page = self.page
        page.goto(f"{self.live_server_url}/admin/gallery/albumstacked/")
        expect(page.locator("input[name=_save]")).to_be_hidden()

        # A switch: at once.
        page.check("input[name=form-0-is_featured]")
        status = page.locator(".django-admin-tables-autosave-status").first
        expect(status).to_have_text("Saved")
        album.refresh_from_db()
        assert album.is_featured is True

        # A text: on Enter (not the changelist's submit).
        title = page.locator("input[name=form-0-title]")
        title.fill("Summer")
        title.press("Enter")
        expect(page).to_have_url(f"{self.live_server_url}/admin/gallery/albumstacked/")
        expect(
            page.locator("td", has=title).locator(
                ".django-admin-tables-autosave-status"
            )
        ).to_have_text("Saved")
        album.refresh_from_db()
        assert album.title == "Summer"

        # Not valid: put back, saying why.
        title.fill("")
        title.press("Tab")
        expect(
            page.locator("td", has=title).locator(
                ".django-admin-tables-autosave-status"
            )
        ).to_have_text("This field is required.")
        expect(title).to_have_value("Summer")

        # Nothing unsaved: leaving asks nothing.
        dialogs = []
        page.on(
            "dialog", lambda dialog: (dialogs.append(dialog.type), dialog.dismiss())
        )
        page.goto(f"{self.live_server_url}/admin/")
        assert dialogs == []
        album.refresh_from_db()
        assert album.title == "Summer"
