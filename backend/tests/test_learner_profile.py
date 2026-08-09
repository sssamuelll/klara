"""Contrato del Perfil de Aprendizaje (F1.5) — los 11 puntos del gate cerrado.

Estos tests SON la spec ejecutable: cada uno cita el contrato que defiende.
Lo que se prueba acá es el contrato del servidor; la medición de `timings`
vive en el cliente y se prueba en vitest.
"""

import pytest
from sqlalchemy import select

from klara.models import LearnerProfile

pytestmark = pytest.mark.anyio

URL = "/api/v1/me/learning-profile"


async def _register_and_login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


def _h(cookie: str) -> dict:
    return {"Cookie": cookie}


# --------------------------------------------------------------------------
# Auth (gate 6) y ausencia (gate 1)
# --------------------------------------------------------------------------


async def test_requires_auth(client):
    """Los endpoints van tras la auth de cookie existente, como el resto de /me."""
    assert (await client.get(URL)).status_code == 401
    assert (await client.put(URL, json={"answers": {}, "timings": {}})).status_code == 401


async def test_get_404_when_never_saved(client, seed_invite):
    """«No existe» no se disfraza de «existe vacío»: los defaults viven en la
    generación, no en el read path (gate 1)."""
    cookie = await _register_and_login(client, seed_invite, "lp404@example.com")
    r = await client.get(URL, headers=_h(cookie))
    assert r.status_code == 404


# --------------------------------------------------------------------------
# Guardado, versionado y frescura de derivados (gate 4, 7)
# --------------------------------------------------------------------------


async def test_first_put_creates_version_1_without_expected_version(client, seed_invite):
    """expected_version es obligatorio SALVO en la creación."""
    cookie = await _register_and_login(client, seed_invite, "lp1@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"ses_duracion": "10 minutos"}, "timings": {"ses_duracion": 4200}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["answers"]["ses_duracion"] == "10 minutos"
    assert body["timings"]["ses_duracion"] == 4200


async def test_put_is_full_replacement_not_merge(client, seed_invite):
    """PUT es reemplazo completo: lo que no viene, desaparece. Así «borrar una
    respuesta» es expresable sin un DELETE por pregunta."""
    cookie = await _register_and_login(client, seed_invite, "lp2@example.com")
    await client.put(
        URL,
        headers=_h(cookie),
        json={
            "answers": {"ses_duracion": "10 minutos", "entrada_reto": "Fácil, y que suba"},
            "timings": {"ses_duracion": 1000, "entrada_reto": 2000},
        },
    )
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"entrada_reto": "Rétame de una vez"}, "timings": {"entrada_reto": 900}},
        params={"expected_version": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "ses_duracion" not in body["answers"], "el merge silencioso está prohibido"
    assert body["timings"] == {"entrada_reto": 900}
    assert body["version"] == 2


async def test_stale_expected_version_conflicts(client, seed_invite):
    """Concurrencia: expected_version desalineado → 409, nunca pisar en silencio."""
    cookie = await _register_and_login(client, seed_invite, "lp3@example.com")
    await client.put(URL, headers=_h(cookie), json={"answers": {}, "timings": {}})
    await client.put(
        URL, headers=_h(cookie), json={"answers": {}, "timings": {}}, params={"expected_version": 1}
    )
    r = await client.put(
        URL, headers=_h(cookie), json={"answers": {}, "timings": {}}, params={"expected_version": 1}
    )
    assert r.status_code == 409, r.text


async def test_new_answers_mark_derived_stale(client, seed_invite, db_session):
    """derived_for_version < version ⇒ la síntesis mostrada es vieja. Guardar
    de nuevo NO puede dejar una síntesis vieja declarándose fresca."""
    cookie = await _register_and_login(client, seed_invite, "lp4@example.com")
    await client.put(URL, headers=_h(cookie), json={"answers": {}, "timings": {}})

    row = (await db_session.execute(select(LearnerProfile))).scalar_one()
    row.synthesis = "prosa vieja"
    row.facts = {"abandono_por": "video largo"}
    row.derived_for_version = 1
    await db_session.commit()

    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"ses_duracion": "3 minutos"}, "timings": {}},
        params={"expected_version": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 2
    assert body["derived_for_version"] == 1, "la marca vieja no se toca al guardar"
    assert body["stale"] is True, "el cliente necesita saberlo sin comparar números"


# --------------------------------------------------------------------------
# Esquema canónico (gate 2) — allow-list, cardinalidad, condicionales
# --------------------------------------------------------------------------


async def test_unknown_question_id_is_422(client, seed_invite):
    """Clave desconocida = cliente desactualizado o bug. Se rechaza, no se
    ignora en silencio."""
    cookie = await _register_and_login(client, seed_invite, "lp5@example.com")
    r = await client.put(
        URL, headers=_h(cookie), json={"answers": {"pregunta_inventada": "x"}, "timings": {}}
    )
    assert r.status_code == 422, r.text


async def test_value_outside_option_list_is_422(client, seed_invite):
    """El valor tiene que ser una de las opciones declaradas."""
    cookie = await _register_and_login(client, seed_invite, "lp6@example.com")
    r = await client.put(
        URL, headers=_h(cookie), json={"answers": {"ses_duracion": "45 minutos"}, "timings": {}}
    )
    assert r.status_code == 422, r.text


async def test_null_is_a_valid_skip(client, seed_invite):
    """null = la vio y la saltó. Es dato, no ausencia."""
    cookie = await _register_and_login(client, seed_invite, "lp7@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"ses_duracion": None}, "timings": {"ses_duracion": 800}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["answers"]["ses_duracion"] is None


async def test_radio_rejects_list_and_checkbox_rejects_scalar(client, seed_invite):
    """Cardinalidad por control."""
    cookie = await _register_and_login(client, seed_invite, "lp8@example.com")
    r1 = await client.put(
        URL, headers=_h(cookie), json={"answers": {"ses_duracion": ["3 minutos"]}, "timings": {}}
    )
    assert r1.status_code == 422, r1.text
    r2 = await client.put(
        URL, headers=_h(cookie), json={"answers": {"ses_lugar": "En casa"}, "timings": {}}
    )
    assert r2.status_code == 422, r2.text


async def test_empty_checkbox_list_is_allowed(client, seed_invite):
    """[] = la abrió y la dejó vacía. Distinto de null, y se guarda distinto."""
    cookie = await _register_and_login(client, seed_invite, "lp9@example.com")
    r = await client.put(
        URL, headers=_h(cookie), json={"answers": {"ses_lugar": []}, "timings": {}}
    )
    assert r.status_code == 200, r.text
    assert r.json()["answers"]["ses_lugar"] == []


async def test_negation_option_is_exclusive(client, seed_invite):
    """`Las fichas no me funcionan` no coexiste con ninguna otra (gate 9).
    Se bloquea en UI y también acá: el servidor no confía en el cliente."""
    cookie = await _register_and_login(client, seed_invite, "lp10@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={
            "answers": {"fija_fichas": ["Término y significado", "Las fichas no me funcionan"]},
            "timings": {},
        },
    )
    assert r.status_code == 422, r.text


async def test_negation_alone_is_valid(client, seed_invite):
    cookie = await _register_and_login(client, seed_invite, "lp11@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"fija_fichas": ["Las fichas no me funcionan"]}, "timings": {}},
    )
    assert r.status_code == 200, r.text


async def test_otra_text_requires_its_option_selected(client, seed_invite):
    """`hist_exito_otra` solo es válida si `hist_exito == "Otra cosa"`."""
    cookie = await _register_and_login(client, seed_invite, "lp12@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={
            "answers": {"hist_exito": "Explicándoselo a otro", "hist_exito_otra": "a la fuerza"},
            "timings": {},
        },
    )
    assert r.status_code == 422, r.text

    r2 = await client.put(
        URL,
        headers=_h(cookie),
        json={
            "answers": {"hist_exito": "Otra cosa", "hist_exito_otra": "a la fuerza"},
            "timings": {},
        },
    )
    assert r2.status_code == 200, r2.text


async def test_triage_accepts_only_known_methods_and_verdicts(client, seed_invite):
    """hist_metodos es {método: "sirve"|"no"} con claves de la lista cerrada."""
    cookie = await _register_and_login(client, seed_invite, "lp13@example.com")
    ok = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"hist_metodos": {"Fichas de repaso": "sirve"}}, "timings": {}},
    )
    assert ok.status_code == 200, ok.text

    bad_key = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"hist_metodos": {"Telepatía": "sirve"}}, "timings": {}},
        params={"expected_version": 1},
    )
    assert bad_key.status_code == 422, bad_key.text

    bad_val = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"hist_metodos": {"Fichas de repaso": "quizá"}}, "timings": {}},
        params={"expected_version": 1},
    )
    assert bad_val.status_code == 422, bad_val.text


async def test_text_length_limits(client, seed_invite):
    """hist_*_otra ≤200, libre_texto ≤1000."""
    cookie = await _register_and_login(client, seed_invite, "lp14@example.com")
    r = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {"hist_exito": "Otra cosa", "hist_exito_otra": "x" * 201}, "timings": {}},
    )
    assert r.status_code == 422, r.text

    r2 = await client.put(
        URL, headers=_h(cookie), json={"answers": {"libre_texto": "y" * 1001}, "timings": {}}
    )
    assert r2.status_code == 422, r2.text


async def test_timings_are_clamped_and_keys_validated(client, seed_invite):
    """Tope duro de 300000 ms; por encima es ruido. Clave de timing que no es
    pregunta = 422 (mismo criterio que answers)."""
    cookie = await _register_and_login(client, seed_invite, "lp15@example.com")
    r = await client.put(
        URL, headers=_h(cookie), json={"answers": {}, "timings": {"ses_duracion": 999999}}
    )
    assert r.status_code == 200, r.text
    assert r.json()["timings"]["ses_duracion"] == 300000

    r2 = await client.put(
        URL,
        headers=_h(cookie),
        json={"answers": {}, "timings": {"no_existe": 10}},
        params={"expected_version": 1},
    )
    assert r2.status_code == 422, r2.text


# --------------------------------------------------------------------------
# Estado del perfil (gate 10) — «Completo» atado a las 8 de consumo
# --------------------------------------------------------------------------

_CONSUMO_OK = {
    "ses_duracion": "10 minutos",
    "ses_lugar": ["En casa"],
    "fija_fichas": ["Término y significado"],
    "error_correccion": "Directa y al momento",
    "entrada_interes": "Que me sirva ya para algo",
    "entrada_reto": "Fácil, y que suba",
    "error_atasco": "Explícamelo distinto",
    "error_pista": "Depende del día",
}


async def test_completo_requires_only_the_eight_consumption_questions(client, seed_invite):
    """Completo NO es 23/23: se ata a las 8 que cambian el comportamiento.
    Contar saltos convertiría la fila en un reproche (D-A, sin guilt)."""
    cookie = await _register_and_login(client, seed_invite, "lp16@example.com")
    r = await client.put(URL, headers=_h(cookie), json={"answers": _CONSUMO_OK, "timings": {}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completo"


async def test_missing_one_consumption_question_is_a_medias(client, seed_invite):
    cookie = await _register_and_login(client, seed_invite, "lp17@example.com")
    partial = dict(_CONSUMO_OK)
    partial["error_pista"] = None
    r = await client.put(URL, headers=_h(cookie), json={"answers": partial, "timings": {}})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "a_medias"


async def test_empty_checkbox_does_not_count_as_answered(client, seed_invite):
    """[] en una pregunta de consumo no completa el perfil."""
    cookie = await _register_and_login(client, seed_invite, "lp18@example.com")
    partial = dict(_CONSUMO_OK)
    partial["ses_lugar"] = []
    r = await client.put(URL, headers=_h(cookie), json={"answers": partial, "timings": {}})
    assert r.json()["status"] == "a_medias"


# --------------------------------------------------------------------------
# facts: allow-list cerrada (corrección propia de la enmienda)
# --------------------------------------------------------------------------


async def test_facts_allowlist_drops_unknown_keys(client, seed_invite, db_session):
    """El LLM inventa claves; el servidor las descarta. Sin esto el JSONB es
    inconsultable a los tres meses."""
    from klara.services.learner_synthesis import filter_facts

    kept = filter_facts(
        {
            "abandono_por": "video largo",
            "quit_reason": "video largo",
            "razon_abandono": "video largo",
            "metodo_sirve": ["Fichas de repaso"],
        }
    )
    assert set(kept) == {"abandono_por", "metodo_sirve"}


async def test_facts_derived_from_options_not_prose(client, seed_invite):
    """metodo_sirve / metodo_no_sirve / restriccion salen de las opciones,
    no de extracción LLM: el handoff los volvió enumerables."""
    from klara.services.learner_synthesis import facts_from_answers

    facts = facts_from_answers(
        {
            "hist_metodos": {"Fichas de repaso": "sirve", "Videos largos": "no"},
            "libre": ["Estudio de noche", "Me distraigo fácil"],
        }
    )
    assert facts["metodo_sirve"] == ["Fichas de repaso"]
    assert facts["metodo_no_sirve"] == ["Videos largos"]
    assert facts["restriccion"] == ["Estudio de noche", "Me distraigo fácil"]


async def test_nada_especial_excluded_from_restriccion(client, seed_invite):
    """`Nada especial` es la negación de libre: no es una restricción."""
    from klara.services.learner_synthesis import facts_from_answers

    facts = facts_from_answers({"libre": ["Nada especial"]})
    assert "restriccion" not in facts


# --------------------------------------------------------------------------
# Síntesis: best-effort y frescura
# --------------------------------------------------------------------------


class _LLMBoom:
    async def complete(self, **kw):
        raise RuntimeError("proveedor caído")


class _LLMFake:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.seen: list = []

    async def complete(self, **kw):
        self.seen.append(kw)

        class R:
            content = self.payload

        return R()


async def test_synthesis_failure_still_returns_deterministic_facts():
    """Si el LLM se cae, los facts que salen de opciones marcadas sobreviven:
    no dependen de prosa. Guardar nunca depende de la síntesis."""
    from klara.services.learner_synthesis import generate_synthesis

    prosa, facts = await generate_synthesis(
        _LLMBoom(), {"hist_metodos": {"Fichas de repaso": "sirve"}}
    )
    assert prosa is None
    assert facts == {"metodo_sirve": ["Fichas de repaso"]}


async def test_deterministic_facts_beat_llm_invention():
    """El LLM no puede pisar lo que salió de una opción marcada."""
    from klara.services.learner_synthesis import generate_synthesis

    llm = _LLMFake(
        '{"prosa": "x", "facts": {"metodo_sirve": ["Telepatía"], "motivacion": "mudanza"}}'
    )
    _, facts = await generate_synthesis(llm, {"hist_metodos": {"Videos largos": "sirve"}})
    assert facts["metodo_sirve"] == ["Videos largos"], "lo determinista manda"
    assert facts["motivacion"] == "mudanza", "lo que solo vive en texto libre sí entra"


async def test_synthesis_drops_llm_keys_outside_allowlist():
    from klara.services.learner_synthesis import generate_synthesis

    llm = _LLMFake('{"prosa": "x", "facts": {"quit_reason": "video largo", "evitar": ["ruido"]}}')
    _, facts = await generate_synthesis(llm, {})
    assert "quit_reason" not in facts
    assert facts["evitar"] == ["ruido"]


async def test_answers_never_reach_the_logs(client, seed_invite, caplog):
    """Contrato de privacidad: se registra el resultado, jamás el contenido."""
    from klara.services.learner_synthesis import generate_synthesis

    secreto = "me mudo a Núremberg en marzo"
    with caplog.at_level("DEBUG"):
        await generate_synthesis(_LLMBoom(), {"libre_texto": secreto})
    assert secreto not in caplog.text
