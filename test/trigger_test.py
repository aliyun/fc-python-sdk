import fc2
import logging
import unittest
import os
import json


class TestService(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestService, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']
        self.account_id = os.environ['ACCOUNT_ID']
        self.region = os.environ['REGION']
        self.code_bucket = os.environ['CODE_BUCKET']
        self.invocation_role = os.environ['INVOCATION_ROLE']
        self.invocation_role_sls = os.environ['INVOCATION_ROLE_SLS']
        self.log_project = os.environ['LOG_PROJECT']
        self.log_store = os.environ['LOG_STORE']
        self.service_name = 'test_trigger_service'
        self.function_name = 'test_trigger_function'
        self.http_function_name = 'test_http_function'
        self.trigger_name = 'test_trigger'

        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )

    def setUp(self):
        for i in range(1, 5):
            try:
                self.client.delete_trigger(self.service_name, self.function_name, self.trigger_name + str(i))
            except:
                pass
        try:
            self.client.delete_trigger(self.service_name, self.function_name, self.trigger_name)
        except:
            pass
        try:
            self.client.delete_trigger(self.service_name, self.http_function_name, self.trigger_name)
        except:
            pass
        try:
            self.client.delete_function(self.service_name, self.http_function_name)
        except:
            pass
        try:
            self.client.delete_function(self.service_name, self.function_name)
        except:
            pass
        try:
            self.client.delete_service(self.service_name)
        except:
            pass
        self.client.create_service(self.service_name)
        self.client.create_function(self.service_name, self.function_name, handler='main.my_handler',
                                    runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(self.service_name, self.http_function_name, handler='main.wsgi_echo_handler',
                                    runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')

    def tearDown(self):
        for i in range(1, 5):
            try:
                self.client.delete_trigger(self.service_name, self.function_name, self.trigger_name + str(i))
            except:
                pass
        try:
            self.client.delete_trigger(self.service_name, self.function_name, self.trigger_name)
        except:
            pass
        try:
            self.client.delete_trigger(self.service_name, self.http_function_name, self.trigger_name)
        except:
            pass
        try:
            self.client.delete_function(self.service_name, self.http_function_name)
        except:
            pass
        try:
            self.client.delete_function(self.service_name, self.function_name)
        except:
            pass
        try:
            self.client.delete_service(self.service_name)
        except:
            pass

    def test_oss_trigger(self):
        service_name = self.service_name
        function_name = self.function_name
        trigger_type = 'oss'
        trigger_name = self.trigger_name
        source_arn = 'acs:oss:{0}:{1}:{2}'.format(self.region, self.account_id, self.code_bucket)
        invocation_role = self.invocation_role
        prefix = 'pre'
        suffix = 'suf'
        trigger_config = {
            'events': ['oss:ObjectCreated:*'],
            'filter': {
                'key': {
                    'prefix': prefix,
                    'suffix': suffix
                }
            }
        }

        # create
        # 200 ok
        logging.info('create trigger: {0}'.format(trigger_name))
        create_trigger_resp = self.client.create_trigger(service_name, function_name, trigger_name, trigger_type,
                                                         trigger_config, source_arn, invocation_role).data
        self.check_trigger_response(create_trigger_resp, trigger_name, trigger_type, trigger_config, source_arn,
                                    invocation_role)
        # 404
        with self.assertRaises(fc2.FcError):
            self.client.create_trigger(service_name + 'invalid', function_name, trigger_name, trigger_type,
                                       trigger_config, source_arn, invocation_role)

        # get
        # 200 ok
        logging.info('get trigger: {0}'.format(trigger_name))
        get_trigger_resp = self.client.get_trigger(service_name, function_name, trigger_name).data
        self.check_trigger_response(get_trigger_resp, trigger_name, trigger_type, trigger_config, source_arn,
                                    invocation_role)
        # 404
        with self.assertRaises(fc2.FcError):
            self.client.get_trigger(service_name, function_name + 'invalid', trigger_name)

        # update
        # 200 ok
        prefix_update = prefix + 'update'
        suffix_update = suffix + 'update'
        trigger_config_update = {
            'events': ['oss:ObjectCreated:*'],
            'filter': {
                'key': {
                    'prefix': prefix_update,
                    'suffix': suffix_update
                }
            }
        }
        logging.info('update trigger: {0}'.format(trigger_name))
        update_trigger_resp = self.client.update_trigger(service_name, function_name, trigger_name,
                                                         trigger_config_update, invocation_role).data
        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update, source_arn,
                                    invocation_role)
        # 404
        with self.assertRaises(fc2.FcError):
            self.client.update_trigger(service_name + 'invalid', function_name, trigger_name,
                                       trigger_config_update, invocation_role)

        # list
        for i in range(1, 5):
            trigger_config = {
                'events': ['oss:ObjectCreated:*'],
                'filter': {
                    'key': {
                        'prefix': prefix_update + str(i),
                        'suffix': suffix_update + str(i)
                    }
                }
            }
            self.client.create_trigger(service_name, function_name, trigger_name + str(i), trigger_type, trigger_config,
                                       source_arn, invocation_role)
        logging.info('list trigger: {0}'.format(trigger_name))
        list_trigger_resp = self.client.list_triggers(service_name, function_name).data
        self.assertEqual(len(list_trigger_resp['triggers']), 5)
        list_trigger_resp = self.client.list_triggers(service_name, function_name, limit=2).data
        num_called = 1
        while 'nextToken' in list_trigger_resp and list_trigger_resp['nextToken']:
            list_trigger_resp = self.client.list_triggers(service_name, function_name, limit=2,
                                                          nextToken=list_trigger_resp['nextToken']).data
            num_called += 1
        self.assertEqual(num_called, 3)

        # delete
        for i in range(1, 5):
            self.client.delete_trigger(service_name, function_name, trigger_name + str(i))
            logging.info('delete trigger: {0}'.format(trigger_name + str(i)))
        self.client.delete_trigger(service_name, function_name, trigger_name)
        logging.info('delete trigger: {0}'.format(trigger_name))
        with self.assertRaises(fc2.FcError):
            self.client.delete_trigger(service_name, function_name, trigger_name)

    def test_http_trigger(self):
        service_name = self.service_name
        function_name = self.http_function_name
        trigger_type = 'http'
        trigger_name = self.trigger_name
        source_arn = 'dummy_arn'
        invocation_role = ''

        trigger_config = {
                'authType': 'anonymous',
                'methods': ['GET'],
        }

        # create
        # 200 ok
        logging.info('create trigger: {0}'.format(trigger_name))
        create_trigger_resp = self.client.create_trigger(service_name, function_name, trigger_name, trigger_type,
                                                         trigger_config, source_arn, invocation_role).data
        self.check_trigger_response(create_trigger_resp, trigger_name, trigger_type, trigger_config, None,
                                    invocation_role)

        # 404
        with self.assertRaises(fc2.FcError):
            self.client.create_trigger(service_name + 'invalid', function_name, trigger_name, trigger_type,
                                       trigger_config, source_arn, invocation_role)

        # get
        # 200 ok
        logging.info('get trigger: {0}'.format(trigger_name))
        get_trigger_resp = self.client.get_trigger(service_name, function_name, trigger_name).data
        self.check_trigger_response(get_trigger_resp, trigger_name, trigger_type, trigger_config, None,
                                    invocation_role)
        # 404
        with self.assertRaises(fc2.FcError):
            self.client.get_trigger(service_name + 'invalid', function_name, trigger_name)

        # update
        # 200 ok
        trigger_config_update = {
                'authType': 'function',
                'methods': ['GET', 'POST'],
        }
        logging.info('update trigger: {0}'.format(trigger_name))
        update_trigger_resp = self.client.update_trigger(service_name, function_name, trigger_name,
                                                         trigger_config_update, invocation_role).data
        self.assertEqual(update_trigger_resp['triggerConfig']['authType'], 'function')
        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update,
                                    None,
                                    invocation_role)

        headers = {
                'Foo': 'Bar',
        }
        params = {
                'key with space': 'value with space',
                'key': 'value',
        }
        r = self.client.do_http_request('POST', service_name, function_name, '/action%20with%20space', headers=headers, params=params, body='hello world')
        self.assertEqual(r.status_code, 202)
        self.assertEqual(json.loads(r.content).get('body'), 'hello world')

        r = self.client.do_http_request('GET', service_name, function_name, '/')
        self.assertEqual(r.status_code, 202)

        with self.assertRaises(TypeError):
            self.client.do_http_request('GET', service_name, function_name, '/', params=123)

        # 404 service not found
        with self.assertRaises(fc2.FcError):
            self.client.update_trigger(service_name + 'invalid', function_name, trigger_name,
                                       trigger_config_update, invocation_role)

        # list
        logging.info('list trigger: {0}'.format(trigger_name))
        list_trigger_resp = self.client.list_triggers(service_name, function_name).data
        self.assertEqual(len(list_trigger_resp['triggers']), 1)

        # delete
        logging.info('delete trigger: {0}'.format(trigger_name))
        self.client.delete_trigger(service_name, function_name, trigger_name)
        with self.assertRaises(fc2.FcError):
            self.client.delete_trigger(service_name, function_name, trigger_name)

    def test_log_trigger(self):
        service_name = self.service_name
        function_name = self.function_name
        trigger_type = 'log'
        trigger_name = self.trigger_name
        source_arn = 'acs:log:{0}:{1}:project/{2}'.format(self.region, self.account_id, self.log_project)
        invocation_role = self.invocation_role_sls
        log_store = self.log_store
        log_project = self.log_project

        trigger_config = {
            'sourceConfig': {
                'logstore': log_store + '_source'
            },
            'jobConfig': {
                'triggerInterval': 60,
                'maxRetryTime': 10
            },
            'functionParameter': {},
            'logConfig': {
                'project': log_project,
                'logstore': log_store
            },
            'enable': False
        }

        # create
        # 200 ok
        logging.info('create trigger: {0}'.format(trigger_name))
        create_trigger_resp = self.client.create_trigger(service_name, function_name, trigger_name, trigger_type,
                                                         trigger_config, source_arn, invocation_role).data
        self.check_trigger_response(create_trigger_resp, trigger_name, trigger_type, trigger_config, source_arn,
                                    invocation_role)

        # 404
        with self.assertRaises(fc2.FcError):
            self.client.create_trigger(service_name + 'invalid', function_name, trigger_name, trigger_type,
                                       trigger_config, source_arn, invocation_role)

        # get
        # 200 ok
        logging.info('get trigger: {0}'.format(trigger_name))
        get_trigger_resp = self.client.get_trigger(service_name, function_name, trigger_name).data
        self.check_trigger_response(get_trigger_resp, trigger_name, trigger_type, trigger_config, source_arn,
                                    invocation_role)
        # 404
        with self.assertRaises(fc2.FcError):
            self.client.get_trigger(service_name + 'invalid', function_name, trigger_name)

        # update
        # 200 ok
        trigger_config_update = {
            'sourceConfig': {
                'logstore': log_store + '_source'
            },
            'jobConfig': {
                'maxRetryTime': 0,
                'triggerInterval': 80
            },
            'functionParameter': {},
            'logConfig': {
                'project': log_project,
                'logstore': log_store
            },
            'enable': False
        }
        logging.info('update trigger: {0}'.format(trigger_name))
        update_trigger_resp = self.client.update_trigger(service_name, function_name, trigger_name,
                                                         trigger_config_update, invocation_role).data
        self.assertEqual(update_trigger_resp['triggerConfig']['jobConfig']['triggerInterval'], 80)
        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update,
                                    source_arn,
                                    invocation_role)
        # 404 service not found
        with self.assertRaises(fc2.FcError):
            self.client.update_trigger(service_name + 'invalid', function_name, trigger_name,
                                       trigger_config_update, invocation_role)

        # list
        logging.info('list trigger: {0}'.format(trigger_name))
        list_trigger_resp = self.client.list_triggers(service_name, function_name).data
        self.assertEqual(len(list_trigger_resp['triggers']), 1)

        # delete
        logging.info('delete trigger: {0}'.format(trigger_name))
        self.client.delete_trigger(service_name, function_name, trigger_name)
        with self.assertRaises(fc2.FcError):
            self.client.delete_trigger(service_name, function_name, trigger_name)

    def check_trigger_response(self, resp, trigger_name, trigger_type, trigger_config, source_arn, invocation_role):
        self.assertEqual(resp['triggerName'], trigger_name)
        self.assertEqual(resp['triggerType'], trigger_type)
        self.assertEqual(resp['sourceArn'], source_arn)
        self.assertEqual(resp['invocationRole'], invocation_role)
        self.assertTrue('createdTime' in resp)
        self.assertTrue('lastModifiedTime' in resp)
        self.assertEqual(resp['triggerConfig'], trigger_config)


if __name__ == '__main__':
    unittest.main()
