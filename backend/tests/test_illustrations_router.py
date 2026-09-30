"""GET /illustrations/{hash} (spec §3.5): pública, inmutable, 404 si no existe."""

import pytest

from klara.models import Illustration

H = "b" * 64


@pytest.mark.asyncio
async def test_sirve_la_imagen_sin_sesion(client, db_session):
    db_session.add(
        Illustration(
            hash=H,
            scene="x",
            style_version=1,
            model="m",
            mime_type="image/jpeg",
            image_data=b"\xff\xd8jpeg",
            size_bytes=6,
        )
    )
    await db_session.commit()
    resp = await client.get(f"/api/v1/illustrations/{H}")
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8jpeg"
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"] == f'"{H}"'
    assert resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_mime_que_no_es_imagen_sale_como_octet_stream(client, db_session):
    db_session.add(
        Illustration(
            hash="d" * 64,
            scene="x",
            style_version=1,
            model="m",
            mime_type="text/html",
            image_data=b"<script>",
            size_bytes=8,
        )
    )
    await db_session.commit()
    resp = await client.get(f"/api/v1/illustrations/{'d' * 64}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("hash_", ["c" * 64, "B" * 64, "z" * 64, "abc", "b" * 65])
async def test_404(client, hash_):
    resp = await client.get(f"/api/v1/illustrations/{hash_}")
    assert resp.status_code == 404
