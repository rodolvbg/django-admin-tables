import django_admin_rows
from django_admin_rows import ExclusiveRadioFieldsMixin, ForeignKeyLinkMixin
from django_admin_rows.fk_links import UNFOLD_LINK_CLASS
from django_admin_rows.fk_links.mixins import ForeignKeyLinkMixin as LinksFromModule
from django_admin_rows.radio_select import RadioCheckboxInput
from django_admin_rows.radio_select.formsets import make_radio_select_exclusive_formset
from django_admin_rows.radio_select.mixins import (
    ExclusiveRadioFieldsMixin as RadioFromModule,
)


def test_public_api_is_importable_from_top_level_package():
    assert ExclusiveRadioFieldsMixin is RadioFromModule
    assert ForeignKeyLinkMixin is LinksFromModule
    assert django_admin_rows.__all__ == [
        "ExclusiveRadioFieldsMixin",
        "ForeignKeyLinkMixin",
    ]


def test_package_exposes_a_version():
    assert isinstance(django_admin_rows.__version__, str)
    assert django_admin_rows.__version__


def test_internal_modules_are_importable():
    assert callable(make_radio_select_exclusive_formset)
    assert issubclass(RadioCheckboxInput, object)
    assert UNFOLD_LINK_CLASS
