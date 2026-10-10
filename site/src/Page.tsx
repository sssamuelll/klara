import { NeoProvider, Button, Badge, Card, Table, Alert } from 'neobrutalistcomponents';
import { copy, type Lang } from './copy';

export const REPO = 'https://github.com/sssamuelll/klara';
const README_SETUP = `${REPO}#local-setup`;
const MAIL = 'mailto:samueldarioballesteros@gmail.com';
const SITE = 'https://sdar.dev';

function Brand() {
  return (
    <>
      <span className="kl-k" aria-hidden="true">K</span>
      <span className="kl-word">Klara</span>
    </>
  );
}

export function Page({ lang }: { lang: Lang }) {
  const t = copy[lang];
  const asset = (p: string) => `${t.assetBase}${p}`;
  return (
    <NeoProvider theme="klara" mode="dark">
      <div className="kl">
        <header className="kl-mast">
          <a className="kl-brand" href={t.homeHref}><Brand /></a>
          <nav className="kl-nav" aria-label={t.navLabel}>
            <span className="kl-nav__here" aria-current="page">{t.thisLabel}</span>
            <a href={t.otherHref} lang={t.otherLang} hrefLang={t.otherLang}>{t.otherLabel}</a>
            <a href={REPO}>{t.code}</a>
          </nav>
        </header>

        <main>
          <section className="kl-hero">
            <h1 className="kl-hero__title">
              {t.hero.title}
              <span className="kl-hero__dot" aria-hidden="true">.</span>
            </h1>
            <p className="kl-hero__dek">{t.hero.dek}</p>
          </section>

          <figure className="kl-art">
            <img src={asset('hero.webp')} alt="" width="2000" height="848" decoding="async" fetchPriority="high" />
          </figure>

          <section className="kl-why" aria-labelledby="why">
            <h2 className="kl-cap" id="why">{t.why.cap}</h2>
            {t.why.paragraphs.map((p) => (
              <p className="kl-why__p" key={p.slice(0, 24)}>{p}</p>
            ))}
          </section>

          <section className="kl-screens" aria-labelledby="screens">
            <h2 className="kl-cap" id="screens">{t.screens.cap}</h2>
            <div className="kl-screens__grid">
              {t.screens.items.map((s) => (
                <Card key={s.key} className="kl-screen">
                  <Card.Content>
                    <div className="kl-phone">
                      <div className="kl-phone__shell">
                        <img src={asset(`shots/${s.key}.webp`)} alt={s.alt} width="390" height="760" loading="lazy" decoding="async" />
                      </div>
                    </div>
                  </Card.Content>
                  <Card.Header>
                    <Card.Title>{s.title}</Card.Title>
                    <Card.Description>{s.body}</Card.Description>
                  </Card.Header>
                </Card>
              ))}
            </div>
          </section>

          <section className="kl-maps" aria-labelledby="maps">
            <div className="kl-maps__head">
              <h2 className="kl-cap" id="maps">{t.maps.cap}</h2>
              <Badge variant="accent" size="sm">{t.maps.badge}</Badge>
            </div>
            <p className="kl-maps__intro">{t.maps.intro}</p>
            <div className="kl-maps__grid">
              {t.maps.tiles.map((m) => (
                <div className="kl-map" key={m.key}>
                  <div className={m.mono ? 'kl-map__glyph kl-map__glyph--mono' : 'kl-map__glyph'} lang={m.key} aria-hidden="true">{m.glyph}</div>
                  <h3 className="kl-map__title">{m.title}</h3>
                  <p className="kl-map__body">{m.body}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="kl-made" aria-labelledby="made">
            <h2 className="kl-cap" id="made">{t.made.cap}</h2>
            <p className="kl-badges">
              {t.made.badges.map((b) => <Badge key={b} variant="neutral">{b}</Badge>)}
            </p>
            <Table density="compact" className="kl-table">
              <Table.Body>
                {t.made.rows.map(([k, v]) => (
                  <Table.Row key={k}>
                    <Table.HeaderCell scope="row">{k}</Table.HeaderCell>
                    <Table.Cell>{v}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table>
            <div className="kl-alert">
              <Alert variant="info">{t.made.alert}</Alert>
            </div>
            <p className="kl-ctas">
              <Button asChild variant="primary" size="lg"><a href={REPO}>{t.made.code}</a></Button>
              <Button asChild variant="secondary" size="lg"><a href={README_SETUP}>{t.made.run}</a></Button>
            </p>
          </section>
        </main>

        <footer className="kl-foot">
          <span className="kl-brand"><Brand /></span>
          <a href={MAIL}>{t.footer.email}</a>
          <a href={SITE}>sdar.dev</a>
        </footer>
      </div>
    </NeoProvider>
  );
}
