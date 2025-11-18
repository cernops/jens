# Copyright (C) 2014-2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import git
import logging
from jens.decorators import git_exec

def hash_object(path):
    args = [path]
    kwargs = {}
    logging.debug("Hashing object %s", path)

    @git_exec
    def hash_object_exec(*args, **kwargs):
        return git.cmd.Git().hash_object(*args, **kwargs).strip()

    return hash_object_exec(name='hash-object', args=args, kwargs=kwargs)

# pylint: disable=invalid-name
# (too short but all match Git command names)
def gc(repository_path, aggressive=False):
    args = []
    kwargs = {"quiet": True, "aggressive": aggressive}
    logging.debug("Collecting garbage in %s", repository_path)

    @git_exec
    def gc_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        repo.git.gc(*args, **kwargs)

    gc_exec(name='gc', args=args, kwargs=kwargs)

def clone(repository_path, url, bare=False, shared=False, branch=None):
    args = [url, repository_path]
    kwargs = {"no-hardlinks": True, "shared": shared,
              "odbt": git.GitCmdObjectDB}
    logging.debug("Cloning from %s to %s", url, repository_path)
    if bare is True:
        kwargs["bare"] = True
        kwargs["mirror"] = True
    if branch is not None:
        kwargs["branch"] = branch

    @git_exec
    def clone_exec(*args, **kwargs):
        git.Repo.clone_from(*args, **kwargs)

    clone_exec(name='clone', args=args, kwargs=kwargs)

def fetch(repository_path, prune=False):
    args = []
    kwargs = {"no-tags": True, "prune": prune}
    logging.debug("Fetching new refs in %s", repository_path)

    @git_exec
    def fetch_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        repo.remotes.origin.fetch(*args, **kwargs)
        # You may face that the repo object leaves lock files behind after fetch, so we need to
        # clean them up with a forced object delete
        # Ref: https://github.com/gitpython-developers/GitPython/issues/718#issuecomment-360267779
        # We suspect this is due to git cat-file calls in fetch implementation together with
        # using GitCmdObjectDB as the object database
        # Ref: https://gitpython.readthedocs.io/en/stable/tutorial.html#gitcmdobjectdb
        # Using GitDB seems to fix the issue but we keep using GitCmdObjectDB for consistency
        repo.__del__()

    fetch_exec(name='fetch', args=args, kwargs=kwargs)

def reset(repository_path, treeish, hard=False):
    args = [treeish]
    kwargs = {"hard": hard}
    logging.debug("Resetting %s to %s", repository_path, treeish)

    @git_exec
    def reset_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        repo.git.reset(*args, **kwargs)

    reset_exec(name='reset', args=args, kwargs=kwargs)

def get_refs(repository_path):
    args = []
    kwargs = {}

    @git_exec
    def get_refs_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        return dict((h.name, h.commit.hexsha) for h in repo.heads)

    return get_refs_exec(name='show-ref', args=args, kwargs=kwargs)

def rev_parse(repository_path, ref, short=False):
    args = [ref]
    kwargs = {"short": short}

    @git_exec
    def rev_parse_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        return repo.git.rev_parse(*args, **kwargs)

    return rev_parse_exec(name='rev-parse', args=args, kwargs=kwargs)

def get_head(repository_path, short=False):
    args = []
    kwargs = {}
    logging.debug("Getting HEAD of %s", repository_path)

    @git_exec
    def get_head_exec(*args, **kwargs):
        repo = git.Repo(repository_path, odbt=git.GitCmdObjectDB)
        sha = repo.head.commit.hexsha
        if short:
            sha = rev_parse(repository_path, sha, short=True)
        return sha

    return get_head_exec(name='get-head', args=args, kwargs=kwargs)
