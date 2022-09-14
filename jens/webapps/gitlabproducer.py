#!/usr/bin/python3
# Copyright (C) 2015, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import fcntl
import json
import re
import logging
import yaml

from flask import Flask, request, current_app

from jens.errors import JensError, JensMessagingError
from jens.messaging import enqueue_hint

app = Flask(__name__)

# https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/regex.rb#L262
REPO_URL_NAMESPACE_AND_REPO = r'[-+\w.]+/[-+\w.]+$'

def __git_url_match_fuzzy(hook_url, metadata_url):
    settings = current_app.config['settings']
    for prefix in settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES:
        if hook_url.startswith(prefix):
            hook_match = re.search(REPO_URL_NAMESPACE_AND_REPO, hook_url)
            metadata_match = re.search(REPO_URL_NAMESPACE_AND_REPO, metadata_url)
            if hook_match and metadata_match:
                return hook_match.group(0) == metadata_match.group(0)
    return False

def git_url_match(hook_url, metadata_url):
    """Compare the URL repository URLs. Return True if they're similar enough."""
    if hook_url == metadata_url:
        return True
    return __git_url_match_fuzzy(hook_url, metadata_url)

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
                repositories = yaml.safe_load(metadata)['repositories']
                fcntl.flock(metadata, fcntl.LOCK_UN)
        except Exception as error:
            raise JensError("Could not read '%s' ('%s')"
                            "" % (settings.REPO_METADATA, error))

        for _partition, _mapping in repositories.items():
            for _name, _url in _mapping.items():
                if git_url_match(url, _url):
                    partition, name = _partition, _name

        enqueue_hint(partition, name)
        return 'OK'
    except JensMessagingError as error:
        logging.error("%s/%s couldn't be added to the queue (%s)" %
            (partition, name, str(error)))
        return 'Queue not accessible', 500
    except NameError as error:
        logging.error("'%s' couldn't be found in repositories" % (url))
        return 'Repository not found', 404
    except Exception as error:
        logging.error("Unexpected error (%s)" % repr(error))
        return 'Internal Server Error!', 500
