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
        (bare, user) = create_fake_repository(self.sandbox_path, ['qa'])
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
