# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import logging
import fcntl

from jens.settings import Settings
import jens.git_wrapper as git
from jens.decorators import timed
from jens.errors import JensError, JensGitError

@timed
def refresh_metadata():
    _refresh_environments()
    _refresh_repositories()

def validate_directories():
    settings = Settings()
    directories = [settings.BAREDIR,
                   settings.CLONEDIR,
                   settings.CACHEDIR,
                   settings.CACHEDIR + "/environments",
                   settings.ENVIRONMENTSDIR,
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
        raise JensError("%s not initialized (no Git repository found)" %
                        settings.ENV_METADATADIR)

    if not os.path.exists(settings.REPO_METADATA):
        raise JensError("Couldn't find metadata of repositories (%s not initialized)" %
                        settings.REPO_METADATADIR)

def _validate_directory(directory):
    try:
        os.stat(directory)
    except OSError:
        raise JensError("Directory '%s' does not exist" % directory)
    if not os.access(directory, os.W_OK):
        raise JensError("Cannot read or write on directory '%s'" % directory)

def _refresh_environments():
    settings = Settings()
    logging.debug("Refreshing environment metadata...")
    path = settings.ENV_METADATADIR
    try:
        git.fetch(path)
        git.reset(path, "origin/master", hard=True)
    except JensGitError, error:
        raise JensError("Couldn't refresh environments metadata (%s)" % error)

def _refresh_repositories():
    settings = Settings()
    logging.debug("Refreshing repositories metadata...")
    path = settings.REPO_METADATADIR
    try:
        git.fetch(path)
        try:
            metadata = open(settings.REPO_METADATA, 'r')
        except IOError, error:
            raise JensError("Could not open '%s' to put a lock on it" %
                            settings.REPO_METADATA)
        # jens-gitlab-producer collaborates with jens-update asynchronously
        # so have to make sure that exclusive access to the file when writing
        # is guaranteed. Of course, the reader will have to implement the same
        # protocol on the other end.
        try:
            logging.info("Trying to acquire a lock to refresh the metadata...")
            fcntl.flock(metadata, fcntl.LOCK_EX)
            logging.debug("Lock acquired")
        except IOError, error:
            metadata.close()
            raise JensError("Could not lock '%s'" % settings.REPO_METADATA)
        git.reset(path, "origin/master", hard=True)
        try:
            logging.debug("Trying to release the lock used to refresh the metadata...")
            fcntl.flock(metadata, fcntl.LOCK_UN)
            logging.debug("Lock released")
        except IOError, error:
            raise JensError("Could not unlock '%s'" % settings.REPO_METADATA)
        finally:
            metadata.close()
    except JensGitError, error:
        raise JensError("Couldn't refresh repositories metadata (%s)" % error)
