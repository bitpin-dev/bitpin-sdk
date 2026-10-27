# Changelog

## 0.1.0 (2026-10-27)


### Features

* **python:** async client with public market data ([e23997b](https://github.com/bitpin-dev/bitpin-sdk/commit/e23997b3e3135e0d2d1352d86ac62fb301141c41))
* **python:** config, rate limiter, symbol and decimal helpers ([4bf3f14](https://github.com/bitpin-dev/bitpin-sdk/commit/4bf3f142848c800c6e2dd8e40ada0053683d3d12))
* **python:** error hierarchy and mapping ([5795634](https://github.com/bitpin-dev/bitpin-sdk/commit/57956343ad9f8ad9219269ce2047f89e5aed3350))
* **python:** generate endpoint table from spec ([7377da1](https://github.com/bitpin-dev/bitpin-sdk/commit/7377da15cd4a326ff9a49ad61951e05d6660e9b8))
* **python:** generate sync client with unasync ([2e1c41c](https://github.com/bitpin-dev/bitpin-sdk/commit/2e1c41c7c304ce83a6508f30850554519ca56cf7))
* **python:** request builder, parsers and shared fixtures ([daaa339](https://github.com/bitpin-dev/bitpin-sdk/commit/daaa339f942065ee7a06f00513c4928af80766b4))
* **python:** token lifecycle and token stores ([300ddf6](https://github.com/bitpin-dev/bitpin-sdk/commit/300ddf6040bb5bd2964ae3fda843cddbe146cdf5))
* **python:** trading, wallet and not-supported methods ([5007c21](https://github.com/bitpin-dev/bitpin-sdk/commit/5007c211cdf9b0ec4041a8d1f52e8556709fd5be))
* **python:** websocket watch methods ([03b6624](https://github.com/bitpin-dev/bitpin-sdk/commit/03b66249e637f7abad484cfc2b75ad1a685fbbeb))


### Bug fixes

* **ci:** dependabot PR titles pass the conventional-title check ([d9edc02](https://github.com/bitpin-dev/bitpin-sdk/commit/d9edc02c6cc66dc2c922799c7245747eb79396d7))
* **examples:** market maker always cancels its quotes on exit ([6c1b066](https://github.com/bitpin-dev/bitpin-sdk/commit/6c1b0665d22b0b64bac7b742a51c37ee105d61ad))
* **python:** give each websocket watch its own queue ([41cee57](https://github.com/bitpin-dev/bitpin-sdk/commit/41cee574bd748341b5ca4e71df5e4df956c479ba))
* **python:** ignore a late 401 for a token that was already replaced ([5f7092a](https://github.com/bitpin-dev/bitpin-sdk/commit/5f7092a732ee738b5f2fbd7ff6867100df1cae46))
* **python:** paginate reads every page and can't loop forever ([f25b7b3](https://github.com/bitpin-dev/bitpin-sdk/commit/f25b7b316254534f99ac900c0e515a97abe491ba))
* **python:** parse one-digit fractions on Python 3.10; derive the token-file id with PBKDF2 ([d896f26](https://github.com/bitpin-dev/bitpin-sdk/commit/d896f26e5cfe066b06b8ee99dcae829cb2484f15))
* **python:** reserve rate-limit slots so concurrent calls don't burst ([d934e3d](https://github.com/bitpin-dev/bitpin-sdk/commit/d934e3dda3a02bb754e3555e4b23faac15d337f5))
* **python:** safe concurrent token-file saves; keep credentials out of exception chains ([1835e09](https://github.com/bitpin-dev/bitpin-sdk/commit/1835e09d9fbd5023d2c99e064609a2eb00d7c61a))
* **python:** ticker change is a ratio, report it as ccxt percentage ([d81d56e](https://github.com/bitpin-dev/bitpin-sdk/commit/d81d56ec33e32ffe3c0e92325b7f72c6d1f7c4b7))


### Documentation

* **ai:** agent instructions, rules, skills and permissions ([0b5989a](https://github.com/bitpin-dev/bitpin-sdk/commit/0b5989ad4a41323487d3d7efe0d711031796189a))
* bilingual documentation and llms.txt ([69e7f6a](https://github.com/bitpin-dev/bitpin-sdk/commit/69e7f6a5e0c4cb276796c1c0c7c411a5626d0f45))
* **examples:** add dry-run examples ([58620ac](https://github.com/bitpin-dev/bitpin-sdk/commit/58620ac1999ef10f2a503b43df6eae32a71d8cae))

## Changelog

All notable changes to the Python SDK, written by release-please from Conventional Commits.
