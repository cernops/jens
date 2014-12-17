# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging
import os
import re
import threading
import signal
from subprocess import Popen, PIPE

from jens.errors import JensGitError

GITBINPATH = "git"

GIT_DEFAULT_SOFT_TIMEOUT = 4
GIT_FETCH_TIMEOUT = GIT_DEFAULT_SOFT_TIMEOUT
GIT_CLONE_TIMEOUT = 8
GIT_GC_TIMEOUT = 10

def hash_object(path):
    logging.debug("Hashing object %s" % path)
    out, rc = _git(["hash-object", path])
    return out.strip()

def gc(repository_path, aggressive=False, bare=False):
    logging.debug("Collecting garbage in %s" % repository_path)
    args = ["gc", "--quiet"]
    if bare is False:
        repository_path = "%s/.git" % repository_path
    if aggressive is True:
        args.append("--aggressive")
    _git(args, gitdir=repository_path, timeout=GIT_GC_TIMEOUT)

def clone(repository_path, url, bare=False, shared=False, branch=None):
    logging.debug("Cloning from %s to %s" % (url, repository_path))
    args = ["clone", "--no-hardlinks"]
    if bare is True:
        args.extend(["--bare", "--mirror"])
    if shared is True:
        args.append("--shared")
    if branch is not None:
        args.extend(["--branch", branch])
    args.extend([url, repository_path])
    _git(args, timeout=GIT_CLONE_TIMEOUT)

def fetch(repository_path, bare=False, prune=False):
    logging.debug("Fetching new refs in %s" % repository_path)
    args = ["fetch", "--no-tags"]
    if prune is True:
        args.extend(["--prune"])
    if bare is False:
        repository_path = "%s/.git" % repository_path
    args.extend(["origin"])
    _git(args, gitdir=repository_path, timeout=GIT_FETCH_TIMEOUT)

def merge(repository_path, branchname):
    logging.debug("Merging in %s with origin/%s" % (repository_path, branchname))
    gitdir="%s/.git" % repository_path
    _git(["merge", "origin/%s" % branchname],
        gitdir=gitdir, gitworkingtree=repository_path)

def reset(repository_path, treeish, hard=False):
    logging.debug("Resetting %s to %s" % (repository_path, treeish))
    gitdir = "%s/.git" % repository_path
    args = ["reset"]
    if hard:
        args.append("--hard")
    args.append(treeish)
    _git(args, gitdir=gitdir, gitworkingtree=repository_path)

def get_refs(repository_path):
    out, returncode = _git(["show-ref", "--heads"], gitdir=repository_path)
    result = {}
    for ref in out.strip().split('\n'):
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
