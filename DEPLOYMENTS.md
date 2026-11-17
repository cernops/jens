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
ERROR/CRITICAL, unresolved required override or component, broken link, cyclic
directory link or content link escaping the prepared serving trees rejects the
build. Validation follows nested links inside module/hostgroup code and data;
links within the prepared trees are supported. Logs are in `log/prepare.log` and
`worker-output.log`.

A successful generation has a version 2 `complete.json` manifest recording
checkout and metadata commits, the expected environments/components, protected
environment names, and hashes of serving files plus directory/link inventories.
Publication revalidates this inventory, including modified, missing or added
worktree content; HEAD commits alone are not used as an integrity check. Git
administration files are excluded from serving-content fingerprints.

Configured protected environments must exist even on the first preparation.
Preparation and publication also preserve protections in the currently selected
generation, so a previously prepared candidate cannot bypass a newer protection.
To remove a protection intentionally, first publish a generation that still
includes that environment with the protection removed; a later generation can
then remove the environment. Initial prototype version 1 manifests are not
accepted: reprepare using a fresh test root.

Generation directories start with owner-only permissions. Completed clone and
environment trees have write permission bits removed to prevent accidental
updates. The owner/root can override those permissions; this is not a security
boundary, and modifying a tree concurrently with publication is unsupported.
Reader access/ACLs must be configured as part of the serving integration after
preparation succeeds. Changing read/traverse permissions does not change file
identity, but changing executable status does.
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

### Code and data in the same module repository

Jens links `modules/example` to a checkout's `code` directory and
`hieradata/module_names/example` to the **same checkout's** `data` directory.
This keeps each prepared generation internally consistent. It does not make two
independent reads through a moving `current` pointer into one transaction:

1. Open `current/environments/production/modules/example/manifests/init.pp`
   while `current` selects A. Retain the parsed code in memory.
2. Publish B, where both `code` and `data` came from one newer module commit.
3. Open `current/environments/production/hieradata/module_names/example/example.yaml`.
   This new lookup selects B, giving old code in memory with new data.

No Git operation splits a commit in this example. The two opens select different
complete checkouts of the same repository. The pause can simply be the interval
between reads. An already open file descriptor is not retargeted by the switch.
If both reads use a retained absolute A path, both remain on A instead.

`test_same_repository_reads_can_cross_current_switch` demonstrates this filesystem
behavior deterministically; it is not a reproduction of Puppet's compiler or
cache behavior. Whether actual Puppet requests retain resolved paths or repeat
lookups through a moving path still needs serving-side investigation.

Each serving group needs coordinated promotion; this is not a distributed
transaction. Test NFS visibility and caching on the deployment filesystem.
The pointer replacement handles process interruption with old-or-new selection;
power-loss durability/fsync guarantees have not been implemented.

Previous generations are retained. Rollback uses the same publication command
with a previous completed generation and the same reader/cache coordination.
There is intentionally no automatic garbage collection yet: remove a generation
only when no reader, file-serving request or rollback plan needs it. Interrupted
and failed preparation directories can be removed when no builder is running.
The owner may need to restore write permissions on sealed directories before
removing them. Do not delete directories still needed by readers or rollback.

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
