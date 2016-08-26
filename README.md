[![Build Status](https://travis-ci.org/cernops/jens.svg?branch=master)]
(https://travis-ci.org/cernops/jens)

## What's Jens?

Jens is the Puppet modules/hostgroups librarian used by the [CERN IT
department] (https://cern.ch/it). It is basically a Python toolkit that
generates [Puppet environments]
(https://docs.puppetlabs.com/puppet/latest/reference/environments.html)
dynamically based on some input metadata. Jens is useful in sites where there
are several administrators taking care of siloed services (mapped to what we
call top-level "hostgroups", see below) with very service-specific
configuration but sharing configuration logic via modules.

This tool covers the need of several roles that might show up in a typical
shared Puppet infrastructure:

  * Developers writing manifests who want an environment to test new code: Jens
    provides dynamic environments that automatically update with overrides for
    the modules being developed that point to development branches.
  * Administrators who don't care: Jens supports simple dynamic environments
    that default to the production branch of all modules and that only update
    automatically when there's new production code.
  * Administrators looking for extra stability who are reluctant to do rolling
    updates: Jens implements snapshot environments that are completely static and
    don't update unless redefined, as all modules are pinned by commit
    identifier.

Right now, the functionality is quite tailored to CERN IT's needs, however
all contributions to make it more generic and therefore more useful for the
community are more than welcome.

This program has been used as the production Puppet librarian at CERN IT since
August 2013.

## Introduction

In Jens' realm, Puppet environments are basically a collection of modules,
hostgroups, hierarchies of Hiera data and a site.pp. These environments
are defined in environment definition files which are stored in a separate
repository that's known to the program. Also, Jens makes use of a second
metadata repository to know what modules and hostgroups are part of the library
and are therefore available to generate environments.

With all this information, Jens produces a set of environments that can be used
by Puppet masters to compile Puppet catalogs. Two types of environments are
supported: dynamic and static. The former update automatically as new commits
arrive to the concerned repositories whereas the latter remain static pointing
to the specified commits to implement the concept of "configuration snapshot"
(read the environments section for more information).

Jens is composed by several CLIs: jens-config, jens-gc, jens-reset, jens-stats
and jens-update to perform different tasks. Manual pages are shipped for all of
them.

Basically, the input data that's necessary for an execution of jens-update (the
core tool provided by this toolset) is two Git repositories:

  * The repository metadata repository (or _the library_)
  * The environment definitions repository (or _the environments_)

More details about these are given in the following sections.

## Repository metadata

Jens uses a single YAML file stored in a Git repository to know what are the
modules and hostgroups available to generate environments. Apart from that,
it's also used to define the paths to two special Git repositories containing
what's called around here _the common Hiera data_ and the site manifest.

This is all set up via two configuration keys: `repositorymetadata` (which is
the directory containing a clone of the repository) and `repositorymetadatadir`
(the file itself).

The following is how a skeleton of the file looks like:

```
---
repositories:
  common:
      hieradata: http://git.example.org/pub/it-puppet-common-hieradata
      site: http://git.example.org/pub/it-puppet-site
  hostgroups:
      ...
      aimon: http://git.example.org/pub/it-puppet-hostgroup-aimon
      cloud: http://git.example.org/pub/it-puppet-hostgroup-cloud
      ...
  modules:
      ...
      apache: http://git.example.org/pub/it-puppet-module-apache
      bcache: http://git.example.org/pub/it-puppet-module-bcache
      ...
```

The idea is that when a new top-level hostgroup is added or a new module
is needed this file gets populated with the corresponding clone URLs of
the repositories. Jens will add new elements to all the environments
that are entitled to get them during the next run of jens-update.

Another example is available in examples/repositories/repositories.yaml.

### Common Hiera data and Site

There are two bits that are declared via the library file that require some
extra clarifications, especially because they are fundamentally traversal to
the rest of the declarations and are maybe a bit hardcoded to how our Puppet
infrastructure is designed.

The repository pointed to by _site_ must contain a single manifest called
site.pp that serves as the catalog compilation entrypoint and therefore where
all the hostgroup autoloading (explained later) takes place.

```
it-puppet-site/
├── code
│   └── site.pp
└── README
```

OTOH, the common hieradata is a special repository that hosts different types
of Hiera data to fill the gaps that can't be defined at hostgroup or module
level (operating system, hardware vendor, datacentre location and environment
dependent keys). The list of these items is configurable and can be set by using
the configuration key `common_hieradata_items`. The following is an example of
how the hierarchy in there should look like.

```
it-puppet-common-hieradata/
├── data
│   ├── common.yaml
│   ├── environments
│   │   ├── production.yaml
│   │   └── qa.yaml
│   ├── datacentres
│   │   ├── europe.yaml
│   │   ├── usa.yaml
│   │   └── ...
│   ├── hardware
│   │   └── vendor
│   │       ├── foovendor.yaml
│   │       └── ...
│   └── operatingsystems
│       └── RedHat
│           ├── 5.yaml
│           ├── 6.yaml
│           └── 7.yaml
└── README
```

common.yaml is the most generic Hiera data YAML file of all the hierarchy as
it's visible for all nodes regardless of their hostgroup, environment, hardware
type, operatingsystem and datacentre. It's useful to define very top-level keys.

Working examples of both repositories (used during the installation tutorial
later on) can be found in the following locations

  * examples/example-repositories/common-hieradata
  * examples/example-repositories/site

Also, an example of a Hiera hierarchy configuration file that matches this
structure is available on examples/hiera.yaml.

### Modules: Code and data directories

Each module/hostgroup lives in a separate Git repository, which contains two
top-level directories: code and data.

 * code: this is where the actual Puppet code resides, basically where the
   manifests, lib, files and templates directories live.
 * data: all the relevant Hiera data is stored here. For modules,
   there's only one YAML file named after the module.

Example:

```
it-puppet-module-lemon/
├── code
│   ├── lib
│   │   └── facter
│   │       ├── configured_kernel.rb
│   │       ├── lemon_exceptions.rb
│   │       └── ...
│   ├── manifests
│   │   ├── config.pp
│   │   ├── init.pp
│   │   ├── install.pp
│   │   ├── klogd.pp
│   │   ├── las.pp
│   │   └── ...
│   ├── Modulefile
│   ├── README
│   └── templates
│       └── metric.conf.rb
└── data
    └── lemon.yaml
```

For those already wondering how we manage to keep track of upstream modules
with this strutucture: Git subtree :)

### Hostgroups: What they are and why they're useful

Hostgroups are just Puppet modules that are a bit special, allowing us to
automatically load Puppet classes based on the hostgroup a given host belongs
to (information which is fetched at compilation time from an ENC).

This is a CERNism and unfortunately we're not aware of anybody in the Puppet
community doing something similar. However, we found this idea very useful to
classify IT services, grouping machines belonging to a given service in the
same top-level hostgroup. Modules are normally included in the hostgroup
manifests (along the hierarchy) and configured via Hiera.

In short, hostgroups represent the service-specific configuration and modules
are reusable "blocks" of code that abstract certain recurrent configuration
tasks which are typically used by several hostgroups.

Getting back to the structure itself, the code directory serves the same
purpose as the one for modules, however the data one is slightly different, as
it contains FQDN-specific Hiera data for hosts belonging to this hostgroup and
data that applies at different levels of the hostgroup hierarchy.

Next, a partial example of a real-life hostgroup and its subhostgroups with
the corresponding manifests and Hiera data:

```
it-puppet-hostgroup-punch/code/manifests/
├── aijens
│   ├── app
│   │   └── live.pp
│   ├── app.pp
...
├── init.pp
```

```
it-puppet-hostgroup-punch/data/hostgroup
├── punch
│   ├── aijens
│   │   ├── app
│   │   │   ├── live
│   │   │   │   └── primary.yaml
│   │   │   └── live.yaml
│   │   └── app.yaml
│   ├── aijens.yaml
...
└── punch.yaml
```

```
it-puppet-hostgroup-punch/data/fqdns/
├── foo1.cern.ch.yaml
```

For instance, if **foo1.cern.ch** belonged to **punch/aijens/app/live**, it'd
be entitled to automatically include init.pp, aijens.pp (which does no exist in
this case), app.pp and live.pp. Also, Hiera keys will be looked up using files
foo1.cern.ch.yaml, punch.yaml, aijens.yaml, app.yaml and live.yaml

To avoid clashes during the autoloading with modules that might have
the same name, the top-most class of the hostgroup is prefixed with **hg_**.

```
~ $ grep ^class it-puppet-hostgroup-punch/code/manifests/aijens/app.pp
class hg_punch::aijens::app {
~ $ grep ^class it-puppet-hostgroup-punch/code/manifests/init.pp
class hg_punch {
```

There's more information about how this all works filesystem-wise below. An
example of the autoloading mechanism can be found in the example site.pp
mentioned above.

## An introduction to Jens environments

One of the parameters that can be configured via the configuration file is the
path to a clone of the Git repository containing the environment definitions
(configuration key `environmentsmetadatadir`). Each file with .yaml extension
is a candidate environment and will be considered by Jens during the update cycle.

An example of a very simple one can be located in examples/environments.

That said, environments are mostly useful for development, for instance to
validate the effect of a change in an specific module using the stable version
of the remaining configuration. This is accomplished by using environment
overrides:

```
~/it-puppet-environments $ cat devticket34.yaml
---
default: master
notifications: higgs@example.org
overrides:
  modules:
    apache: dev34
```

See ENVIRONMENTS.md for further details on this subject, including how to
create configuration snapshots instead of dynamic environments :)

### "Golden" environments

Environments are cool to quickly get a development sandbox. They go in and out
in a very rapid fashion, as new features are needed or finished. However, these
are indeed not ideal for production nodes. Because of this, it's also
interesting to have some kind of special environments and use them as the place
where all the code converges at some point after development/testing/QA and
place the bulk of the service there.

This section is just a recommendation that describes how things are done over
here, however Jens does not enforce the existence or the structure of any
environment at all.

In our site there's the concept of **golden environment**. These are
long-lived, simple and unmodifiable dynamic environments used for production
and QA (mandatory for all changes in modules impacting several unrelated
services). The following are the definitions:

```
~/it-puppet-environments $ cat production.yaml qa.yaml
---
default: master
notifications: higgs@example.org
---
default: qa
notifications: higgs@example.org
```

As you can see, these are very simple environments that collect all the master
and qa branches of all modules and hostgroups available in the library.  This
of course relies on one of our internal policies that say that all the
repositories containing Puppet code must have at least two branches: `master`
and `qa`, meaning that they will always be expanded by Jens. This behaviour can
be configured by the `mandatorybranches` configuration key.

As environment definitions are just Yaml files, the files can be easily
protected from unauthorized/accidental modification via, for instance,
Gitolite rules :)

### How does an environment look like on disk?

Internally, Jens uses different directories to keep track of what's going on
with the Git repositories it has to be aware of. There's one called `clone`
that contains a checked out working tree of all the branches that are necessary
by environments for a each module/hostgroup. This way, an environment is just a
collection of symbolic links to these directories, which targets depend on the
environment definition. As an example, this is how the whole tree for the
hypothetical environment _devticket34_ declared previously would look like:

```
environments/devticket34/
├── hieradata
│   ├── common.yaml -> ../../../clone/common/hieradata/master/data/common.yaml
│   ├── environments -> ../../../clone/common/hieradata/master/data/environments
│   ├── fqdns
│   │   ├── aimon -> ../../../../clone/hostgroups/aimon/master/data/fqdns
│   │   ├── cloud -> ../../../../clone/hostgroups/cloud/master/data/fqdns
│   │   └── ...
│   ├── hardware -> ../../../clone/common/hieradata/master/data/hardware
│   ├── hostgroups
│   │   ├── aimon -> ../../../../clone/hostgroups/aimon/master/data/hostgroup
│   │   ├── cloud -> ../../../../clone/hostgroups/cloud/master/data/hostgroup
│   │   └── ...
│   ├── module_names
│   │   ├── apache -> ../../../../clone/modules/apache/dev34/data
│   │   ├── bcache -> ../../../../clone/modules/apache/bcache/data
│   │   └── ...
│   └── operatingsystems -> ../../../clone/common/hieradata/master/data/operatingsystems
├── hostgroups
│   ├── hg_aimon -> ../../../clone/hostgroups/aimon/master/code
│   ├── hg_cloud -> ../../../clone/hostgroups/cloud/master/code
│   └── hg_...
├── modules
│   ├── apache -> ../../../clone/modules/apache/dev34/code
│   ├── bcache -> ../../../clone/modules/apache/master/code
│   └── ...
└── site -> ../../clone/common/site/master/code
```

As shown, the master branch of all available repositories are used (as the
_default_ dictates) however the module _apache_ has been overridden to use a
different one.

Environments will be written to the directory specified by the configuration
key `environmentsdir`.

## What's a Jens run?

It's an execution of jens-update, which is normally trigged by a cronjob. It
will determine what's new, what branches have to be updated and what
environments have to be created/modified/deleted. The following is an example
of what's typically found in the log files after a run where there was not much
to do (a hostgroup got new code in the QA branch and a new environment was
created):

```
INFO Obtaining lock 'aijens' (attempt: 1)...
INFO Refreshing metadata...
INFO Refreshing repositories...
INFO Fetching repositories inventory...
INFO Refreshing bare repositories (modules)
INFO New repositories: []
INFO Deleted repositories: []
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (hostgroups)
INFO New repositories: []
INFO Deleted repositories: []
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Updating ref '/mnt/puppet/aijens-3afegt67.cern.ch/clone/hostgroups/vocms/qa'
INFO Purging REMOVED bare repositories...
INFO Refreshing bare repositories (common)
INFO New repositories: []
INFO Deleted repositories: []
INFO Cloning and expanding NEW bare repositories...
INFO Expanding EXISTING bare repositories...
INFO Purging REMOVED bare repositories...
INFO Persisting repositories inventory...
INFO Executed 'refresh_repositories' in 6287.78 ms
INFO Refreshing environments...
INFO New environments: ['am1286']
INFO Existing and changed environments: []
INFO Deleted environments: []
INFO Creating new environments...
INFO Creating new environment 'am1286'
INFO Processing modules...
INFO Processing hostgroups...
INFO hostgroups 'aimon' overridden to use treeish 'am1286'
INFO Processing site...
INFO Processing common Hiera data...
INFO Purging deleted environments...
INFO Recreating changed environments...
INFO Refreshing not changed environments...
INFO Executed 'refresh_environments' in 1395.03 ms
INFO Releasing lock 'aijens'...
INFO Done
```

## Installation, configuration and deployment

See INSTALL.md

## Contributing

As mentioned before, Jens, as it is now, is very coupled to the Puppet
deployment that it was designed to work with. Probably the main goal we're
trying to achieve making it free software is to try to attract the interest of
more Puppeteers so we can all together improve the tool and make it useful for
as many Puppet installations out there as we possibly can.

Hence, we'd be more than happy to get contributions of any kind! Feel free to
submit bug reports and pull requests via
[Github](https://github.com/cernops/jens).

There's also a DEVELOPERS.md that explains how to run the testsuite that is
available for developers.

## Authors

Jens has been written and it's currently being maintained by [Nacho
Barrientos](https://cern.ch/nacho), however it has been designed the way it is
and has evolved thanks to the feedback provided by staff of the CERN IT
department.

## License

See COPYING

## Etymology

Jens was named after [M. Jens Vigen](https://twitter.com/jensvigen), CERN's
librarian.
