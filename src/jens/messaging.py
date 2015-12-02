# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import yaml
import logging

from jens.errors import JensMessagingError
from jens.decorators import timed

@timed
def fetch_update_hints(settings, lock):
    hints = {}
    logging.info("Getting and processing hints...")
    try:
        messages = _fetch_all_messages(settings)
    except Exception, error: # FIXME
        raise JensMessagingError("Could not retrieve messages")

    logging.info("%d update hints found" % len(messages))
    hints = _merge_messages(messages)
    return hints

def _fetch_all_messages(settings):
    # TODO:
    # New setting for dirq's path
    # Get messages from the queue
    pass

def _merge_messages(messages):
    hints = {'modules': [], 'hostgroups': [], 'common': []}
    def _merger(acc, element):
        if 'data' not in element or type(element['data']) != dict:
            return acc
        for k,v in element['data'].iteritems():
            if k not in hints:
                continue
            for item in v:
                acc[k].append(item)
        return acc
    return reduce(_merger, messages, hints)
