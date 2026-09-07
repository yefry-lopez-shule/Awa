# Self-hosted IBM Plex

**IBM Plex Sans** (400 / 500 / 600) and **IBM Plex Mono** (400), SIL Open Font
License 1.1, © 2017 IBM Corp — <https://github.com/IBM/plex>.

Epic #29 asks for the `latin` + `latin-ext` subset. IBM/plex itself ships only
the "complete" (full-Unicode) `.woff2` files; subsetting them here would need a
font-tooling build step the project deliberately doesn't have. So the files are
the pre-cut `latin` / `latin-ext` `.woff2` that
[Fontsource](https://fontsource.org) publishes — `@fontsource/ibm-plex-sans@5.1.0`
and `@fontsource/ibm-plex-mono@5.1.0`, which repackage the upstream IBM/plex glyph
data unchanged and only slice it by `unicode-range`. Those `@font-face` rules and
their matching `unicode-range` values live in `../app.css`.

| file | sha-256 |
| --- | --- |
| `ibm-plex-sans-latin-400-normal.woff2` | `db71f8a28ad8501544fb4e7668e3c6d0b731760b6f20de3525ebaeba597f1922` |
| `ibm-plex-sans-latin-500-normal.woff2` | `5ef914e59b0047a261844d96acabb60c34d3acab6b85ea24198726ce4781fd37` |
| `ibm-plex-sans-latin-600-normal.woff2` | `31535a91ce3f6b8ed3ddedadab1e49957e2220263a640df1a3f14f6fdfe15eb6` |
| `ibm-plex-sans-latin-ext-400-normal.woff2` | `9a4ad5a9fd17ad03f878c0f1b126f460c4f409f29c633d5fc7c20276a7060914` |
| `ibm-plex-sans-latin-ext-500-normal.woff2` | `b45dda4ca1e499e1e46b0fab82dbb94e06634fbc7de370b2a542049ec749c5dd` |
| `ibm-plex-sans-latin-ext-600-normal.woff2` | `19d8e8252c984a204ba97d48d9abfe56a1ab5caa0b3468495d8db57dd144a780` |
| `ibm-plex-mono-latin-400-normal.woff2` | `3c5a451f9ec27a354b0c2bcca636c6ec17a651281aabf29f8427e210a1d31e85` |
| `ibm-plex-mono-latin-ext-400-normal.woff2` | `91e8ae155e1cd949e9b03f82cfa0bfb04ce6bbcf149e807de9385d58c5dfc6ce` |
