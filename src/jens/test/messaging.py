# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from datetime import datetime

from jens.messaging import _merge_messages
from jens.errors import JensMessagingError
from jens.test.tools import init_repositories
from jens.test.tools import add_repository, del_repository

from jens.test.testcases import JensTestCase

class MessagingTest(JensTestCase):
    def setUp(self):
        super(MessagingTest, self).setUp()

    #### TESTS ####

    def test_merge_messages(self):
        messages = [
            {'time': datetime.now().isoformat()},
            {'time': datetime.now().isoformat(),
                'data': ''},
            {'time': datetime.now().isoformat(),
                'data': {}},
            {'time': datetime.now().isoformat(),
                'data': {'modules': ['foo']}},
            {'time': datetime.now().isoformat(),
                'data': {'modules': ['bar']}},
            {'time': datetime.now().isoformat(),
                'data': {'modules': ['baz1', 'baz2']}},
            {'time': datetime.now().isoformat(),
                'data': {'hostgroups': ['hg0']}},
            {'time': datetime.now().isoformat(),
                'data': {'hostgroups': ['hg1', 'hg2']}},
            {'time': datetime.now().isoformat(),
                'data': {'hostgroups': ['hg3', 'hg4'],
                'modules': ['m1']}},
            {'time': datetime.now().isoformat(),
                'data': {'crap': ['hg3', 'hg4'],
                'modules': ['m2']}}
        ]

        modules = ['foo', 'bar', 'baz1', 'baz2', 'm1', 'm2']
        hgs = ['hg0', 'hg1', 'hg2', 'hg3', 'hg4']

        result = _merge_messages(messages)

        self.assertTrue('modules' in result)
        self.assertTrue('hostgroups' in result)
        self.assertEqual(len(modules), len(result['modules']))
        self.assertEqual(len(hgs), len(result['hostgroups']))
        for m in modules:
            self.assertTrue(m in result['modules'])
        for h in hgs:
            self.assertTrue(h in result['hostgroups'])
