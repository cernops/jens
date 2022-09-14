from __future__ import absolute_import
import json
from mock import patch

from jens.errors import JensMessagingError
from jens.test.tools import init_repositories
from jens.test.tools import add_repository
from jens.test.tools import create_fake_repository
from jens.test.testcases import JensTestCase
from jens.webapps.gitlabproducer import app as gitlabproducer
from jens.settings import Settings

class GitlabProducerTestCase(JensTestCase):

    def setUp(self):
        super().setUp()
        init_repositories()
        (bare, _) = create_fake_repository(self.sandbox_path, ['qa'])
        add_repository('common', 'site', bare)
        self.site_bare = bare
        gitlabproducer.config['settings'] = Settings()
        self.app = gitlabproducer.test_client()

    def test_get(self):
        self.assertEqual(self.app.get('/gitlab').status_code, 405)

    def test_no_payload(self):
        reply = self.app.post('/gitlab')
        self.assertEqual(reply.data.decode(), 'Malformed request')
        self.assertEqual(reply.status_code, 400)

    def test_wrong_payload(self):
        reply = self.app.post('/gitlab', data={'iam':'wrong'}, content_type='application/json')
        self.assertEqual(reply.data.decode(), 'Malformed request')
        self.assertEqual(reply.status_code, 400)

    def test_wrong_payload2(self):
        reply = self.app.post('/gitlab', data=json.dumps({'repository':'wrong'}), content_type='application/json')
        self.assertEqual(reply.data.decode(), 'Malformed request')
        self.assertEqual(reply.status_code, 400)

    def test_no_content_type(self):
        reply = self.app.post('/gitlab',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-hostgroup-playground',
                         'git_ssh_url': 'http://git.cern.ch/cernpub/it-puppet-hostgroup-playground'
                        }
                    }))
        self.assertEqual(reply.data.decode(), 'Malformed request')
        self.assertEqual(reply.status_code, 400)

    @patch('jens.webapps.gitlabproducer.enqueue_hint')
    def test_known_repository(self, mock_eq):
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-site',
                         'git_ssh_url': f"file://{self.site_bare}"
                        }
                    }))
        mock_eq.assert_called_once_with('common', 'site')
        self.assertEqual(reply.status_code, 200)

    @patch('jens.webapps.gitlabproducer.enqueue_hint', side_effect=JensMessagingError)
    def test_queue_error(self, mock_eq):
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-site',
                         'git_ssh_url': f"file://{self.site_bare}"
                        }
                    }))
        mock_eq.assert_called_once()
        self.assertEqual(reply.data.decode(), 'Queue not accessible')
        self.assertEqual(reply.status_code, 500)

    def test_repository_not_found(self):
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-site',
                         'git_ssh_url': "file://foo"
                        }
                    }))
        self.assertEqual(reply.status_code, 404)

    @patch('jens.webapps.gitlabproducer.enqueue_hint')
    def test_fuzzy_matching_vague_match(self, mock_eq):
        """No exact match, matching URL prefix and simplest
        namespace/repo case. Should find the module.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.example.org:']
        add_repository('modules', 'module1', \
                       "ssh://git@gitlab.example.org:1234/name+space-1/it-re_module1.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-re_module1',
                         'git_ssh_url': "git@gitlab.example.org:name+space-1/it-re_module1.git",
                        }
                    }))
        mock_eq.assert_called_once_with('modules', 'module1')
        self.assertEqual(reply.status_code, 200)

    @patch('jens.webapps.gitlabproducer.enqueue_hint')
    def test_fuzzy_matching_vague_match_several_prefixes(self, mock_eq):
        """No exact match, matching URL prefix (not the first) and
        simplest namespace/repo case. Makes sure that
        GITLAB_PRODUCER_FUZZY_URL_PREFIXES is iterated. Should find
        the module.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = \
            ['user@gl.example.com', 'git@gitlab.example.org:']
        add_repository('modules', 'module1', \
                       "ssh://git@gitlab.example.org:1234/namespace/module1.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module1',
                         'git_ssh_url': "git@gitlab.example.org:namespace/module1.git",
                        }
                    }))
        mock_eq.assert_called_once_with('modules', 'module1')
        self.assertEqual(reply.status_code, 200)

    @patch('jens.webapps.gitlabproducer.enqueue_hint')
    # No exact match, matching URL prefix and path with not just
    # namespace/repo. Should find the repository in the metadata
    # as the "tail" namespace/repo matches.
    def test_fuzzy_matching_vague_match_long_path(self, mock_eq):
        """No exact match, matching URL prefix and path with not just
        namespace/repo. Should find the repository in the metadata
        as the "tail" namespace/repo matches.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.example.org:']
        add_repository('modules', 'module5', \
                       "ssh://git@gitlab.example.org:1234/foo/namespace/module5.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module1',
                         'git_ssh_url': "git@gitlab.example.org:bar/namespace/module5.git",
                        }
                    }))
        mock_eq.assert_called_once_with('modules', 'module5')
        self.assertEqual(reply.status_code, 200)

    def test_fuzzy_matching_good_prefix_different_repo(self):
        """No exact match, hook URL matches a configured prefix but the
        repository itself is not the correct one, should 404.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.example.org:']
        add_repository('modules', 'module5', \
                       "ssh://git@gitlab.example.org:1234/namespace/module5.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module55',
                         'git_ssh_url': "git@gitlab.example.org:namespace/module55.git",
                        }
                    }))
        self.assertEqual(reply.status_code, 404)

    def test_fuzzy_matching_no_valid_prefix(self):
        """No exact match and no URL prefixes that match either, should 404."""
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.somewhereelse.org:']
        add_repository('modules', 'module2', \
                       "ssh://git@gitlab.somewhereelse.org:1234/namespace/module2.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module2',
                         'git_ssh_url': "git@gitlab.example.org:namespace/module2.git",
                        }
                    }))
        self.assertEqual(reply.status_code, 404)

    @patch('jens.webapps.gitlabproducer.enqueue_hint')
    def test_fuzzy_matching_not_matching_start_exact_match_nonetheless(self, mock_eq):
        """Even if a prefix is configured, exact matches should always win."""
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.foo.org:']
        add_repository('modules', 'module3', \
                       "ssh://git@gitlab.example.org:1234/namespace/module3.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module3',
                         'git_ssh_url': "ssh://git@gitlab.example.org:1234/namespace/module3.git",
                        }
                    }))
        mock_eq.assert_called_once_with('modules', 'module3')
        self.assertEqual(reply.status_code, 200)

    def test_fuzzy_matching_repo_no_tail_exact_match(self):
        """No exact match and matching URL prefix. Partial match in the
        namespace/repo combo, but not good enough. Should 404.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.example.org:']
        add_repository('modules', 'module2', \
                       "ssh://git@gitlab.example.org:1234/namespace/module2.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module2',
                         'git_ssh_url': "git@gitlab.example.org:namespace/module2",
                        }
                    }))
        self.assertEqual(reply.status_code, 404)

    def test_fuzzy_matching_repo_no_namespace_match(self):
        """No exact match and matching URL prefix. Good match in repo
        name but different namespace. Should 404.
        """
        self.settings.GITLAB_PRODUCER_FUZZY_URL_PREFIXES = ['git@gitlab.example.org:']
        add_repository('modules', 'module7', \
                       "ssh://git@gitlab.example.org:1234/start/module7.git",
                       local=False)
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'module7',
                         'git_ssh_url': "git@gitlab.example.org:planet/module7.git",
                        }
                    }))
        self.assertEqual(reply.status_code, 404)
