#! /bin/bash

if [ "$COVERALLS_ENDPOINT" == "" ]; then
    echo "Error: \$COVERALLS_ENDPOINT not set"
    exit 1
fi

export GIT_COMMIT="$TRAVIS_COMMIT"
export GIT_BRANCH="$TRAVIS_BRANCH"

exec coveralls --verbose
