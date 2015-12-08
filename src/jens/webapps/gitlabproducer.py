import fcntl
import logging
import optparse
import pickle
import sys
import yaml

from datetime import datetime
from flask import Flask, request, current_app
from dirq.queue import Queue, QueueLockError

from jens.errors import JensConfigError, JensError
from jens.settings import Settings
from jens.messaging import MSG_SCHEMA

app = Flask(__name__)

@app.route('/gitlab', methods=['POST'])
def hello_gitlab():
    try:
        payload = request.get_json(silent=True) or {}
        url = payload['repository']['git_ssh_url']

        settings = current_app.config['settings']
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
        except IOError as error:
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
        name = dirq.add(response)
        logging.info("%s - %s-%s added to the queue"
                     "" % (response['time'], partition, name))
        return 'OK'

    except KeyError as error:
        logging.error("Failed (%s)" % error)
        return 'Malformed request', 400
    except NameError as error:
        logging.error("Failed (%s)" % error)
        return 'Repository not found', 404
    except Exception as error:
        logging.error("Failed (%s)" % error)
        return 'Internal Server Error!', 500
