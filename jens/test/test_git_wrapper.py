# Copyright (C) 2014-2016, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import os
import jens.git_wrapper as git_wrapper
from mock import patch
from jens.test.testcases import JensTestCase
from jens.errors import JensGitError
from jens.test.tools import *


class GitWrapperTest(JensTestCase):
    def setUp(self):
        super(GitWrapperTest, self).setUp()

    def test_hash_object_raises_jens_git_error(self):
        self.assertRaises(JensGitError, git_wrapper.hash_object,
                          'platform-9-and-0.75')

    def test_gc_existing_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path,
                                              ['qa'])
        git_wrapper.gc(bare)

    def test_gc_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.gc, '/tmp/37d8s8dd')

    def test_gc_not_repository(self):
        not_repo_path = create_folder_not_repository(self.sandbox_path)
        self.assertRaises(JensGitError, git_wrapper.gc, not_repo_path)

    def test_bare_clone_existing_bare_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        git_wrapper.clone("%s/repo" % self.settings.CLONEDIR, bare, bare=True)

    def test_clone_existing_bare_repository_specific_branch(self):
        (bare, user) = create_fake_repository(self.sandbox_path,
                                              ['qa', 'foo'])
        git_wrapper.clone("%s/repo" % self.settings.CLONEDIR, bare,
                          bare=False, branch='foo')

    def test_clone_existing_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path,
                                              ['qa'])
        git_wrapper.clone("%s/repo" % self.settings.CLONEDIR, user)

    def test_clone_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.clone, "%s/repo"
                          % self.settings.CLONEDIR, '/tmp/37d8s8de')

    def test_clone_mirrored_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        clone_path = "%s/repo" % self.settings.CLONEDIR
        git_wrapper.clone(clone_path, bare, shared=True)
        self.assertTrue(os.path.isfile("%s/.git/objects/info/alternates" %
                                       clone_path))

    def test_fetch_existing_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        git_wrapper.fetch(user)

    @patch('git.remote.Remote.fetch')
    def test_fetch_fails_when_assertion_error_is_raised(self, stub):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        stub.side_effect = AssertionError()
        self.assertRaises(JensGitError, git_wrapper.fetch, user, prune=True)

    def test_fetch_existing_bare_repository_and_prune(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa', 'f'])
        jens_bare = "%s/_bare" % self.settings.BAREDIR
        git_wrapper.clone(jens_bare, bare, bare=True)
        git_wrapper.fetch(jens_bare, prune=True)
        self.assertTrue('f' in git_wrapper.get_refs(jens_bare))
        remove_branch_from_repo(user, 'f')
        git_wrapper.fetch(jens_bare, prune=False)
        self.assertTrue('f' in git_wrapper.get_refs(jens_bare))
        git_wrapper.fetch(jens_bare, prune=True)
        self.assertFalse('f' in git_wrapper.get_refs(jens_bare))

    def test_fetch_existing_bare_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        new_bare_path = "%s/cloned" % self.settings.CLONEDIR
        git_wrapper.clone(new_bare_path, bare, bare=True)
        git_wrapper.fetch(new_bare_path)

    def test_fetch_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.fetch, '/tmp/37d8s8df')

    def test_fetch_not_repository(self):
        not_repo_path = create_folder_not_repository(self.sandbox_path)
        self.assertRaises(JensGitError, git_wrapper.fetch, not_repo_path)

    def test_reset_to_head(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        head = get_repository_head(user)
        git_wrapper.reset(user, head)

    def test_reset_to_commit(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        head = get_repository_head(user)
        commit_id = add_commit_to_branch(user, "master")
        git_wrapper.reset(user, head)

    def test_reset_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.reset, '/tmp/37d8s8e0',
                          "37d8s8e0")

    def test_reset_non_existing_commit(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        self.assertRaises(JensGitError, git_wrapper.reset, user, "37d8s8e1")

    def test_reset_and_fetch_refs_match_after_remote_commit(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        jens_bare = "%s/_bare" % self.settings.BAREDIR
        git_wrapper.clone(jens_bare, bare, bare=True)
        jens_clone = "%s/_clone" % self.settings.CLONEDIR
        git_wrapper.clone(jens_clone, jens_bare, bare=False, branch='qa')
        fname = 'should_be_checkedout'
        commit_id = add_commit_to_branch(user, 'qa', fname=fname)
        git_wrapper.fetch(jens_bare)
        git_wrapper.fetch(jens_clone)
        git_wrapper.reset(jens_clone, 'origin/qa', hard=True)
        self.assertEqual(get_repository_head(jens_clone),
                          commit_id)
        self.assertTrue(os.path.isfile("%s/%s" % (jens_clone, fname)))


        new_commit = add_commit_to_branch(user, 'qa', fname=fname, remove=True)
        git_wrapper.fetch(jens_bare)
        git_wrapper.fetch(jens_clone)
        git_wrapper.reset(jens_clone, 'origin/qa', hard=True)
        self.assertFalse(os.path.isfile("%s/%s" %
            (jens_clone, fname)))

    def test_reset_not_repository(self):
        not_repo_path = create_folder_not_repository(self.sandbox_path)
        self.assertRaises(JensGitError, git_wrapper.reset, not_repo_path,
                          "37d8s8e2")

    def test_get_refs_existing_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        r = git_wrapper.get_refs(user)
        self.assertEqual(type(r), dict)
        self.assertTrue('qa' in r)
        self.assertTrue('master' in r)

    def test_get_refs_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.get_refs, '/tmp/37d8s8e3')

    def test_get_refs_not_repository(self):
        not_repo_path = create_folder_not_repository(self.sandbox_path)
        self.assertRaises(JensGitError, git_wrapper.get_refs, not_repo_path)

    def test_get_head_existing_repository(self):
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
        jens_clone = "%s/_clone" % self.settings.CLONEDIR
        git_wrapper.clone(jens_clone, bare, bare=False, branch='qa')
        commit_id = add_commit_to_branch(user, 'qa')
        git_wrapper.fetch(jens_clone)
        git_wrapper.reset(jens_clone, 'origin/qa', hard=True)
        self.assertEqual(git_wrapper.get_head(jens_clone),
                          commit_id)
        self.assertEqual(git_wrapper.get_head(jens_clone, short=False),
                          commit_id)
        self.assertEqual(git_wrapper.get_head(jens_clone, short=True),
                          commit_id[0:7])

    def test_get_head_non_existing_repository(self):
        self.assertRaises(JensGitError, git_wrapper.get_head, '/tmp/37d8s8e3')

    def test_get_head_not_repository(self):
        not_repo_path = create_folder_not_repository(self.sandbox_path)
        self.assertRaises(JensGitError, git_wrapper.get_head, not_repo_path)
