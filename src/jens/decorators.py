# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging

import os
import git.exc
from functools import wraps
from time import time
from jens.errors import JensGitError
from jens.settings import Settings

def timed(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        elapsed = time() - start
        logging.info("Executed '%s' in %.2f ms" % (f.__name__, elapsed*1000))
        return result
    return wrapper

def git_exec(f):
    @wraps(f)
    def wrapper(*w_args, **w_kwargs):
        settings = Settings()
        ssh_cmd_path = settings.SSH_CMD_PATH

        if ssh_cmd_path:
            os.environ['GIT_SSH'] = ssh_cmd_path

        args = w_kwargs["args"]
        kwargs = w_kwargs["kwargs"]
        name = w_kwargs["name"]

        logging.debug("Executing git %s %s %s" % (name, args, kwargs))

        try:
            res = f(*args, **kwargs)
        except (git.exc.GitCommandError, git.exc.GitCommandNotFound) as e:
            raise JensGitError("Couldn't execute %s (%s)" %
                               (e.command, e.stderr))
        except git.exc.NoSuchPathError as e:
            raise JensGitError("No such path %s" % e)
        except git.exc.InvalidGitRepositoryError as e:
            raise JensGitError("Not a git repository: %s" % e)
        except AssertionError as e:
            raise JensGitError("Git operation failed: %s" % e)
        return res

    return wrapper
