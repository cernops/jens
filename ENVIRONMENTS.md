## Disclaimer

This documentation has been based on internal instructions available for CERN
users so if there's something odd/unclear/stupid please report back to us.

It's recommended to read the README first as it contains more generic
information about Jens that might be interesting to digest before reading this.

## Introduction

Environments are collections of modules and hostgroups at different development
levels. They are defined in YAML files living in a Git repository. Jens uses
this repository to check out the correct modules and hostgroups for each
environment.

With these files you can basically specify which is the default branch that
must be used (normally _master_ or _qa_), who to inform in case of problems and
any modules which must be overridden. The name of the Puppet environment much
match the name of the file (without the .yaml extension).

## How to create/edit/delete environments

Environment definions are plain text files. To do CUD operations on them, just
add/edit/delete the file defining it and publish the change.

## Dynamic environments

Dynamic environments give you a reasonable list of defaults (that will be
dynamically updated) and the possibility to define overrides for specific modules or
hostgroups. For instance, to create an environment named _ai321_ with all the
modules/hostgroups pointing to the QA branch except from the module 'sssd' which
will use the 'ai321' branch instead, just create a file looking like:

```
$ cat ai321.yaml
---
default: qa
notifications: bob@cern.ch
  overrides:
    modules:
      sssd: ai456
```

This kind of environment is the normal one, where all the included components
follow the corresponding HEADs and update automatically (in the above example,
every time a new commit is pushed to the QA branch of whatever module and Jens
runs, the change is visible to all machines on environment ai321). Also, new
modules and hostgroups that get added to the library after the environment has
been created are automatically included following the default rule.

Dynamic environments are meant to be used for development (essentially to have
a sandbox to test a new configuration change without affecting any production
service), whereas production and QA machines (CERNism warning) should live in
the corresponding supported and long-lived "golden environments" with the same
name.

```
$ cat production.yaml
---
default: master
notitications: bob@cern.ch

$ cat qa.yaml
---
default: qa
notitications: higgs@cern.ch
```

## Static (snapshot) environments

It is also possible (but not recommended) to create configuration
snapshots.

A static environment is one that doesn't update dynamically, and is normally
generated based on the state of an already existing dynamic environment.
Nothing will change in a snapshot environment unless the environment definition
is tweaked by hand. This type of environment is called a **snapshot** or an
**environment with no default**. To create a static environment, just don't set
any default and specify the refs you want to be expanded for each
module/hostgroup, for instance:

```
$ cat snap1.yaml
# Snapshot created on 2014-03-03 14:25:37.150312 based on production
---
notifications: bob@example.org
overrides:
  common:
   hieradata: commit/fb96070c9c77cc442ac60ba273768f547d376c17
   site: commit/fb96070c9c77cc442ac60ba273768f547d376c17
  hostgroups:
    adcmon: commit/8bf3ca9fe39a6f354dfc70377205ed806d6ae540
    foo: master
    ...
  modules:
    abrt: commit/580cdbcf154dec2fa9ae717f2f55a18abbaebd72
    ...
```

Internally, snapshots look a bit like dynamic environments but with some
exceptions:

* There's no default, therefore only modules/hostgroups specified in the list
  of overrides are included.
* New modules/hostgroups cannot be sensibly added automatically, so a snapshot
  will not include any modules/hostgroups which are added after the snapshot
  is created.
* Overrides point normally to commit hashes instead of branches, although
  branch names are supported.

However, the same way as dynamic environments:

* If a module/hostgroup is removed from the library, it will be removed from
  all the shapshots too, as if they were dynamic environments.

## Which environment should I use for my production service?

Disclaimer: The following tips are inevitably coupled to CERN IT policies so
  it can be safely ignored. They're kept here as they might be useful for the
  general public to understand a bit more what dynamic and static environments
  are.

You should use the _production_ environment.

Reasons to use the default production dynamic environment:

* You will get configuration fully aligned to infrastructure changes for free,
  guaranteeing that your machine works with the latest components.

Reasons not to use snapshots:

* You will get off the train of changes very quickly.
* They are difficult to maintain, as once something is broken, mangling the
  overrides to make it work again by trying to get a newer version of
  several configuration components can be very tricky and potentially dangerous.
* Make Jens slower and fatter.

If you really need snapshots:

* Make the lifetime of them as short as you can (i.e. don't stay on them
  for any long length of time). Your risk of divergence from the infrastructure
  increases with time.
* When you want to advance, make a new snapshot from the current
  __production__ environment.
* Delete them as soon as you don't need them anymore.
