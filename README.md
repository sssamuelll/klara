# Klara

App personal de apoyo para aprender idiomas, con una IA tutora llamada **Klara**.

> Klara soporta varios idiomas (es, en, de, fr, ja, pt). El idioma a aprender lo elige cada usuario en sus ajustes.

## Stack

- **Backend**: FastAPI + SQLAlchemy async + Alembic, sobre PostgreSQL.
- **Frontend**: React + Vite + TypeScript.
- **LLM**: agnóstico de proveedor vía LiteLLM (Anthropic, DeepSeek, OpenAI configurables por env).
- **TTS**: ElevenLabs.
- **Orquestación**: Docker Compose.

## Estructura

```
app/
├── backend/    # FastAPI (paquete Python: klara)
├── frontend/   # React + Vite
└── docker-compose.yml
```

## Levantar el entorno local

1. Copiar `.env.example` a `.env` y completar las claves que vayas a usar:

   ```bash
   cp .env.example .env
   ```

2. Levantar todo con Docker:

   ```bash
   docker compose up --build
   ```

3. Acceder:
   - Frontend: http://localhost:5173
   - Backend (API): http://localhost:8000
   - Postgres: `localhost:5432`

## Variables de entorno relevantes

Ver `.env.example`. Como mínimo se necesita una API key de LLM (Anthropic, DeepSeek u OpenAI) y, si se quiere TTS, una de ElevenLabs.

## Notas

- Los textos de la interfaz están en **español neutro**.
- Klara es agnóstica de proveedor de LLM: el modelo se elige por configuración, no en código.
