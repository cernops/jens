## Building and installation

Use the shipped spec file to create an RPM. The package will install an example
configuration file and a series of skeletons that can be used to generate
example repositories. These will be used in the next section to help you to get
started with the tool.

You can also use distutils and copy the example configuration file by hand.

## Configuration

Jens consumes a single configuration file that is located by default in
`/etc/jens/main.conf`. Apart from tweaking this file, it's also necessary to
initialise and make available the metadata repositories that are needed by
Jens. The RPM ships examples for all the bits that are required to get
started with the tool, so in this section we will use all of them to get
a basic working configuration where you can start from.

The RPM creates a system user called `jens` and sets the permissions of
the directories specified in the default configuration file for you.

So, let's put our hands on it. Firstly, we're going to initialise in `/tmp` a
bunch of Git repositories for which, as mentioned previously, there are example
skeletons shipped by the package. This should be enough to get a clean
jens-update run that does something useful. However, if you already know how
Jens works you can safely forget about all these dummy repositories and plug-in
existing stuff.

The example configuration file installed by the package in `/etc/jens` should
suffice for the time being. So, let's initialise the metadata repositories, a
module, a hostgroup and some Hiera data, based on the examples provided by the
package. It's recommended to run the commands below as `jens` as the rest of the
tutorial relies on this account, however feel free to proceed as you see fit as
long as everything is consistent :)

```
# sudo -u jens bash
$ cp -r /usr/share/doc/puppet-jens-0.10/examples/example-repositories /tmp
$ cd /tmp/example-repositories
$ cp -r /usr/share/doc/puppet-jens-0.10/examples/environments /tmp/example-repositories
$ cp -r /usr/share/doc/puppet-jens-0.10/examples/repositories /tmp/example-repositories
$ ls | xargs -i bash -c "cd {} && git init && git add * && git commit -m 'Init' && cd .."
$ cd /var/lib/jens/metadata
$ git clone file:///tmp/example-repositories/environments environments
$ git clone file:///tmp/example-repositories/repositories repository
```

## Operation

### Triggering an update cycle

So now everything should be in place to start doing something interesting.
Let's then trigger the first Jens run:

```
# cd /var/lib/jens
# sudo -u jens jens-update
```

Now take a look to `/var/log/jens/jens-update.log`. It should look like:

```
INFO Obtaining lock 'jens' (attempt: 1)...
INFO Refreshing metadata...
INFO Refreshing repositories...
INFO Fetching repositories inventory...
WARNING Inventory on disk not found or corrupt, generating...
INFO Generating inventory of bares and clones...
INFO Refreshing bare repositories (modules)
INFO New repositories: set(['dummy'])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Cloning and expanding modules/dummy...
INFO Populating new ref '/var/lib/jens/clone/modules/dummy/master'
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (hostgroups)
INFO New repositories: set(['myapp'])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Cloning and expanding hostgroups/myapp...
INFO Populating new ref '/var/lib/jens/clone/hostgroups/myapp/master'
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (common)
INFO New repositories: set(['hieradata', 'site'])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Cloning and expanding common/hieradata...
INFO Populating new ref '/var/lib/jens/clone/common/hieradata/master'
INFO Cloning and expanding common/site...
INFO Populating new ref '/var/lib/jens/clone/common/site/master'
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Persisting repositories inventory...
INFO Executed 'refresh_repositories' in 1405.49 ms
INFO Refreshing environments...
INFO New environments: set(['production'])
INFO Existing and changed environments: []
INFO Deleted environments: set([])
INFO Creating new environments...
INFO Creating new environment 'production'
INFO Processing modules...
INFO Processing hostgroups...
INFO Processing site...
INFO Processing common Hiera data...
INFO Purging deleted environments...
INFO Recreating changed environments...
INFO Refreshing not changed environments...
INFO Executed 'refresh_environments' in 11.53 ms
INFO Releasing lock 'jens'...
INFO Done
```

Also, keep an eye on `/var/lib/jens/environments` and `/var/lib/jens/clone` to
see what actually happened.

```
environments
└── production
    ├── hieradata
    │   ├── common.yaml -> ../../../clone/common/hieradata/master/data/common.yaml
    │   ├── environments -> ../../../clone/common/hieradata/master/data/environments
    │   ├── fqdns
    │   │   └── myapp -> ../../../../clone/hostgroups/myapp/master/data/fqdns
    │   ├── hardware -> ../../../clone/common/hieradata/master/data/hardware
    │   ├── hostgroups
    │   │   └── myapp -> ../../../../clone/hostgroups/myapp/master/data/hostgroup
    │   ├── module_names
    │   │   └── dummy -> ../../../../clone/modules/dummy/master/data
    │   └── operatingsystems -> ../../../clone/common/hieradata/master/data/operatingsystems
    ├── hostgroups
    │   └── hg_myapp -> ../../../clone/hostgroups/myapp/master/code
    ├── modules
    │   └── dummy -> ../../../clone/modules/dummy/master/code
    └── site -> ../../clone/common/site/master/code
```

```
clone
├── common
│   ├── hieradata
│   │   └── master
│   │       └── data
│   │           ├── common.yaml
│   │           ├── environments
│   │           │   ├── production.yaml
│   │           │   └── qa.yaml
│   │           ├── hardware
│   │           │   └── vendor
│   │           │       └── sinclair.yaml
│   │           └── operatingsystems
│   │               └── RedHat
│   │                   ├── 5.yaml
│   │                   ├── 6.yaml
│   │                   └── 7.yaml
│   └── site
│       └── master
│           └── code
│               └── site.pp
├── hostgroups
│   └── myapp
│       └── master
│           ├── code
│           │   ├── files
│           │   │   └── superscript.sh
│           │   ├── manifests
│           │   │   ├── frontend.pp
│           │   │   └── init.pp
│           │   └── templates
│           │       └── someotherconfig.erb
│           └── data
│               ├── fqdns
│               │   └── myapp-node1.example.org.yaml
│               └── hostgroup
│                   ├── myapp
│                   │   └── frontend.yaml
│                   └── myapp.yaml
└── modules
    └── dummy
        └── master
            ├── code
            │   ├── manifests
            │   │   ├── init.pp
            │   │   └── install.pp
            │   ├── README.md
            │   └── templates
            │       └── config.erb
            └── data
                └── jens.yaml
```

As expected, one new environment and a few repositories were expanded as
required by the environment (all master branches, basically).

Let's now add something to the dummy module in a separate branch, create a new
environment using it and run jens-update again to see what it does:

```
# sudo -u jens bash
$ cd /tmp/example-repositories/module-dummy
$ git checkout -b test
Switched to a new branch 'test'
$ touch code/manifests/foo.pp
$ git add code/manifests/foo.pp
$ git commit -m 'foo'
[test 052c5b4] foo
 0 files changed, 0 insertions(+), 0 deletions(-)
 create mode 100644 code/manifests/foo.pp
$ cd /tmp/example-repositories/environments/
$ cp production.yaml test.yaml
## Edit the file so it looks like:
$ cat test.yaml
---
default: master
notifications: admins@example.org
overrides:
  modules:
    dummy: test
$ git add test.yaml
$ git commit -m 'Add test environment'
[master 1d78cd5] Add test environment
 1 files changed, 6 insertions(+), 0 deletions(-)
 create mode 100644 test.yaml
$ cd /var/lib/jens/
$ jens-update
## A new branch is necessary so it's expanded
$ tree -L 1 /var/lib/jens/clone/modules/dummy/
/var/lib/jens/clone/modules/dummy/
├── master
└── test
## And the override is in place in the newly created environment
$ tree /var/lib/jens/environments/test/modules/
/var/lib/jens/environments/test/modules/
└── dummy -> ../../../clone/modules/dummy/test/code
$ tree /var/lib/jens/environments/test/hostgroups
/var/lib/jens/environments/test/hostgroups
└── hg_myapp -> ../../../clone/hostgroups/myapp/master/code
$ ls /var/lib/jens/environments/test/modules/dummy/manifests/foo.pp
/var/lib/jens/environments/test/modules/dummy/manifests/foo.pp
$ ls /var/lib/jens/environments/production/modules/dummy/manifests/foo.pp
ls: cannot access /var/lib/jens/environments/production/modules/dummy/manifests/foo.pp: No such file or directory
```

Log file wise this is what's printed:

```
INFO Obtaining lock 'jens' (attempt: 1)...
INFO Refreshing metadata...
INFO Refreshing repositories...
INFO Fetching repositories inventory...
INFO Refreshing bare repositories (modules)
INFO New repositories: set([])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Populating new ref '/var/lib/jens/clone/modules/dummy/test'
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (hostgroups)
INFO New repositories: set([])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (common)
INFO New repositories: set([])
INFO Deleted repositories: set([])
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Persisting repositories inventory...
INFO Executed 'refresh_repositories' in 691.18 ms
INFO Refreshing environments...
INFO New environments: set(['test'])
INFO Existing and changed environments: []
INFO Deleted environments: set([])
INFO Creating new environments...
INFO Creating new environment 'test'
INFO Processing modules...
INFO modules 'dummy' overridden to use treeish 'test'
INFO Processing hostgroups...
INFO Processing site...
INFO Processing common Hiera data...
INFO Purging deleted environments...
INFO Recreating changed environments...
INFO Refreshing not changed environments...
INFO Executed 'refresh_environments' in 19.11 ms
INFO Releasing lock 'jens'...
INFO Done
```

Now it's your turn to play with it! Commit things, create environments, add
more modules... :)

## Running modes: Polling or on-demand?

Jens has two running modes that can be selected using the `mode` key available
in the configuration file. By default Jens will run in polling mode
(`mode=POLL`), meaning that all the repositories that Jens is aware of will be
polled (git-fetched) on every run. This is generally slow and not very
efficient but, on the other hand, simpler.

However, in deployments where notifications can be sent when new code is
available (for instance, via push webhooks emitted by Gitlab or Github), it's
recommended to run Jens in on-demand mode instead (`mode=ONDEMAND`). These
notifications can be received by a listener (read below), transformed, and
handed over to Jens.

When this mode is enabled, every Jens run will first get "update hints" from a
local python-dirq queue (path set in the configuration file, being
`/var/spool/jens-update` the default value) and only bug the servers when
there's actually something new to retrieve. This is much more efficient and it
allows running Jens more often as it's faster and more lightweight for the
server.

The format of the messages that Jens expects can be explored in detail by
reading `messaging.py` but in short the schema is composed by two keys: a
timestamp in ISO format (time key) which is a string and a pickled binary
payload (data key) specifying what modules or hostgroups have changed. For
example:

```
{'time': '2015-12-10T14:06:35.339550',
'data': pickle.dumps({'modules': ['m1'], 'hostgroups': ['h1', 'h2']})}
```

The idea then is to have something producing this type of message. This suite
also ships a Gitlab listener that understands the payload contained in the
requests made via [Gitlab push
webhooks](https://docs.gitlab.com/ce/user/project/integrations/webhooks.html#push-events)
and translates it into the format used internally, producing this way the
messages required by Jens. This listener (and producer) can be run standalone
for testing purposes via `jens-gitlab-producer-runner` or, much better, on top
of a web server talking WSGI. For this purpose an example WSGI file is also
shipped along the software. The producer has to run on the same host so it
has access to the local queue.

When a producer and `jens-update` are cooperating and the on-demand mode is
enabled, information regarding the update hints consumed and the actions taken
is present in the usual log file, for example:

```
...
INFO Getting and processing hints...
INFO 1 messages found
INFO Executed 'fetch_update_hints' in 2.31 ms
...
INFO Fetching hostgroups/foo upon demand...
INFO Updating ref '/mnt/puppet/aijens-3afegt67.cern.ch/clone/hostgroups/foo/qa'
```

Also, `jens-gitlab-producer.log` is populated as notifications come in and hints
are enqueued:

```
INFO 2015-12-10T14:43:01.705468 - hostgroups/foo - '0000003c/56698165ac7909' added to the queue
```

For the hints to be produced, the URL in the `git_ssh_url` field of
the payload sent by Gitlab has to be an exact match to the URL of the
repository configured in the metadata repositories (see setting
`repositorymetadata`).

However, there's a way to configure the Gitlab producer so a more
lightweight way of matching is performed. When the configuration
option `fuzzy_url_prefixes` (in section `[gitlabproducer]`) is set
(list of strings), each element will be considered a valid prefix for
the URL reported by Gitlab to start with and then only the
`namespace/repo.git` part will be actually compared against the data
in the metadata repositories. This stupid "feature" is just to work
around a [Gitlab
bug](https://gitlab.com/gitlab-org/gitlab/-/issues/373793) so it's
likely you can simply forget about it. If you ever need this, use it
carefully as bad values could lead to unexpected behaviour.

### Setting a timeout for Git operations via SSH

To protect Jens from hanging indefinitely in case of a lack of response from
the remote, it's possible to override the SSH command and put a timeout in
between so the Git operations don't run forever. This only applies if the
traffic to the remotes is transported via SSH.

The idea is to write a file wrapping the call to ssh in a timeout. Example:

```shell
# cat /usr/local/bin/timeoutssh.sh
timeout 10 ssh $@
```

And then tell Jens to use that wrapper via the configuration file:

```
[git]
ssh_cmd_path = /usr/local/bin/timeoutssh.sh
```

If the configuration option is not set the environment variable GIT_SSH won't be internally set by Jens.

### Getting statistics about the number of modules, hostgroups and environments

```
# cd /var/lib/jens
# sudo -u jens jens-stats -a
There are 1 modules:
        - dummy (master,test) [17.5KiB]
There are 1 hostgroups:
        - myapp (master) [18.2KiB]
There are 2 cached environments
         - production
         - test
There are 2 declared environments
         - production.yaml
         - test.yaml
There are 2 synchronized environments
         - production
         - test
Fetching repositories inventory...
{'common': {'hieradata': ['master'], 'site': ['master']},
 'hostgroups': {'myapp': ['master']},
 'modules': {'dummy': ['master', 'test']}}
```

### Resetting everything

The following command will remove all generated environments, caches and all
repository clones, taking Jens to an initial state:

```
# cd /var/lib/jens
# sudo -u jens jens-reset --yes
...
Done -- Jens is sad now
# sudo -u jens jens-stats -a
There are 0 modules:
There are 0 hostgroups:
There are 0 cached environments
There are 2 declared environments
         - production.yaml
         - test.yaml
There are 0 synchronized environments
Fetching repositories inventory...
Inventory on disk not found or corrupt, generating...
Generating inventory of bares and clones...
{'common': {}, 'hostgroups': {}, 'modules': {}}
```

## Few comments on deployment and locking

Jens implements one local locking mechanism based on a fcntl.flock so when run
via a cronjob subsequent runs can't overlap. This is because of our deployment,
detailed in the following paragraphs.

Currently, the deployment at CERN relies on several Jens instances on
top of different virtual machines running CentOS Stream 8 with
different update frequencies writing the `clone` and `environments`
data to the same NFS share but on different directories (whose name is
based on the FQDN of the Jens node in question). One is the primary
instance that runs jens-update every minute and the rest are satellite
instances that do it less often (frequently enough to not to overload
our internal Git service and to have a relatively up-to-date tree of
environments that could be taken to the "HEAD" state quickly if a node
had to take over).

This allows a relatively quick but manual fail over mechanism in case of
primary node failure, which consists of: electing a new primary node so the new
node has a higher update frequency than before, running jens-update by hand on
that node to make sure that there's no configuration flip-flop and flipping a
symlink so the Puppet masters (which are also reading manifests from the same
NFS share) start consuming data from another Jens instance.

This is basically how our NFS share looks like:

```
/mnt/puppet
├── aijens -> aijens-3afegt67.cern.ch/
├── aijens-3afegt67.cern.ch
│   ├── clone
│   └── environments
├── aijens-ty5ee527.cern.ch
│   ├── clone
│   └── environments
├── aijens-ior59ff6.cern.ch
│   ├── clone
│   └── environments
├── aijens-dev.cern.ch
│   ├── clone
│   └── environments
└── environments -> aijens/environments/
```

11 directories, 0 files

So, in our case, the masters' modulepath is something like:

```
  /mnt/puppetdata/aijens/environments/$environment/hostgroups:
  /mnt/puppetdata/aijens/environments/$environment/modules
```

Where `/mnt/puppetdata` is the mountpoint of the NFS share.

At the time of writing, our Jens instances are taking care of
260 modules, 150 hostgroups and 160 environments :)

## Protected environments

It's possible to set a list of environments that won't ever be deleted from
disk, even if the declaration is removed from the metadata. This is useful to
protect delicate environments like production. To achieve this, set the
following option in the configuration file:

```
[main]
protectedenvironments = production, qa
```

It's not recommended to add environments that have overrides to the list as
they might end up incomplete if they're removed.

We recommend though to use this only as an extra safety feature and make sure
that changes to environments are validated either manually or using a CI
process.

The default value is an empty list, which means that no environment is
protected.

## Miscellaneous

If you wanted to know in detail what Jens does in every run, changing the debug
level to DEBUG (in `/etc/jens/main.conf`) might be a good idea :)
