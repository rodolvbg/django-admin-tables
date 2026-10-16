import django_admin_tables
from django_admin_tables import (
    AdminTablesMixin,
    ExclusiveRadioFieldsMixin,
    ForeignKeyLinkMixin,
)
from django_admin_tables.fk_links import UNFOLD_LINK_CLASS
from django_admin_tables.fk_links.mixins import ForeignKeyLinkMixin as LinksFromModule
from django_admin_tables.mixins import AdminTablesMixin as RowsFromModule
from django_admin_tables.radio_select import RadioCheckboxInput
from django_admin_tables.radio_select.formsets import (
    make_radio_select_exclusive_formset,
)
from django_admin_tables.radio_select.mixins import (
    ExclusiveRadioFieldsMixin as RadioFromModule,
)


def test_public_api_is_importable_from_top_level_package():
    assert ExclusiveRadioFieldsMixin is RadioFromModule
    assert ForeignKeyLinkMixin is LinksFromModule
    assert AdminTablesMixin is RowsFromModule
    assert django_admin_tables.__all__ == [
        "AdminTablesMixin",
        "ExclusiveRadioFieldsMixin",
        "FooterRowsMixin",
        "ForeignKeyLinkMixin",
        "HideableColumnsMixin",
        "RowActionsMixin",
        "row_action",
    ]


def test_package_exposes_a_version():
    assert isinstance(django_admin_tables.__version__, str)
    assert django_admin_tables.__version__


def test_internal_modules_are_importable():
    assert callable(make_radio_select_exclusive_formset)
    assert issubclass(RadioCheckboxInput, object)
    assert UNFOLD_LINK_CLASS
