# Contributing to narrow
If you're interested in helping us mature narrow, you've come to the right place!

## Have bug reports or suggestions?

If you have questions or suggestions, please use the GitHub issue tracker.

Note: we use issues for larger architectural or roadmap discussions so don't be shy!

## Contributing pull requests
Please use GitHub's pull request feature to submit fixes or improvements to narrow.

1. It's expected that your pull request will pass unit and integration tests (see below).
1. Your pull request title should reference at least one GitHub issue. If there isn't an issue related to your work, please create one.
1. While `make lint` (currently) does not produce clean output, please be sure you aren't worsening the situation in your change.

## Linting
You can run a linter using `make lint`.

Note, however, that we currently are not enforcing clean output here. 

### Testing

1. To run integration tests, run `make integrationTests`.
1. To run unit tests, run `make unitTests`.
1. To run narrow on itself (an audit), run `make audit`.