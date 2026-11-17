"""Isolated integration tests: only local fixture repositories and temporary files."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from jens.deployment import DeploymentError, prepare, publish


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='jens_deploy_test_')
        self.addCleanup(self.temporary.cleanup)
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
        (self.code / 'code/manifests/init.pp').write_text('new code')
        (self.code / 'data/example.yaml').write_text('new data')
        self.commit(self.code)
        second = prepare(self.config, self.root)
        self.assertEqual((self.root / 'current').resolve(), first)
        publish(self.root, second, readers_drained=True)
        self.assertEqual(old.read_text(), 'old code')
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


if __name__ == '__main__':
    unittest.main()
