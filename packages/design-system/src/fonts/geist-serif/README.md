# Geist Serif

`GeistSerif-Regular.woff2` is the Regular variant of Geist Serif, unchanged, from the
`geist` package, version 1.9.2 (https://github.com/vercel/geist-font), published by Vercel
under the SIL Open Font Licence 1.1. The licence is in `LICENSE.txt` beside it and must
stay with the file.

It is kept here, and not installed, because that package requires the Next.js framework
(ADR-025). `scripts/licenses.mjs` lists it among what ships and fails if it goes missing.

To update: copy `dist/fonts/geist-serif/GeistSerif-Regular.woff2` and `LICENSE.txt` from a
newer `geist` package over these, and change the version in `scripts/licenses.mjs`.
