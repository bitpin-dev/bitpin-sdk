# Changelog

## 0.1.0 (2026-10-27)


### Features

* **python:** async client with public market data ([115e0b1](https://github.com/bitpin-dev/bitpin-sdk/commit/115e0b1f6fc8a018a470505745367d2446d4edc5))
* **python:** config, rate limiter, symbol and decimal helpers ([3018dd2](https://github.com/bitpin-dev/bitpin-sdk/commit/3018dd224aa404cfb77724abcf3fb6c48ab01d7d))
* **python:** error hierarchy and mapping ([554bfcd](https://github.com/bitpin-dev/bitpin-sdk/commit/554bfcdeabbaeb5cb70bb89fa16780acd15549e2))
* **python:** generate endpoint table from spec ([69b1ff9](https://github.com/bitpin-dev/bitpin-sdk/commit/69b1ff9566d7cfe9ff43166ea5d283f5d949c7a9))
* **python:** generate sync client with unasync ([bf84c16](https://github.com/bitpin-dev/bitpin-sdk/commit/bf84c163e04c4b51a4e3768682439601054e70fb))
* **python:** request builder, parsers and shared fixtures ([c745eda](https://github.com/bitpin-dev/bitpin-sdk/commit/c745eda08df1e455cb4378eae8eac0e9ce2bd110))
* **python:** token lifecycle and token stores ([85b2c44](https://github.com/bitpin-dev/bitpin-sdk/commit/85b2c4476a55c383cdbcd7bc8b3b64211fa139b5))
* **python:** trading, wallet and not-supported methods ([35bd1c4](https://github.com/bitpin-dev/bitpin-sdk/commit/35bd1c4e7ac8cb7fa5d252743b48d5e7a7df2dd4))
* **python:** websocket watch methods ([684653f](https://github.com/bitpin-dev/bitpin-sdk/commit/684653f15037d77cc36ac3301709bc388d106b57))


### Bug fixes

* **ci:** dependabot PR titles pass the conventional-title check ([cbffb5f](https://github.com/bitpin-dev/bitpin-sdk/commit/cbffb5ffdc16ee501685169ef8f9c67f4956f649))
* **examples:** market maker always cancels its quotes on exit ([85ef75b](https://github.com/bitpin-dev/bitpin-sdk/commit/85ef75b7f827a6f40a1d7da4060c72e8db8b6f91))
* **python:** give each websocket watch its own queue ([fed6d10](https://github.com/bitpin-dev/bitpin-sdk/commit/fed6d10a39bed64c692acdb1ec6228a99e97c399))
* **python:** ignore a late 401 for a token that was already replaced ([e8dec1c](https://github.com/bitpin-dev/bitpin-sdk/commit/e8dec1cc2c0d44854dbccfff8a5c035e85491136))
* **python:** paginate reads every page and can't loop forever ([9b231d3](https://github.com/bitpin-dev/bitpin-sdk/commit/9b231d30a36e9fc548e7984333ae4394b9f136b7))
* **python:** parse one-digit fractions on Python 3.10; derive the token-file id with PBKDF2 ([0588ebb](https://github.com/bitpin-dev/bitpin-sdk/commit/0588ebbd3d39935b86bd5e99c7048d768fb7314a))
* **python:** reserve rate-limit slots so concurrent calls don't burst ([a71f5f5](https://github.com/bitpin-dev/bitpin-sdk/commit/a71f5f54c947cebea57e6f3936b2974aeb248c09))
* **python:** safe concurrent token-file saves; keep credentials out of exception chains ([0b3fa17](https://github.com/bitpin-dev/bitpin-sdk/commit/0b3fa17efade8ef519574bbad9469e30b0bef98e))
* **python:** ticker change is a ratio, report it as ccxt percentage ([afacb4f](https://github.com/bitpin-dev/bitpin-sdk/commit/afacb4f64fb550c013233511d6f83750a5777070))


### Documentation

* **ai:** agent instructions, rules, skills and permissions ([b28c9f3](https://github.com/bitpin-dev/bitpin-sdk/commit/b28c9f35066da61c2f4a54a59c6a3f61120a0b60))
* bilingual documentation and llms.txt ([545592f](https://github.com/bitpin-dev/bitpin-sdk/commit/545592f67c491ce9891ae5455146c0ca84af2e8a))
* **examples:** add dry-run examples ([17e417a](https://github.com/bitpin-dev/bitpin-sdk/commit/17e417a4cfc3cd9e4f4e8a9be2be8af5cbb1ed23))

## Changelog

All notable changes to the Python SDK, written by release-please from Conventional Commits.
