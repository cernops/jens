# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

# while WIP, just no to rename current module for now
from __future__ import absolute_import
import logging
import os
import re
import git
import threading
import signal
from subprocess import Popen, PIPE

from jens.errors import JensGitError

GITBINPATH = "git"

GIT_DEFAULT_SOFT_TIMEOUT = 4
GIT_FETCH_TIMEOUT = GIT_DEFAULT_SOFT_TIMEOUT
GIT_CLONE_TIMEOUT = 8
GIT_GC_TIMEOUT = 10

def _init_git_env(timeout=GIT_DEFAULT_SOFT_TIMEOUT):
    env = os.environ.copy()
    env['GIT_HTTP_LOW_SPEED_TIME'] = str(timeout)
    env['GIT_HTTP_LOW_SPEED_LIMIT'] = "2000"
    return env

def hash_object(path):
    logging.debug("Hashing object %s" % path)
    env = _init_git_env()

    with git.cmd.Git().custom_environment(**env):
        return git.cmd.Git().hash_object(path).strip()

def gc(repository_path, aggressive=False, bare=False):
    logging.debug("Collecting garbage in %s" % repository_path)
    repo = git.Repo(repository_path)
    if bare is False:
        repository_path = "%s/.git" % repository_path

    env = _init_git_env(GIT_GC_TIMEOUT)
    logging.debug("Setting GIT_DIR to %s" % gitdir)
    env['GIT_DIR'] = gitdir

    with git.cmd.Git().custom_environment(**env):
        repo.git.gc('--quiet', aggressive=aggressive)

def clone(repository_path, url, bare=False, shared=False, branch=None):
    logging.debug("Cloning from %s to %s" % (url, repository_path))
    args = {"no-hardlinks": True}
    args["shared"] = shared
    if bare is True:
        args["bare"] = True
        args["mirror"] = True
    if branch is not None:
        args["branch"] = branch

    env = _init_git_env(GIT_CLONE_TIMEOUT)
    try:
        git.Repo.clone_from(url, repository_path, env=env, **args)
    except git.exc.GitCommandError as e:
        raise JensGitError("Couldn't execute git %s (%s)" % \
            (args, e.stderr.strip()))

def fetch(repository_path, bare=False, prune=False):
    logging.debug("Fetching new refs in %s" % repository_path)
    args = {"no-tags": True, "prune": prune}
    if bare is False:
        repository_path = "%s/.git" % repository_path
    env = _init_git_env(GIT_FETCH_TIMEOUT)
    logging.debug("Setting GIT_DIR to %s" % repository_path)
    env['GIT_DIR'] = repository_path

    try:
        with git.cmd.Git().custom_environment(**env):
            git.Repo(repository_path).remotes.origin.fetch(**args)
    except git.exc.GitCommandError as e:
        raise JensGitError("Couldn't execute git %s (%s)" % \
            (args, e.stderr.strip()))

def reset(repository_path, treeish, hard=False):
    logging.debug("Resetting %s to %s" % (repository_path, treeish))
    repo = git.Repo(repository_path)
    args = {"hard": hard}
    env = _init_git_env()
    
    gitdir = "%s/.git" % repository_path
    logging.debug("Setting GIT_DIR to %s" % gitdir)
    env['GIT_DIR'] = gitdir
    
    gitworkingtree = repository_path
    logging.debug("Setting GIT_WORK_TREE to %s" % gitworkingtree)
    env['GIT_WORK_TREE'] = gitworkingtree

    try:
        with git.cmd.Git().custom_environment(**env):
            git.refs.head.HEAD(repo).reset(treeish, **args)
    except git.exc.GitCommandError as e:
        raise JensGitError("Couldn't execute git %s (%s)" % \
            (args, e.stderr.strip()))

def get_refs(repository_path):
    env = _init_git_env()
    logging.debug("Setting GIT_DIR to %s" % repository_path)
    env['GIT_DIR'] = repository_path
    
    git_context = git.cmd.Git()
    with git_context.custom_environment(**env):
        refs = git_context.show_ref("--heads")

    result = {}
    for ref in refs.strip().split('\n'):
        sha, name = ref.split(" ")
        name = re.search(r"refs/heads/(?P<refname>.+)", name).group("refname")
        result[name] = sha
    return result

def _git(args, gitdir=None, gitworkingtree=None,
        timeout=GIT_DEFAULT_SOFT_TIMEOUT):
    env = os.environ.copy()
    if gitdir is not None:
        logging.debug("Setting GIT_DIR to %s" % gitdir)
        env['GIT_DIR'] = gitdir
    if gitworkingtree is not None:
        logging.debug("Setting GIT_WORK_TREE to %s" % gitworkingtree)
        env['GIT_WORK_TREE'] = gitworkingtree
    env['GIT_HTTP_LOW_SPEED_TIME'] = str(timeout)
    env['GIT_HTTP_LOW_SPEED_LIMIT'] = "2000"
    args = [GITBINPATH] + args
    logging.debug("Executing git %s" % args)
    (returncode, stdout, stderr) = _exec(args, env, timeout)
    if returncode != 0:
        raise JensGitError("Couldn't execute git %s (%s)" % \
            (args, stderr.strip()))
    return (stdout, returncode)

def _exec(args, environment, timeout):
    git = Popen(args, stdout = PIPE, stderr=PIPE, env=environment)
    (stdout, stderr) = git.communicate()
    return (git.returncode, stdout, stderr)
