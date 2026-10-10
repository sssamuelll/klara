export type Lang = 'en' | 'es';

export interface PageCopy {
  /** Prefijo relativo a los assets de `public/` desde esta página. */
  assetBase: './' | '../';
  homeHref: string;
  thisLabel: string;
  otherLabel: string;
  otherLang: Lang;
  otherHref: string;
  navLabel: string;
  code: string;
  hero: { title: string; dek: string };
}

export const copy: Record<Lang, PageCopy> = {
  en: {
    assetBase: './',
    homeHref: './',
    thisLabel: 'EN',
    otherLabel: 'ES',
    otherLang: 'es',
    otherHref: './es/',
    navLabel: 'Language and code',
    code: 'Code',
    hero: {
      title: 'Your study library',
      dek: 'Read, speak, review. Every course is shaped to the way you learn.',
    },
  },
  es: {
    assetBase: '../',
    homeHref: './',
    thisLabel: 'ES',
    otherLabel: 'EN',
    otherLang: 'en',
    otherHref: '../',
    navLabel: 'Idioma y código',
    code: 'Código',
    hero: {
      title: 'Tu biblioteca de estudio',
      dek: 'Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.',
    },
  },
};
