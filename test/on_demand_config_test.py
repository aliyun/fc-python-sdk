import unittest
import os
import fc2
import re
import logging
import random
import string


class TestOnDemandConfig(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestOnDemandConfig, self).__init__(*args, **kwargs)
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
        self.service_name = "test-on-demand-config-" + ''.join(random.choice(
            string.ascii_lowercase) for _ in range(8))
        self.func_name1 = self.service_name + "_f1"
        self.func_name2 = self.service_name + "_f2"
        self.alias_name = "test"

    def setUp(self):
        service_name = self.service_name
        self.client.create_service(service_name)
        self.client.create_function(
            service_name, self.func_name1,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')

        self.client.create_function(
            service_name, self.func_name2,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')

        r = self.client.publish_version(
            service_name, "test service v1")
        data = r.data
        v1 = data['versionId']
        r_data = self.client.create_alias(
            service_name, self.alias_name, v1, "test alias").data
        self.assertEqual(r_data['aliasName'], "test")
        self.assertEqual(r_data['versionId'], v1)

    def tearDown(self):
        # clear all functions and triggers
        service_name = self.service_name

        r = re.compile('services/([a-zA-Z0-9_\-]+).([a-zA-Z0-9_\-]+)/functions/([a-zA-Z0-9_\-]+)$')

        # clear all configs of this account
        nextToken = ''
        while True:
            list_ret = self.client.list_on_demand_config(nextToken=nextToken).data
            nextToken = list_ret.get('nextToken', '')

            configs = list_ret.get('configs', [])
            if len(configs) < 1:
                break

            for conf in configs:
                resource = conf['resource']
                service_to_rm, alias_to_rm, func_to_rm = r.match(resource).groups()

                self.client.delete_on_demand_config(
                    service_to_rm, alias_to_rm, func_to_rm)

            if nextToken == '':
                break

        self.client.delete_function(service_name, self.func_name1)
        self.client.delete_function(service_name, self.func_name2)

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

    def test_on_demand_config(self):
        service_name = self.service_name
        list_ret = self.client.list_on_demand_config().data
        self.assertEqual(list_ret.get("nextToken", None), None)
        self.assertEqual(list_ret.get("configs"), None)

        self.client.put_on_demand_config(service_name, self.alias_name, self.func_name1, 1)
        get_ret = self.client.get_on_demand_config(service_name, self.alias_name, self.func_name1).data
        self.assertEqual(get_ret["maximumInstanceCount"], 1)
        self.assertEqual(get_ret["resource"], "services/%s.%s/functions/%s" % (service_name, self.alias_name, self.func_name1))

        list_ret = self.client.list_on_demand_config().data
        self.assertEqual(list_ret.get("nextToken", None), None)
        self.assertEqual(len(list_ret["configs"]), 1)

        self.client.put_on_demand_config(service_name, self.alias_name, self.func_name2, 2)
        get_ret = self.client.get_on_demand_config(service_name, self.alias_name, self.func_name2).data
        self.assertEqual(get_ret["maximumInstanceCount"], 2)
        self.assertEqual(get_ret["resource"], "services/%s.%s/functions/%s" % (service_name, self.alias_name, self.func_name2))

        list_ret1 = self.client.list_on_demand_config(limit=1).data
        self.assertEqual(len(list_ret1["configs"]), 1)
        self.assertNotEqual(list_ret1.get("nextToken", None), None)
        list_ret2 = self.client.list_on_demand_config(nextToken=list_ret1["nextToken"]).data
        self.assertEqual(len(list_ret2["configs"]), 1)
        self.assertEqual(list_ret2.get("nextToken"), None)

        # after delete one config, only one left
        self.client.delete_on_demand_config(service_name, self.alias_name, self.func_name2)
        list_ret = self.client.list_on_demand_config(limit=2).data
        self.assertEqual(len(list_ret["configs"]), 1)
        self.assertEqual(list_ret.get("nextToken", None), None)

if __name__ == '__main__':
    unittest.main()
