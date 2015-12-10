# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import shutil
import fcntl

from mock import Mock, patch

from jens.maintenance import refresh_metadata
from jens.git import clone
from jens.errors import JensError

from jens.test.tools import create_fake_repository
from jens.test.tools import add_commit_to_branch, reset_branch_to
from jens.test.tools import get_repository_head

from jens.test.testcases import JensTestCase

class MetadataTest(JensTestCase):
    def setUp(self):
        super(MetadataTest, self).setUp()

        (self.environments_bare, self.environments) = \
            create_fake_repository(self.settings, self.sandbox_path)
        shutil.rmtree(self.settings.ENV_METADATADIR)
        clone(self.settings.ENV_METADATADIR, self.environments_bare, \
            branch='master')

        (self.repositories_bare, self.repositories) = \
            create_fake_repository(self.settings, self.sandbox_path)
        shutil.rmtree(self.settings.REPO_METADATADIR)
        clone(self.settings.REPO_METADATADIR, self.repositories_bare, \
            branch='master')

    def _jens_refresh_metadata(self, errorsExpected=False, errorRegexp=None):
        refresh_metadata(self.settings, self.lock)
        if errorsExpected:
            self.assertLogErrors(errorRegexp)
        else:
            self.assertLogNoErrors()

    #### TESTS ####

    def test_basic_updates(self):
        self._jens_refresh_metadata()

        new_commit = add_commit_to_branch(self.settings, \
            self.environments, 'master')
        self._jens_refresh_metadata()
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.ENV_METADATADIR), new_commit)

        new_commit = add_commit_to_branch(self.settings, \
            self.repositories, 'master')
        self._jens_refresh_metadata()
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.REPO_METADATADIR), new_commit)

    def test_fails_if_remote_repositories_unavailable(self):
        initial = get_repository_head(self.settings, self.repositories)
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.REPO_METADATADIR), initial)
        self._jens_refresh_metadata()
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.REPO_METADATADIR), initial)

        # -- "not available" --

        temporary_path = "%s-temp" % self.repositories_bare
        shutil.move(self.repositories_bare, temporary_path)
        self.assertRaises(JensError, self._jens_refresh_metadata)

        # -- "available again" --

        shutil.move(temporary_path, self.repositories_bare)
        self._jens_refresh_metadata()

    def test_fails_if_remote_environments_unavailable(self):
        initial = get_repository_head(self.settings, self.environments)
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.ENV_METADATADIR), initial)
        self._jens_refresh_metadata()
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.ENV_METADATADIR), initial)

        # -- "not available" --

        temporary_path = "%s-temp" % self.environments_bare
        shutil.move(self.environments_bare, temporary_path)
        self.assertRaises(JensError, self._jens_refresh_metadata)

        # -- "available again" --

        shutil.move(temporary_path, self.environments_bare)
        self._jens_refresh_metadata()

    def test_repositories_is_history_is_mangled(self):
        self._jens_refresh_metadata()

        bombs = []
        for x in range(0,4):
            bombs.append(add_commit_to_branch(self.settings, self.repositories, 'master'))

        self._jens_refresh_metadata()

        self.assertEquals(get_repository_head(self.settings, self.repositories), bombs[-1])

        reset_branch_to(self.settings, self.repositories, "master", bombs[0])
        new_commit = add_commit_to_branch(self.settings, self.repositories, \
            'master', force=True)

        self._jens_refresh_metadata()

        # Should be the same if it did a reset
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.REPO_METADATADIR), new_commit)

    def test_environments_is_history_is_mangled(self):
        self._jens_refresh_metadata()

        bombs = []
        for x in range(0,4):
            bombs.append(add_commit_to_branch(self.settings, self.environments, 'master'))

        self._jens_refresh_metadata()

        self.assertEquals(get_repository_head(self.settings, self.environments), bombs[-1])

        reset_branch_to(self.settings, self.environments, "master", bombs[0])
        new_commit = add_commit_to_branch(self.settings, self.environments, \
            'master', force=True)

        self._jens_refresh_metadata()

        # Should be the same if it did a reset
        self.assertEquals(get_repository_head(self.settings,\
            self.settings.ENV_METADATADIR), new_commit)

    @patch.object(fcntl, 'flock', side_effect=IOError)
    def test_fails_if_lock_cannot_be_acquired(self, mock):
        self.assertRaises(JensError, self._jens_refresh_metadata)
