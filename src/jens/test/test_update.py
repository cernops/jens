# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import yaml
import shutil

from jens.messaging import count_pending_hints
from jens.repos import refresh_repositories
from jens.locks import JensLockFactory
from jens.environments import refresh_environments
from jens.git import get_refs

from jens.test.tools import ensure_environment, destroy_environment
from jens.test.tools import init_repositories
from jens.test.tools import add_repository, del_repository
from jens.test.tools import create_fake_repository
from jens.test.tools import add_branch_to_repo, remove_branch_from_repo
from jens.test.tools import add_commit_to_branch, reset_branch_to

from jens.test.testcases import JensTestCase

COMMIT_PREFIX = JensTestCase.COMMIT_PREFIX
MANDATORY_BRANCHES = JensTestCase.MANDATORY_BRANCHES

class UpdateTest(JensTestCase):
    def setUp(self):
        super(UpdateTest, self).setUp()

        ensure_environment(self.settings, 'production', 'master')
        ensure_environment(self.settings, 'qa', 'qa')

        init_repositories(self.settings)
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        add_repository(self.settings, 'common', 'site', bare)
        self.site_user = user
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        add_repository(self.settings, 'common', 'hieradata', bare)
        self.hieradata_user = user

        self.lock = JensLockFactory.makeLock(self.settings)

    def _create_fake_module(self, modulename, branches=[]):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, branches)
        add_repository(self.settings, 'modules', modulename, bare)
        return user

    def _create_fake_hostgroup(self, hostgroup, branches=[]):
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, branches)
        add_repository(self.settings, 'hostgroups', hostgroup, bare)
        return user

    def _jens_update(self, errorsExpected=False, errorRegexp=None, hints=None):
        repositories_deltas, inventory = \
            refresh_repositories(self.settings, self.lock, hints=hints)
        refresh_environments(self.settings, self.lock, repositories_deltas, inventory)
        if errorsExpected:
            self.assertLogErrors(errorRegexp)
        else:
            self.assertLogNoErrors()
        return repositories_deltas

    #### TESTS ####

    def test_base(self):
        self._jens_update()

        self.assertBare('common/site')
        self.assertBare('common/hieradata')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('common/site/%s' % branch)
            self.assertClone('common/hieradata/%s' % branch)
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentLinks("production")

    def test_empty_common_hieradata(self):
        self.settings.COMMON_HIERADATA_ITEMS = []
        self._jens_update()

        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentLinks("production")

    def test_missing_common_hieradata_item(self):
        self.settings.COMMON_HIERADATA_ITEMS = ["missing"]
        self._jens_update()

        self.assertEnvironmentBrokenLinks("qa")
        self.assertEnvironmentBrokenLinks("production")

    def test_base_with_directory_environments(self):
        self.settings.DIRECTORY_ENVIRONMENTS = True
        self._jens_update()

        self.assertBare('common/site')
        self.assertBare('common/hieradata')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('common/site/%s' % branch)
            self.assertClone('common/hieradata/%s' % branch)
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentHasAConfigFile("qa")
        self.assertEnvironmentHasAConfigFileAndParserSet('qa', None)
        self.assertEnvironmentLinks("production")
        self.assertEnvironmentHasAConfigFile("production")
        self.assertEnvironmentHasAConfigFileAndParserSet('production', None)

    def test_directory_environments_not_enabled_by_default(self):
        self._jens_update()

        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentDoesNotHaveAConfigFile("qa")

    def test_repositories_add_and_remove_mandatory_expanded_and_cleanup(self):
        self._jens_update()

        self._create_fake_module('electron', ['qa'])
        self._create_fake_hostgroup('aisusie', ['qa'])

        repositories_deltas = self._jens_update()

        self.assertBare('modules/electron')
        self.assertTrue('electron' in repositories_deltas['modules']['new'])
        self.assertBare('hostgroups/aisusie')
        self.assertTrue('aisusie' in repositories_deltas['hostgroups']['new'])
        for branch in MANDATORY_BRANCHES:
            self.assertClone('modules/electron/%s' % branch)
            self.assertClone('hostgroups/aisusie/%s' % branch)
        self.assertEnvironmentLinks("production")
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentOverride('production', 'modules/electron', 'master')
        self.assertEnvironmentOverride('production', 'hostgroups/hg_aisusie', 'master')

        del_repository(self.settings, 'hostgroups', 'aisusie')

        repositories_deltas = self._jens_update()

        self.assertTrue('aisusie' in repositories_deltas['hostgroups']['deleted'])
        self.assertBare('modules/electron')
        self.assertNotBare('hostgroups/aisusie')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('modules/electron/%s' % branch)
            self.assertNotClone('hostgroups/aisusie/%s' % branch)
        self.assertEnvironmentLinks("production")
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentOverride('production', 'modules/electron', 'master')
        self.assertEnvironmentOverrideDoesntExist('production', 'hostgroups/hg_aisusie')
        self.assertEnvironmentOverrideDoesntExist('qa', 'hostgroups/hg_aisusie')

    def test_repositories_cleanup_includes_commits(self):
        self._jens_update()

        self._create_fake_module('electron', ['qa'])
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        commit_id = get_refs(murdock_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:%s" % override])

        repositories_deltas = self._jens_update()

        self.assertTrue('electron' in repositories_deltas['modules']['new'])
        self.assertTrue('murdock' in repositories_deltas['hostgroups']['new'])
        self.assertBare('modules/electron')
        self.assertBare('hostgroups/murdock')
        self.assertClone('hostgroups/murdock/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)

        del_repository(self.settings, 'hostgroups', 'murdock')

        repositories_deltas = self._jens_update()

        self.assertTrue('murdock' in repositories_deltas['hostgroups']['deleted'])
        self.assertNotBare('hostgroups/murdock')
        self.assertNotClone('hostgroups/murdock/master')
        self.assertNotClone('hostgroups/murdock/qa')
        self.assertEnvironmentOverrideDoesntExist('test', 'hostgroups/hg_murdock')

    def test_new_repository_is_not_added_if_broken(self):
        self._jens_update()

        electron_path = self._create_fake_module('electron', ['qa'])
        electron_path_bare = electron_path.replace('/user/', '/bare/')
        temporary_path = "%s-temp" % electron_path_bare
        shutil.move(electron_path_bare, temporary_path)

        # -- Repository is not "available"

        repositories_deltas = self._jens_update(errorsExpected=True,
            errorRegexp="repos.+electron")

        self.assertFalse('electron' in repositories_deltas['modules']['new'])
        self.assertNotBare('modules/electron')
        self.assertNotClone('modules/electron/qa')
        self.assertEnvironmentLinks("qa")

        # -- Repository is "available" now

        shutil.move(temporary_path, electron_path_bare)

        repositories_deltas = self._jens_update(errorsExpected=False)

        self.assertTrue('electron' in repositories_deltas['modules']['new'])
        self.assertBare('modules/electron')
        self.assertClone('modules/electron/qa')
        self.assertClone('modules/electron/master')
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentLinks("production")

    def test_clone_is_updated_if_remote_changes(self):
        h1_path = self._create_fake_hostgroup('h1', ['qa', 'boom'])
        m1_path = self._create_fake_module('m1', ['qa', 'boom'])

        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['h1:boom'], modules=['m1:boom'])

        self._jens_update()

        self.assertBare('hostgroups/h1')
        self.assertBare('modules/m1')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/h1/%s' % branch)
            self.assertClone('modules/m1/%s' % branch)

        h1_commit_id = add_commit_to_branch(self.settings, h1_path, 'qa')
        m1_commit_id = add_commit_to_branch(self.settings, m1_path, 'master')
        h1_boom_commit_id = add_commit_to_branch(self.settings, h1_path, 'boom')
        m1_boom_commit_id = add_commit_to_branch(self.settings, m1_path, 'boom')

        self._jens_update()

        self.assertClone('hostgroups/h1/qa', pointsto=h1_commit_id)
        self.assertClone('modules/m1/master', pointsto=m1_commit_id)
        self.assertClone('hostgroups/h1/boom', pointsto=h1_boom_commit_id)
        self.assertClone('modules/m1/boom', pointsto=m1_boom_commit_id)

    def test_all_is_added_to_new_environments(self):
        self._create_fake_module('electron', ['qa'])
        self._create_fake_hostgroup('aisusie', ['qa'])

        self._jens_update()

        self.assertBare('modules/electron')
        self.assertBare('hostgroups/aisusie')
        self.assertClone('modules/electron/qa')
        self.assertClone('hostgroups/aisusie/qa')

        # -- Add new environment, check all is added

        ensure_environment(self.settings, 'test', 'qa')

        self._jens_update()

        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride('test', 'modules/electron', 'qa')
        self.assertEnvironmentOverride('test', 'hostgroups/hg_aisusie', 'qa')

    def test_bare_not_created_if_missing_mandatory_branches(self):
        self._create_fake_module('electron')

        self._jens_update(errorsExpected=True,
            errorRegexp="electron.+mandatory branches")

        self.assertNotBare('modules/electron')
        self.assertNotClone('modules/electron/master')

    def test_branch_not_expanded_if_not_needed(self):
        self._create_fake_hostgroup('murdock', ['qa', 'aijens_etcd'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
        self.assertNotClone('hostgroups/murdock/aijens_etcd')

    def test_override_to_branch(self):
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['murdock:aijens_etcd'], modules=['foo:bar'])
        self._create_fake_hostgroup('murdock', ['qa', 'aijens_etcd'])
        self._create_fake_module('foo', ['qa', 'bar'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertClone('hostgroups/murdock/aijens_etcd')
        self.assertClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test", 'modules/foo', 'bar')

    def test_override_to_branch_malformed_override_wrong_partition_name(self):
        environment = {'notifications': 'higgs@example.org',
            'default': 'master', 'overrides': {}}
        # Usual typo
        environment['overrides']['hostgroup'] = {'murdock': 'aijens_etcd'}
        environment['overrides']['module'] = {'foo': 'bar'}
        environment['overrides']['foo'] = {'bar': 'baz'}
        environment_file = open("%s/test.yaml" % self.settings.ENV_METADATADIR, 'w+')
        yaml.dump(environment, environment_file, default_flow_style=False)
        environment_file.close()

        self._create_fake_hostgroup('murdock', ['qa', 'aijens_etcd'])
        self._create_fake_module('foo', ['qa', 'bar'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertNotClone('hostgroups/murdock/aijens_etcd')
        self.assertNotClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'master')
        self.assertEnvironmentOverride("test", 'modules/foo', 'master')

    def test_environment_with_empty_overrides_is_ignored(self):
        environment = {'notifications': 'higgs@example.org',
            'default': 'master', 'overrides': None}
        environment_file = open("%s/test.yaml" % self.settings.ENV_METADATADIR, 'w+')
        yaml.dump(environment, environment_file, default_flow_style=False)
        environment_file.close()

        self._create_fake_hostgroup('murdock', ['qa'])
        self._create_fake_module('foo', ['qa'])

        self._jens_update(errorsExpected=True,
            errorRegexp="test")

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertEnvironmentDoesntExist("test")

    def test_environment_is_deleted_if_ok_and_then_broken(self):
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['murdock:aijens_etcd'], modules=['foo:bar'])
        ensure_environment(self.settings, 'test2', 'master',
            hostgroups=['murdock:aijens_etcd'])
        self._create_fake_hostgroup('murdock', ['qa', 'aijens_etcd'])
        self._create_fake_module('foo', ['qa', 'bar'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertClone('hostgroups/murdock/aijens_etcd')
        self.assertClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentLinks("test2")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test", 'modules/foo', 'bar')
        self.assertEnvironmentOverride("test2", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test2", 'modules/foo', 'master')

        os.remove("%s/test.yaml" % self.settings.ENV_METADATADIR)
        environment = {'notifications': 'higgs@example.org',
            'default': 'master', 'overrides': None}
        environment_file = open("%s/test.yaml" % self.settings.ENV_METADATADIR, 'w+')
        yaml.dump(environment, environment_file, default_flow_style=False)
        environment_file.close()

        self._create_fake_hostgroup('murdock', ['qa'])
        self._create_fake_module('foo', ['qa'])

        self._jens_update(errorsExpected=True,
            errorRegexp="test")

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        # Needed by test2
        self.assertClone('hostgroups/murdock/aijens_etcd')
        self.assertNotClone('modules/foo/bar')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertEnvironmentDoesntExist("test")
        self.assertEnvironmentOverride("test2", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test2", 'modules/foo', 'master')

    def test_override_to_mandatory_branch_with_new_repo(self):
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['murdock:qa'], modules=['foo:qa'])
        self._create_fake_hostgroup('murdock', ['qa'])
        self._create_fake_module('foo', ['qa'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        self.assertBare('modules/foo')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'qa')
        self.assertEnvironmentOverride("test", 'modules/foo', 'qa')

    def test_override_to_commit(self):
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        commit_id = get_refs(murdock_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:%s" % override])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
        self.assertClone('hostgroups/murdock/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)

    def test_override_to_commit_is_static(self):
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        commit_id = get_refs(murdock_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:%s" % override])

        self._jens_update()

        # Check that the clone points to commit_id
        self.assertClone('hostgroups/murdock/qa', pointsto=commit_id)
        self.assertClone('hostgroups/murdock/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)

        new_qa = add_commit_to_branch(self.settings, murdock_path, 'qa')

        self._jens_update()

        self.assertClone('hostgroups/murdock/qa', pointsto=new_qa)
        self.assertClone('hostgroups/murdock/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)

    def test_override_to_branch_and_commit_combined(self):
        self._jens_update()

        self._create_fake_module('foo', ['qa', 'bar'])
        self._create_fake_module('bar', ['qa'])
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        commit_id = get_refs(murdock_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', None,
            hostgroups=["murdock:%s" % override],
            modules=['foo:bar'])

        self._jens_update()

        self.assertBare('modules/foo')
        self.assertBare('modules/bar')
        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
            self.assertClone('modules/foo/%s' % branch)
            self.assertClone('modules/bar/%s' % branch)
        self.assertClone('hostgroups/murdock/.%s' % commit_id, pointsto=commit_id)
        self.assertClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)
        self.assertEnvironmentOverride("test", 'modules/foo', 'bar')

    def test_broken_links_if_override_not_present_as_ref(self):
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['murdock:aijens_etcd'])
        self._create_fake_hostgroup('murdock', ['qa'])

        # No error message, the ref won't be selected for expansion.
        self._jens_update()

        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
        self.assertEnvironmentBrokenLinks("test")

    def test_broken_links_if_override_not_present_as_commit(self):
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')

        commit_id = "deadbeef" * 5
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:%s" % override])

        # Commits are always expanded, there's no check to verify
        # if they exist before asking for expansion.
        self._jens_update(errorsExpected=True,
            errorRegexp=commit_id)

        self.assertEnvironmentBrokenLinks("test")

    def test_nothing_created_if_repo_override_not_in_inventory(self):
        self._create_fake_module('useful', ['qa'])
        self._jens_update()

        ensure_environment(self.settings, 'test', 'qa',
            modules=['lost:foo'], hostgroups=['miss:rats'])

        self._jens_update()

        self.assertBare('modules/useful')
        self.assertNotBare('modules/lost')
        self.assertNotBare('hostgroups/miss')
        self.assertEnvironmentOverride("test", 'modules/useful', 'qa')
        self.assertEnvironmentOverrideDoesntExist("test", 'modules/lost')
        self.assertEnvironmentOverrideDoesntExist("test", 'hostgroups/hg_miss')

    def test_prefix_is_case_insensitive(self):
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        commit_id = get_refs(murdock_path + '/.git')['qa']
        prefix = COMMIT_PREFIX
        prefix = prefix[0:len(prefix)/2] + \
            prefix[len(prefix)/2:len(prefix)].upper()
        override = "{0}{1}".format(prefix, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:%s" % override])

        self._jens_update()

        self.assertClone('hostgroups/murdock/.%s' % commit_id,
            pointsto=commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', override)

    def test_override_not_deleted_if_shared(self):
        ensure_environment(self.settings, 'test', 'master')
        self._create_fake_hostgroup('murdock', ['qa', 'aijens_etcd'])
        sonic_path = self._create_fake_module('sonic', ['qa'])
        commit_id = get_refs(sonic_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)

        self._jens_update()

        self.assertNotClone('hostgroups/murdock/aijens_etcd')

        # ----- Add two environments needing the same override

        ensure_environment(self.settings, 'test', 'master',
            modules=['sonic:%s' % override],
            hostgroups=['murdock:aijens_etcd'])
        ensure_environment(self.settings, 'test2', 'master',
            modules=['sonic:%s' % override],
            hostgroups=['murdock:aijens_etcd'])

        self._jens_update()

        self.assertClone('hostgroups/murdock/aijens_etcd')
        self.assertClone('modules/sonic/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test2", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test", 'modules/sonic', override)
        self.assertEnvironmentOverride("test2", 'modules/sonic', override)
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentNumberOf("test2", "modules", 1)
        self.assertEnvironmentNumberOf("test2", "hostgroups", 1)

        # ----- Destroy one of them

        destroy_environment(self.settings, 'test2')

        self._jens_update()

        self.assertClone('hostgroups/murdock/aijens_etcd')
        self.assertClone('modules/sonic/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentDoesntExist("test2")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'aijens_etcd')
        self.assertEnvironmentOverride("test", 'modules/sonic', override)

    def test_branch_is_added_after_initial_expand_and_removed_if_not_nec(self):
        ensure_environment(self.settings, 'test', 'master')
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])

        self._jens_update()

        # --- Add override

        add_branch_to_repo(self.settings, murdock_path, 'foo')
        destroy_environment(self.settings, 'test')
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['murdock:foo'])

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
        self.assertClone('hostgroups/murdock/foo')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'foo')

        # --- Remove it

        destroy_environment(self.settings, 'test')
        ensure_environment(self.settings, 'test', 'master')

        self._jens_update()

        self.assertBare('hostgroups/murdock')
        for branch in MANDATORY_BRANCHES:
            self.assertClone('hostgroups/murdock/%s' % branch)
        self.assertNotClone('hostgroups/murdock/foo')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'master')

    def test_broken_link_if_branch_disappears(self):
        ensure_environment(self.settings, 'test', 'master',
            modules=['foo:bar'])
        foo_path = self._create_fake_module('foo', ['qa', 'bar'])

        self._jens_update()

        self.assertClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/foo', 'bar')

        # ---- Remove branch (a broken link should be kept)

        remove_branch_from_repo(self.settings, foo_path, 'bar')

        self._jens_update()

        self.assertNotClone('modules/foo/bar')
        self.assertEnvironmentBrokenLinks("test")
        self.assertEnvironmentOverrideExistsButBroken("test", 'modules/foo', 'bar')

        # ---- Add it again (link should be ok again)

        add_branch_to_repo(self.settings, foo_path, 'bar')

        self._jens_update()

        self.assertClone('modules/foo/bar')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/foo', 'bar')

    def test_environments_with_no_default_dont_grow(self):
        guy_path = self._create_fake_module('guy', ['qa'])
        commit_id = get_refs(guy_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', None,
            modules=["guy:%s" % override])

        self._jens_update()

        self.assertBare('modules/guy')
        self.assertClone('modules/guy/.%s' % commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 0)
        self.assertEnvironmentOverride("test", 'modules/guy', override)

        # -- The new module shouldn't be present in 'test' env.

        self._create_fake_module('newguy', ['qa'])

        repositories_deltas = self._jens_update()

        self.assertTrue('newguy' in repositories_deltas['modules']['new'])
        self.assertEnvironmentOverride('production', 'modules/newguy', 'master')
        self.assertEnvironmentOverride('qa', 'modules/newguy', 'qa')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 0)
        self.assertEnvironmentOverrideDoesntExist("test", 'modules/newguy')

    def test_environments_with_no_default_only_expand_overrides(self):
        self._jens_update()

        self._create_fake_module('m1', ['qa', 'lol'])
        self._create_fake_module('m2', ['qa', 'lol'])
        self._create_fake_hostgroup('h1', ['qa', 'lol'])
        self._create_fake_hostgroup('h2', ['qa', 'lol'])

        ensure_environment(self.settings, 'test', None,
            modules=["m1:lol"], hostgroups=["h1:lol"])
        ensure_environment(self.settings, 'test2', None)

        self._jens_update()

        self.assertBare('modules/m1')
        self.assertBare('modules/m2')
        self.assertBare('hostgroups/h1')
        self.assertBare('hostgroups/h2')
        self.assertClone('modules/m1/lol')
        self.assertClone('hostgroups/h1/lol')
        self.assertNotClone('modules/m2/lol')
        self.assertNotClone('hostgroups/h2/lol')
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentOverride("test", 'modules/m1', 'lol')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_h1', 'lol')
        self.assertEnvironmentLinks("test2")
        self.assertEnvironmentNumberOf("test2", "modules", 0)
        self.assertEnvironmentNumberOf("test2", "hostgroups", 0)
        self.assertEnvironmentOverrideDoesntExist("test", 'modules/m2')
        self.assertEnvironmentOverrideDoesntExist("test", 'hostgroups/hg_h2')
        self.assertEnvironmentOverrideDoesntExist("test2", 'modules/m1')
        self.assertEnvironmentOverrideDoesntExist("test2", 'hostgroups/hg_h1')
        self.assertEnvironmentOverrideDoesntExist("test2", 'modules/m2')
        self.assertEnvironmentOverrideDoesntExist("test2", 'hostgroups/hg_h2')

    def test_environments_shrink(self):
        guy_path = self._create_fake_module('guy', ['qa'])
        self._create_fake_module('guy2', ['qa'])
        commit_id = get_refs(guy_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', 'master',
            modules=["guy:%s" % override])
        ensure_environment(self.settings, 'test2', None,
            modules=["guy:%s" % override])

        self._jens_update()

        self.assertBare('modules/guy')
        self.assertClone('modules/guy/.%s' % commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 2)
        self.assertEnvironmentNumberOf("test", "hostgroups", 0)
        self.assertEnvironmentOverride("test", 'modules/guy', override)
        self.assertEnvironmentLinks("test2")
        self.assertEnvironmentNumberOf("test2", "modules", 1)
        self.assertEnvironmentNumberOf("test2", "hostgroups", 0)
        self.assertEnvironmentOverride("test2", 'modules/guy', override)

        # -- The deleted module shouldn't be present in any  env.

        del_repository(self.settings, 'modules', 'guy')

        repositories_deltas = self._jens_update()

        self.assertTrue('guy' in repositories_deltas['modules']['deleted'])
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 0)
        self.assertEnvironmentOverrideDoesntExist("test", 'modules/guy')

        self.assertEnvironmentLinks("test2")
        self.assertEnvironmentNumberOf("test2", "modules", 0)
        self.assertEnvironmentNumberOf("test2", "hostgroups", 0)
        self.assertEnvironmentOverrideDoesntExist("test2", 'modules/guy')
        self.assertEnvironmentOverrideDoesntExist('production', 'modules/guy')
        self.assertEnvironmentOverrideDoesntExist('qa', 'modules/guy')

    def test_environments_with_no_default_can_be_modified(self):
        guy_path = self._create_fake_module('guy', ['qa'])
        commit_id = get_refs(guy_path + '/.git')['qa']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', None,
            modules=["guy:%s" % override])

        self._jens_update()

        self.assertBare('modules/guy')
        self.assertClone('modules/guy/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/guy', override)

        # ---- Point the override to a different commit

        destroy_environment(self.settings, 'test')
        commit_id = get_refs(guy_path + '/.git')['master']
        override = "{0}{1}".format(COMMIT_PREFIX, commit_id)
        ensure_environment(self.settings, 'test', None,
            modules=["guy:%s" % override])

        self._jens_update()

        self.assertBare('modules/guy')
        self.assertClone('modules/guy/.%s' % commit_id, pointsto=commit_id)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/guy', override)

    def test_broken_repository_does_not_create_anything_and_recovers(self):
        self._jens_update()

        path = "/tmp/foobroken"
        add_repository(self.settings, 'modules', 'broken', path)
        self._create_fake_module('newguy', ['qa'])

        repositories_deltas = self._jens_update(errorsExpected=True,
            errorRegexp='broken')

        self.assertNotBare('modules/broken')
        self.assertBare('modules/newguy')
        self.assertFalse('broken' in repositories_deltas['modules']['new'])
        self.assertTrue('newguy' in repositories_deltas['modules']['new'])
        for branch in MANDATORY_BRANCHES:
            self.assertNotClone('modules/broken/%s' % branch)
            self.assertClone('modules/newguy/%s' % branch)
        self.assertEnvironmentLinks("production")
        self.assertEnvironmentLinks("qa")
        self.assertEnvironmentOverrideDoesntExist("production", 'modules/broken')
        self.assertEnvironmentOverride("production", 'modules/newguy', 'master')

    def test_malformed_environments_are_not_processed(self):
        ensure_environment(self.settings, 'ok1', 'master', hostgroups=['flik:flak'])
        ensure_environment(self.settings, 'ok2', 'qa', modules=['stop:here'])
        ensure_environment(self.settings, 'ok3', None)
        self._create_fake_hostgroup('flik', ['qa', 'flak', 'dontexpand'])
        self._create_fake_module('stop', ['qa', 'here', 'dontexpand'])

        fail1 = {}
        environment_file = open("%s/%s.yaml" % (self.settings.ENV_METADATADIR, "fail1"), 'w+')
        yaml.dump(fail1, environment_file, default_flow_style=False)
        environment_file.close()

        fail2 = {'notifications': 'foo@bar.com', 'overrides': None}
        environment_file = open("%s/%s.yaml" % (self.settings.ENV_METADATADIR, "fail2"), 'w+')
        yaml.dump(fail2, environment_file, default_flow_style=False)
        environment_file.close()

        fail3 = {'overrides': {'hostgroups': {'flik': 'dontexpand'}}}
        environment_file = open("%s/%s.yaml" % (self.settings.ENV_METADATADIR, "fail3"), 'w+')
        yaml.dump(fail3, environment_file, default_flow_style=False)
        environment_file.close()

        fail4 = {'default': 'master', 'overrides': {'hostgroups': None}}
        environment_file = open("%s/%s.yaml" % (self.settings.ENV_METADATADIR, "fail4"), 'w+')
        yaml.dump(fail4, environment_file, default_flow_style=False)
        environment_file.close()

        self._jens_update(errorsExpected=True)

        self.assertEnvironmentLinks("ok1")
        self.assertEnvironmentLinks("ok2")
        self.assertEnvironmentLinks("ok3")
        self.assertClone('hostgroups/flik/flak')
        self.assertClone('modules/stop/here')
        self.assertNotClone('hostgroups/flik/dontexpand')
        self.assertNotClone('modules/stop/dontexpand')
        self.assertEnvironmentOverride("ok1", 'hostgroups/hg_flik', 'flak')
        self.assertEnvironmentOverride("ok2", 'modules/stop', 'here')
        self.assertEnvironmentDoesntExist("fail1")
        self.assertEnvironmentDoesntExist("fail2")
        self.assertEnvironmentDoesntExist("fail3")
        self.assertEnvironmentDoesntExist("fail4")

    def test_clone_and_bare_still_present_if_fetch_fails(self):
        yi_path = self._create_fake_hostgroup('yi', ['qa'])
        yi_path_bare = yi_path.replace('/user/', '/bare/')

        self._jens_update()

        self.assertBare('hostgroups/yi')
        self.assertClone('hostgroups/yi/qa')

        # ---- Make it temporary unavailable
        shutil.move("%s/refs" % yi_path_bare, "%s/goat" % yi_path_bare)

        self._jens_update(errorsExpected=True)

        self.assertBare('hostgroups/yi')
        self.assertClone('hostgroups/yi/qa')


        # ---- Bring it back
        shutil.move("%s/goat" % yi_path_bare, "%s/refs" % yi_path_bare)
        add_branch_to_repo(self.settings, yi_path, 'lol')
        ensure_environment(self.settings, 'test', 'qa',
            hostgroups=['yi:lol'])

        self._jens_update()

        self.assertBare('hostgroups/yi')
        self.assertClone('hostgroups/yi/qa')
        self.assertClone('hostgroups/yi/lol')
        self.assertEnvironmentLinks("test")

    def test_mandatory_branches_are_not_left_behind_if_initial_expand_fails(self):
        self._create_fake_module('foo', ['qa'])

        self._jens_update()

        self.assertClone('modules/foo/qa')

        # ---- The module is not new and qa won't be in the inventory
        # after reading it from disk, so it should be considered as a new
        # branch to expand as if it was an override (as it's "always needed")

        shutil.rmtree("%s/modules/foo/qa" % self.settings.CLONEDIR)
        os.remove("%s/repositories" % self.settings.CACHEDIR)

        self._jens_update()

        self.assertClone('modules/foo/qa')

    def test_clone_is_updated_if_remotes_history_is_mangled(self):
        h1_path = self._create_fake_hostgroup('h1', ['qa', 'boom'])

        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['h1:boom'])

        self._jens_update()

        self.assertBare('hostgroups/h1')

        bombs = []
        for x in range(0,4):
            bombs.append(add_commit_to_branch(self.settings, h1_path, 'boom'))

        self._jens_update()

        self.assertClone('hostgroups/h1/boom', pointsto=bombs[-1])

        reset_branch_to(self.settings, h1_path, "boom", bombs[0])
        new_commit = add_commit_to_branch(self.settings,
            h1_path, 'boom', force=True)

        self._jens_update()

        self.assertClone('hostgroups/h1/boom', pointsto=new_commit)

    def test_environment_completely_deleted_even_if_conf_file_is_present(self):
        self.settings.DIRECTORY_ENVIRONMENTS = True
        self._create_fake_hostgroup('murdock', ['qa', 'foo'])
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:foo"])

        self._jens_update()

        self.assertClone('hostgroups/murdock/foo')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'foo')
        self.assertEnvironmentNumberOf("test", "modules", 0)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentHasAConfigFile("test")

        destroy_environment(self.settings, 'test')

        # ----- This should destroy all, including the configuration file

        self._jens_update()

        self.assertEnvironmentDoesntExist("test")

    def test_clones_not_refreshed_if_bare_not_in_hints(self):
        self.settings.MODE = "ONDEMAND"
        murdock_path = self._create_fake_hostgroup('murdock', ['qa'])
        old_qa = get_refs(murdock_path + '/.git')['qa']
        ensure_environment(self.settings, 'test', 'master',
            hostgroups=["murdock:qa"])

        self._jens_update()

        self.assertClone('hostgroups/murdock/qa', pointsto=old_qa)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'qa')

        new_qa = add_commit_to_branch(self.settings, murdock_path, 'qa')

        self._jens_update(hints={'hostgroups': ['other']})

        self.assertClone('hostgroups/murdock/qa', pointsto=old_qa)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'qa')

        self._jens_update(hints=None)

        self.assertClone('hostgroups/murdock/qa', pointsto=new_qa)
        self.assertEnvironmentOverride("test", 'hostgroups/hg_murdock', 'qa')

    def test_clones_refreshed_if_bare_in_hints(self):
        self.settings.MODE = "ONDEMAND"
        murdock_path = self._create_fake_module('murdock', ['qa'])
        old_qa = get_refs(murdock_path + '/.git')['qa']
        old_site_qa = get_refs(self.site_user + '/.git')['qa']
        old_hieradata_qa = get_refs(self.hieradata_user + '/.git')['qa']
        ensure_environment(self.settings, 'test', 'master',
            modules=["murdock:qa"])

        self._jens_update()

        self.assertClone('modules/murdock/qa', pointsto=old_qa)
        self.assertEnvironmentOverride("test", 'modules/murdock', 'qa')

        new_qa = add_commit_to_branch(self.settings, murdock_path, 'qa')
        new_site_qa = add_commit_to_branch(self.settings, self.site_user, 'qa')
        new_hieradata_qa = add_commit_to_branch(self.settings, self.hieradata_user, 'qa')

        # Test that it actually intersects existing and hints
        self._jens_update(hints={'modules': ['foo']})

        self.assertClone('modules/murdock/qa', pointsto=old_qa)
        self.assertClone('common/site/qa', pointsto=old_site_qa)
        self.assertClone('common/hieradata/qa', pointsto=old_hieradata_qa)
        self.assertEnvironmentOverride("test", 'modules/murdock', 'qa')

        self._jens_update(hints=
            {'modules': ['murdock', 'foo'], 'hostgroups': ['foo'], 'common': ['site']})

        self.assertClone('modules/murdock/qa', pointsto=new_qa)
        self.assertClone('common/site/qa', pointsto=new_site_qa)
        self.assertClone('common/hieradata/qa', pointsto=old_hieradata_qa)
        self.assertEnvironmentOverride("test", 'modules/murdock', 'qa')

        self._jens_update(hints= {'common': ['hieradata']})
        self.assertClone('common/hieradata/qa', pointsto=new_hieradata_qa)

    def test_clones_not_refreshed_if_constaints_enabled_but_no_partition_declared(self):
        self.settings.MODE = "ONDEMAND"
        murdock_path = self._create_fake_module('murdock', ['qa'])
        old_qa = get_refs(murdock_path + '/.git')['qa']
        ensure_environment(self.settings, 'test', 'master',
            modules=["murdock:qa"])

        self._jens_update()

        self.assertBare('modules/murdock')
        self.assertClone('modules/murdock/qa', pointsto=old_qa)
        self.assertEnvironmentOverride("test", 'modules/murdock', 'qa')

        new_qa = add_commit_to_branch(self.settings, murdock_path, 'qa')

        self._jens_update(hints={'hostgroups': ['foo']})

        self.assertClone('modules/murdock/qa', pointsto=old_qa)

    def test_created_if_new_and_removed_if_gone_regardless_of_hints(self):
        self.settings.MODE = "ONDEMAND"
        murdock_path = self._create_fake_module('murdock', ['qa'])
        steve_path = self._create_fake_hostgroup('steve', ['qa'])
        old_qa = get_refs(murdock_path + '/.git')['qa']
        ensure_environment(self.settings, 'test', 'master',
            modules=["murdock:qa"])

        self._jens_update(hints={'hostgroups': ['foo']})

        self.assertBare('modules/murdock')
        self.assertBare('hostgroups/steve')
        self.assertClone('modules/murdock/master')
        self.assertClone('modules/murdock/qa', pointsto=old_qa)
        self.assertClone('hostgroups/steve/qa')
        self.assertClone('hostgroups/steve/master')
        self.assertEnvironmentNumberOf("test", "modules", 1)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentOverride("test", 'modules/murdock', 'qa')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_steve', 'master')

        del_repository(self.settings, 'modules', 'murdock')

        repositories_deltas = self._jens_update(hints={'hostgroups': ['foo']})

        self.assertTrue('murdock' in repositories_deltas['modules']['deleted'])
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentNumberOf("test", "modules", 0)
        self.assertEnvironmentNumberOf("test", "hostgroups", 1)
        self.assertEnvironmentOverrideDoesntExist("test", 'modules/murdock')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_steve', 'master')

    def test_environments_are_created_and_known_branches_expanded_regardless_of_update_hints(self):
        self.settings.MODE = "ONDEMAND"
        h1_path = self._create_fake_hostgroup('h1', ['qa', 'boom'])
        old_h1_qa = get_refs(h1_path + '/.git')['qa']
        m1_path = self._create_fake_module('m1', ['qa', 'boom'])

        self._jens_update()

        ensure_environment(self.settings, 'test', 'master',
            hostgroups=['h1:boom'], modules=['m1:boom'])
        new_h1_qa = add_commit_to_branch(self.settings, h1_path, 'qa')

        self._jens_update(hints={'hostgroups': ['other']})

        self.assertClone('hostgroups/h1/qa', pointsto=old_h1_qa)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/m1', 'boom')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_h1', 'boom')

        self._jens_update(hints={'modules': ['m1'], 'hostgroups': ['h1']})

        self.assertClone('hostgroups/h1/qa', pointsto=new_h1_qa)
        self.assertEnvironmentLinks("test")
        self.assertEnvironmentOverride("test", 'modules/m1', 'boom')
        self.assertEnvironmentOverride("test", 'hostgroups/hg_h1', 'boom')

    def test_hint_readded_to_the_queue_if_fetch_fails(self):
        self.settings.MODE = "ONDEMAND"
        yi_path = self._create_fake_hostgroup('yi', ['qa'])
        old_yi_qa = get_refs(yi_path + '/.git')['qa']
        yi_path_bare = yi_path.replace('/user/', '/bare/')

        self._jens_update()

        self.assertBare('hostgroups/yi')
        self.assertClone('hostgroups/yi/qa')

        new_yi_qa = add_commit_to_branch(self.settings, yi_path, 'qa')

        # ---- Make it temporary unavailable
        shutil.move("%s/refs" % yi_path_bare, "%s/goat" % yi_path_bare)

        self.assertEqual(0, count_pending_hints(self.settings))
        self._jens_update(hints={'hostgroups': ['yi']}, errorsExpected=True)
        self.assertEqual(1, count_pending_hints(self.settings))

        self.assertBare('hostgroups/yi')
        self.assertClone('hostgroups/yi/qa', pointsto=old_yi_qa)

        # ---- Bring it back
        shutil.move("%s/goat" % yi_path_bare, "%s/refs" % yi_path_bare)

        self._jens_update(hints={'hostgroups': ['yi']})
        self.assertClone('hostgroups/yi/qa', pointsto=new_yi_qa)

    def test_directory_environments_parser_modes(self):
        self.settings.DIRECTORY_ENVIRONMENTS = True
        ensure_environment(self.settings, 'noparser', 'qa')
        ensure_environment(self.settings, 'parserfuture', 'qa', parser='future')
        ensure_environment(self.settings, 'parsercurrent', 'qa', parser='current')
        self._jens_update()

        self.assertEnvironmentLinks('noparser')
        self.assertEnvironmentHasAConfigFile('noparser')
        self.assertEnvironmentHasAConfigFileAndParserSet('noparser', None)
        self.assertEnvironmentLinks('parserfuture')
        self.assertEnvironmentHasAConfigFile('parserfuture')
        self.assertEnvironmentHasAConfigFileAndParserSet('parserfuture', 'future')
        self.assertEnvironmentLinks('parsercurrent')
        self.assertEnvironmentHasAConfigFile('parsercurrent')
        self.assertEnvironmentHasAConfigFileAndParserSet('parsercurrent', 'current')

    def test_directory_environments_parser_modes_bad_value(self):
        ensure_environment(self.settings, 'parserbroken', 'qa', parser='broken')
        self._jens_update(errorsExpected=True)
        self.assertEnvironmentDoesntExist('parserbroken')
