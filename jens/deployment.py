"""Experimental generation preparation and explicitly gated publication.

This module never updates the legacy deployment directories. See DEPLOYMENTS.md
for the serving-side requirements; a pointer swap does not pin Puppet readers.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

import yaml
from configobj import ConfigObj
from validate import Validator

from jens.configfile import CONFIG_GRAMMAR


class DeploymentError(RuntimeError):
    pass


def _git(*args):
    try:
        return subprocess.check_output(['git'] + list(args), stderr=subprocess.PIPE,
                                       text=True).strip()
    except subprocess.CalledProcessError as error:
        raise DeploymentError('Git failed: %s' % error.stderr.strip()) from error


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
    # Follow reachable content, not just the environment's top-level links.
    # Cache visited directories to avoid repeatedly scanning shared module trees.
    visited = set()

    def visit(path, ancestors):
        try:
            target = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise DeploymentError('Broken or cyclic content link: %s' % path) from error
        relative = target.relative_to(generation) if generation in target.parents else None
        if relative is None or relative.parts[0] not in ('clone', 'environments') or '.git' in relative.parts:
            raise DeploymentError('Content link escapes serving trees: %s' % path)
        if target.is_dir():
            if target in ancestors:
                raise DeploymentError('Cyclic content directory: %s' % path)
            if target in visited:
                return
            for child in sorted(target.iterdir()):
                if child.name != '.git':
                    visit(child, ancestors | {target})
            visited.add(target)
        elif not target.is_file():
            raise DeploymentError('Unsupported content file: %s' % path)

    for name in ('environments', 'clone'):
        path = generation / name
        if path.is_symlink() or not path.is_dir():
            raise DeploymentError('Generation has no regular %s tree' % name)
        visit(path, set())


def _relative(path):
    """Reject paths that could make a builder write outside its private tree."""
    if not isinstance(path, str) or not path or Path(path).is_absolute() or any(
            part in ('', '.', '..', '.git') for part in path.split('/')):
        raise DeploymentError('Invalid component path: %r' % path)
    return path


def _requirements():
    """Run in the configured worker; enumerate required output independently.

    The legacy builder iterates known repositories and can silently ignore an
    override naming an unknown repository. Validate that before building.
    """
    from jens.settings import Settings
    from jens.environments import get_names_of_declared_environments
    from jens.environments import read_environment_definition, _resolve_branch
    settings = Settings()
    with open(settings.REPO_METADATA) as metadata:
        repositories = yaml.safe_load(metadata)['repositories']
    for partition in ('modules', 'hostgroups', 'common'):
        for name in repositories[partition]:
            _relative(name)
    for branch in settings.MANDATORY_BRANCHES:
        _relative(branch)
    required = {'environments': sorted(get_names_of_declared_environments()),
                'links': {}, 'files': []}
    for environment in required['environments']:
        _relative(environment)
        definition = read_environment_definition(environment)
        overrides = definition.get('overrides', {})
        for partition, components in overrides.items():
            for name, ref in components.items():
                if name not in repositories[partition]:
                    raise DeploymentError('Unknown override %s/%s in %s' % (
                        partition, name, environment))
                _relative(ref)
        base = 'environments/' + environment

        def link(path, partition, name, suffix):
            if name not in repositories[partition]:
                raise DeploymentError('Missing required repository %s/%s' % (partition, name))
            branch, _ = _resolve_branch(partition, name, definition)
            _relative(branch)
            required['links'][base + '/' + path] = 'clone/%s/%s/%s/%s' % (
                partition, name, branch, suffix)

        for partition in ('modules', 'hostgroups'):
            names = repositories[partition] if 'default' in definition else overrides.get(partition, {})
            for name in names:
                if partition == 'modules':
                    link('modules/' + name, partition, name, 'code')
                    link('hieradata/module_names/' + name, partition, name, 'data')
                else:
                    link('hostgroups/hg_' + name, partition, name, 'code')
                    link('hieradata/hostgroups/' + name, partition, name, 'data/hostgroup')
                    link('hieradata/fqdns/' + name, partition, name, 'data/fqdns')
        link('site', 'common', 'site', 'code')
        required['files'].append(base + '/site/site.pp')
        for item in settings.COMMON_HIERADATA_ITEMS:
            _relative(item)
            link('hieradata/' + item, 'common', 'hieradata', 'data/' + item)
        if settings.DIRECTORY_ENVIRONMENTS:
            required['files'].append(base + '/environment.conf')
    return required


def _check_requirements(generation, required):
    actual = sorted(path.name for path in (generation / 'environments').iterdir())
    if actual != required['environments']:
        raise DeploymentError('Generated environment set does not match definitions')
    for relative, destination in required['links'].items():
        path = generation / relative
        if not path.is_symlink() or path.resolve() != (generation / destination).resolve():
            raise DeploymentError('Missing or incorrect required component: %s' % relative)
    for relative in required['files']:
        if not (generation / relative).is_file():
            raise DeploymentError('Missing required file: %s' % relative)


def _contents(generation):
    """Fingerprint all serving entries, including empty directories and links.

    Git administration files are excluded; actual worktree content is hashed so
    HEAD alone cannot conceal deleted, dirty or added files. Access permissions
    may be adjusted for readers, but executable status is part of file identity.
    """
    result = {}

    def record(path):
        relative = str(path.relative_to(generation))
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            result[relative] = {'type': 'link', 'target': os.readlink(path)}
        elif stat.S_ISDIR(mode):
            result[relative] = {'type': 'directory'}
            for child in sorted(path.iterdir()):
                if child.name != '.git':
                    record(child)
        elif stat.S_ISREG(mode):
            digest = hashlib.sha256()
            with path.open('rb') as content:
                for chunk in iter(lambda: content.read(1024 * 1024), b''):
                    digest.update(chunk)
            result[relative] = {'type': 'file', 'sha256': digest.hexdigest(),
                                'executable': bool(mode & 0o111)}
        else:
            raise DeploymentError('Unsupported content file: %s' % path)

    for name in ('environments', 'clone'):
        record(generation / name)
    return result


def _seal(generation):
    # Accidental-write protection, not a boundary against the owner or root.
    for name in ('clone', 'environments'):
        for directory, dirs, files in os.walk(generation / name, topdown=False):
            for entry in files + dirs:
                path = Path(directory) / entry
                if not path.is_symlink():
                    path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
            Path(directory).chmod(stat.S_IMODE(Path(directory).stat().st_mode) & ~0o222)


def _read_manifest(generation):
    try:
        if (generation / 'complete.json').is_symlink():
            raise ValueError('Completion manifest must be a regular file')
        with open(generation / 'complete.json') as complete:
            manifest = json.load(complete)
        if (not isinstance(manifest, dict) or manifest.get('format') != 2 or
                not isinstance(manifest.get('contents'), dict) or
                not isinstance(manifest.get('commits'), dict) or
                not isinstance(manifest.get('required'), dict) or
                not isinstance(manifest.get('protected_environments'), list)):
            raise ValueError('Unsupported or incomplete completion manifest')
        required = manifest['required']
        if (not isinstance(required.get('environments'), list) or
                not isinstance(required.get('links'), dict) or
                not isinstance(required.get('files'), list)):
            raise ValueError('Missing required output inventory')
        for path in required['environments'] + required['files'] + manifest['protected_environments']:
            _relative(path)
        for source, destination in required['links'].items():
            _relative(source)
            _relative(destination)
        return manifest
    except (OSError, ValueError, TypeError) as error:
        raise DeploymentError('Invalid completion manifest in %s: %s' % (generation, error)) from error


def _check_protected(root, environments, protected):
    protected = set(protected)
    current = root / 'current'
    if os.path.lexists(current):
        if not current.is_symlink():
            raise DeploymentError('Current deployment must be a symlink')
        active = current.resolve()
        if active.parent != root / 'generations':
            raise DeploymentError('Current deployment is outside this root')
        protected.update(_read_manifest(active)['protected_environments'])
    missing = protected.difference(environments)
    if missing:
        raise DeploymentError('Refusing to omit protected environments: %s' % ', '.join(sorted(missing)))


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
        with open(generation / 'required.json') as output:
            required = json.load(output)
        _check_requirements(generation, required)
        _check_protected(root, required['environments'], main['protectedenvironments'])
        manifest = {'format': 2, 'commits': {}, 'required': required,
                    'protected_environments': main['protectedenvironments'],
                    'contents': _contents(generation)}
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
        _seal(generation)
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
        manifest = _read_manifest(generation)
        _validate_links(generation)
        _check_requirements(generation, manifest['required'])
        if _contents(generation) != manifest['contents']:
            raise DeploymentError('Serving content changed after preparation: %s' % generation)
        _check_protected(root, manifest['required']['environments'],
                         manifest['protected_environments'])
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
    required = _requirements()
    deltas, inventory = refresh_repositories()
    refresh_environments(deltas, inventory)
    with open(Path(config).parent / 'required.json', 'w') as output:
        json.dump(required, output, indent=2, sort_keys=True)


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
