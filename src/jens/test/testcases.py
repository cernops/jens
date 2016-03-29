# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import unittest
import logging
import re
import tempfile
import time

from string import Template
from configobj import ConfigObj

from jens.locks import JensLockFactory
from jens.settings import Settings
from jens.reposinventory import get_inventory
from jens.test.tools import init_sandbox, destroy_sandbox
from jens.tools import refname_to_dirname
from jens.tools import dirname_to_refname
from jens.test.tools import get_repository_head

BASE_CONFIG = Template("""
[main]
baredir = $sandbox/lib/bare
clonedir = $sandbox/lib/clone
cachedir = $sandbox/lib/cache
environmentsdir = $sandbox/lib/environments
debuglevel = $debuglevel
logdir = $sandbox/log
mandatorybranches = $mandatory_branches
environmentsmetadatadir = $sandbox/lib/metadata/environments
repositorymetadatadir = $sandbox/lib/metadata/repositories
repositorymetadata = $sandbox/lib/metadata/repositories/repositories.yaml
hashprefix = $hashprefix
common_hieradata_items = environments, hardware, operatingsystems, datacentres, common.yaml

[lock]
type = DISABLED

[messaging]
queuedir = $sandbox/spool
""")

class JensTestCase(unittest.TestCase):
    COMMIT_PREFIX = 'commit/'
    DEFAULT_DEBUG_LEVEL = 'DEBUG'
    MANDATORY_BRANCHES = ['master', 'qa']

    def setUp(self):
        self.sandbox_path = tempfile.mkdtemp(
            prefix="jens_sandbox_%s-" % self._testMethodName,
            suffix='-' + str(time.time()))
        init_sandbox(self.sandbox_path)
        self.keep_sandbox = False
        self.debug_level = JensTestCase.DEFAULT_DEBUG_LEVEL
        self.config_file_path = "%s/etc/main.conf" % self.sandbox_path
        config_file = open(self.config_file_path, 'w+')
        config_file.write(BASE_CONFIG.substitute(
            sandbox=self.sandbox_path,
            hashprefix=JensTestCase.COMMIT_PREFIX,
            debuglevel=self.debug_level,
            mandatory_branches=','.join(JensTestCase.MANDATORY_BRANCHES)))
        config_file.close()

        root = logging.getLogger()
        map(root.removeHandler, root.handlers[:])
        map(root.removeFilter, root.filters[:])

        self.settings = Settings("jens-test")
        self.settings.parse_config(self.config_file_path)

        self.lock = JensLockFactory.makeLock(self.settings)

    def tearDown(self):
        if self.keep_sandbox:
            print "Sandbox kept in %s" % self.sandbox_path
        else:
            destroy_sandbox(self.sandbox_path)

    def assertLogNoErrors(self):
        try:
            self.log
        except AttributeError:
            self.log = open("%s/jens-test.log" % self.settings.LOGDIR)
        for line in self.log.readlines():
            if re.match(r'.+ERROR.+', line):
                raise AssertionError(line)

    def assertLogErrors(self, errorRegexp=None):
        try:
            self.log
        except AttributeError:
            self.log = open("%s/jens-test.log" % self.settings.LOGDIR)
        found = False
        regexp = r'.+ERROR.+'
        if errorRegexp is not None:
            regexp = r'.+ERROR.+%s.+' % errorRegexp
        for line in self.log.readlines():
            if re.match(regexp, line):
                found = True
        if not found:
            raise AssertionError("There should be errors")

    def assertClone(self, identifier, pointsto=None):
        partition, element, dirname = identifier.split('/')
        path = "%s/%s/%s/%s" % (self.settings.CLONEDIR, \
            partition, element, dirname)
        if not os.path.isdir(path):
            raise AssertionError("Clone '%s' not found" % path)
        if not os.path.isdir("%s/code" % path):
            raise AssertionError("Clone '%s' does not have code dir" % path)
        if not os.path.isdir("%s/data" % path):
            raise AssertionError("Clone '%s' does not have data dir" % path)
        inventory = get_inventory(self.settings)
        self.assertTrue(partition in inventory)
        self.assertTrue(element in inventory[partition])
        refname = dirname_to_refname(self.settings, dirname)
        self.assertTrue(refname in inventory[partition][element])
        if pointsto is not None:
            self.assertEquals(get_repository_head(self.settings, path),
                pointsto)

    def assertNotClone(self, identifier):
        try:
            self.assertClone(identifier)
        except AssertionError:
            return
        raise AssertionError("Clone '%s' seems present" % identifier)

    def assertBare(self, identifier):
        partition, element = identifier.split('/')
        path = "%s/%s/%s" % (self.settings.BAREDIR, \
            partition, element)
        if not os.path.isdir(path):
            raise AssertionError("Bare '%s' not found" % path)
        if not os.path.isfile("%s/HEAD" % path):
            raise AssertionError("Bare '%s' does not have HEAD" % path)

    def assertNotBare(self, identifier):
        try:
            self.assertBare(identifier)
        except AssertionError:
            return
        raise AssertionError("Bare '%s' seems present" % identifier)

    def assertEnvironmentLinks(self, environment):
        base_path = "%s/%s" % (self.settings.ENVIRONMENTSDIR, environment)
        common_hieradata_items = set(self.settings.COMMON_HIERADATA_ITEMS)
        if not os.path.isdir(base_path):
            raise AssertionError("Environment '%s' not present" % environment)
        for path, dirs, files in os.walk(base_path):
            if path.endswith('hieradata'):
                self.assertTrue(common_hieradata_items.issubset(set(dirs + files)))
            for file in files + dirs:
                file_apath = "%s/%s" % (path, file)
                if os.path.islink(file_apath):
                   if not self._verify_link(path, file_apath):
                        raise AssertionError("Environment '%s' -- '%s' link broken" % \
                            (environment, file_apath))

    def assertEnvironmentHasAConfigFile(self, environment):
        # https://docs.puppetlabs.com/puppet/latest/reference/config_file_environment.html
        conf_file_path = "%s/%s/environment.conf" % \
            (self.settings.ENVIRONMENTSDIR, environment)
        if not os.path.isfile(conf_file_path):
            raise AssertionError("Environment '%s' doesn't have a config file" % environment)
        if not os.stat(conf_file_path).st_size > 0:
            raise AssertionError("Environment '%s''s config file seems empty" % environment)

    def assertEnvironmentHasAConfigFileAndParserSet(self, environment, parser):
        conf_file_path = "%s/%s/environment.conf" % \
            (self.settings.ENVIRONMENTSDIR, environment)

        config = ConfigObj(conf_file_path)
        if config.get('parser', None) != parser:
            raise AssertionError("Environment '%s''s parser:'s value is not %s" %
                (environment, parser))

    def assertEnvironmentDoesNotHaveAConfigFile(self, environment):
        try:
            self.assertEnvironmentHasAConfigFile(environment)
        except AssertionError:
            return
        raise AssertionError("Environment '%s' seems to have a config file" % environment)

    def assertEnvironmentBrokenLinks(self, environment):
        try:
            self.assertEnvironmentLinks(environment)
        except AssertionError:
            return
        raise AssertionError("Environment '%s' seems fine" % environment)

    def assertEnvironmentDoesntExist(self, environment):
        base_path = "%s/%s" % (self.settings.ENVIRONMENTSDIR, environment)
        if os.path.isdir(base_path):
            raise AssertionError("Environment '%s' present" % environment)

    def assertEnvironmentOverride(self, environment, identifier, desired):
        base_path = "%s/%s" % (self.settings.ENVIRONMENTSDIR, environment)
        partition, element = identifier.split('/')
        links = []
        links.append("%s/%s/%s" % (base_path, partition, element))
        if partition == 'modules':
            links.append("%s/hieradata/module_names/%s" % (base_path, element))
        if partition == 'hostgroups':
            canonical_name = element.replace('hg_', '')
            links.append("%s/hieradata/hostgroups/%s" % \
                (base_path, canonical_name))
            links.append("%s/hieradata/fqdns/%s" % \
                (base_path, canonical_name))
        for link in links:
            # Override created
            if not os.path.lexists(link):
                raise AssertionError("Env '%s' -- '%s' -- '%s' does not exist" % \
                    (environment, identifier, link))
            target = os.readlink(link)
            dirname = refname_to_dirname(self.settings, desired)
            # Link not broken
            link_parent = os.path.abspath(os.path.join(link, os.pardir))
            if not self._verify_link(link_parent, link):
                raise AssertionError("Env '%s' -- '%s' -- '%s' is broken" % \
                    (environment, identifier, link))
            # And points to the correct clone
            link_type = 'data' if re.match(r'^%s/hieradata/.+' % \
                base_path, link) else 'code'
            if not re.match(r".+/%s/%s.*" % (dirname, link_type), target):
                raise AssertionError("Env '%s' '%s' // '%s' -> '%s' not to '%s' (%s)" % \
                    (environment, identifier, link, target, dirname, desired))

    def assertEnvironmentOverrideDoesntExist(self, environment, identifier):
        base_path = "%s/%s" % (self.settings.ENVIRONMENTSDIR, environment)
        partition, element = identifier.split('/')
        links = []
        links.append("%s/%s/%s" % (base_path, partition, element))
        if partition == 'modules':
            links.append("%s/hieradata/module_names/%s" % (base_path, element))
        if partition == 'hostgroups':
            canonical_name = element.replace('hg_', '')
            links.append("%s/hieradata/hostgroups/%s" % \
                (base_path, canonical_name))
            links.append("%s/hieradata/fqdns/%s" % \
                (base_path, canonical_name))
        for link in links:
            if os.path.lexists(link):
                raise AssertionError("Env '%s' -- '%s' -- '%s' exists" % \
                    (environment, identifier, link))

    def assertEnvironmentOverrideExistsButBroken(self, environment, identifier, desired):
        base_path = "%s/%s" % (self.settings.ENVIRONMENTSDIR, environment)
        partition, element = identifier.split('/')
        links = []
        links.append("%s/%s/%s" % (base_path, partition, element))
        if partition == 'modules':
            links.append("%s/hieradata/module_names/%s" % (base_path, element))
        if partition == 'hostgroups':
            canonical_name = element.replace('hg_', '')
            links.append("%s/hieradata/hostgroups/%s" % \
                (base_path, canonical_name))
            links.append("%s/hieradata/fqdns/%s" % \
                (base_path, canonical_name))
        for link in links:
            # Override created
            if not os.path.lexists(link):
                raise AssertionError("Env '%s' -- '%s' -- '%s' does not exist" % \
                    (environment, identifier, link))
            target = os.readlink(link)
            dirname = refname_to_dirname(self.settings, desired)
            link_parent = os.path.abspath(os.path.join(link, os.pardir))
            # Link broken
            if self._verify_link(link_parent, link):
                raise AssertionError("Env '%s' -- '%s' -- '%s' is not broken" % \
                    (environment, identifier, link))

    def assertEnvironmentNumberOf(self, environment, partition, count):
        base_path = "%s/%s/%s" % \
            (self.settings.ENVIRONMENTSDIR, environment, partition)
        actual = len(os.listdir(base_path))
        if actual != count:
            raise AssertionError("'%s' has %d %s (expected: %d)" % \
                (environment, actual, partition, count))

    def _verify_link(self, base, path):
        cwd = os.getcwd()
        os.chdir(base)
        try:
            os.stat(os.readlink(path))
        except OSError:
            return False
        finally:
            os.chdir(cwd)
        return True
