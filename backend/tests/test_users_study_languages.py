"""`study_languages` en /me (spec 2026-10-09 §2.2 y §5.6)."""

import pytest

from tests.ayudas import entrar

EMAIL = "idiomas@example.com"


async def _me(client, h) -> dict:
    r = await client.get("/api/v1/me", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_sin_elegir_vale_el_idioma_de_estudio_si_tiene_mapa(
    client, seed_invite, catalogo_mini
):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    assert (await _me(client, h))["study_languages"] == []  # «de» todavía no tiene mapa


async def test_elegir_japones(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    r = await client.patch("/api/v1/me", json={"study_languages": ["ja"]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["study_languages"] == ["ja"]
    assert (await _me(client, h))["study_languages"] == ["ja"]


@pytest.mark.parametrize("valor", [["fr"], ["xx"], [], ["ja", "ja"], ["ja", "de", "en", "fr"]])
async def test_lo_que_no_vale_es_422(client, seed_invite, catalogo_mini, valor):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    r = await client.patch("/api/v1/me", json={"study_languages": valor}, headers=h)
    assert r.status_code == 422, valor


async def test_null_vuelve_al_idioma_de_estudio(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    await client.patch("/api/v1/me", json={"study_languages": ["ja"]}, headers=h)
    await client.patch("/api/v1/me", json={"target_language": "ja"}, headers=h)
    r = await client.patch("/api/v1/me", json={"study_languages": None}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["study_languages"] == ["ja"]  # sale de target_language


async def test_null_borra_lo_elegido(client, seed_invite, catalogo_mini):
    # El test de arriba no distingue «null borra» de «null se ignora»: ahí lo
    # elegido y el idioma de estudio coinciden. Aquí el de estudio («de») no
    # tiene mapa, así que solo borrar deja la lista vacía.
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    await client.patch("/api/v1/me", json={"study_languages": ["ja"]}, headers=h)
    r = await client.patch("/api/v1/me", json={"study_languages": None}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["study_languages"] == []


async def test_un_422_no_aplica_el_resto_a_medias(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    antes = await _me(client, h)
    # «fr» es un código válido, pero sin mapa: lo rechaza la ruta, ya con otros campos asignados.
    r = await client.patch(
        "/api/v1/me", json={"display_name": "Otro nombre", "study_languages": ["fr"]}, headers=h
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "study_languages.sin_mapa"
    assert await _me(client, h) == antes
