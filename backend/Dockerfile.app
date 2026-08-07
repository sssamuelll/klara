# Capa de aplicación del backend: sólo COPY sobre la base ya construida.
#
# Este es el único Dockerfile que se construye EN LA CAJA. No instala nada, no
# baja nada, no compila nada — por eso cabe en 1,9 GB de RAM (el equivalente en
# Atrium se midió en 1,9 s y 52 MB).
#
# BASE la pasa scripts/deploy-prod.sh y lleva el hash de pyproject.toml+uv.lock,
# así que una imagen de app nunca puede quedar apareada con dependencias que no
# son las suyas.

ARG BASE
FROM ${BASE}

WORKDIR /app

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src

# En vez de `uv sync` (que necesitaría red y un índice de paquetes acá arriba),
# el código entra por PYTHONPATH. Es equivalente: pyproject declara
# packages = ["src/klara"], así que el wheel mapearía src/klara -> klara, que es
# exactamente lo que hace esta ruta. Sin console scripts que se pierdan.
ENV PYTHONPATH=/app/src

EXPOSE 8000

# docker-compose.prod.yml sobreescribe este CMD (sin --reload). Se deja el de
# desarrollo acá para que la imagen sea usable suelta.
CMD ["sh", "-c", "alembic upgrade head && uvicorn klara.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 10 --ws-ping-timeout 10"]
