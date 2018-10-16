# -*- coding: utf-8 -*-

import logging
import os
import random
import string
import unittest
import uuid

import fc2


class TestVersioning(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestVersioning, self).__init__(*args, **kwargs)
        self.vpcId = os.environ['VPC_ID']
        self.vSwitchIds = os.environ['VSWITCH_IDS']
        self.securityGroupId = os.environ['SECURITY_GROUP_ID']
        self.vpcRole = os.environ['VPC_ROLE']
        self.userId = os.environ['USER_ID']
        self.groupId = os.environ['GROUP_ID']
        self.nasServerAddr = os.environ['NAS_SERVER_ADDR']
        self.nasMountDir = os.environ['NAS_MOUNT_DIR']
        self.region = os.environ['REGION']
        self.account_id = os.environ['ACCOUNT_ID']
        self.code_bucket = os.environ['CODE_BUCKET']
        self.invocation_role = os.environ['INVOCATION_ROLE']
        self.client = fc2.Client(
            endpoint=os.environ['ENDPOINT'],
            accessKeyID=os.environ['ACCESS_KEY_ID'],
            accessKeySecret=os.environ['ACCESS_KEY_SECRET'],
        )
        self._test_service_name = ""

    def setUp(self):
        name = 'test_version_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        self._test_service_name = name
        desc = u'这是测试service'
        logging.info('Create service: {0}'.format(name))
        service = self.client.create_service(name, description=desc)
        etag = service.headers['etag']
        self.assertNotEqual(etag, '')

        service = service.data
        self.assertEqual(service['serviceName'], name)
        self.assertEqual(service['description'], desc)
        self.assertTrue('createdTime' in service)
        self.assertTrue('lastModifiedTime' in service)
        self.assertTrue('logConfig' in service)
        self.assertTrue('role' in service)
        self.assertTrue('serviceId' in service)

    def tearDown(self):
        # clear all functions and triggers
        r = self.client.list_functions(self._test_service_name)
        functions = r.data['functions']
        for f in functions:
          function_name = f['functionName']
          triggers = self.client.list_triggers(self._test_service_name, function_name).data['triggers']
          for t in triggers:
            trigger_name = t['triggerName']
            self.client.delete_trigger(self._test_service_name, function_name, trigger_name)
          self.client.delete_function(self._test_service_name, function_name)
        
        # clear all versions and alias
        data = self.client.list_versions(self._test_service_name).data
        versions = data['versions']
        nextToken = data.get('nextToken')
        while nextToken:
            data = self.client.list_versions(self._test_service_name, nextToken = nextToken).data
            versions.extend(data['versions'])
            nextToken = data.get('nextToken')

        for v in versions:
            self.client.delete_version(self._test_service_name, v['versionId'])


        data = self.client.list_aliases(self._test_service_name).data
        aliases = data['aliases']
        nextToken = data.get('nextToken')
        while nextToken:
            data = self.client.list_aliases(self._test_service_name, nextToken = nextToken).data
            aliases.extend(data['aliases'])
            nextToken = data.get('nextToken')

        for a in aliases:
            self.client.delete_alias(self._test_service_name, a['aliasName'])

        self.client.delete_service(self._test_service_name)

    def test_version(self):
        r = self.client.publish_version(self._test_service_name, "test service v1")
        data = r.data
        self.assertTrue('versionId' in data)
        self.assertEqual(data['description'], 'test service v1')
        self.assertTrue('createdTime' in data)
        self.assertTrue('lastModifiedTime' in data)
        v1 = data['versionId']

        with self.assertRaises(fc2.FcError):
            self.client.publish_version(self._test_service_name, "test service v2")

        with self.assertRaises(fc2.FcError):
            self.client.delete_service(self._test_service_name)

        self.client.delete_version(self._test_service_name, v1)

        data = self.client.list_versions(self._test_service_name, limit = 2).data
        versions = data['versions']
        self.assertEqual(len(versions), 0)

        for i in range(6):
            desc = 'service description' + str(i)
            service = self.client.update_service(self._test_service_name, desc)
            self.assertEqual(service.data['description'], desc)
            version = str(i+2)
            r = self.client.publish_version(self._test_service_name, "test service v" + version)
            data = r.data
            self.assertEqual(data['versionId'], version)
            self.assertEqual(data['description'], "test service v" + version)
            self.assertTrue('createdTime' in data)
            self.assertTrue('lastModifiedTime' in data)

        data = self.client.list_versions(self._test_service_name, limit = 2).data
        versions = data['versions']
        nextToken = data['nextToken']
        self.assertEqual(len(versions), 2)
        for i in range(2):
            data = versions[i]
            self.assertTrue('versionId' in data)
            self.assertTrue('description' in data)
            self.assertTrue('createdTime' in data)
            self.assertTrue('lastModifiedTime' in data)

        self.assertTrue(nextToken != None)
        versions_len = 2
        while nextToken:
            data = self.client.list_versions(self._test_service_name, nextToken = nextToken).data
            versions = data['versions']
            nextToken = data.get('nextToken')
            versions_len += len(versions)

        self.assertEqual(versions_len, 6)

    def test_alias(self):
        r = self.client.publish_version(self._test_service_name, "test service v1")
        data = r.data
        v1 = data['versionId']
        r_data = self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9}).data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)
        self.assertEqual(r_data['description'], "test alias")
        self.assertEqual(r_data['additionalVersionWeight'], {"1": 0.9})
        self.assertTrue('createdTime' in data)
        self.assertTrue('lastModifiedTime' in data)

        r_data = self.client.get_alias(self._test_service_name, "test").data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)
        self.assertEqual(r_data['description'], "test alias")
        self.assertEqual(r_data['additionalVersionWeight'], {"1": 0.9})
        self.assertTrue('createdTime' in data)
        self.assertTrue('lastModifiedTime' in data)


        r_data = self.client.update_alias(self._test_service_name, "test", v1, "test alias_update", {"1": 0.8}).data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)
        self.assertEqual(r_data['description'], "test alias_update")
        self.assertEqual(r_data['additionalVersionWeight'], {"1": 0.8})
        self.assertTrue('createdTime' in data)
        self.assertTrue('lastModifiedTime' in data)

        self.client.delete_alias(self._test_service_name, "test")
        with self.assertRaises(fc2.FcError):
            self.client.get_alias(self._test_service_name, "test").data


        for i in range(6):
            desc = 'service description' + str(i)
            service = self.client.update_service(self._test_service_name, desc)
            self.assertEqual(service.data['description'], desc)
            version = str(i+2)
            self.client.publish_version(self._test_service_name, "test service v" + version)
            self.client.create_alias(self._test_service_name, "test" + str(version), v1, "test alias" + str(version), {"1": 0.9})

        data = self.client.list_aliases(self._test_service_name, limit = 2).data
        aliases = data['aliases']
        nextToken = data['nextToken']
        self.assertEqual(len(aliases), 2)
        for i in range(2):
            data = aliases[i]
            self.assertTrue('aliasName' in data)
            self.assertTrue('versionId' in data)
            self.assertTrue('description' in data)
            self.assertTrue('createdTime' in data)
            self.assertTrue('lastModifiedTime' in data)

        self.assertTrue(nextToken != None)
        aliases_len = 2
        while nextToken:
            data = self.client.list_aliases(self._test_service_name, nextToken = nextToken).data
            aliases = data['aliases']
            nextToken = data.get('nextToken')
            aliases_len += len(aliases)

        self.assertEqual(aliases_len, 6)

    def test_get_service(self):
        r = self.client.publish_version(self._test_service_name, "test service v1 desc")
        data = r.data
        v1 = data['versionId']

        service = self.client.get_service(self._test_service_name, v1, headers={'x-fc-trace-id': str(uuid.uuid4())}).data
        self.assertEqual(service['serviceName'], self._test_service_name)
        self.assertEqual(service['description'], "test service v1 desc")

        service = self.client.get_service(self._test_service_name).data
        self.assertEqual(service['serviceName'], self._test_service_name)
        self.assertEqual(service['description'], u"这是测试service")

        self.client.update_service(self._test_service_name, "update test service v2 desc")
        r = self.client.publish_version(self._test_service_name, "test service v2 desc")
        data = r.data
        v2 = data['versionId']

        service = self.client.get_service(self._test_service_name, v2).data
        self.assertEqual(service['serviceName'], self._test_service_name)
        self.assertEqual(service['description'], "test service v2 desc")

        service = self.client.get_service(self._test_service_name).data
        self.assertEqual(service['serviceName'], self._test_service_name)
        self.assertEqual(service['description'], "update test service v2 desc")

        self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9}).data
        service = self.client.get_service(self._test_service_name, "test").data
        self.assertEqual(service['serviceName'], self._test_service_name)
        self.assertEqual(service['description'], "test service v1 desc")


    def test_get_function(self):
        functionName= 'test_function_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        function = self.client.create_function(
            self._test_service_name, functionName,
            handler='main.my_handler', runtime='python2.7', 
            codeDir='test/hello_world', description=desc, environmentVariables={'testKey': 'testValue'})

        function = function.data
        self.assertEqual(function['environmentVariables']['testKey'], 'testValue')
        checksum = function['codeChecksum']
        self.check_function(functionName, desc, checksum)

        r = self.client.publish_version(self._test_service_name, "test service v1 desc")
        data = r.data
        v1 = data['versionId']
        self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9})

        self.check_function(functionName, desc, checksum, v1)
        self.check_function(functionName, desc, checksum, "test")

        function = self.client.update_function(self._test_service_name, functionName, 
            codeZipFile='test/hello_world/hello_world.zip', description="update function desc", environmentVariables={'newTestKey':'newTestValue'})
        function = function.data
        self.assertEqual(function['description'], "update function desc")

        self.assertEqual(function['environmentVariables']['newTestKey'], 'newTestValue')
        checksum2 = function['codeChecksum']
        self.assertNotEqual(checksum, checksum2)
        self.check_function(functionName, "update function desc", checksum2)

        r = self.client.publish_version(self._test_service_name, "test service v2 desc")
        data = r.data
        v2 = data['versionId']
        self.client.create_alias(self._test_service_name, "prod", v2, "test alias", {"1": 0.8})

        self.check_function(functionName, "update function desc", checksum2, v2)
        self.check_function(functionName, "update function desc", checksum2, "prod")


    def check_function(self, functionName, desc, checksum, qualifier = None,  runtime = 'python2.7'):
        function = self.client.get_function(self._test_service_name, functionName, qualifier)
        function = function.data
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], runtime)
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)

        code = self.client.get_function_code(self._test_service_name, functionName, qualifier)
        code = code.data
        self.assertEqual(code['checksum'], checksum)
        self.assertTrue(code['url'] != '')


    def test_list_functions(self):
        prefix = 'test_list_'
        runtime = 'python2.7'

        self.client.create_function(
            self._test_service_name, prefix + 'abc',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self._test_service_name, prefix + 'abd',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self._test_service_name, prefix + 'ade',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')

        r = self.client.publish_version(self._test_service_name, "test service v1 desc")
        data = r.data
        v1 = data['versionId']
        self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9})


        self.client.create_function(
            self._test_service_name, prefix + 'bcd',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self._test_service_name, prefix + 'bde',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self._test_service_name, prefix + 'zzz',
            handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')

        r = self.client.publish_version(self._test_service_name, "test service v2 desc")
        data = r.data
        v2 = data['versionId']
        self.client.create_alias(self._test_service_name, "prod", v2, "test alias", {"1": 0.8})

        r = self.client.list_functions(self._test_service_name).data
        functions = r['functions']
        self.assertEqual(len(functions), 6)
        functions = r['functions']

        r1 = self.client.list_functions(self._test_service_name, qualifier="test").data
        r2 = self.client.list_functions(self._test_service_name, qualifier=v1).data
        self.assertEqual(r1, r2)
        functions = r1['functions']
        self.assertEqual(len(functions), 3)

        r3 = self.client.list_functions(self._test_service_name, qualifier="prod").data
        r4 = self.client.list_functions(self._test_service_name, qualifier=v2).data
        self.assertEqual(r3, r4)
        functions = r3['functions']
        self.assertEqual(len(functions), 6)

    def test_invoke_function(self):
        functionName= 'test_function_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        self.client.create_function(
            self._test_service_name, functionName,
            handler='main.my_handler', runtime='python2.7', 
            codeDir='test/hello_world', description=desc)

        r = self.client.publish_version(self._test_service_name, "test service v1 desc")
        data = r.data
        v1 = data['versionId']
        self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9})

        self.client.update_function(self._test_service_name, functionName, 
             handler='a.my_handler', runtime='python2.7', 
            codeDir='test/hello_world', description="update function desc")
       
        r = self.client.publish_version(self._test_service_name, "test service v2 desc")
        data = r.data
        v2 = data['versionId']
        self.client.create_alias(self._test_service_name, "prod", v2, "test alias", {"1": 0.8})


        r = self.client.invoke_function(self._test_service_name, functionName)
        self.assertEqual(r.data.decode('utf-8'), 'new hello world')

        # r = self.client.invoke_function(self._test_service_name, functionName, v1)
        # self.assertEqual(r.data.decode('utf-8'), 'hello world')

        # r = self.client.invoke_function(self._test_service_name, functionName, "test")
        # self.assertEqual(r.data.decode('utf-8'), 'hello world')


        # r = self.client.invoke_function(self._test_service_name, functionName, v2)
        # self.assertEqual(r.data.decode('utf-8'), 'new hello world')

        # r = self.client.invoke_function(self._test_service_name, functionName, "prod")
        # self.assertEqual(r.data.decode('utf-8'), 'new hello world')

    def test_trigger(self):
        # use oss trigger as example
        functionName= 'test_function_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        self.client.create_function(
            self._test_service_name, functionName,
            handler='main.my_handler', runtime='python2.7', 
            codeDir='test/hello_world', description=desc)

        r = self.client.publish_version(self._test_service_name, "test service v1 desc")
        data = r.data
        v1 = data['versionId']
        self.client.create_alias(self._test_service_name, "test", v1, "test alias", {"1": 0.9})

        trigger_type = 'oss'
        trigger_name = "test-oss-trigger"
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

        logging.info('create trigger: {0}'.format(trigger_name))
        create_trigger_resp = self.client.create_trigger(self._test_service_name, functionName, trigger_name, trigger_type,
                                                         trigger_config, source_arn, invocation_role, qualifier=v1).data
        self.check_trigger_response(create_trigger_resp, trigger_name, trigger_type, trigger_config, source_arn,
                                    invocation_role, v1)
        
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

        update_trigger_resp = self.client.update_trigger(self._test_service_name, functionName, trigger_name, v1, 
                                                         trigger_config_update, invocation_role).data

        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update, source_arn,
                                    invocation_role, v1)

        update_trigger_resp = self.client.update_trigger(self._test_service_name, functionName, trigger_name, "test", 
                                                         trigger_config_update, invocation_role).data

        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update, source_arn,
                                    invocation_role, "test")

        self.client.update_function(self._test_service_name, functionName, 
            codeZipFile='test/hello_world/hello_world.zip', description="update function desc")

        r = self.client.publish_version(self._test_service_name, "test service v2 desc")
        data = r.data
        v2 = data['versionId']
        self.client.create_alias(self._test_service_name, "prod", v2, "test alias", {"1": 0.8})

        update_trigger_resp = self.client.update_trigger(self._test_service_name, functionName, trigger_name, v2, 
                                                         trigger_config_update, invocation_role).data

        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update, source_arn,
                                    invocation_role, v2)


        update_trigger_resp = self.client.update_trigger(self._test_service_name, functionName, trigger_name, "prod", 
                                                         trigger_config_update, invocation_role).data

        self.check_trigger_response(update_trigger_resp, trigger_name, trigger_type, trigger_config_update, source_arn,
                                    invocation_role, "prod")
        

    def check_trigger_response(self, resp, trigger_name, trigger_type, trigger_config, source_arn, invocation_role, qualifier):
        self.assertEqual(resp['qualifier'], qualifier)
        self.assertEqual(resp['triggerName'], trigger_name)
        self.assertEqual(resp['triggerType'], trigger_type)
        self.assertEqual(resp['sourceArn'], source_arn)
        self.assertEqual(resp['invocationRole'], invocation_role)
        self.assertTrue('createdTime' in resp)
        self.assertTrue('lastModifiedTime' in resp)
        self.assertEqual(resp['triggerConfig'], trigger_config)

if __name__ == '__main__':
    unittest.main()
