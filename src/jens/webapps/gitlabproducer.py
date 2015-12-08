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
        settings = current_app.config['settings']
        dirq = Queue(settings.MESSAGING_QUEUEDIR, schema=MSG_SCHEMA)
        url = request.json['repository']['git_ssh_url']

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

def parse_cmdline_args():
    """Parses command line parameters."""
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config',
        help="Configuration file path (defaults to '/etc/jens/main.conf'",
        default="/etc/jens/main.conf")
    opts, args = parser.parse_args()
    return opts

def main():
    """Application entrypoint."""
    opts = parse_cmdline_args()

    settings = Settings("jens-gitlab-producer")
    try:
        settings.parse_config(opts.config)
    except JensConfigError, error:
        logging.error(error)
        return 2

    app.config['settings'] = settings
    app.run(host='0.0.0.0', port=8000)
    return 0

if __name__ == '__main__':
    sys.exit(main())
