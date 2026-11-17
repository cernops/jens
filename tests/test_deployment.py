"""Isolated integration tests: only local fixture repositories and temporary files."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from jens.deployment import DeploymentError, prepare, publish


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='jens_deploy_test_')
        self.addCleanup(self.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'deployments'
        self.code = self.repository('code', {
            'code/manifests/init.pp': 'old code', 'code/site.pp': '# site',
            'data/example.yaml': 'old data', 'data/hostgroup/example.yaml': '{}',
            'data/fqdns/example.yaml': '{}', 'data/common.yaml': '{}'})
        self.envs = self.repository('envs', {'production.yaml': 'notifications: fixture@example.invalid\ndefault: master\n'})
        definition = {'repositories': {'modules': {'example': str(self.code)},
                                      'hostgroups': {'example': str(self.code)},
                                      'common': {'site': str(self.code),
                                                 'hieradata': str(self.code)}}}
        self.metadata = self.repository('metadata', {'repositories.yaml': yaml.safe_dump(definition)})
        self.config = self.base / 'source.conf'
        self.config.write_text('''[main]
environmentsmetadatadir = %s
repositorymetadatadir = %s
repositorymetadata = %s/repositories.yaml
common_hieradata_items = common.yaml,
directory_environments = True
mode = ONDEMAND
[messaging]
queuedir = %s/do_not_consume
''' % (self.envs, self.metadata, self.metadata, self.base))

    def cleanup(self):
        # Older TemporaryDirectory implementations cannot reliably remove a
        # sealed tree containing symlinks. Restore only real directory access;
        # never follow links into another tree during cleanup.
        for directory, _, _ in os.walk(self.base, followlinks=False):
            path = Path(directory)
            path.chmod(path.stat().st_mode | 0o700)
        self.temporary.cleanup()

    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path)] + list(args),
                                       stderr=subprocess.PIPE, text=True).strip()

    def repository(self, name, files):
        path = self.base / name
        path.mkdir()
        self.git(path, 'init', '-b', 'master')
        self.git(path, 'config', 'user.name', 'Test fixture')
        self.git(path, 'config', 'user.email', 'fixture@example.invalid')
        for name, content in files.items():
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        self.commit(path)
        self.git(path, 'branch', 'qa')
        return path

    def commit(self, path):
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-m', 'Update fixture')

    def test_complete_replacement_keeps_old_generation_unchanged(self):
        first = prepare(self.config, self.root)
        self.assertFalse((self.root / 'current').exists())
        with self.assertRaises(DeploymentError):
            publish(self.root, first)
        publish(self.root, first, readers_drained=True)
        # Reader pinning: resolve once and retain this path for the operation.
        pinned = (self.root / 'current/environments').resolve()
        old = pinned / 'production/modules/example/manifests/init.pp'
        self.assertEqual(old.read_text(), 'old code')
        self.assertEqual((pinned / 'production/hieradata/module_names/example/example.yaml').read_text(), 'old data')
        (self.code / 'code/manifests/init.pp').write_text('new code')
        (self.code / 'data/example.yaml').write_text('new data')
        self.commit(self.code)
        second = prepare(self.config, self.root)
        self.assertEqual((self.root / 'current').resolve(), first)
        publish(self.root, second, readers_drained=True)
        self.assertEqual(old.read_text(), 'old code')
        self.assertEqual((pinned / 'production/hieradata/module_names/example/example.yaml').read_text(), 'old data')
        new = self.root / 'current/environments/production'
        self.assertEqual((new / 'modules/example/manifests/init.pp').read_text(), 'new code')
        self.assertEqual((new / 'hieradata/module_names/example/example.yaml').read_text(), 'new data')
        manifest = json.loads((second / 'complete.json').read_text())
        self.assertEqual(manifest['commits']['clone/modules/example/master'],
                         self.git(self.code, 'rev-parse', 'master'))
        publish(self.root, first, readers_drained=True)
        self.assertEqual(old.read_text(), 'old code')
        self.assertEqual(self.git(self.envs, 'status', '--porcelain'), '')
        self.assertFalse((self.base / 'do_not_consume').exists())

    def test_failed_fetch_does_not_publish_and_retry_needs_no_new_commit(self):
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        hidden = self.base / 'unavailable'
        self.code.rename(hidden)
        try:
            with self.assertRaises(DeploymentError):
                prepare(self.config, self.root)
        finally:
            hidden.rename(self.code)
        self.assertEqual((self.root / 'current').resolve(), first)
        retried = prepare(self.config, self.root)
        self.assertTrue((retried / 'complete.json').exists())
        failed = [p for p in (self.root / 'generations').iterdir()
                  if not (p / 'complete.json').exists()]
        self.assertEqual(len(failed), 1)
        with self.assertRaises(DeploymentError):
            publish(self.root, failed[0], readers_drained=True)

    def test_bad_override_and_broken_content_are_rejected(self):
        (self.envs / 'production.yaml').write_text(
            'notifications: fixture@example.invalid\ndefault: master\noverrides:\n  modules:\n    example: absent\n')
        self.commit(self.envs)
        with self.assertRaises(DeploymentError):
            prepare(self.config, self.root)
        self.assertFalse((self.root / 'current').exists())
        (self.envs / 'production.yaml').write_text('notifications: fixture@example.invalid\ndefault: master\n')
        self.commit(self.envs)
        self.git(self.code, 'rm', '-r', 'code')
        self.git(self.code, 'commit', '-m', 'Remove required code')
        with self.assertRaises(DeploymentError):
            prepare(self.config, self.root)

    def test_publish_rejects_escape_and_non_symlink_destination(self):
        generation = prepare(self.config, self.root)
        (generation / 'environments').chmod(0o700)  # Simulate owner interference.
        link = generation / 'environments/escape'
        link.symlink_to(self.code)
        with self.assertRaises(DeploymentError):
            publish(self.root, generation, readers_drained=True)
        link.unlink()
        (self.root / 'current').mkdir()
        with self.assertRaises(DeploymentError):
            publish(self.root, generation, readers_drained=True)
        with self.assertRaises(DeploymentError):
            publish(self.root, self.base, readers_drained=True)

    def test_interrupted_publication_preserves_current_and_can_retry(self):
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        second = prepare(self.config, self.root)
        with patch('jens.deployment.os.replace', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                publish(self.root, second, readers_drained=True)
        self.assertEqual((self.root / 'current').resolve(), first)
        # Simulate a killed publisher leaving a temporary pointer behind.
        (self.root / '.current.new').symlink_to(first)
        publish(self.root, second, readers_drained=True)
        self.assertEqual((self.root / 'current').resolve(), second)
        self.assertFalse(os.path.lexists(self.root / '.current.new'))

    def test_missing_config_and_missing_environment_tree_are_rejected(self):
        with self.assertRaises(OSError):
            prepare(self.base / 'missing.conf', self.root)
        self.assertFalse(self.root.exists())
        generation = prepare(self.config, self.root)
        (generation / 'environments').rename(generation / 'removed_environments')
        with self.assertRaises(DeploymentError):
            publish(self.root, generation, readers_drained=True)

    def test_busy_lock_and_unmanaged_root_are_rejected(self):
        unmanaged = self.base / 'unmanaged'
        unmanaged.mkdir()
        with self.assertRaises(DeploymentError):
            prepare(self.config, unmanaged)
        generation = prepare(self.config, self.root)
        with open(self.root / 'deploy.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                prepare(self.config, self.root)
            with self.assertRaises(BlockingIOError):
                publish(self.root, generation, readers_drained=True)

    def test_protected_environment_cannot_disappear(self):
        self.config.write_text(self.config.read_text().replace(
            '[main]', '[main]\nprotectedenvironments = production,'))
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        self.git(self.envs, 'rm', 'production.yaml')
        self.git(self.envs, 'commit', '-m', 'Remove protected environment')
        with self.assertRaisesRegex(DeploymentError, 'protected environments: production'):
            prepare(self.config, self.root)
        self.assertEqual((self.root / 'current').resolve(), first)
        self.assertEqual(sum((path / 'complete.json').exists()
                             for path in (self.root / 'generations').iterdir()), 1)

    def test_initial_protected_environment_must_exist(self):
        self.config.write_text(self.config.read_text().replace(
            '[main]', '[main]\nprotectedenvironments = absent,'))
        with self.assertRaisesRegex(DeploymentError, 'protected environments: absent'):
            prepare(self.config, self.root)
        self.assertFalse(os.path.lexists(self.root / 'current'))

    def test_protection_can_be_removed_before_environment_removal(self):
        source = self.config.read_text()
        self.config.write_text(source.replace(
            '[main]', '[main]\nprotectedenvironments = production,'))
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        self.config.write_text(source)
        unprotected = prepare(self.config, self.root)
        publish(self.root, unprotected, readers_drained=True)
        self.git(self.envs, 'rm', 'production.yaml')
        self.git(self.envs, 'commit', '-m', 'Remove explicitly unprotected environment')
        empty = prepare(self.config, self.root)
        publish(self.root, empty, readers_drained=True)
        self.assertFalse((self.root / 'current/environments/production').exists())

    def test_publication_rechecks_current_protection(self):
        definition = (self.envs / 'production.yaml').read_text()
        self.git(self.envs, 'rm', 'production.yaml')
        self.git(self.envs, 'commit', '-m', 'Prepare old empty environment set')
        stale = prepare(self.config, self.root)
        (self.envs / 'production.yaml').write_text(definition)
        self.commit(self.envs)
        self.config.write_text(self.config.read_text().replace(
            '[main]', '[main]\nprotectedenvironments = production,'))
        active = prepare(self.config, self.root)
        publish(self.root, active, readers_drained=True)
        with self.assertRaisesRegex(DeploymentError, 'protected environments: production'):
            publish(self.root, stale, readers_drained=True)
        self.assertEqual((self.root / 'current').resolve(), active)

    def test_unknown_overrides_are_rejected_in_all_partitions(self):
        for partition in ('modules', 'hostgroups', 'common'):
            with self.subTest(partition=partition):
                (self.envs / 'production.yaml').write_text(
                    'notifications: fixture@example.invalid\ndefault: master\n'
                    'overrides:\n  %s:\n    missing: master\n' % partition)
                self.commit(self.envs)
                with self.assertRaisesRegex(DeploymentError, 'Unknown override %s/missing' % partition):
                    prepare(self.config, self.root)

    def test_nested_external_links_are_rejected(self):
        external = self.base / 'mutable.pp'
        external.write_text('mutable content')
        manifest = self.code / 'code/manifests/init.pp'
        manifest.unlink()
        manifest.symlink_to(external)
        self.commit(self.code)
        with self.assertRaisesRegex(DeploymentError, 'escapes serving trees'):
            prepare(self.config, self.root)
        manifest.unlink()
        manifest.write_text('restored code')
        (self.code / 'code/manifests/external').symlink_to(self.base)
        self.commit(self.code)
        with self.assertRaisesRegex(DeploymentError, 'escapes serving trees'):
            prepare(self.config, self.root)

    def test_nested_internal_links_are_valid_and_remain_isolated(self):
        shared = self.code / 'code/shared.pp'
        shared.write_text('first value')
        manifest = self.code / 'code/manifests/init.pp'
        manifest.unlink()
        manifest.symlink_to('../shared.pp')
        self.commit(self.code)
        generation = prepare(self.config, self.root)
        publish(self.root, generation, readers_drained=True)
        served = generation / 'environments/production/modules/example/manifests/init.pp'
        shared.write_text('second value')
        self.commit(self.code)
        self.assertEqual(served.read_text(), 'first value')

    def test_nested_broken_and_cyclic_links_are_rejected(self):
        link = self.code / 'code/manifests/link'
        for target in ('missing', 'link', '.'):
            with self.subTest(target=target):
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(target)
                self.commit(self.code)
                with self.assertRaisesRegex(DeploymentError, '(Broken|Cyclic)'):
                    prepare(self.config, self.root)

    def test_publication_rejects_modified_or_missing_content(self):
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        for mutation in ('remove_environment', 'dirty_file', 'extra_file', 'executable', 'remove_file'):
            with self.subTest(mutation=mutation):
                candidate = prepare(self.config, self.root)
                code = candidate / 'clone/modules/example/master/code'
                manifest = code / 'manifests/init.pp'
                # Deliberately override accidental-write protection as the owner.
                if mutation == 'remove_environment':
                    (candidate / 'environments').chmod(0o700)
                    for directory, dirs, _ in os.walk(candidate / 'environments/production'):
                        Path(directory).chmod(0o700)
                    shutil.rmtree(candidate / 'environments/production')
                elif mutation == 'dirty_file':
                    manifest.chmod(0o600)
                    manifest.write_text('modified after completion')
                elif mutation == 'extra_file':
                    code.chmod(0o700)
                    (code / 'extra.pp').write_text('added after completion')
                elif mutation == 'executable':
                    manifest.chmod(0o555)
                else:
                    manifest.parent.chmod(0o700)
                    manifest.unlink()
                with self.assertRaises(DeploymentError):
                    publish(self.root, candidate, readers_drained=True)
                self.assertEqual((self.root / 'current').resolve(), first)

    def test_publication_rejects_wrong_but_valid_component_link(self):
        candidate = prepare(self.config, self.root)
        link = candidate / 'environments/production/modules/example'
        link.parent.chmod(0o700)
        link.unlink()
        link.symlink_to(candidate / 'clone/modules/example/qa/code')
        with self.assertRaisesRegex(DeploymentError, 'incorrect required component'):
            publish(self.root, candidate, readers_drained=True)

    def test_invalid_completion_manifests_are_rejected(self):
        candidate = prepare(self.config, self.root)
        for content in ('not json', '{}', '{"format": 1}', '{"format": 2}'):
            with self.subTest(content=content):
                (candidate / 'complete.json').write_text(content)
                with self.assertRaisesRegex(DeploymentError, 'Invalid completion manifest'):
                    publish(self.root, candidate, readers_drained=True)
        self.assertFalse(os.path.lexists(self.root / 'current'))

    def test_completed_serving_content_has_write_bits_removed(self):
        candidate = prepare(self.config, self.root)
        for relative in ('clone', 'environments', 'clone/modules/example/master/code/manifests/init.pp'):
            self.assertEqual((candidate / relative).stat().st_mode & 0o222, 0)

    def test_reader_access_permissions_can_be_adjusted_without_changing_identity(self):
        candidate = prepare(self.config, self.root)
        (candidate / 'clone/modules/example/master/code').chmod(0o550)
        (candidate / 'clone/modules/example/master/code/manifests/init.pp').chmod(0o440)
        publish(self.root, candidate, readers_drained=True)
        self.assertEqual((self.root / 'current').resolve(), candidate)

    def test_same_repository_reads_can_cross_current_switch(self):
        # A filesystem example, not a simulation of Puppet's compiler/caches.
        first = prepare(self.config, self.root)
        publish(self.root, first, readers_drained=True)
        (self.code / 'code/manifests/init.pp').write_text('new code')
        (self.code / 'data/example.yaml').write_text('new data')
        self.commit(self.code)  # Both files change in one repository commit.
        second = prepare(self.config, self.root)
        live = self.root / 'current/environments/production'
        pinned = live.resolve()
        code = (live / 'modules/example/manifests/init.pp').read_text()
        publish(self.root, second, readers_drained=True)
        data = (live / 'hieradata/module_names/example/example.yaml').read_text()
        self.assertEqual((code, data), ('old code', 'new data'))
        self.assertEqual((pinned / 'hieradata/module_names/example/example.yaml').read_text(), 'old data')


if __name__ == '__main__':
    unittest.main()
