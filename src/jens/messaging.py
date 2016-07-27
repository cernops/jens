# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import yaml
import logging
import pickle

from datetime import datetime

from dirq.queue import Queue
from dirq.queue import QueueLockError, QueueError

from jens.errors import JensMessagingError
from jens.decorators import timed
from jens.settings import Settings

MSG_SCHEMA = {'time': 'string', 'data': 'binary'}

# Ex (after unpickling 'data'):
# {'time': '2015-12-10T14:06:35.339550', 'data': {'modules': ['m1']}}

@timed
def fetch_update_hints(lock):
    hints = {}
    logging.info("Getting and processing hints...")
    try:
        messages = _fetch_all_messages()
    except Exception, error:
        raise JensMessagingError("Could not retrieve messages (%s)" % error)

    logging.info("%d messages found" % len(messages))
    hints = _validate_and_merge_messages(messages)
    return hints

def enqueue_hint(partition, name):
    if partition not in ("modules", "hostgroups", "common"):
        raise JensMessagingError("Unknown partition '%s'" % partition)
    hint = {'time': datetime.now().isoformat(),
            'data': pickle.dumps({partition: [name]})}

    _queue_item(hint)
    logging.info("Hint '%s/%s' added to the queue" % (partition, name))

def _queue_item(item):
    settings = Settings()
    try:
        queue = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
    except OSError, error:
        raise JensMessagingError("Failed to create Queue object (%s)" % error)

    try:
        queue.add(item)
    except QueueError, error:
        raise JensMessagingError("Failed to element (%s)" % error)

def count_pending_hints():
    settings = Settings()
    try:
        queue = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
        return queue.count()
    except OSError, error:
        raise JensMessagingError("Failed to create Queue object (%s)" % error)

def _fetch_all_messages():
    settings = Settings()
    try:
        queue = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
    except OSError, error:
        raise JensMessagingError("Failed to create Queue object (%s)" % error)
    msgs = []
    for i, name in enumerate(queue):
        try:
            item = queue.dequeue(name)
        except QueueLockError, error:
            logging.warn("Element %s was locked when dequeuing" % name)
            continue
        except OSError, error:
            logging.error("I/O error when getting item %s" % name)
            continue
        try:
            item['data'] = pickle.loads(item['data'])
        except (pickle.PickleError, EOFError), error:
            logging.debug("Couldn't unpickle item %s. Will be ignored." % name)
            continue
        logging.debug("Message %s extracted and unpickled" % name)
        msgs.append(item)

    return msgs

def _validate_and_merge_messages(messages):
    hints = {'modules': set(), 'hostgroups': set(), 'common': set()}
    def _merger(acc, element):
        if 'time' not in element:
            logging.warn("Discarding message: No timestamp")
            return acc
        time = element['time']
        if 'data' not in element or type(element['data']) != dict:
            logging.warn("Discarding message (%s): Bad data section" % time)
            return acc
        for k, v in element['data'].iteritems():
            if k not in hints:
                logging.warn("Discarding message (%s): Unknown partition '%s'" % (time, k))
                continue
            if type(v) != list:
                logging.warn("Discarding message (%s): Value '%s' is not a list" % (time, v))
                continue
            for item in v:
                if type(item) == str:
                    logging.debug("Accepted message %s:%s created at %s" %
                                  (k, v, element['time']))
                    acc[k].add(item)
                else:
                    logging.warn("Discarding item '%s' in (%s - %s:%s): not a str"
                                 "not a str" % (item, time, k, v))
        return acc
    return reduce(_merger, messages, hints)
