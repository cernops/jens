# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from datetime import datetime

from dirq.queue import Queue, QueueLockError

from jens.messaging import _merge_messages, _fetch_all_messages
from jens.messaging import fetch_update_hints
from jens.errors import JensMessagingError
from jens.test.tools import init_repositories
from jens.test.tools import add_repository, del_repository
from jens.test.tools import add_msg_to_queue
from jens.test.tools import notify_hostgroup, notify_module

from jens.test.testcases import JensTestCase

from mock import Mock, patch

class MessagingTest(JensTestCase):
    def setUp(self):
        super(MessagingTest, self).setUp()

    #### TESTS ####

    def test_update_hints(self):
        modules = ['foo', 'bar', 'baz1', 'baz2', 'm1', 'm2']
        hgs = ['hg0', 'hg1', 'hg2', 'hg3', 'hg4']
        for module in modules:
            notify_module(self.settings, module)
        for hg in hgs:
            notify_hostgroup(self.settings, hg)
        hints = fetch_update_hints(self.settings, self.lock)
        for m in modules:
            self.assertTrue(m in hints['modules'])
        for h in hgs:
            self.assertTrue(h in hints['hostgroups'])
        self.assertTrue('common' in hints)
        self.assertEquals(0, len(hints['common']))

    def test_fetch_all_messages_noerrors(self):
        notify_module(self.settings, 'foo')
        notify_hostgroup(self.settings, 'bar')
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(2, len(msgs))

    def test_fetch_all_messages_ununpickable(self):
        notify_hostgroup(self.settings, 'bar')
        broken = {'time': datetime.now().isoformat(),
            'data': '))'}
        add_msg_to_queue(self.settings, broken)
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(1, len(msgs))

    @patch.object(Queue, 'dequeue', side_effect=QueueLockError)
    def test_fetch_all_messages_locked_item(self, mock_queue):
        notify_module(self.settings, 'foo')
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(0, len(msgs))
        mock_queue.assert_called_once()

    @patch.object(Queue, 'dequeue', side_effect=OSError)
    def test_fetch_all_messages_ioerror_when_dequeuing(self, mock_queue):
        notify_module(self.settings, 'foo')
        msgs = _fetch_all_messages(self.settings)
        self.assertLogErrors()
        mock_queue.assert_called_once()
        self.assertEquals(0, len(msgs))

    # TODO: Test that other messages are fetched if one is locked/broken

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
