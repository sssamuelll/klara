// Solo para `vite dev`: el prerender quita este script de la página publicada.
import { createRoot } from 'react-dom/client';
import './styles';
import { Page } from './Page';
import type { Lang } from './copy';

const lang: Lang = document.documentElement.lang === 'es' ? 'es' : 'en';
createRoot(document.getElementById('root')!).render(<Page lang={lang} />);
