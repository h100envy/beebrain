# web

static site. no build server, no framework. every page works from disk.

set the domain once: `python web/build.py --domain your.domain` (replaces BEEBRAIN_DOMAIN in meta tags, robots.txt and sitemap.xml).
rebuild the article and the computed blocks: `python web/build.py`.

- vercel: `npx vercel deploy web --prod`
- netlify: `npx netlify deploy --dir web --prod`
- github pages: push `web/` to a `gh-pages` branch with `git subtree push --prefix web origin gh-pages`, then set pages to that branch and add your custom domain (404.html uses root paths, so serve it from a domain root).
- cloudflare pages: `npx wrangler pages deploy web`
