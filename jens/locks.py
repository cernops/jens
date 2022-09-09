# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import logging
import time
from jens.settings import Settings

from jens.errors import JensLockError, JensLockExistsError

class JensLockFactory(object):
    @staticmethod
    def make_lock(tries=1, waittime=10):
        settings = Settings()
        if settings.LOCK_TYPE == 'FILE':
            return JensFileLock(tries, waittime)
        elif settings.LOCK_TYPE == 'DISABLED':
            logging.warning("Danger zone: no locking has been configured!")
            return JensDumbLock(tries, waittime)
        else:  # Shouldn't ever happen, config is validated
            raise JensLockError("Unknown lock type '%s'", settings.LOCK_TYPE)

class JensLock(object):
    def __init__(self, tries, waittime):
        self.settings = Settings()
        self.tries = tries
        self.waittime = waittime

    def __enter__(self):
        for attempt in range(1, self.tries+1):
            logging.info("Obtaining lock '%s' (attempt: %d)...",
                         self.settings.LOCK_NAME, attempt)
            try:
                self.obtain_lock()
                logging.debug("Lock acquired")
                return self
            except JensLockExistsError as error:
                if attempt == self.tries:
                    raise error
                else:
                    logging.debug("Couldn't lock (%s). Sleeping for %d seconds...",
                                  error, self.waittime)
                    time.sleep(self.waittime)

    def __exit__(self, e_type, e_value, e_traceback):
        logging.info("Releasing lock '%s'...", self.settings.LOCK_NAME)
        self.release_lock()

    def renew(self, ttl=10):
        if ttl <= 0:
            logging.warning("Invalid new TTL, resetting to 1 by default")
            ttl = 1
        logging.info("Setting '%s' lock TTL to %d secs...",
                     self.settings.LOCK_NAME, ttl)
        self.renew_lock(ttl)

    def obtain_lock(self):
        raise NotImplementedError('You are not meant to instantiate this class')

    def release_lock(self):
        raise NotImplementedError('You are not meant to instantiate this class')

    def renew_lock(self, ttl):
        raise NotImplementedError('You are not meant to instantiate this class')

class JensFileLock(JensLock):
    def __init__(self, tries, waittime):
        super(JensFileLock, self).__init__(tries, waittime)
        self.lockfile = None

    def obtain_lock(self):
        lockfile_path = self.__get_lock_file_path()
        try:
            self.lockfile = open(lockfile_path, "w")
        except IOError as error:
            raise JensLockError("Can't open lock file for writing (%s)" % error)

        import fcntl
        try:
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as error:
            raise JensLockExistsError("Lock already taken")

    def release_lock(self):
        # Nothing to do, the OS will close the FDs after finishing.
        pass

    def renew_lock(self, ttl):
        # Nothing to do, local lock
        pass

    def __get_lock_file_path(self):
        return self.settings.FILELOCK_LOCKDIR + "/%s" % self.settings.LOCK_NAME

class JensDumbLock(JensLock):
    def obtain_lock(self):
        pass

    def release_lock(self):
        pass

    def renew_lock(self, ttl):
        pass
