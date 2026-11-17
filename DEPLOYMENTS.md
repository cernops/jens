# Experimental staged deployments

`jens-deploy` is an opt-in prototype for #49. It does not change `jens-update`,
its timers, environment definitions or existing deployments. It is intended for
isolated testing before designing production Puppet integration.

## Prepare

Run as the deployment user, using a new root owned by that user:

```
jens-deploy prepare --config /path/to/main.conf --root /path/to/new/deployments
```

This prints a generation directory. The source config is read, never rewritten.
The committed `master` branches of the configured local metadata repositories
are cloned privately; uncommitted metadata changes are excluded. Fetch source
metadata separately if newer remote metadata is needed. Repository URLs and
existing branch/environment rules are used unchanged.

All bare repositories, checkouts, environment trees, cache, logs, queue and locks
are created inside the new generation. The live ONDEMAND queue is never read:
preparation performs a full POLL build. Fresh checkouts also avoid the existing
stale-checkout retry bug. Failed generations remain for diagnosis, without a
`complete.json` marker, and cannot be published. Any worker failure, logged
ERROR/CRITICAL, broken environment link or link escaping the generation rejects
the build. Logs are in `log/prepare.log` and `worker-output.log`.

A successful generation has a `complete.json` manifest recording checkout and
metadata commits. Generation directories start with owner-only permissions. Reader access/ACLs must
be configured as part of the serving integration, after preparation succeeds.
Do not mutate a generation after preparation. Legacy
`jens-update`, `jens-gc`, and `jens-reset` must never target a published generation.
This prototype cold-builds every generation; allow for increased disk, network
and preparation time. Optimization through immutable content reuse is future work.

## Publish only with coordinated readers

```
jens-deploy publish --root /path/to/new/deployments \
  --generation /path/to/new/deployments/generations/generation_ID --readers-drained
```

Publication atomically replaces `ROOT/current`, a symlink to the complete
generation. Environments are under `ROOT/current/environments`. A separate root
lock serializes preparation/publication. No service is stopped, cache cleared,
or serving configuration changed by this command. `--readers-drained` is an
operator assertion, not automatic draining or a check that Puppet is idle.

**This is filesystem publication atomicity, not a completed Puppet integration.**
A compilation accessing `current` repeatedly can cross a switch. Before production
use, either prove that each compilation retains one resolved generation path for
all code/data access, or drain backends, finish existing work, publish, refresh
relevant Puppet caches, then resume. Include subsequent file-serving requests in
the integration design. Until that exists, use publication only with isolated
fixture readers. Do not wire a live Puppet server to this prototype.

Each serving group needs coordinated promotion; this is not a distributed
transaction. Test NFS visibility and caching on the deployment filesystem.
The pointer replacement handles process interruption with old-or-new selection;
power-loss durability/fsync guarantees have not been implemented.

Previous generations are retained. Rollback uses the same publication command
with a previous completed generation and the same reader/cache coordination.
There is intentionally no automatic garbage collection yet: remove a generation
only when no reader, file-serving request or rollback plan needs it. Interrupted
and failed preparation directories can be removed when no builder is running.

No snapshot environments, release manifests or dependency relationships are
introduced. The internal commit manifest is diagnostic only. Independently moving
branches may still yield incompatible combinations across update cycles.

## Isolated validation

From a source checkout, with the existing runtime dependencies installed:

```
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

Tests create only temporary local fixture Git repositories and deployment roots;
they do not read `/etc/jens`, use production repository URLs, consume production
queues, run service commands or install packages. `TMPDIR` can constrain all test
state to a dedicated directory. The tests clean up their fixtures automatically.
