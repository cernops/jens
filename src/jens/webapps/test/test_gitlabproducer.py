import json
import unittest
import os
import yaml
from mock import patch
from dirq.queue import Queue, QueueLockError

from jens.test.tools import init_repositories
from jens.test.tools import add_repository, del_repository
from jens.test.tools import create_fake_repository
from jens.test.testcases import JensTestCase
from jens.webapps.gitlabproducer import app as gitlabproducer

class GitlabProducerTestCase(JensTestCase):

    def setUp(self):
        super(GitlabProducerTestCase, self).setUp()
        init_repositories(self.settings)
        (bare, user) = create_fake_repository(self.settings, self.sandbox_path, ['qa'])
        add_repository(self.settings, 'common', 'site', bare)
        self.site_bare = bare
        gitlabproducer.config['settings'] = self.settings
        self.app = gitlabproducer.test_client()
   
    def test_get(self):
        self.assertEquals(self.app.get('/gitlab').status_code, 405)

    def test_no_payload(self):
        reply = self.app.post('/gitlab')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)

    def test_wrong_payload(self):
        reply = self.app.post('/gitlab', data={'iam':'wrong'}, content_type='application/json')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)

    def test_wrong_payload2(self):
        reply = self.app.post('/gitlab', data=json.dumps({'repository':'wrong'}), content_type='application/json')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)
    
    def test_no_content_type(self):
        reply = self.app.post('/gitlab',
                    data=json.dumps({'repository': 
                        {
                         'name': 'it-puppet-hostgroup-playground',
                         'git_ssh_url': 'http://git.cern.ch/cernpub/it-puppet-hostgroup-playground'
                        }
                    }))
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)

    @patch.object(Queue, 'add')
    def test_known_repository(self, mock_add):
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-site',
                         'git_ssh_url': "file://%s" % self.site_bare
                        }
                    }))
        mock_add.assert_called_once()
        self.assertEquals(reply.status_code, 200)

    def test_repository_not_found(self):
        reply = self.app.post('/gitlab', content_type='application/json',
                    data=json.dumps({'repository':
                        {
                         'name': 'it-puppet-site',
                         'git_ssh_url': "file://foo"
                        }
                    }))
        self.assertEquals(reply.status_code, 404)
