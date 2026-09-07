# Vendored third-party assets

Committed on purpose — the app runs on `runserver` with `DEBUG=True` and has no
build step or package manager for front-end assets. Epic #29's locked decisions:
"vendored `pico.classless.min.css`" and "no dependency packages in
`requirements.txt`"; deployment concerns (`collectstatic`, WhiteNoise) are
explicitly out of scope there.

## `pico.classless.jade.min.css`

- **Pico CSS** v2.0.6, classless build, jade accent — <https://picocss.com>
- MIT licensed, © 2019–2024 Pico CSS
- Source: `@picocss/pico@2.0.6` on npm, file `css/pico.classless.jade.min.css`,
  byte-identical to the `v2.0.6` tag on <https://github.com/picocss/pico>
- SHA-256: `914479a170667407b381a1aae6529ebcfb51d69aa7c51fef7f8873b538ebdc0c`

Verify:

```sh
sha256sum static/vendor/pico.classless.jade.min.css
```

To upgrade: bump the version, re-download from the matching GitHub release tag,
re-check the hash against the release, and update this file.
