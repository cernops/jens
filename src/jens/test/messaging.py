# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os

from datetime import datetime

from dirq.queue import Queue, QueueLockError

from jens.messaging import _validate_and_merge_messages, _fetch_all_messages
from jens.messaging import fetch_update_hints
from jens.errors import JensMessagingError
from jens.test.tools import init_repositories
from jens.test.tools import add_repository, del_repository
from jens.test.tools import add_msg_to_queue
from jens.test.tools import create_hostgroup_event, create_module_event
from jens.test.tools import create_common_event

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
            create_module_event(self.settings, module)
        for hg in hgs:
            create_hostgroup_event(self.settings, hg)
        hints = fetch_update_hints(self.settings, self.lock)
        for m in modules:
            self.assertTrue(m in hints['modules'])
        for h in hgs:
            self.assertTrue(h in hints['hostgroups'])
        self.assertTrue('common' in hints)
        self.assertEquals(0, len(hints['common']))
        create_module_event(self.settings, 'm1')
        create_common_event(self.settings, 'baz')
        hints = fetch_update_hints(self.settings, self.lock)
        self.assertTrue('hostgroups' in hints)
        self.assertEquals(0, len(hints['hostgroups']))
        self.assertTrue('baz' in hints['common'])
        self.assertEquals(1, len(hints['modules']))
        self.assertTrue('m1' in hints['modules'])

    def test_update_hints_no_dups(self):
        create_module_event(self.settings, 'foo')
        create_module_event(self.settings, 'foo')
        hints = fetch_update_hints(self.settings, self.lock)
        self.assertEquals(1, len(hints['modules']))

    def test_update_hints_no_messages(self):
        hints = fetch_update_hints(self.settings, self.lock)
        self.assertTrue('modules' in hints)
        self.assertEquals(0, len(hints['hostgroups']))
        self.assertTrue('hostgroups' in hints)
        self.assertEquals(0, len(hints['hostgroups']))
        self.assertTrue('common' in hints)
        self.assertEquals(0, len(hints['common']))

    def test_fetch_all_messages_noerrors(self):
        create_module_event(self.settings, 'foo')
        create_hostgroup_event(self.settings, 'bar')
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(2, len(msgs))

    def test_fetch_all_messages_no_queuedir_is_created(self):
        self.settings.MESSAGING_QUEUEDIR = "%s/notthere" % \
            self.settings.MESSAGING_QUEUEDIR
        self.assertFalse(os.path.isdir(self.settings.MESSAGING_QUEUEDIR))
        msgs = _fetch_all_messages(self.settings)
        self.assertTrue(os.path.isdir(self.settings.MESSAGING_QUEUEDIR))
        self.assertEquals(0, len(msgs))

    def test_fetch_all_messages_queuedir_cannot_be_created(self):
        self.settings.MESSAGING_QUEUEDIR = "/oops"
        self.assertRaises(JensMessagingError, _fetch_all_messages, self.settings)

    def test_fetch_all_messages_ununpickable(self):
        create_hostgroup_event(self.settings, 'bar')
        broken = {'time': datetime.now().isoformat(),
            'data': '))'}
        add_msg_to_queue(self.settings, broken)
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(1, len(msgs))

    @patch.object(Queue, 'dequeue', side_effect=QueueLockError)
    def test_fetch_all_messages_locked_item(self, mock_queue):
        create_module_event(self.settings, 'foo')
        msgs = _fetch_all_messages(self.settings)
        self.assertEquals(0, len(msgs))
        mock_queue.assert_called_once()

    @patch.object(Queue, 'dequeue', side_effect=OSError)
    def test_fetch_all_messages_ioerror_when_dequeuing(self, mock_queue):
        create_module_event(self.settings, 'foo')
        msgs = _fetch_all_messages(self.settings)
        self.assertLogErrors()
        mock_queue.assert_called_once()
        self.assertEquals(0, len(msgs))

    # TODO: Test that other messages are fetched if one is locked/broken

    def test_validate_and_merge_messages(self):
        self.keep_sandbox = True
        messages = [
            {}, # Bad
            {'data': {'modules': ['foo']}}, # Bad
            {'time': datetime.now().isoformat()}, # Bad
            {'time': datetime.now().isoformat(),
                'data': ''}, # Bad
            {'time': datetime.now().isoformat(),
                'data': {}}, # Bad
            {'time': datetime.now().isoformat(),
                'data': {'modules': 'foo'}}, # Bad
            {'time': datetime.now().isoformat(),
                'data': {'modules': ['foo', []]}}, # Bad
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
                'modules': ['m2']}},
            {'time': datetime.now().isoformat(),
                'data': {'common': ['site']}},
        ]

        modules = ['foo', 'bar', 'baz1', 'baz2', 'm1', 'm2']
        hgs = ['hg0', 'hg1', 'hg2', 'hg3', 'hg4']

        result = _validate_and_merge_messages(messages)

        self.assertTrue('modules' in result)
        self.assertTrue('hostgroups' in result)
        self.assertTrue('common' in result)
        self.assertEqual(len(modules), len(result['modules']))
        self.assertEqual(len(hgs), len(result['hostgroups']))
        for m in modules:
            self.assertTrue(m in result['modules'])
        for h in hgs:
            self.assertTrue(h in result['hostgroups'])
        self.assertTrue('site' in result['common'])
