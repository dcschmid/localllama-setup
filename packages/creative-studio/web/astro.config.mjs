import { defineConfig } from 'astro/config';

// Local Creative Studio UI. Static build; served by the creative-studio
// backend on 127.0.0.1:8700. No external CDNs, no cloud fonts, no analytics.
export default defineConfig({
  output: 'static',
  base: '/',
  trailingSlash: 'ignore',
  build: { assets: '_assets', inlineStylesheets: 'auto' },
  devToolbar: { enabled: false },
});
