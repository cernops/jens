import json
import unittest
import os
import yaml
from mock import patch

from jens.webapps.gitlabproducer import app as gitlabproducer

class GitlabProducerTestCase(unittest.TestCase):

    def setUp(self):
        gitlabproducer.config['config_file'] = os.path.join(os.path.dirname(__file__), 
                   '..',
                   'conf' 
                   'main.conf')
        self.app = gitlabproducer.test_client()
   
    def mock_settings(test):
        @patch('jens.settings.Settings')
        @patch('jens.settings.Settings.parse_config')
        def run_test( *args, **kwargs):
            test(*args, **kwargs)
        return run_test

    def test_get(self):
        self.assertEquals(self.app.get('/gitlab').status_code, 405)

    @mock_settings
    def test_no_payload(self, *args):
        reply = self.app.post('/gitlab')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)

    @mock_settings
    def test_wrong_payload(self, *args):
        reply = self.app.post('/gitlab', data={'iam':'wrong'}, content_type='application/json')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)

    @mock_settings
    def test_wrong_payload2(self, *args):
        reply = self.app.post('/gitlab', data=json.dumps({'repository':'wrong'}), content_type='application/json')
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)
    
    @mock_settings
    def test_no_content_type(self, *args):
        reply = self.app.post('/gitlab',
                    data=json.dumps({'repository': 
                        {
                         'name': 'it-puppet-hostgroup-playground',
                         'git_ssh_url': 'http://git.cern.ch/cernpub/it-puppet-hostgroup-playground'
                        }
                    }))
        self.assertEquals(reply.data, 'Malformed request')
        self.assertEquals(reply.status_code, 400)
    
