# How to run the testsuite

Jens is shipped with a bunch of functional tests which live in
`jens/test`.  Make sure that all the run-time dependencies declared in
`requirements.txt` and `mock` are installed before running them.

## Running the tests with a human-readable output

```
$ python -W ignore:ResourceWarning -m unittest -v
```

### Just a single test

```
$ python -W ignore:ResourceWarning -m unittest jens.test.test_update.UpdateTest.test_base -v
```

### And keeping the sandbox in disk

```
$ JENS_TEST_KEEP_SANDBOX=1 python -W ignore:ResourceWarning -m unittest jens.test.test_update.UpdateTest.test_base -v
```
