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
import pickle
import yaml

from datetime import datetime
from flask import Flask, request, current_app
from dirq.queue import Queue

from jens.errors import JensError
from jens.messaging import MSG_SCHEMA
from jens.settings import Settings

app = Flask(__name__)

@app.route('/gitlab', methods=['POST'])
def hello_gitlab():
    try:
        settings = Settings('jens-gitlab-producer')
        settings.parse_config(current_app.config['config_file'])

        payload = request.get_json(silent=True) or {}
        if payload:
            logging.debug('Incoming request with payload: %s' % str(payload))
        try:
            url = payload['repository']['git_ssh_url']
        except (KeyError, TypeError) as error:
            logging.error("Malformed payload (%s)" % json.dumps(payload))
            return 'Malformed request', 400

        try:
            dirq = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
        except Exception as error:
            logging.error("Problem initializing the queue ('%s')" % repr(error))
            raise
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

        response = {
            'time' : datetime.now().isoformat(),
            'data' : pickle.dumps({partition : [name]})
        }
        result = dirq.add(response)
        logging.info("%s - %s/%s - '%s' added to the queue"
                     "" % (response['time'], partition, name, result))
        return 'OK'

    except NameError as error:
        logging.error("'%s' couldn't be found in repositories" % (url))
        return 'Repository not found', 404
    except Exception as error:
        logging.error("Unexpected error (%s)" % repr(error))
        return 'Internal Server Error!', 500

