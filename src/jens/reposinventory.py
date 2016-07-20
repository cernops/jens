# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

import os
import logging
import re
import pickle

from jens.settings import Settings
from jens.errors import JensRepositoriesError
from jens.errors import JensEnvironmentsError
from jens.environments import read_environment_definition
from jens.environments import get_names_of_declared_environments
from jens.tools import ref_is_commit
from jens.tools import dirname_to_refname

def get_inventory():
    logging.info("Fetching repositories inventory...")
    try:
        return _read_inventory_from_disk()
    except (IOError, pickle.PickleError):
        logging.warn("Inventory on disk not found or corrupt, generating...")
        return _generate_inventory()

def persist_inventory(inventory):
    logging.info("Persisting repositories inventory...")
    _write_inventory_to_disk(inventory)

def get_desired_inventory():
    return _read_desired_inventory()

def _read_inventory_from_disk():
    settings = Settings()
    inventory_file = open(settings.CACHEDIR + "/repositories", "r")
    return pickle.load(inventory_file)

def _write_inventory_to_disk(inventory):
    settings = Settings()
    inventory_file_path = settings.CACHEDIR + "/repositories"
    try:
        inventory_file = open(inventory_file_path, "w+")
    except IOError, error:
        raise JensRepositoriesError("Unable to write inventory to disk (%s)" %
                                    error)
    logging.debug("Writing inventory to %s" % inventory_file_path)
    try:
        pickle.dump(inventory, inventory_file)
    except pickle.PickleError, error:
        raise JensRepositoriesError("Unable to write inventory to disk (%s)" %
                                    error)

def _generate_inventory():
    settings = Settings()
    logging.info("Generating inventory of bares and clones...")
    inventory = {}
    for partition in ("modules", "hostgroups", "common"):
        inventory[partition] = {}
        baredir = settings.BAREDIR + "/%s" % partition
        try:
            names = os.listdir(baredir)
        except OSError, error:
            raise JensRepositoriesError("Unable to list %s (%s)" %
                                        (baredir, error))
        for name in names:
            inventory[partition][name] = \
                _read_list_of_clones(partition, name)
    return inventory

def _read_list_of_clones(partition, name):
    settings = Settings()
    try:
        clones = os.listdir(settings.CLONEDIR + "/%s/%s" %
                            (partition, name))
    except OSError, error:
        raise JensRepositoriesError("Unable to list clones of %s/%s (%s)" %
                                    (partition, name, error))
    return [dirname_to_refname(clone) for clone in clones]

# This is basically the 'look-ahead' bit
def _read_desired_inventory():
    desired = {'modules': {}, 'hostgroups': {}, 'common': {}}
    environments = get_names_of_declared_environments()
    for environmentname in environments:
        try:
            environment = read_environment_definition(environmentname)
            # TODO: what if overrides empty? what if overrides,partition empty?
            if 'overrides' in environment:
                for partition in environment['overrides'].iterkeys():
                    if partition in ("modules", "hostgroups", "common"):
                        for name, override in \
                                environment['overrides'][partition].iteritems():
                            # prefixhash is equivalent to PREFIXhash, contrary to
                            # refs (branches, sic) which as case-sensitiive
                            if ref_is_commit(override):
                                override = override.lower()
                            if name not in desired[partition]:
                                desired[partition][name] = [override]
                            else:
                                if override not in desired[partition][name]:
                                    desired[partition][name].append(override)
        except JensEnvironmentsError, error:
            logging.error("Unable to process '%s' definition. Skipping" %
                          environmentname)
            continue  # Just ignore, as won't be generated later on either.
    return desired
