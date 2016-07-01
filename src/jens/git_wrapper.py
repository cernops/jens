# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import git
import logging
import os
import re
from jens.decorators import git_exec

GIT_DEFAULT_SOFT_TIMEOUT = 4
GIT_FETCH_TIMEOUT = GIT_DEFAULT_SOFT_TIMEOUT
GIT_CLONE_TIMEOUT = 8
GIT_GC_TIMEOUT = 10


def _init_git_env(timeout=GIT_DEFAULT_SOFT_TIMEOUT):
    env = os.environ.copy()
    env['GIT_HTTP_LOW_SPEED_TIME'] = str(timeout)
    env['GIT_HTTP_LOW_SPEED_LIMIT'] = "2000"
    git_context = git.cmd.Git()

    return env, git_context

def hash_object(path):
    args = [path]
    kwargs = {}
    env, git_context = _init_git_env()
    logging.debug("Hashing object %s" % path)

    @git_exec
    def hash_object_exec(*args, **kwargs):
        return git.cmd.Git().hash_object(*args, **kwargs).strip()

    return hash_object_exec(env=env, git_context=git_context,
                            args=args, kwargs=kwargs)

def gc(repository_path, aggressive=False, bare=False):
    args = []
    kwargs = {"quiet": True, "aggressive": aggressive}
    env, git_context = _init_git_env(GIT_GC_TIMEOUT)
    logging.debug("Collecting garbage in %s" % repository_path)
    repo = git.Repo(repository_path)
    if bare is False:
        repository_path = "%s/.git" % repository_path
    gitdir = repository_path
    logging.debug("Setting GIT_DIR to %s" % gitdir)
    env['GIT_DIR'] = gitdir

    @git_exec
    def gc_exec(*args, **kwargs):
        repo.git.gc(*args, **kwargs)

    gc_exec(env=env, git_context=git_context, args=args, kwargs=kwargs)

def clone(repository_path, url, bare=False, shared=False, branch=None):
    args = [url, repository_path]
    kwargs = {"no-hardlinks": True, "shared": shared}
    env, git_context = _init_git_env(GIT_CLONE_TIMEOUT)
    logging.debug("Cloning from %s to %s" % (url, repository_path))
    if bare is True:
        kwargs["bare"] = True
        kwargs["mirror"] = True
    if branch is not None:
        kwargs["branch"] = branch

    @git_exec
    def clone_exec(*args, **kwargs):
        git.Repo.clone_from(*args, **kwargs)

    clone_exec(env=env, git_context=git_context, args=args, kwargs=kwargs)

def fetch(repository_path, bare=False, prune=False):
    args = []
    kwargs = {"no-tags": True, "prune": prune}
    env, git_context = _init_git_env(GIT_FETCH_TIMEOUT)
    logging.debug("Fetching new refs in %s" % repository_path)
    if bare is False:
        repository_path = "%s/.git" % repository_path
    logging.debug("Setting GIT_DIR to %s" % repository_path)
    env['GIT_DIR'] = repository_path

    @git_exec
    def fetch_exec(*args, **kwargs):
        git.Repo(repository_path).remotes.origin.fetch(*args, **kwargs)

    fetch_exec(env=env, git_context=git_context, args=args, kwargs=kwargs)

def reset(repository_path, treeish, hard=False):
    args = [treeish]
    kwargs = {"hard": hard}
    env, git_context = _init_git_env()
    logging.debug("Resetting %s to %s" % (repository_path, treeish))
    repo = git.Repo(repository_path)

    gitdir = "%s/.git" % repository_path
    logging.debug("Setting GIT_DIR to %s" % gitdir)
    env['GIT_DIR'] = gitdir

    gitworkingtree = repository_path
    logging.debug("Setting GIT_WORK_TREE to %s" % gitworkingtree)
    env['GIT_WORK_TREE'] = gitworkingtree

    @git_exec
    def reset_exec(*args, **kwargs):
        git.refs.head.HEAD(repo).reset(*args, **kwargs)

    reset_exec(env=env, git_context=git_context, args=args, kwargs=kwargs)

def get_refs(repository_path):
    args = []
    kwargs = {"heads": True}
    env, git_context = _init_git_env()
    logging.debug("Setting GIT_DIR to %s" % repository_path)
    env['GIT_DIR'] = repository_path

    @git_exec
    def get_refs_exec(*args, **kwargs):
        return git_context.show_ref(*args, **kwargs)

    refs = get_refs_exec(env=env, git_context=git_context,
                         args=args, kwargs=kwargs)

    result = {}
    for ref in refs.strip().split('\n'):
        sha, name = ref.split(" ")
        name = re.search(r"refs/heads/(?P<refname>.+)", name).group("refname")
        result[name] = sha
    return result
