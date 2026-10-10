import { renderToStaticMarkup } from 'react-dom/server';
import { Page } from './Page';
import type { Lang } from './copy';

export function render(lang: Lang): string {
  return renderToStaticMarkup(<Page lang={lang} />);
}
