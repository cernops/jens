#!/usr/bin/env python
# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import fcntl
import json
import logging
import yaml

from flask import Flask, request, current_app

from jens.errors import JensError, JensMessagingError
from jens.messaging import enqueue_hint

app = Flask(__name__)

@app.route('/gitlab', methods=['POST'])
def hello_gitlab():
    try:
        settings = current_app.config['settings']

        payload = request.get_json(silent=True) or {}
        if payload:
            logging.debug('Incoming request with payload: %s' % str(payload))
        try:
            url = payload['repository']['git_ssh_url']
        except (KeyError, TypeError) as error:
            logging.error("Malformed payload (%s)" % json.dumps(payload))
            return 'Malformed request', 400

        try:
            with open(settings.REPO_METADATA, 'r') as metadata:
                fcntl.flock(metadata, fcntl.LOCK_SH)
                repositories = yaml.load(metadata)['repositories']
                fcntl.flock(metadata, fcntl.LOCK_UN)
        except Exception as error:
            raise JensError("Could not read '%s' ('%s')"
                            "" % (settings.REPO_METADATA, error))

        for _partition, _mapping in repositories.items():
            for _name, _url in _mapping.items():
                if _url == url:
                    partition, name = _partition, _name

        enqueue_hint(settings, partition, name)
        return 'OK'
    except JensMessagingError as error:
        logging.error("%s-%s couldn't be added to the Queue (%s)" % (partition, name, str(error)))
        return 'Queue not accessible', 500
    except NameError as error:
        logging.error("'%s' couldn't be found in repositories" % (url))
        return 'Repository not found', 404
    except Exception as error:
        logging.error("Unexpected error (%s)" % repr(error))
        return 'Internal Server Error!', 500

