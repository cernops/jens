# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import jens.git_wrapper as git_wrapper
from jens.test.testcases import JensTestCase
from jens.errors import JensGitError
from jens.test.tools import create_fake_repository

class GitWrapperTest(JensTestCase):
    def setUp(self):
        super(GitWrapperTest, self).setUp()

    def test_hash_object_raises_jens_git_error(self):
        self.assertRaises(JensGitError, git_wrapper.hash_object, 'platform-9-and-0.75')

    def test_gc_existing_repository(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        git_wrapper.gc(bare)

    def test_gc_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.gc, '/tmp/37d8s8dd')

    def test_fetch_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.fetch, '/tmp/37d8s8de')
