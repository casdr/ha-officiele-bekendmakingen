# Contributing

Contributions are **welcome** and will be fully **credited**.

We accept contributions via Pull Requests on [GitHub](https://github.com/casdr/ha-officiele-bekendmakingen).

## Development environment

This project uses [uv](https://docs.astral.sh/uv/) and
[prek](https://github.com/j178/prek). Install uv, then:

```sh
uv sync                        # install Home Assistant and the development tools
uv run prek install            # run all checks on every commit
uv run prek run --all-files    # run all checks manually
uv run pytest                  # run the tests
```

## Pull Requests

- **Document any change in behaviour**: keep `README.md` up to date.
- **Follow [SemVer v2.0.0](https://semver.org/)**.
- **Create feature branches**: don't ask us to pull from your main branch.
- **One pull request per feature**: send several pull requests for several changes.
- **Label your pull request**: the release notes are drafted from the labels.
- **Test fixtures stay anonymous**: replace names, e-mail addresses, tokens and serial
  numbers before adding API responses to `tests/fixtures`.
