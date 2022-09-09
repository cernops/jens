# Copyright (C) 2014, CERN
# This software is distributed under the terms of the GNU General Public
# Licence version 3 (GPL Version 3), copied verbatim in the file "COPYING".
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import
import os
import logging
import yaml
import shutil
import re

from configobj import ConfigObj

from jens.git_wrapper import hash_object
from jens.decorators import timed
from jens.errors import JensEnvironmentsError
from jens.tools import refname_to_dirname
from jens.settings import Settings

DIRECTORY_ENVIRONMENTS_CONF_FILENAME = "environment.conf"
DIRECTORY_ENVIRONMENTS_CONF_PARSER_VALUES = ('current', 'future')

@timed
def refresh_environments(repositories_deltas, inventory):
    logging.debug("Calculating delta...")
    delta = _calculate_delta()
    logging.info("New environments: %s", delta['new'])
    logging.info("Existing and changed environments: %s", delta['changed'])
    logging.debug("Existing but not changed environments: %s", delta['notchanged'])
    logging.info("Deleted environments: %s", delta['deleted'])

    logging.info("Creating new environments...")
    _create_new_environments(delta['new'], inventory)
    logging.info("Purging deleted environments...")
    _purge_deleted_environments(delta['deleted'])
    logging.info("Recreating changed environments...")
    _recreate_changed_environments(delta['changed'], inventory)
    logging.info("Refreshing not changed environments...")
    _refresh_notchanged_environments(delta['notchanged'], repositories_deltas)

def _refresh_notchanged_environments(environments, repositories_deltas):
    for environment in environments:
        logging.debug("Refreshing environment '%s'...", environment)
        try:
            definition = read_environment_definition(environment)
        except JensEnvironmentsError as error:
            logging.error("Unable to read and parse '%s' definition (%s). Skipping",
                          environment, error)
            return

        if definition.get('default', None) is None:
            logging.debug("Environment '%s' won't get new modules (no default)",
                          environment)
        else:
            for module in repositories_deltas['modules']['new']:
                try:
                    _link_module(module, environment, definition)
                except JensEnvironmentsError as error:
                    logging.error("Failed to link module '%s' in enviroment '%s' (%s)",
                                  module, environment, error)

        for module in repositories_deltas['modules']['deleted']:
            logging.debug("Deleting module '%s' from environment '%s'",
                          module, environment)
            _unlink_module(module, environment)

        if definition.get('default', None) is None:
            logging.debug("Environment '%s' won't get new hostgroups (no default)",
                          environment)
        else:
            for hostgroup in repositories_deltas['hostgroups']['new']:
                try:
                    _link_hostgroup(hostgroup, environment, definition)
                except JensEnvironmentsError as error:
                    logging.error("Failed to link hostgroup '%s' in enviroment '%s' (%s)",
                                  hostgroup, environment, error)

        for hostgroup in repositories_deltas['hostgroups']['deleted']:
            logging.debug("Deleting hostgroup '%s' from environment '%s'",
                          hostgroup, environment)
            _unlink_hostgroup(hostgroup, environment)

def _recreate_changed_environments(environments, inventory):
    for environment in environments:
        logging.info("Recreating environment '%s'", environment)
        _purge_deleted_environment(environment)
        _create_new_environment(environment, inventory)

def _purge_deleted_environments(environments):
    settings = Settings()
    for environment in environments:
        if environment not in settings.PROTECTED_ENVIRONMENTS:
            _purge_deleted_environment(environment)
        else:
            logging.warning("Refusing to delete '%s' as it's protected", environment)

def _purge_deleted_environment(environment):
    settings = Settings()
    logging.info("Deleting environment '%s'", environment)
    env_basepath = "%s/%s" % (settings.ENVIRONMENTSDIR, environment)
    shutil.rmtree(env_basepath)
    logging.info("Deleted '%s'", env_basepath)
    _remove_environment_annotation(environment)

def _create_new_environments(environments, inventory):
    for environment in environments:
        _create_new_environment(environment, inventory)

#pylint: disable=too-many-branches, too-many-statements
def _create_new_environment(environment, inventory):
    settings = Settings()
    logging.info("Creating new environment '%s'", environment)

    if re.match(r"^\w+$", environment) is None:
        logging.error("Environment name '%s' is invalid. Skipping", environment)
        return

    try:
        definition = read_environment_definition(environment)
    except JensEnvironmentsError as error:
        logging.error("Unable to read and parse '%s' definition (%s). Skipping",
                      environment, error)
        return

    if definition is None:
        logging.error("Environment '%s' is empty", environment)
        return

    logging.debug("Creating directory structure...")
    env_basepath = "%s/%s" % (settings.ENVIRONMENTSDIR, environment)
    os.mkdir(env_basepath)
    for directory in ("modules", "hostgroups", "hieradata"):
        os.mkdir("%s/%s" % (env_basepath, directory))

    hieradata_directories = ("module_names", "hostgroups", "fqdns")
    for directory in hieradata_directories:
        os.mkdir("%s/hieradata/%s" % (env_basepath, directory))

    logging.info("Processing modules...")
    modules = list(inventory['modules'].keys())
    if 'default' not in definition:
        try:
            necessary_modules = list(definition['overrides']['modules'].keys())
        except KeyError:
            necessary_modules = set()
        modules = set(modules).intersection(necessary_modules)
    for module in modules:
        try:
            _link_module(module, environment, definition)
        except JensEnvironmentsError as error:
            logging.error("Failed to link module '%s' in enviroment '%s' (%s)",
                          module, environment, error)

    logging.info("Processing hostgroups...")
    hostgroups = list(inventory['hostgroups'].keys())
    if 'default' not in definition:
        try:
            necessary_hostgroups = list(definition['overrides']['hostgroups'].keys())
        except KeyError:
            necessary_hostgroups = set()
        hostgroups = set(hostgroups).intersection(necessary_hostgroups)
    for hostgroup in hostgroups:
        try:
            _link_hostgroup(hostgroup, environment, definition)
        except JensEnvironmentsError as error:
            logging.error("Failed to link hostgroup '%s' in enviroment '%s' (%s)",
                          hostgroup, environment, error)

    logging.info("Processing site...")
    try:
        _link_site(environment, definition)
    except JensEnvironmentsError as error:
        logging.error("Failed to link site in enviroment '%s' (%s)",
                      environment, error)

    logging.info("Processing common Hiera data...")
    try:
        _link_common_hieradata(environment, definition)
    except JensEnvironmentsError as error:
        logging.error("Failed to link common hieradata in enviroment '%s' (%s)",
                      environment, error)

    if settings.DIRECTORY_ENVIRONMENTS:
        try:
            _add_configuration_file(environment, definition)
        except JensEnvironmentsError as error:
            logging.error("Failed to generate config file for environment '%s' (%s)",
                          environment, error)

    _annotate_environment(environment)

# This function guarantees that if keys are defined they contain things that
# make sense. If there's overrides defined then the partitions are in the list
# of known ones and they contain a dictionary.
def read_environment_definition(environment):
    settings = Settings()
    try:
        path = settings.ENV_METADATADIR + "/%s.yaml" % environment
        logging.debug("Reading environment from %s", path)
        environment = yaml.safe_load(open(path, 'r'))
        for key in ('notifications',):
            if key not in environment:
                raise JensEnvironmentsError("Missing '%s' in environment '%s'" %
                                            (key, environment))

        if 'default' in environment and not isinstance(environment['default'], str):
            raise JensEnvironmentsError("Default declared but it is not a "
                                        "string in environment '%s'" % environment)

        if 'overrides' in environment:
            if environment['overrides'] is None:
                raise JensEnvironmentsError("Overrides declared but nothing "
                                            "overriden in environment '%s'" %
                                            environment)
            elif not isinstance(environment['overrides'], dict):
                raise JensEnvironmentsError("Overrides declared but what's inside "
                                            "does not look like a dict in environment '%s'" %
                                            environment)
            else:
                for partition in environment['overrides'].keys():
                    if partition in ("modules", "hostgroups", "common"):
                        if environment['overrides'][partition] is None:
                            raise JensEnvironmentsError("Overrides declared but nothing "
                                                        "overriden in environment %s" %
                                                        environment)
                        if not isinstance(environment['overrides'][partition], dict):
                            raise JensEnvironmentsError("Overrides declared but they don't "
                                                        "look like a dict in environment %s" %
                                                        environment)
                    else:
                        raise JensEnvironmentsError("Unknown partition to override (%s) in "
                                                    "environment %s" %
                                                    (partition, environment))

        if 'parser' in environment and \
            environment['parser'] not in DIRECTORY_ENVIRONMENTS_CONF_PARSER_VALUES:
            raise JensEnvironmentsError("Environment '%s' has an invalid "
                                        "value for the parser option: %s" %
                                        (environment, environment['parser']))

        # What about checking that default in settings.mandatory_branches?
        return environment
    except yaml.YAMLError:
        raise JensEnvironmentsError("Unable to parse %s" % path)
    except IOError:
        raise JensEnvironmentsError("Unable to open %s for reading" % path)

def _link_module(module, environment, definition):
    settings = Settings()
    branch, _ = _resolve_branch('modules', module, definition)
    logging.debug("Adding module '%s' (%s) to environment '%s'",
                  module, branch, environment)

    # 1. Module's code directory
    # LINK_NAME: $environment/modules/$module
    # TARGET: $clonedir/modules/$module/$branch/code
    target = "%s/modules/%s/%s/code" % \
        (settings.CLONEDIR, module, branch)
    link_name = _generate_module_env_code_path(module, environment)
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

    # 2. Module's data directory
    # LINK_NAME: $environment/hieradata/module_names/$module
    # TARGET: $clonedir/modules/$module/$branch/data
    target = "%s/modules/%s/%s/data" % \
             (settings.CLONEDIR, module, branch)
    link_name = _generate_module_env_hieradata_path(module, environment)
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

def _link_hostgroup(hostgroup, environment, definition):
    settings = Settings()
    branch, _ = _resolve_branch('hostgroups', hostgroup, definition)
    logging.debug("Adding hostgroup '%s' (%s) to environment '%s'",
                  hostgroup, branch, environment)
    # 1. Hostgroup's code directory
    # LINK_NAME: $environment/hostgroups/hg_$hostgroup
    # TARGET: $clonedir/hostgroups/$hostgroup/$branch/code
    target = "%s/hostgroups/%s/%s/code" % \
             (settings.CLONEDIR, hostgroup, branch)
    link_name = _generate_hostgroup_env_code_path(hostgroup, environment)
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

    # 2. Hostgroup's hostgroup data directory
    # LINK_NAME: $environment/hostgroups/hieratata/hostgroups/$hostgroup
    # TARGET: $clonedir/hostgroups/$hostgroup/$branch/data/hostgroup
    target = "%s/hostgroups/%s/%s/data/hostgroup" % \
             (settings.CLONEDIR, hostgroup, branch)
    link_name = _generate_hostgroup_env_hieradata_hostgroup_path(hostgroup,
                                                                 environment)
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

    # 3. Hostgroup's FQDNs data directory
    # LINK_NAME: $environment/hostgroups/hieratata/fqdns/$hostgroup
    # TARGET: $clonedir/hostgroups/$hostgroup/$branch/data/fqdns
    target = "%s/hostgroups/%s/%s/data/fqdns" % \
             (settings.CLONEDIR, hostgroup, branch)
    link_name = \
        _generate_hostgroup_env_hieradata_fqdns_path(hostgroup, environment)
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

def _unlink_module(module, environment):
    # 1. Module's code directory
    # LINK_NAME: $environment/modules/$module
    link_name = _generate_module_env_code_path(module, environment)
    logging.debug("Making sure link '%s' does not exist", link_name)
    if os.path.islink(link_name):
        os.unlink(link_name)

    # 2. Module's data directory
    # LINK_NAME: $environment/hieradata/module_names/$module
    link_name = _generate_module_env_hieradata_path(module, environment)
    logging.debug("Making sure link '%s' does not exist", link_name)
    if os.path.islink(link_name):
        os.unlink(link_name)

def _unlink_hostgroup(hostgroup, environment):
    # 1. Hostgroup's code directory
    # LINK_NAME: $environment/hostgroups/hg_$hostgroup
    link_name = _generate_hostgroup_env_code_path(hostgroup, environment)
    logging.debug("Making sure link '%s' does not exist", link_name)
    if os.path.islink(link_name):
        os.unlink(link_name)

    # 2. Hostgroup's hostgroup data directory
    # LINK_NAME: $environment/hostgroups/hieratata/hostgroups/$hostgroup
    link_name = \
        _generate_hostgroup_env_hieradata_hostgroup_path(hostgroup, environment)
    logging.debug("Making sure link '%s' does not exist", link_name)
    if os.path.islink(link_name):
        os.unlink(link_name)

    # 3. Hostgroup's FQDNs data directory
    # LINK_NAME: $environment/hostgroups/hieratata/fqdns/$hostgroup
    link_name = \
        _generate_hostgroup_env_hieradata_fqdns_path(hostgroup, environment)
    logging.debug("Making sure link '%s' does not exist", link_name)
    if os.path.islink(link_name):
        os.unlink(link_name)

def _generate_module_env_code_path(module, environment):
    settings = Settings()
    return "%s/%s/modules/%s" % \
            (settings.ENVIRONMENTSDIR, environment, module)

def _generate_module_env_hieradata_path(module, environment):
    settings = Settings()
    return "%s/%s/hieradata/module_names/%s" % \
            (settings.ENVIRONMENTSDIR, environment, module)

def _generate_hostgroup_env_code_path(hostgroup, environment):
    settings = Settings()
    return "%s/%s/hostgroups/hg_%s" % \
            (settings.ENVIRONMENTSDIR, environment, hostgroup)

def _generate_hostgroup_env_hieradata_hostgroup_path(hostgroup, environment):
    settings = Settings()
    return "%s/%s/hieradata/hostgroups/%s" % \
            (settings.ENVIRONMENTSDIR, environment, hostgroup)

def _generate_hostgroup_env_hieradata_fqdns_path(hostgroup, environment):
    settings = Settings()
    return "%s/%s/hieradata/fqdns/%s" % \
            (settings.ENVIRONMENTSDIR, environment, hostgroup)

def _annotate_environment(environment):
    settings = Settings()
    hash_cache_file = open(settings.CACHEDIR + "/environments/%s" %
                           environment, "w+")
    environment_definition = settings.ENV_METADATADIR + "/%s.yaml" % \
                             environment
    hash_value = hash_object(environment_definition)
    logging.debug("New cached hash for environment '%s' is '%s'",
                  environment, hash_value)
    # TODO: Add error handling here, if the cache can't be saved
    # basically the environment will be regenerated in the next
    # run (which is fine, but must be logged at INFO level)
    hash_cache_file.write(hash_value)
    hash_cache_file.close()

def _remove_environment_annotation(environment):
    settings = Settings()
    logging.debug("Removing cached hash for environment '%s'", environment)
    hash_cache_file = settings.CACHEDIR + "/environments/%s" % environment
    try:
        os.remove(hash_cache_file)
    # This shouldn't ever happen unless someone deleted the file or
    # changed its permissions externally
    except OSError as error:
        logging.error("Couldn't remove cached hash for environment '%s' (%s)",
                      environment, error)

def get_names_of_declared_environments():
    settings = Settings()
    environments = os.listdir(settings.ENV_METADATADIR)
    environments = [env for env in environments if re.match(r'^.+?\.yaml$', env)]
    return [re.sub(r'\.yaml$', '', env) for env in environments]

def _calculate_delta():
    settings = Settings()
    delta = {'notchanged': [], 'changed': []}
    current_envs = set(os.listdir(settings.CACHEDIR + "/environments"))
    updated_envs = set(get_names_of_declared_environments())

    delta['new'] = updated_envs.difference(current_envs)
    delta['deleted'] = current_envs.difference(updated_envs)

    existing = updated_envs.intersection(current_envs)

    for environment in existing:
        # TODO: Cache file should always be there, but check just in case
        # and count it as changed if missing so the cache is generated again.
        hash_cache_file = open(settings.CACHEDIR + "/environments/%s" %
                               environment)
        old_hash = hash_cache_file.read()
        hash_cache_file.close()
        new_hash = hash_object(settings.ENV_METADATADIR + "/%s.yaml" %
                               environment)
        if old_hash == new_hash:
            delta['notchanged'].append(environment)
        else:
            delta['changed'].append(environment)

    return delta

def _resolve_branch(partition, element, definition):
    overridden = False
    branch = 'master'
    if 'overrides' in definition:
        if partition in definition['overrides']:
            if element in list(definition['overrides'][partition].keys()):
                branch = definition['overrides'][partition][element]
                logging.info("%s '%s' overridden to use treeish '%s'",
                             partition, element, branch)
                overridden = True
    if not overridden and 'default' in definition:
        branch = definition['default']
    return (refname_to_dirname(branch), overridden)

def _link_site(environment, definition):
    # LINK_NAME: $environment/site
    # TARGET: $clonedir/common/site/$branch/code
    settings = Settings()
    branch, _ = _resolve_branch('common', 'site', definition)
    target = settings.CLONEDIR + "/common/site/%s/code" % branch
    link_name = settings.ENVIRONMENTSDIR + "/%s/site" % environment
    target = os.path.relpath(target,
                             os.path.abspath(os.path.join(link_name, os.pardir)))
    logging.debug("Linking %s to %s", link_name, target)
    try:
        os.symlink(target, link_name)
    except OSError as error:
        raise JensEnvironmentsError(error)

def _link_common_hieradata(environment, definition):
    # Global scoped (aka, 'common') Hiera data
    # LINK_NAME: $environment/hieradata/
    # {settings.COMMON_HIERADATA_ITEMS}
    # TARGET: $clonedir/common/hieradata/$branch/data/{ditto}
    settings = Settings()
    branch, _ = _resolve_branch('common', 'hieradata', definition)
    base_target = settings.CLONEDIR + "/common/hieradata/%s/data" % branch
    base_link_name = settings.ENVIRONMENTSDIR + "/%s/hieradata" % environment

    for element in settings.COMMON_HIERADATA_ITEMS:
        target = base_target + "/%s" % element
        link_name = base_link_name + "/%s" % element
        target = os.path.relpath(target, \
            os.path.abspath(os.path.join(link_name, os.pardir)))
        logging.debug("Linking %s to %s", link_name, target)
        try:
            os.symlink(target, link_name)
        except OSError as error:
            raise JensEnvironmentsError(error)

def _add_configuration_file(environment, definition):
    settings = Settings()
    conf_file_path = "%s/%s/%s" % \
        (settings.ENVIRONMENTSDIR, environment,
         DIRECTORY_ENVIRONMENTS_CONF_FILENAME)
    config = ConfigObj(conf_file_path)
    config['modulepath'] = "modules:hostgroups"
    config['manifest'] = "site/site.pp"
    if 'parser' in definition:
        config['parser'] = definition['parser']

    try:
        config.write()
    except IOError:
        raise JensEnvironmentsError("Unable to write to %s" %
                                    conf_file_path)
