# Copyright (C) 2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import shutil

from jens.maintenance import validate_directories
from jens.git_wrapper import clone
from jens.settings import Settings
from jens.errors import JensError

from jens.test.tools import create_fake_repository

from jens.test.testcases import JensTestCase

class MaintenanceTest(JensTestCase):
    def setUp(self):
        super(MaintenanceTest, self).setUp()

        self.settings = Settings()

        # validate_directories() expects both below to look
        # like a Git repository.

        (self.environments_bare, self.environments) = \
            create_fake_repository(self.sandbox_path)
        shutil.rmtree(self.settings.ENV_METADATADIR)
        clone(self.settings.ENV_METADATADIR, self.environments_bare, \
            branch='master')

        (self.repositories_bare, self.repositories) = \
            create_fake_repository(self.sandbox_path)
        shutil.rmtree(self.settings.REPO_METADATADIR)
        clone(self.settings.REPO_METADATADIR, self.repositories_bare, \
            branch='master')


    #### TESTS ####

    def test_all_expected_directories_are_present_and_inited(self):
        validate_directories()

    def test_no_bares_dir(self):
        shutil.rmtree(self.settings.BAREDIR)
        self.assertRaisesRegex(JensError,
            self.settings.BAREDIR, validate_directories)

    def test_no_cache_dir(self):
        shutil.rmtree(self.settings.CACHEDIR)
        self.assertRaisesRegex(JensError,
            self.settings.CACHEDIR, validate_directories)

    def test_no_clones_dir(self):
        shutil.rmtree(self.settings.CLONEDIR)
        self.assertRaisesRegex(JensError,
            self.settings.CLONEDIR, validate_directories)

    def test_no_environments_dir(self):
        shutil.rmtree(self.settings.ENVIRONMENTSDIR)
        self.assertRaisesRegex(JensError,
            self.settings.ENVIRONMENTSDIR, validate_directories)

    def test_no_repometadata_dir(self):
        shutil.rmtree(self.settings.REPO_METADATADIR)
        self.assertRaisesRegex(JensError,
            self.settings.REPO_METADATADIR, validate_directories)

    def test_no_envmetadata_dir(self):
        shutil.rmtree(self.settings.ENV_METADATADIR)
        self.assertRaisesRegex(JensError,
            self.settings.ENV_METADATADIR, validate_directories)
