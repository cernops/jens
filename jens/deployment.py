"""Experimental generation preparation and explicitly gated publication.

This module never updates the legacy deployment directories. See DEPLOYMENTS.md
for the serving-side requirements; a pointer swap does not pin Puppet readers.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from configobj import ConfigObj
from validate import Validator

from jens.configfile import CONFIG_GRAMMAR


class DeploymentError(RuntimeError):
    pass


def _git(*args):
    return subprocess.check_output(['git'] + list(args), stderr=subprocess.PIPE,
                                   text=True).strip()


def _config(path):
    config = ConfigObj(str(path), configspec=CONFIG_GRAMMAR.split('\n'),
                       file_error=True)
    if config.validate(Validator()) is not True:
        raise DeploymentError('Invalid source configuration')
    return config


def _root(path):
    root = Path(path).resolve()
    try:
        root.mkdir()
    except FileExistsError:
        if not (root / '.jens-deployment-root').is_file():
            raise DeploymentError('Existing root is not managed by jens-deploy')
    (root / '.jens-deployment-root').touch()
    (root / 'generations').mkdir(exist_ok=True)
    return root


def _validate_links(generation):
    if not (generation / 'environments').is_dir():
        raise DeploymentError('Generation has no environment tree')
    # Do not follow symlink directories: validate their complete targets instead.
    for directory, dirs, files in os.walk(generation / 'environments'):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                target = path.resolve()
                if not target.exists():
                    raise DeploymentError('Broken environment link: %s' % path)
                if os.path.commonpath([str(generation), str(target)]) != str(generation):
                    raise DeploymentError('Environment link escapes generation: %s' % path)


def prepare(source_config, root):
    """Cold-build a generation. Failure never changes current.

    Metadata is cloned from the configured local master branches. All generated
    state, logs, locks and queues are private; the live queue is never consumed.
    Failed generations remain available for diagnosis and are never published.
    """
    config = _config(source_config)
    root = _root(root)
    with open(root / 'deploy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        generation = Path(tempfile.mkdtemp(prefix='generation_', dir=root / 'generations'))
        main = config['main']
        metadata_relative = os.path.relpath(main['repositorymetadata'],
                                           main['repositorymetadatadir'])
        if metadata_relative == '..' or metadata_relative.startswith('../'):
            raise DeploymentError('Repository metadata must be inside its repository')
        for key, relative in [('baredir', 'bare'), ('clonedir', 'clone'),
                              ('cachedir', 'cache'), ('environmentsdir', 'environments'),
                              ('logdir', 'log')]:
            main[key] = str(generation / relative)
            Path(main[key]).mkdir()
        for relative in ['cache/environments', 'lock', 'queue']:
            (generation / relative).mkdir()
        for partition in ['modules', 'hostgroups', 'common']:
            (generation / 'bare' / partition).mkdir()
            (generation / 'clone' / partition).mkdir()
        for key, relative in [('environmentsmetadatadir', 'metadata/environments'),
                              ('repositorymetadatadir', 'metadata/repository')]:
            source = str(Path(main[key]).resolve())
            destination = generation / relative
            destination.parent.mkdir(exist_ok=True)
            _git('clone', '--no-local', '--branch', 'master', source, str(destination))
            main[key] = str(destination)
        main['repositorymetadata'] = str(generation / 'metadata/repository' / metadata_relative)
        main['mode'] = 'POLL'
        # A dedicated worker has only ERROR/CRITICAL messages in this log.
        # Legacy helpers sometimes log errors and return success: reject those too.
        main['debuglevel'] = 'ERROR'
        config['lock']['type'] = 'FILE'
        config['lock']['name'] = 'generation'
        config['filelock']['lockdir'] = str(generation / 'lock')
        config['messaging']['queuedir'] = str(generation / 'queue')
        # Producer credentials are not needed by the isolated POLL worker.
        config['gitlabproducer']['secret_token'] = None
        config.filename = str(generation / 'main.conf')
        config.write()
        with open(generation / 'worker-output.log', 'w') as output:
            result = subprocess.run([sys.executable, '-m', 'jens.deployment',
                                     '_worker', config.filename],
                                    stdout=output, stderr=subprocess.STDOUT)
        errors = generation / 'log/prepare.log'
        if result.returncode or not errors.exists() or errors.stat().st_size:
            raise DeploymentError('Preparation failed; see %s\n%s\n%s' % (
                generation, errors.read_text() if errors.exists() else '',
                (generation / 'worker-output.log').read_text()))
        _validate_links(generation)
        manifest = {'format': 1, 'commits': {}}
        for directory, dirs, _ in os.walk(generation / 'clone'):
            if '.git' in dirs:
                manifest['commits'][os.path.relpath(directory, generation)] = _git(
                    '-C', directory, 'rev-parse', 'HEAD')
                dirs.remove('.git')
        for relative in ['metadata/environments', 'metadata/repository']:
            manifest['commits'][relative] = _git('-C', str(generation / relative),
                                                'rev-parse', 'HEAD')
        with open(generation / '.complete.new', 'w') as complete:
            json.dump(manifest, complete, indent=2, sort_keys=True)
            complete.write('\n')
        os.replace(generation / '.complete.new', generation / 'complete.json')
        return generation


def publish(root, generation, readers_drained=False):
    if not readers_drained:
        raise DeploymentError('Publication requires drained readers and coordinated cache refresh')
    root = _root(root)
    generation = Path(generation).resolve()
    with open(root / 'deploy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if generation.parent != root / 'generations' or not (generation / 'complete.json').is_file():
            raise DeploymentError('Not a completed generation belonging to this root')
        _validate_links(generation)
        current = root / 'current'
        if os.path.lexists(current) and not current.is_symlink():
            raise DeploymentError('Refusing to replace a non-symlink current path')
        temporary = root / '.current.new'
        # The root lock serializes publishers, including cleanup after interruption.
        if os.path.lexists(temporary):
            temporary.unlink()
        try:
            temporary.symlink_to(os.path.relpath(generation, root), target_is_directory=True)
            os.replace(temporary, current)
        finally:
            if os.path.lexists(temporary):
                temporary.unlink()


def _worker(config):
    from jens.settings import Settings
    from jens.maintenance import validate_directories, refresh_metadata
    from jens.repos import refresh_repositories
    from jens.environments import refresh_environments
    Settings('prepare').parse_config(config)
    validate_directories()
    refresh_metadata()
    deltas, inventory = refresh_repositories()
    refresh_environments(deltas, inventory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--config', required=True)
    prepare_parser.add_argument('--root', required=True)
    publish_parser = commands.add_parser('publish')
    publish_parser.add_argument('--root', required=True)
    publish_parser.add_argument('--generation', required=True)
    publish_parser.add_argument('--readers-drained', action='store_true')
    worker_parser = commands.add_parser('_worker', help=argparse.SUPPRESS)
    worker_parser.add_argument('config')
    args = parser.parse_args()
    try:
        if args.command == '_worker':
            _worker(args.config)
        elif args.command == 'prepare':
            print(prepare(args.config, args.root))
        else:
            publish(args.root, args.generation, args.readers_drained)
    except (DeploymentError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, '%s\n' % error)


if __name__ == '__main__':
    main()
