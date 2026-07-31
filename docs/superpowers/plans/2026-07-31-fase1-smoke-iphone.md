# F1 smoke — iPhone real (PWA instalada) — gate de merge

Prerrequisito: CI verde en el PR (`typecheck` + `i18n:check` + `test` + `build` — los corre GitHub Actions). Este checklist es el gate manual ADICIONAL en device, no un sustituto de los checks.

Build de rama servido al teléfono (dev server con --host o deploy a staging).

- [ ] PWA instalada abre en `/` (Inicio v4) sin barras del navegador.
- [ ] `100dvh`: TabBar visible completa, sin recorte por la home bar; safe-area respetada.
- [ ] Sin scroll vertical en Inicio/Portada/Mapa/Perfil (m3-page no desborda) en viewport corto.
- [ ] Teclado abierto en /settings (legacy) NO rompe el layout al volver a `/`.
- [ ] Tema light/dark desde Perfil aplica en vivo y persiste tras cerrar y reabrir la PWA.
- [ ] Navegar 01 Leer → historia legacy: audio TTS reproduce; volver con back de iOS regresa a Portada.
- [ ] MIC (regresión #103): en /review, grabar una frase con la PWA instalada — el AudioContext
      suspendido NO regresa (primer tap graba).
- [ ] Back gesture de iOS/Android entre `/` ↔ `/curso/aleman` ↔ sesiones legacy: sin estados muertos.
- [ ] Login → logout → login: rutas protegidas redirigen bien con el shell nuevo.
