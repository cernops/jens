# How to run the testsuite

Jens is shipped with a bunch of functional tests which live in `src/jens/test`.
Make sure that all the run-time dependencies declared in the spec file and
`python-nose` are installed before running them.

## Running the tests with a human-readable output

```
$ nosetests -v
```

### Just a single test

```
$ nosetests jens.test.test_update:UpdateTest.test_base -v
```

### Without capturing STDOUT

```
$ nosetests jens.test.test_update:UpdateTest.test_base -v --nocapture
```

## Running the tests with xunit-suitable output


```
$ nosetests -w src jens.test.test_metadata:MetadataTest \
   jens.test.test_update:UpdateTest \
   --with-xunit \
   --xunit-file=/tmp/jens-test-results.xml
```
