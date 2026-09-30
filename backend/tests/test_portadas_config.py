"""Configuración de las portadas (spec §3.6): la clave de Gemini es secreta, en
blanco cuenta como ausente, y el compose la pasa al contenedor."""

from pathlib import Path

from klara.config import get_settings

REPO = Path(__file__).resolve().parents[2]


def test_clave_en_blanco_es_ausente(app_settings):
    app_settings(GEMINI_API_KEY="")
    assert get_settings().gemini_api_key is None


def test_clave_es_secreta(app_settings):
    app_settings(GEMINI_API_KEY="sk-secreta")
    settings = get_settings()
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "sk-secreta"
    assert "sk-secreta" not in repr(settings)


def test_modelo_por_defecto(app_settings):
    app_settings(ILLUSTRATION_MODEL=None)
    assert get_settings().illustration_model == "gemini-3.1-flash-image-preview"


def test_compose_pasa_la_clave_al_backend():
    # La trampa del #95: el compose pasa las claves una por una. Sin esta línea,
    # la clave del .env nunca llega al contenedor.
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY: ${GEMINI_API_KEY:-}" in compose
    assert "ILLUSTRATION_MODEL: ${ILLUSTRATION_MODEL:-gemini-3.1-flash-image-preview}" in compose
