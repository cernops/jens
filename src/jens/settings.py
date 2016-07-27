# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import logging

from configobj import ConfigObj, flatten_errors
from configobj import ConfigObjError
from validate import Validator

from errors import JensConfigError
from configfile import CONFIG_GRAMMAR

class Settings():
    __shared_state = {}

    def __init__(self, logfile=None):
        self.__dict__ = self.__shared_state
        if 'logfile' not in self.__dict__:
            self.logfile = logfile

    def parse_config(self, config_file_path):
        try:
            config = ConfigObj(infile=config_file_path,
                               configspec=CONFIG_GRAMMAR.split("\n"))
        except ConfigObjError, error:
            raise JensConfigError("Config file parsing failed (%s)" % error)

        validator = Validator()
        results = config.validate(validator)

        if results is not True:
            for error in flatten_errors(config, results):
                section_list, key, msg = error
                section_string = '.'.join(section_list)
                if key is not None:
                    raise JensConfigError("Missing/not valid mandatory configuration key %s in section %s"
                                          % (key, section_string))
                else:
                    raise JensConfigError("Section '%s' is missing" % section_string)

        # Save a reference in case we need the raw values later
        self.config = config

        # [main]
        self.DEBUG_LEVEL = config["main"]["debuglevel"]
        self.LOGDIR = config["main"]["logdir"]
        self.BAREDIR = config["main"]["baredir"]
        self.CACHEDIR = config["main"]["cachedir"]
        self.CLONEDIR = config["main"]["clonedir"]
        self.ENVIRONMENTSDIR = config["main"]["environmentsdir"]
        self.MANDATORY_BRANCHES = config["main"]["mandatorybranches"]
        self.REPO_METADATA = config["main"]["repositorymetadata"]
        self.REPO_METADATADIR = config["main"]["repositorymetadatadir"]
        self.ENV_METADATADIR = config["main"]["environmentsmetadatadir"]
        self.HASHPREFIX = config["main"]["hashprefix"]
        self.DIRECTORY_ENVIRONMENTS = config["main"]["directory_environments"]
        self.COMMON_HIERADATA_ITEMS = config["main"]["common_hieradata_items"]
        self.MODE = config["main"]["mode"]

        # [lock]
        self.LOCK_TYPE = config["lock"]["type"]
        self.LOCK_NAME = config["lock"]["name"]

        # [filelock]
        self.FILELOCK_LOCKDIR = config["filelock"]["lockdir"]

        # [messaging]
        self.MESSAGING_QUEUEDIR = config["messaging"]["queuedir"]

        if self.logfile:
            logging.basicConfig(
                level = getattr(logging, self.DEBUG_LEVEL),
                format = '%(asctime)s %(levelname)s %(message)s',
                filename = "%s/%s.log" % (self.LOGDIR, self.logfile))
        else:
            logging.basicConfig(
                level = getattr(logging, self.DEBUG_LEVEL),
                format = '%(message)s')
