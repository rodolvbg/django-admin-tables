"""SelectableRowsMixin: rows that can't be selected for an action."""

import re

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from gallery.models import Album, Image

from django_admin_tables import SelectableRowsMixin
from django_admin_tables.selection import UNSELECTABLE_CLASS, disable_checkbox


class TestSelectableRows(TestCase):
    """The example's ImageAdmin: an album's primary image can't be selected."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        cls.album = Album.objects.create(title="Winter")
        cls.primary = Image.objects.create(
            album=cls.album, title="Cover", is_primary=True
        )
        cls.others = [
            Image.objects.create(album=cls.album, title=f"Photo {n}") for n in (1, 2)
        ]

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:gallery_image_changelist")

    def checkbox(self, html, image):
        return re.search(rf'<input[^>]*(value="{image.pk}"|title="[^"]*")[^>]*>', html)

    def test_the_checkbox_of_a_row_that_cant_be_selected(self):
        html = self.client.get(self.url).content.decode()

        disabled = re.findall(
            rf'<input[^>]*class="[^"]*{UNSELECTABLE_CLASS}[^"]*"[^>]*>', html
        )
        assert len(disabled) == 1
        [box] = disabled
        assert " disabled" in box
        assert (
            'title="The album&#x27;s primary image: choose another one first."' in box
        )
        assert ACTION_CHECKBOX_NAME not in box
        assert "action-select" not in box
        assert f'value="{self.primary.pk}"' in box
        # The others, as the admin renders them; the header's "select all" too.
        selectable = re.findall(r'<input[^>]*class="action-select"[^>]*>', html)
        assert len(selectable) == 2
        assert 'id="action-toggle"' in html

    def test_actions_leave_them_out(self):
        response = self.client.post(
            self.url,
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [str(self.primary.pk), str(self.others[0].pk)],
                "post": "yes",
            },
            follow=True,
        )

        assert list(Image.objects.order_by("pk")) == [self.primary, self.others[1]]
        assert (
            "1 image was left out: it can&#x27;t be selected."
            in response.content.decode()
        )

    def test_select_across_leaves_them_out(self):
        response = self.client.post(
            self.url,
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [str(self.others[0].pk)],
                "select_across": "1",
                "post": "yes",
            },
            follow=True,
        )
        assert list(Image.objects.all()) == [self.primary]
        assert "1 image was left out" in response.content.decode()

    def test_nothing_left_no_action(self):
        response = self.client.post(
            self.url,
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [str(self.primary.pk)],
                "post": "yes",
            },
            follow=True,
        )
        assert Image.objects.count() == 3
        html = response.content.decode()
        assert "1 image was left out" in html
        assert "Successfully deleted" not in html

    def test_two_left_out(self):
        other = Image.objects.create(album=self.album, title="Back", is_primary=True)
        response = self.client.post(
            self.url,
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [
                    str(self.primary.pk),
                    str(other.pk),
                    str(self.others[0].pk),
                ],
                "post": "yes",
            },
            follow=True,
        )
        assert (
            "2 images were left out: they can&#x27;t be selected."
            in response.content.decode()
        )

    def test_actions_keep_their_shape(self):
        model_admin = admin.site._registry[Image]
        request = RequestFactory().get("/")
        request.user = self.user
        [delete] = model_admin.get_actions(request).values()
        assert getattr(delete, "name", None) or delete[1] == "delete_selected"
        assert model_admin.wrap_action((lambda *a: None, "x", "X"))[1:] == ("x", "X")

    def test_nothing_left_out_nothing_said(self):
        response = self.client.post(
            self.url,
            {
                "action": "delete_selected",
                ACTION_CHECKBOX_NAME: [str(self.others[0].pk)],
                "post": "yes",
            },
            follow=True,
        )
        html = response.content.decode()
        assert "left out" not in html
        assert "Successfully deleted 1 image." in html

    def test_actions_without_a_location(self):
        """Django < 6.1 asks for them without one."""
        model_admin = admin.site._registry[Image]
        request = RequestFactory().get("/")
        request.user = self.user
        assert list(model_admin.get_actions(request, action_location=None)) == [
            "delete_selected"
        ]


class PlainAdmin(SelectableRowsMixin, admin.ModelAdmin):
    """Every row selectable (the defaults)."""


class OddAdmin(SelectableRowsMixin, admin.ModelAdmin):
    """Rows chosen object by object, without a reason, nor a filter."""

    def is_row_selectable(self, request, obj):
        return obj.pk % 2 == 1


class TestDefaults(TestCase):
    @classmethod
    def setUpTestData(cls):
        album = Album.objects.create(title="A")
        cls.images = [Image.objects.create(album=album, title=str(n)) for n in range(4)]

    def test_by_default_every_row(self):
        model_admin = PlainAdmin(Image, admin.site)
        request = RequestFactory().get("/")
        assert model_admin.is_row_selectable(request, self.images[0]) is True
        assert model_admin.get_row_unselectable_reason(request, self.images[0]) is None
        queryset = Image.objects.all()
        assert (
            list(model_admin.filter_selectable_rows(request, queryset)) == self.images
        )
        # The admin's own column: its header, and an object never annotated.
        checkbox = model_admin.action_checkbox
        # Its attributes (the header of Django < 6.1, Unfold's) are kept.
        parent = admin.ModelAdmin.action_checkbox
        assert vars(checkbox).items() >= vars(parent).items()
        assert 'class="action-select"' in checkbox(self.images[0])

    def test_object_by_object(self):
        model_admin = OddAdmin(Image, admin.site)
        request = RequestFactory().get("/")
        selectable = model_admin.filter_selectable_rows(request, Image.objects.all())
        assert list(selectable.order_by("pk")) == [
            i for i in self.images if i.pk % 2 == 1
        ]

    def test_without_a_reason(self):
        html = disable_checkbox(
            '<input type="checkbox" name="_selected_action" value="2"'
            ' class="action-select x">',
            "",
        )
        expected = (
            f'<input disabled type="checkbox" value="2" class="{UNSELECTABLE_CLASS} x">'
        )
        assert html == expected


class TestUnfold(TestCase):
    """Unfold's checkbox (its own classes, its header) disabled the same way."""

    def test_unfolds_checkbox(self):
        unfold_admin = __import__("pytest").importorskip("unfold.admin")

        class UnfoldImageAdmin(SelectableRowsMixin, unfold_admin.ModelAdmin):
            def is_row_selectable(self, request, obj):
                return False

        model_admin = UnfoldImageAdmin(Image, admin.site)
        image = Image(pk=7, title="Cover")
        image._django_admin_tables_unselectable = "No."
        checkbox = model_admin.action_checkbox
        parent = unfold_admin.ModelAdmin.action_checkbox
        assert vars(checkbox).items() >= vars(parent).items()
        html = checkbox(image)
        assert " disabled" in html
        assert 'title="No."' in html
        assert UNSELECTABLE_CLASS in html
        assert "action-select" not in html
        # Its own look kept: the classes of Unfold's checkbox.
        own = re.search(r'class="([^"]*)"', parent(model_admin, image)).group(1).split()
        assert set(own) - {"action-select"} <= set(
            re.search(r'class="([^"]*)"', html).group(1).split()
        )
