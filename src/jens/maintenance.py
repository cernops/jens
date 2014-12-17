# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import logging

import jens.git as git
from jens.errors import JensError, JensGitError
from jens.git import GIT_CLONE_TIMEOUT, GIT_FETCH_TIMEOUT

def refresh_metadata(settings, lock):
    lock.renew(2 * GIT_FETCH_TIMEOUT)
    _refresh_environments(settings)
    _refresh_repositories(settings)

def validate_directories(settings):
    directories = [settings.BAREDIR,
        settings.CLONEDIR,
        settings.CACHEDIR,
        settings.CACHEDIR + "/environments",
        settings.REPO_METADATADIR,
        settings.ENV_METADATADIR]

    for partition in ("modules", "hostgroups", "common"):
        directories.append(settings.BAREDIR + "/%s" % partition)
        directories.append(settings.CLONEDIR + "/%s" % partition)

    for directory in directories:
        _validate_directory(directory)

    if settings.LOCK_TYPE == 'FILE':
        _validate_directory(settings.FILELOCK_LOCKDIR)

    if not os.path.exists(settings.ENV_METADATADIR + "/.git"):
        raise JensError("%s not initialized (no Git repository found)" % \
            settings.ENV_METADATADIR)

    if not os.path.exists(settings.REPO_METADATA):
        raise JensError("Couldn't find metadata of repositories (%s not initialized)" % \
            settings.REPO_METADATADIR)

def _validate_directory(directory):
    try:
        os.stat(directory)
    except OSError:
        raise JensError("Directory '%s' does not exist" % directory)
    if not os.access(directory, os.W_OK):
        raise JensError("Cannot read or write on directory '%s'" % directory)

def _refresh_environments(settings):
    logging.debug("Refreshing environment metadata...")
    path = settings.ENV_METADATADIR
    try:
        git.fetch(path)
        git.reset(path, "origin/master", hard=True)
    except JensGitError, error:
        raise JensError("Couldn't refresh environments metadata (%s)" % error)

def _refresh_repositories(settings):
    logging.debug("Refreshing repositories metadata...")
    path = settings.REPO_METADATADIR
    try:
        git.fetch(path)
        git.reset(path, "origin/master", hard=True)
    except JensGitError, error:
        raise JensError("Couldn't refresh repositories metadata (%s)" % error)
