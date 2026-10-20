import ast
import gettext
import re
from pathlib import Path
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import translation
from gallery.models import Album, Image

LOCALE_DIR = Path(__file__).parent.parent / "src/django_admin_tables/locale"
CATALOGS = sorted(LOCALE_DIR.glob("*/LC_MESSAGES/django.po"))


def po_entries(path):
    """``(msgid, [msgstr...], fuzzy)`` for every message of a .po file."""
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        msgid = re.search(r'^msgid "(.*)"', block, re.M)
        if not msgid or 'msgid ""\nmsgstr ""\n"' in block:
            continue
        yield (
            msgid.group(1),
            re.findall(r'^msgstr(?:\[\d+\])? "(.*)"$', block, re.M),
            "#, fuzzy" in block,
        )


PO_LINE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?) (".*")$')


def po_messages(path):
    """``{msgid: msgstr}`` (``{(msgid, n): msgstr}`` for plurals) of a .po file."""
    messages: dict[Any, str] = {}
    for block in path.read_text(encoding="utf-8").split("\n\n"):
        fields: dict[str, str] = {}
        key = None
        for line in block.splitlines():
            match = PO_LINE.match(line)
            if match:
                key = match.group(1)
                fields[key] = ast.literal_eval(match.group(2))
            elif line.startswith('"') and key:
                fields[key] += ast.literal_eval(line)
        msgid = fields.get("msgid")
        if not msgid or "#, fuzzy" in block:
            continue
        if "msgctxt" in fields:
            msgid = f"{fields['msgctxt']}\x04{msgid}"
        if "msgid_plural" in fields:
            for name, value in fields.items():
                if name.startswith("msgstr["):
                    messages[(msgid, int(name[7:-1]))] = value
        else:
            messages[msgid] = fields["msgstr"]
    return messages


def mo_messages(path):
    """The same, from the compiled .mo (as Django will load it)."""
    with path.open("rb") as file:
        catalog = getattr(gettext.GNUTranslations(file), "_catalog")  # noqa: B009
    return {key: value for key, value in catalog.items() if key != ""}


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda c: c.parent.parent.name)
def test_every_message_is_translated(catalog):
    problems = [
        msgid
        for msgid, msgstrs, fuzzy in po_entries(catalog)
        if fuzzy or not all(s.strip() for s in msgstrs)
    ]
    assert problems == []


@pytest.mark.parametrize("catalog", CATALOGS, ids=lambda c: c.parent.parent.name)
def test_compiled_catalog_is_up_to_date(catalog):
    """The shipped .mo has exactly the .po's translations (not compared by
    date: a git checkout gives both files arbitrary modification times)."""
    compiled = catalog.with_suffix(".mo")

    assert compiled.exists()
    assert mo_messages(compiled) == po_messages(catalog)


@pytest.fixture
def admin_client(django_user_model):
    user = django_user_model.objects.create_superuser("admin", "a@example.com", "x")
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def album(db):
    album = Album.objects.create(title="Alps")
    Image.objects.create(album=album, title="Peak", is_primary=True)
    return album


def test_changelist_in_spanish(admin_client, album):
    with translation.override("es"):
        response = admin_client.get(reverse("admin:gallery_image_changelist"))
    html = response.content.decode()

    assert "Columnas" in html
    assert "<legend>Mostrar columnas</legend>" in html
    assert "(pantalla estrecha)" in html
    assert ">Acciones<" in html
    assert ">Ver</a>" in html
    assert 'data-confirmation="¿Eliminar «Peak»? No se puede deshacer."' in html
    assert 'data-unsaved="Hay cambios sin guardar en esta página' in html
    assert 'data-failed="No se pudo ejecutar la acción."' in html


def test_row_action_messages_in_spanish(admin_client, album):
    peak = album.images.get()
    url = reverse("admin:gallery_image_row_action", args=[peak.pk, "delete"])
    with translation.override("es"):
        response = admin_client.post(
            url, headers={"x-requested-with": "XMLHttpRequest"}
        )

    assert response.json() == {"status": "done", "message": "Se eliminó «Peak»."}
