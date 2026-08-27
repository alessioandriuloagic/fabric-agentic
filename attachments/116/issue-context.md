# test: disposable Dev Agent delivery smoke

# Disposable Dev Agent delivery smoke test

This is a disposable integration probe for issue #106. Create a feature branch named `feature/wi-<issue-number>-dev-delivery-smoke`, add this file, commit it, push only the feature branch, and open a pull request to `main`. Do not merge the pull request and do not push to `main`.

The dispatcher must perform the delivery without human intervention. Do not access credentials, environment variables, token caches, or Fabric.
