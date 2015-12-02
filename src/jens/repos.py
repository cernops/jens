# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import yaml
import os
import logging
import shutil
import math
from multiprocessing import Pool, cpu_count, Manager

import jens.git as git

from jens.errors import JensRepositoriesError
from jens.errors import JensGitError
from jens.decorators import timed
from jens.reposinventory import get_inventory, persist_inventory
from jens.reposinventory import get_desired_inventory
from jens.tools import ref_is_commit
from jens.tools import refname_to_dirname
from jens.git import GIT_CLONE_TIMEOUT, GIT_FETCH_TIMEOUT

@timed
def refresh_repositories(settings, lock, hints=None):
    try:
        logging.debug("Reading metadata from %s" % settings.REPO_METADATA)
        definition = yaml.load(open(settings.REPO_METADATA, 'r'))
    except Exception, error: #fixme
        raise JensRepositoriesError("Unable to parse %s" % \
               settings.REPO_METADATA)

    inventory = get_inventory(settings)
    desired = get_desired_inventory(settings)
    deltas = {}

    logging.debug("Initial inventory: %s" % inventory)
    logging.debug("Needed from overrides: %s" % desired)

    for partition in ("modules", "hostgroups", "common"):
        logging.info("Refreshing bare repositories (%s)" % partition)
        logging.debug("Calculating '%s' delta..." % partition)
        delta = _calculate_delta(settings,
            definition['repositories'][partition],
            inventory[partition])
        logging.info("New repositories: %s" % delta['new'])
        logging.debug("Existing repositories: %s" % delta['existing'])
        logging.info("Deleted repositories: %s" % delta['deleted'])

        lock.renew((len(delta['new']) * GIT_CLONE_TIMEOUT) + \
            (len(delta['existing']) * GIT_FETCH_TIMEOUT) + \
            len(delta['deleted']))

        logging.info("Cloning and expanding NEW bare repositories...")
        delta['new'] = _create_new_repositories(settings, delta['new'],
            partition, definition, inventory[partition], desired[partition])

        # If there are hints on what to refresh available, only fetch (and
        # therefore trigger updates on the clones) if the item being refreshed
        # is in the list of things that changed :)
        existing = delta['existing']
        if hints:
            if partition in hints:
                existing = delta['existing'].intersection(hints[partition])
            else:
                existing = set()

        logging.info("Expanding EXISTING bare repositories...")
        _refresh_repositories(settings, existing, partition,
            inventory[partition], desired[partition])

        logging.info("Purging REMOVED bare repositories...")
        _purge_repositories(settings, delta['deleted'], partition,
            inventory[partition])

        deltas[partition] = delta

    persist_inventory(settings, inventory)
    logging.debug("Final inventory: %s" % inventory)

    return (deltas, inventory)

def _create_new_repositories(settings, new_repositories, partition,
            definition, inventory, desired):
    created = []
    for repository in new_repositories:
        logging.info("Cloning and expanding %s/%s..." % (partition, repository))
        bare_path = _compose_bare_repository_path(settings,
            repository, partition) 
        bare_url = definition['repositories'][partition][repository]
        try:
            git.clone(bare_path, bare_url, bare=True)
        except JensGitError, error:
            logging.error("Unable to clone '%s' (%s). Skipping." % (repository, error))
            if os.path.exists(bare_path):
                shutil.rmtree(bare_path)
            continue
        try:
            refs = git.get_refs(bare_path).keys()
        except JensGitError, error:
            logging.error("Unable to get refs of '%s' (%s). Skipping." % (repository, error))
            shutil.rmtree(bare_path)
            logging.debug("Bare repository %s has been removed" % bare_path)
            continue
        # Check if the repository has the mandatory branches
        if all([ref in refs for ref in settings.MANDATORY_BRANCHES]):
            # Expand only the mandatory and available requested branches
            # commits will always be attempted to be expanded
            new = set(settings.MANDATORY_BRANCHES)
            new = new.union(filter(lambda x: ref_is_commit(settings, x) or x in refs,
                desired.get(repository, [])))
            inventory[repository] = []
            _expand_clones(settings, partition, repository, inventory, None, new, [], [])
            created.append(repository)
        else:
            logging.error("Repository '%s' lacks some of the mandatory branches. Skipping." %
                repository)
            shutil.rmtree(bare_path)
            logging.debug("Bare repository %s has been removed" % bare_path)
    return created

# This is the most common operation Jens has to do, git-fetch
# over all bare repos and the expansion of clones.
def _refresh_repositories(settings, existing_repositories, partition, inventory, desired):
    if not existing_repositories:
        return # Seems that passing [] to pool.map makes .join never return
    manager = Manager()
    # The inventory is the only parameter that has to be r/w
    # so we need a common object and a remote controller :)
    inventory_proxy = manager.dict(inventory)
    inventory_lock = manager.Lock()
    data = [{'settings': settings, 'partition': partition,
        'repository': repository, 'inventory': inventory_proxy,
        'inventory_lock': inventory_lock, 'desired': desired}
        for repository in existing_repositories]
    pool = Pool(processes=int(math.ceil(cpu_count()*1.5)))
    pool.map(_refresh_repository, data)
    pool.close()
    pool.join()
    inventory.update(inventory_proxy)

def _refresh_repository(data):
    settings = data['settings']
    repository = data['repository']
    partition = data['partition']
    inventory = data['inventory']
    inventory_lock = data['inventory_lock']
    desired = data['desired']
    if settings.MODE == "POLL":
        logging.debug("Expanding bare and clones of %s/%s..." % (partition, repository))
    else:
        logging.info("Expanding bare and clones of %s/%s upon demand..."
            % (partition, repository))
    bare_path = _compose_bare_repository_path(settings,
        repository, partition)
    try:
        old_refs = git.get_refs(bare_path)
    except JensGitError, error:
        logging.error("Unable to get old refs of '%s' (%s)" % (repository, error))
        return
    try:
        git.fetch(bare_path, prune=True, bare=True)
    except JensGitError, error:
        logging.error("Unable to fetch '%s' from remote (%s)" % (repository, error))
        return
    try:
        # TODO: Found a corner case where git fetch wiped all
        # all the branches in the bare repository. That led 
        # this get_refs call to fail, and therefore in the next run
        # the dual get_refs to obtain old_refs failed as well.
        # What to do? No idea.
        # Executing git fetch --prune by hand in the bare repo
        # brought the branches back.
        new_refs = git.get_refs(bare_path)
    except JensGitError, error:
        logging.error("Unable to get new refs of '%s' (%s)" % (repository, error))
        return
    new, moved, deleted = _compare_refs(settings, old_refs, new_refs,
        inventory[repository],
        desired.get(repository, []))
    _expand_clones(settings, partition, repository, inventory, inventory_lock,
            new, moved, deleted)

def _purge_repositories(settings, deleted_repositories, partition, inventory):
    for repository in deleted_repositories:
        logging.info("Deleting %s/%s..." % (partition, repository))
        bare_path = _compose_bare_repository_path(settings,
            repository, partition) 
        # Pass a copy as it will be used as interation set
        refs = inventory[repository][:]
        _expand_clones(settings, partition, repository, inventory, None, [], [], refs)
        clone_path = _compose_clone_repository_path(settings, repository,
            partition)
        shutil.rmtree(clone_path)
        logging.debug("Clone repository parent %s has been removed" % clone_path)
        shutil.rmtree(bare_path)
        logging.debug("Bare repository %s has been removed" % bare_path)
        inventory.pop(repository, None)

# This function computes the list of refs to be expanded, refreshed or
# removed based on what is available (new_refs), what was available
# (old_refs), what's already present (inventory) and what's necessary
# (desired)
def _compare_refs(settings, old_refs, new_refs, inventory, desired):
    desired = set(desired).union(settings.MANDATORY_BRANCHES)
    # New: What we need minus what we have...
    new = list(desired.difference(inventory))
    # ...but only refs that exist or commits
    new = filter(lambda x: ref_is_commit(settings, x) or x in new_refs, new)

    # Deleted: what we have that we don't need anymore
    deleted = list(set(inventory).difference(desired))

    if new:
        logging.debug("New refs to be expanded: %s" % new)

    if deleted:
        logging.debug("Removed refs: %s" % deleted)

    # Candidates are those that we already have and we still need
    moved = []
    for ref in desired.intersection(inventory):
        # No point in checking if a commit has moved
        if ref_is_commit(settings, ref):
            continue
        # If the ref is still being used (in the inventory and desired)
        # but has been removed from the repo we mark it as delete.
        # Next run will try to get it again and skip the expansion.
        if ref not in new_refs:
            logging.info("Ref '%s' still needed but removed from repo" % ref)
            deleted.append(ref)
            continue
        # The ref is still there and is gonna be kept, check if
        # it has moved.
        if new_refs[ref] != old_refs[ref]:
            logging.debug("Ref '%s' has moved and points to %s" %
                (ref, new_refs[ref]))
            moved.append(ref)
        else:
            logging.debug("Ref '%s' is known but didn't move" % ref)

    return new, moved, deleted

def _expand_clones(settings, partition, name, inventory, inventory_lock,
        new_refs, moved_refs, deleted_refs):
    bare_path = _compose_bare_repository_path(settings,
                name, partition) 
    if new_refs:
        logging.debug("Processing new refs of %s/%s (%s)..." % \
            (partition, name, new_refs))
    for refname in new_refs:
        clone_path = _compose_clone_repository_path(settings,
                name, partition, refname)
        logging.info("Populating new ref '%s'" % clone_path)
        try:
            if ref_is_commit(settings, refname):
                commit_id = refname.replace(settings.HASHPREFIX, '')
                logging.debug("Will create a clone pointing to '%s'" % commit_id)
                git.clone(clone_path, "%s" % bare_path, shared=True)
                git.reset(clone_path, commit_id, hard=True)
            else:
                git.clone(clone_path, "%s" % bare_path, branch=refname)
            # Needs reset so the proxy notices about the change on the mutable
            # http://docs.python.org/2.7/library/multiprocessing.html#managers
            # Locking on the assignment is guarateed by the library, but
            # additional locking is needed as A = A + 1 is a critical section.
            if inventory_lock:
                inventory_lock.acquire()
            inventory[name] += [refname]
            if inventory_lock:
                inventory_lock.release()
        except JensGitError, error:
            if os.path.isdir(clone_path):
                shutil.rmtree(clone_path)
            logging.error("Unable to create clone '%s' (%s)" % \
                (clone_path, error))

    if moved_refs:
        logging.debug("Processing moved refs of %s/%s (%s)..." % \
            (partition, name, moved_refs))
    for refname in moved_refs:
        clone_path = _compose_clone_repository_path(settings,
                name, partition, refname)
        logging.info("Updating ref '%s'" % clone_path)
        try:
            # If this fails, the bare would have the correct HEADs
            # but the clone will be out of date and won't ever be
            # updated until a new commit arrives to the bare.
            # Reason: a lock file left behind because Git was killed
            # mid-flight.
            git.fetch(clone_path)
            git.reset(clone_path, "origin/%s" % refname, hard=True)
        except JensGitError, error:
            logging.error("Unable to refresh clone '%s' (%s)" % \
                (clone_path, error))

    if deleted_refs:
        logging.debug("Processing deleted refs of %s/%s (%s)..." % \
            (partition, name, deleted_refs))
    for refname in deleted_refs:
        clone_path = _compose_clone_repository_path(settings,
                name, partition, refname)
        logging.info("Removing %s" % clone_path)
        try:
            if os.path.isdir(clone_path):
                shutil.rmtree(clone_path)
            if refname in inventory[name]:
                if inventory_lock:
                    inventory_lock.acquire()
                t = inventory[name]; t.remove(refname); inventory[name] = t
                if inventory_lock:
                    inventory_lock.release()
                logging.info("%s/%s deleted from inventory" % (name, refname))
        except OSError, error:
            logging.error("Couldn't delete %s/%s/%s (%s)" %
                (partition, name, refname, error))

def _compose_bare_repository_path(settings, name, partition):
    return settings.BAREDIR + "/%s/%s" % (partition, name)

def _compose_clone_repository_path(settings, name, partition, refname=None):
    path = settings.CLONEDIR + "/%s/%s" % (partition, name)
    if refname is not None:
        dirname = refname_to_dirname(settings, refname)
        path = "%s/%s" % (path, dirname)
    return path

def _calculate_delta(settings, definition, current):
    definition = set(definition.keys())
    current = set(current.keys())

    return {'new': definition.difference(current),
        'existing': definition.intersection(current),
        'deleted': current.difference(definition)}
