import unittest
import os
import fc2
import random
import string

class TestAsyncConfig(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestAsyncConfig, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']
        self.region = os.environ['REGION']
        self.account_id = os.environ['ACCOUNT_ID']
        self.ramRole = os.environ['INVOCATION_ROLE_SLS']

        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )
        self.prefix = "test-async-config-" + ''.join(random.choice(
            string.ascii_lowercase) for _ in range(8))

    def setUp(self):
        pass

    def tearDown(self):
        # clear all functions and triggers
        service_name = self.prefix
        function_name = self.prefix
        self.client.delete_function(service_name, function_name)

        # clear all versions and alias
        data = self.client.list_versions(service_name).data
        versions = data['versions']
        nextToken = data.get('nextToken')
        while nextToken:
            data = self.client.list_versions(
                service_name, nextToken=nextToken).data
            versions.extend(data['versions'])
            nextToken = data.get('nextToken')

        for v in versions:
            self.client.delete_version(service_name, v['versionId'])

        data = self.client.list_aliases(service_name).data
        aliases = data['aliases']
        nextToken = data.get('nextToken')
        while nextToken:
            data = self.client.list_aliases(
                service_name, nextToken=nextToken).data
            aliases.extend(data['aliases'])
            nextToken = data.get('nextToken')

        for a in aliases:
            self.client.delete_alias(service_name, a['aliasName'])

        self.client.delete_service(service_name)

    def test_async_config(self):
        serviceName = self.prefix
        functionName = self.prefix
        self.client.create_service(serviceName, role=self.ramRole)
        self.client.create_function(
            serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')
        
        r = self.client.publish_version(
            serviceName, "test service v1")
        data = r.data
        v1 = data['versionId']
        r_data = self.client.create_alias(
            serviceName, "test", v1, "test alias").data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)

        destination = 'acs:fc:{0}:{1}:services/{2}.{3}/functions/{4}'.format(
            self.region, self.account_id, serviceName, "test", functionName+"_new")

        asyncConfig = {
          "DestinationConfig": {
                "OnSuccess": {
                  "Destination": destination,
                },
                "OnFailure": {
                  "Destination": destination
                }
          },
          "MaxAsyncEventAgeInSeconds": 100,
          "MaxAsyncRetryAttempts": 1
        }
        config = self.client.put_function_async_invoke_config(serviceName, "test", functionName, asyncConfig).data
        self.assertEqual(config['service'], serviceName)
        self.assertEqual(config['qualifier'], "test")
        self.assertTrue('createdTime' in config)
        self.assertTrue('lastModifiedTime' in config)
        self.assertEqual(config['function'], functionName)
        self.assertEqual(config['destinationConfig']['onSuccess']['destination'], asyncConfig['DestinationConfig']['OnSuccess']['Destination'])
        self.assertEqual(config['maxAsyncEventAgeInSeconds'], asyncConfig['MaxAsyncEventAgeInSeconds'])
        self.assertEqual(config['maxAsyncRetryAttempts'], asyncConfig['MaxAsyncRetryAttempts'])

        getConfig = self.client.get_function_async_invoke_config(serviceName, "test", functionName).data
        self.assertEqual(getConfig['service'], serviceName)
        self.assertEqual(getConfig['qualifier'], "test")
        self.assertTrue('createdTime' in getConfig)
        self.assertTrue('lastModifiedTime' in getConfig)
        self.assertEqual(getConfig['function'], functionName)
        self.assertEqual(getConfig['destinationConfig']['onSuccess']['destination'],
                         asyncConfig['DestinationConfig']['OnSuccess']['Destination'])
        self.assertEqual(getConfig['maxAsyncEventAgeInSeconds'], asyncConfig['MaxAsyncEventAgeInSeconds'])
        self.assertEqual(getConfig['maxAsyncRetryAttempts'], asyncConfig['MaxAsyncRetryAttempts'])
        
        listConfigs = self.client.list_function_async_invoke_configs(serviceName, functionName).data
        self.assertEqual(len(listConfigs['configs']), 1)
        self.assertEqual(listConfigs['nextToken'], "")
        
        r = self.client.delete_function_async_invoke_config(serviceName, "test", functionName)
