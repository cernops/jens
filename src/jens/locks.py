# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging
import time
from urllib3.exceptions import TimeoutError

from jens.errors import JensLockError, JensLockExistsError

class JensLockFactory(object):
    @staticmethod
    def makeLock(settings, tries=1, waittime=10):
        if settings.LOCK_TYPE == 'FILE':
            return JensFileLock(settings, tries, waittime)
        elif settings.LOCK_TYPE == 'ETCD':
            return JensEtcdLock(settings, tries, waittime)
        elif settings.LOCK_TYPE == 'DISABLED':
            logging.warn("Danger zone: no locking has been configured!")
            return JensDumbLock(settings, tries, waittime)
        else: # Shouldn't ever happen, config is validated
            raise JensLockError("Unknown lock type '%s'", settings.LOCK_TYPE)

class JensLock(object):
    def __init__(self, settings, tries, waittime):
        self.settings = settings
        self.tries = tries
        self.waittime = waittime

    def __enter__(self):
        for attempt in range(1, self.tries+1):
            logging.info("Obtaining lock '%s' (attempt: %d)..." %
                (self.settings.LOCK_NAME, attempt))
            try:
                self.obtain_lock()
                logging.debug("Lock acquired")
                return self
            except JensLockExistsError, error:
                if attempt == self.tries:
                    raise error
                else:
                    logging.debug("Couldn't lock (%s). Sleeping for %d seconds..." %
                        (error, self.waittime))
                    time.sleep(self.waittime)

    def __exit__(self, type, value, traceback):
        logging.info("Releasing lock '%s'..." % self.settings.LOCK_NAME)
        self.release_lock()

    def renew(self, ttl=10):
        if ttl <= 0:
            logging.warn("Invalid new TTL, resetting to 1 by default")
            ttl = 1
        logging.info("Setting '%s' lock TTL to %d secs..." % \
            (self.settings.LOCK_NAME, ttl))
        self.renew_lock(ttl)

class JensFileLock(JensLock):
    def obtain_lock(self):
        lockfile_path = self.__get_lock_file_path()
        try:
            self.lockfile = open(lockfile_path, "w")
        except IOError, error:
            raise JensLockError("Can't open lock file for writing (%s)" % error)

        import fcntl
        try:
            fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, error:
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

class JensEtcdLock(JensLock):
    def __init__(self, settings, tries, waittime):
        try:
            super(JensEtcdLock, self).__init__(settings, tries, waittime)
            import etcd
            self.etcd = etcd
        except ImportError:
            raise JensLockError("python-etcd not installed")

    def obtain_lock(self):
        from urllib3.exceptions import TimeoutError
        servers = map(lambda x: x.split(':'), self.settings.ETCD_SERVERS)
        servers = map(lambda x: (x[0], int(x[1]) if len(x) > 1 else 4001), servers)
        logging.debug("Etcd servers: %s", servers)
        try:
            client = self.etcd.Client(host=tuple(servers), allow_redirect=True,
                allow_reconnect=True)
            logging.debug("Current leader: %s" % client.leader)
            logging.debug("Machines in the cluster: %s" % client.machines)
            self.lock = client.get_lock('/%s' % self.settings.LOCK_NAME,
                ttl=self.settings.ETCD_INITIALTTL)
            self.lock.acquire(timeout=self.settings.ETCD_ACQTIMEOUT)
        except TimeoutError:
            raise JensLockExistsError("Lock already taken")
        except self.etcd.EtcdException, error:
            raise JensLockError("Etcd locking failed: '%s'" % error)
        # Apparently, if the leader is being elected python-etcd raises
        # exception.Exception FFS.
        except Exception, error:
            raise JensLockError("Couldn't get the etcd lock (%s)" % error)

    def release_lock(self):
        try:
            self.lock.release()
        except TimeoutError:
            raise JensLockError("The connection timed out when releasing the lock")
        except self.etcd.EtcdException, error:
            raise JensLockError("Etcd locking failed: '%s'" % error)

    def renew_lock(self, ttl, timeout=3):
        try:
            self.lock.renew(ttl, timeout)
        except TimeoutError:
            raise JensLockError("The connection timed out when renewing the lock")
        except self.etcd.EtcdException, error:
            raise JensLockError("Etcd lock renewal failed: '%s'" % error)
