import { NeoProvider } from 'neobrutalistcomponents';
import { copy, type Lang } from './copy';

export const REPO = 'https://github.com/sssamuelll/klara';

export function Page({ lang }: { lang: Lang }) {
  const t = copy[lang];
  return (
    <NeoProvider theme="klara" mode="dark">
      <div className="kl">
        <header className="kl-mast">
          <a className="kl-brand" href={t.homeHref}>
            <span className="kl-k" aria-hidden="true">K</span>
            <span className="kl-word">Klara</span>
          </a>
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
        </main>
      </div>
    </NeoProvider>
  );
}
