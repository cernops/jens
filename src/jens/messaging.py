# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import yaml
import logging
import pickle

from dirq.queue import Queue, QueueLockError

from jens.errors import JensMessagingError
from jens.decorators import timed

MSG_SCHEMA = {'time': 'string', 'data': 'binary'}

@timed
def fetch_update_hints(settings, lock):
    hints = {}
    logging.info("Getting and processing hints...")
    try:
        messages = _fetch_all_messages(settings)
    except Exception, error:
        raise JensMessagingError("Could not retrieve messages (%s)" % error)

    logging.info("%d update hints found" % len(messages))
    hints = _validate_and_merge_messages(messages)
    return hints

def _fetch_all_messages(settings):
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
        if 'data' not in element or type(element['data']) != dict:
            return acc
        for k,v in element['data'].iteritems():
            if k not in hints:
                continue
            if type(v) != list:
                continue
            for item in v:
                acc[k].add(item)
        return acc
    return reduce(_merger, messages, hints)
