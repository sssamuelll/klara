"""scripts/backfill_portadas.py (spec §3.4): primero los textos, después una
imagen por escena distinta. --dry-run no escribe ni llama. Es idempotente."""

from __future__ import annotations

import argparse
import json
import sys
import uuid

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from klara.config import get_settings
from klara.llm.base import LLMResponse
from klara.models import Illustration, Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel
from klara.scripts.backfill_portadas import _informe, _run, backfill, main
from klara.services.illustration import illustration_hash

CONTENT = {
    "sentences": [
        {"target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho."},
    ]
}


class TextosLLM:
    def __init__(self, respuestas: list[str]) -> None:
        self.respuestas = list(respuestas)
        self.llamadas = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.llamadas += 1
        return LLMResponse(
            content=self.respuestas.pop(0), model="fake", provider="fake", cost_usd=0.0001
        )

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


class Ilustrador:
    """ensure_illustration falso: guarda una fila por escena y cuenta las llamadas."""

    def __init__(self) -> None:
        self.escenas: list[str] = []

    async def __call__(self, db, scene, *, settings):
        self.escenas.append(scene)
        h = illustration_hash(scene)
        db.add(
            Illustration(
                hash=h,
                scene=scene,
                style_version=1,
                model="fake",
                mime_type="image/jpeg",
                image_data=b"x",
                size_bytes=1,
            )
        )
        await db.flush()
        return h


def _textos(sub: str, scene: str) -> str:
    return json.dumps({"subtitle": sub, "scene": scene})


async def _sembrar(db):
    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Ana",
        level=CEFRLevel.A2,
        native_language="es",
        target_language="de",
    )
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A2,
        sequence_order=1,
        title="En la panadería",
        can_dos=[],
        grammatical_focus=[],
    )
    db.add_all([user, module])
    await db.flush()
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A2,
        title="Die Bäckerei",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash="7" * 64,
    )
    db.add(entry)
    await db.flush()
    clon = Story(
        user_id=user.id,
        level=CEFRLevel.A2,
        target_language="de",
        native_language="es",
        title="Die Bäckerei",
        content=CONTENT,
        target_vocab_item_ids=[],
        module_id=module.id,
        library_source_id=entry.id,
    )
    propia = Story(
        user_id=user.id,
        level=CEFRLevel.A2,
        target_language="de",
        native_language="es",
        title="Mein Hund",
        content=CONTENT,
        target_vocab_item_ids=[],
    )
    db.add_all([clon, propia])
    await db.commit()
    return entry, clon, propia


async def _correr(db, llm, ilustrador, *, dry_run=False, only_library=False):
    return await backfill(
        db,
        llm,
        settings=get_settings(),
        dry_run=dry_run,
        limit=None,
        only_library=only_library,
        illustrate=ilustrador,
    )


@pytest.mark.asyncio
async def test_dry_run_no_escribe_ni_llama(db_session):
    entry, _, _ = await _sembrar(db_session)
    llm, ilustrador = TextosLLM([]), Ilustrador()
    stats = await _correr(db_session, llm, ilustrador, dry_run=True)
    assert (llm.llamadas, ilustrador.escenas) == (0, [])
    assert (stats["library_texts"], stats["own_texts"], stats["images_max"]) == (1, 1, 2)
    await db_session.refresh(entry)
    assert (entry.subtitle, entry.scene) == (None, None)


@pytest.mark.asyncio
async def test_corrida_real_y_segunda_vuelta(db_session):
    entry, clon, propia = await _sembrar(db_session)
    llm = TextosLLM(
        [
            _textos("Una panadería.", "A small bakery at dawn."),
            _textos("Mi perro.", "A dog in a park."),
        ]
    )
    ilustrador = Ilustrador()
    stats = await _correr(db_session, llm, ilustrador)
    for fila in (entry, clon, propia):
        await db_session.refresh(fila)
    assert (entry.subtitle, entry.scene) == ("Una panadería.", "A small bakery at dawn.")
    assert (clon.subtitle, clon.scene) == ("Una panadería.", "A small bakery at dawn.")  # sin LLM
    assert (propia.subtitle, propia.scene) == ("Mi perro.", "A dog in a park.")
    assert llm.llamadas == 2
    assert sorted(ilustrador.escenas) == ["A dog in a park.", "A small bakery at dawn."]
    assert (stats["images"], stats["failed"]) == (2, 0)

    segunda = await _correr(db_session, TextosLLM([]), Ilustrador())
    assert (segunda["library_texts"], segunda["own_texts"], segunda["images"]) == (0, 0, 0)


@pytest.mark.asyncio
async def test_json_invalido_no_frena_a_las_demas(db_session):
    _, _, propia = await _sembrar(db_session)
    llm = TextosLLM(["esto no es json", _textos("Mi perro.", "A dog in a park.")])
    stats = await _correr(db_session, llm, Ilustrador())
    await db_session.refresh(propia)
    assert stats["failed"] == 1
    assert propia.scene == "A dog in a park."


@pytest.mark.asyncio
async def test_only_library_no_toca_historias(db_session):
    _, clon, propia = await _sembrar(db_session)
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn.")])
    await _correr(db_session, llm, Ilustrador(), only_library=True)
    await db_session.refresh(clon)
    await db_session.refresh(propia)
    assert (clon.scene, propia.scene) == (None, None)


# De aquí en adelante: lo que el spec §3.4 promete y las cuatro pruebas de arriba no
# fijan. El tope (--limit), lo que queda confirmado al momento, el alcance de cada
# opción y que el informe se pueda imprimir.


class IlustradorSinSuerte(Ilustrador):
    """Devuelve None (Gemini falló, o no hay clave) para las escenas de `caidas`."""

    def __init__(self, caidas: set[str]) -> None:
        super().__init__()
        self.caidas = caidas

    async def __call__(self, db, scene, *, settings):
        if scene in self.caidas:
            self.escenas.append(scene)
            return None
        return await super().__call__(db, scene, settings=settings)


@pytest.mark.asyncio
async def test_limit_topa_las_llamadas_y_las_imagenes(db_session):
    entry, _, propia = await _sembrar(db_session)
    db_session.add_all(
        [
            StoryLibrary(
                module_id=entry.module_id,
                language="de",
                native_language="es",
                level=CEFRLevel.A2,
                title="Der Markt",
                content=CONTENT,
                target_vocab_item_ids=[],
                source="seed",
                content_hash="8" * 64,
            ),
            Story(
                user_id=propia.user_id,
                level=CEFRLevel.A2,
                target_language="de",
                native_language="es",
                title="Meine Katze",
                content=CONTENT,
                target_vocab_item_ids=[],
            ),
        ]
    )
    await db_session.commit()
    llm = TextosLLM(
        [
            _textos("Una panadería.", "A small bakery at dawn."),
            _textos("Mi perro.", "A dog in a park."),
        ]
    )
    ilustrador = Ilustrador()
    stats = await backfill(
        db_session,
        llm,
        settings=get_settings(),
        dry_run=False,
        limit=1,
        only_library=False,
        illustrate=ilustrador,
    )
    # Hay dos entradas y dos historias propias sin textos, y saldrían dos escenas
    # distintas por dibujar: con --limit 1 sale una llamada por fase y una sola imagen.
    assert (llm.llamadas, stats["library_texts"], stats["own_texts"]) == (2, 1, 1)
    assert (len(ilustrador.escenas), stats["images"]) == (1, 1)


@pytest.mark.asyncio
async def test_una_imagen_que_falla_se_cuenta_y_la_siguiente_corrida_la_reintenta(
    db_session, db_engine
):
    await _sembrar(db_session)
    llm = TextosLLM(
        [
            _textos("Una panadería.", "A small bakery at dawn."),
            _textos("Mi perro.", "A dog in a park."),
        ]
    )
    stats = await _correr(db_session, llm, IlustradorSinSuerte({"A dog in a park."}))
    assert (stats["images"], stats["failed"]) == (1, 1)
    # Lo dibujado ya está confirmado: una conexión aparte lo ve, y lo que falló no dejó fila.
    async with db_engine.connect() as otra:
        guardadas = set((await otra.execute(select(Illustration.hash))).scalars())
    assert guardadas == {illustration_hash("A small bakery at dawn.")}

    ilustrador = Ilustrador()
    segunda = await _correr(db_session, TextosLLM([]), ilustrador)
    assert ilustrador.escenas == ["A dog in a park."]
    assert (segunda["images"], segunda["failed"]) == (1, 0)


@pytest.mark.asyncio
async def test_los_textos_quedan_confirmados_aunque_no_salga_ninguna_imagen(db_session, db_engine):
    # Sin GEMINI_API_KEY ensure_illustration devuelve None para todo: lo pagado en la fase 1
    # no puede depender de que la fase 2 confirme algo.
    await _sembrar(db_session)
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn.")])
    sin_suerte = IlustradorSinSuerte({"A small bakery at dawn."})
    stats = await _correr(db_session, llm, sin_suerte, only_library=True)
    assert (stats["images"], stats["failed"]) == (0, 1)
    async with db_engine.connect() as otra:
        fila = (await otra.execute(select(StoryLibrary.subtitle, StoryLibrary.scene))).one()
    assert tuple(fila) == ("Una panadería.", "A small bakery at dawn.")


@pytest.mark.asyncio
async def test_una_respuesta_sin_escena_es_un_fallo_y_no_guarda_nada_a_medias(db_session):
    _, _, propia = await _sembrar(db_session)
    sin_escena = json.dumps({"subtitle": "Mi perro."})
    stats = await _correr(db_session, TextosLLM([sin_escena, sin_escena]), Ilustrador())
    await db_session.refresh(propia)
    assert (propia.subtitle, propia.scene) == (None, None)  # el próximo intento pide los dos
    assert (stats["failed"], stats["own_texts"], stats["images"]) == (2, 0, 0)


@pytest.mark.asyncio
async def test_completa_lo_que_falta_sin_pisar_lo_que_ya_hay(db_session):
    entry, _, _ = await _sembrar(db_session)
    entry.scene = "A bakery seen from the street."  # ya tiene escena (y quizá su imagen)
    await db_session.commit()
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn.")])
    await _correr(db_session, llm, Ilustrador(), only_library=True)
    await db_session.refresh(entry)
    assert (entry.subtitle, entry.scene) == ("Una panadería.", "A bakery seen from the street.")


@pytest.mark.asyncio
async def test_en_seco_tampoco_copia_los_textos_a_los_clones(db_session):
    entry, clon, _ = await _sembrar(db_session)
    entry.subtitle, entry.scene = "Una panadería.", "A small bakery at dawn."
    await db_session.commit()
    stats = await _correr(db_session, TextosLLM([]), Ilustrador(), dry_run=True)
    await db_session.refresh(clon)
    assert (clon.subtitle, clon.scene, stats["cloned_texts"]) == (None, None, 0)


@pytest.mark.asyncio
async def test_only_library_tampoco_dibuja_las_escenas_de_las_historias(db_session):
    entry, _, propia = await _sembrar(db_session)
    entry.subtitle, entry.scene = "Una panadería.", "A small bakery at dawn."
    propia.subtitle, propia.scene = "Mi perro.", "A dog in a park."
    await db_session.commit()
    ilustrador = Ilustrador()
    await _correr(db_session, TextosLLM([]), ilustrador, only_library=True)
    assert ilustrador.escenas == ["A small bakery at dawn."]


def test_el_informe_cabe_en_cp1252_y_cuenta_el_costo():
    """Un signo fuera de cp1252 reventaría con UnicodeEncodeError al final de una corrida
    ya pagada, si la consola de quien la corre no es UTF-8."""
    stats = {
        "library_texts": 1,
        "cloned_texts": 1,
        "own_texts": 1,
        "images": 2,
        "images_max": 3,
        "failed": 0,
    }
    en_seco = _informe(stats, dry_run=True)
    real = _informe(stats, dry_run=False)
    en_seco.encode("cp1252")
    real.encode("cp1252")
    assert "$0.21" in en_seco  # 3 imágenes a $0.069
    assert "$0.14" in real  # 2 imágenes a $0.069


# Las entradas retiradas (is_active = false) no se sirven nunca: no reciben textos
# ni imagen. Y la clave de Gemini: sin ella una corrida real no empieza.


def _retirada(entry: StoryLibrary, **kw) -> StoryLibrary:
    return StoryLibrary(
        module_id=entry.module_id,
        language="de",
        native_language="es",
        level=CEFRLevel.A2,
        title="Der Kiosk",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash="6" * 64,
        is_active=False,
        **kw,
    )


@pytest.mark.asyncio
async def test_una_entrada_retirada_no_recibe_textos(db_session):
    entry, _, _ = await _sembrar(db_session)
    retirada = _retirada(entry)
    db_session.add(retirada)
    await db_session.commit()

    en_seco = await _correr(
        db_session, TextosLLM([]), Ilustrador(), dry_run=True, only_library=True
    )
    assert (en_seco["library_texts"], en_seco["images_max"]) == (1, 1)

    # Con una sola respuesta preparada: si también fuera por la retirada, su llamada
    # no tendría respuesta y saldría como fallo.
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn.")])
    stats = await _correr(db_session, llm, Ilustrador(), only_library=True)
    assert (llm.llamadas, stats["library_texts"], stats["failed"]) == (1, 1, 0)
    await db_session.refresh(retirada)
    assert (retirada.subtitle, retirada.scene) == (None, None)


@pytest.mark.asyncio
async def test_la_escena_de_una_entrada_retirada_no_se_dibuja(db_session):
    entry, _, _ = await _sembrar(db_session)
    entry.subtitle, entry.scene = "Una panadería.", "A small bakery at dawn."
    db_session.add(_retirada(entry, subtitle="Un quiosco.", scene="A kiosk at night."))
    await db_session.commit()

    en_seco = await _correr(
        db_session, TextosLLM([]), Ilustrador(), dry_run=True, only_library=True
    )
    assert en_seco["images_max"] == 1
    ilustrador = Ilustrador()
    await _correr(db_session, TextosLLM([]), ilustrador, only_library=True)
    assert ilustrador.escenas == ["A small bakery at dawn."]


class _AbrioLaBase(Exception):
    """`init_engine` es lo primero que hace _run tras la comprobación de la clave."""


def _con_clave(monkeypatch, clave: str | None) -> None:
    settings = get_settings().model_copy(
        update={"gemini_api_key": SecretStr(clave) if clave else None}
    )
    monkeypatch.setattr("klara.scripts.backfill_portadas.get_settings", lambda: settings)

    def abrir_la_base(_settings):
        raise _AbrioLaBase

    monkeypatch.setattr("klara.scripts.backfill_portadas.init_engine", abrir_la_base)


def _args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**{"dry_run": False, "limit": None, "only_library": False, **kw})


@pytest.mark.asyncio
async def test_sin_clave_una_corrida_real_se_niega_antes_de_empezar(monkeypatch, capsys):
    """Sin GEMINI_API_KEY la fase 1 pagaría los textos y la fase 2 fallaría en cada escena
    sin decir por qué: se dice aquí, con código de salida distinto de cero."""
    _con_clave(monkeypatch, None)
    assert await _run(_args()) == 1  # no llegó a abrir la base: si no, saltaría _AbrioLaBase
    salida = capsys.readouterr()
    assert "GEMINI_API_KEY" in salida.err
    assert salida.out == ""
    salida.err.encode("cp1252")  # la consola de Windows no admite más


def test_sin_clave_el_proceso_sale_con_1(monkeypatch):
    """Lo que ve quien lo corre en la caja es el código de salida de `main`, no el de `_run`."""
    _con_clave(monkeypatch, None)
    monkeypatch.setattr(sys, "argv", ["backfill_portadas"])
    with pytest.raises(SystemExit) as salida:
        main()
    assert salida.value.code == 1


@pytest.mark.asyncio
async def test_con_clave_la_corrida_real_empieza(monkeypatch):
    _con_clave(monkeypatch, "k")
    with pytest.raises(_AbrioLaBase):
        await _run(_args())


@pytest.mark.asyncio
@pytest.mark.parametrize("clave, dice", [("k", "presente"), (None, "ausente")])
async def test_en_seco_dice_si_la_clave_esta_y_no_se_frena(monkeypatch, capsys, clave, dice):
    _con_clave(monkeypatch, clave)
    with pytest.raises(_AbrioLaBase):
        await _run(_args(dry_run=True))
    assert f"GEMINI_API_KEY: {dice}" in capsys.readouterr().out
