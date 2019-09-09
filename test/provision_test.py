import unittest
import os
import fc2
import logging
import random
import string


class TestProvisonConfig(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestProvisonConfig, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']
        self.region = os.environ['REGION']
        self.account_id = os.environ['ACCOUNT_ID']

        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )
        self.prefix = "test-provision-config-" + ''.join(random.choice(
            string.ascii_lowercase) for _ in range(8))

    def setUp(self):
        pass

    def tearDown(self):
        # clear all functions and triggers
        service_name = self.prefix
        function_name = self.prefix
        self.client.put_provision_config(
            service_name, "test", service_name, 0)
        self.client.put_provision_config(
            service_name, "test", service_name+"2", 0)
        self.client.delete_function(service_name, function_name)
        self.client.delete_function(service_name, function_name + "2")
        
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

    def test_provision(self):
        serviceName = self.prefix
        functionName = self.prefix
        self.client.create_service(serviceName)
        self.client.create_function(
            serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')
        
        self.client.create_function(
            serviceName, functionName + "2",
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')
        
        r = self.client.publish_version(
            serviceName, "test service v1")
        data = r.data
        v1 = data['versionId']
        r_data = self.client.create_alias(
            serviceName, "test", v1, "test alias").data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)
        
        r = self.client.put_provision_config(serviceName, "test", functionName, 10).data
        self.assertEqual(10, r['target'])
        self.assertEqual(
            "{}#{}#{}#{}".format(self.account_id, serviceName, "test", functionName), r['resource'])
        
        r = self.client.put_provision_config(
            serviceName, "test", functionName + "2", 5).data
        self.assertEqual(5, r['target'])
        self.assertEqual(
            "{}#{}#{}#{}".format(self.account_id, serviceName, "test", functionName + "2"), r['resource'])
        

        r = self.client.get_provision_config(serviceName, "test", functionName).data
        self.assertEqual(10, r['target'])
        self.assertTrue(r['current']>=0)
        self.assertEqual(
            "{}#{}#{}#{}".format(self.account_id, serviceName, "test", functionName), r['resource'])
        
        r = self.client.list_provision_configs(serviceName, "test").data
        self.assertEqual(2, len(r["provisionConfigs"]))
        self.assertTrue("nextToken" not in r)
        
        r = self.client.list_provision_configs(
            serviceName, "test", limit=1).data
        self.assertEqual(1, len(r["provisionConfigs"]))
        self.assertTrue("nextToken" in r)
