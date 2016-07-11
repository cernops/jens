# Copyright (C) 2014-2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import jens.git_wrapper as git_wrapper
from jens.test.testcases import JensTestCase
from jens.errors import JensGitError
from jens.test.tools import create_fake_repository, add_commit_to_branch,\
                            get_repository_head

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

    def test_clone_existing_bare_repository(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        git_wrapper.clone("%s/repo" % self.settings.CLONEDIR, bare, bare=True)

    def test_clone_existing_repository(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        git_wrapper.clone("%s/repo" % self.settings.CLONEDIR, user)

    def test_clone_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.clone, "%s/repo" 
                          % self.settings.CLONEDIR, '/tmp/37d8s8de')

    def test_fetch_existing_repository(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        git_wrapper.fetch(user)

    def test_fetch_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.fetch, '/tmp/37d8s8df')

    def test_reset_to_head(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        head = get_repository_head(self.settings, user)
        git_wrapper.reset(user, head)

    def test_reset_to_commit(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        head = get_repository_head(self.settings, user)
        commit_id = add_commit_to_branch(self.settings, user, "master")
        git_wrapper.reset(user, head)

    def test_reset_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.reset, '/tmp/37d8s8e0', "37d8s8e0")

    def test_reset_non_existing_commit(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        self.assertRaises(JensGitError, git_wrapper.reset, user, "37d8s8e1")

    def test_get_refs_existing_repository(self):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        r = git_wrapper.get_refs(user)
        self.assertEqual(type(r), dict)
        self.assertTrue('qa' in r)
        self.assertTrue('master' in r)

    def test_get_refs_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.get_refs, '/tmp/37d8s8e2')
