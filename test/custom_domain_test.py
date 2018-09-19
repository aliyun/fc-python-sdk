import unittest
import os
import fc2
import logging


class TestCustomDomain(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestCustomDomain, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']
        self.domain_name = 'pythonSDK.cn-hongkong.1221968287646227.cname-test.fc.aliyun-inc.com'

        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )

    def setUp(self):
        try:
            self.client.delete_custom_domain(self.domain_name)
        except:
            pass

    def tearDown(self):
        try:
            self.client.delete_custom_domain(self.domain_name)
        except:
            pass

    def test_custom_domain(self):
        domain_name = self.domain_name

        # test create_custom_domain
        # 200
        logging.info('create custom domain: {0}'.format(domain_name))
        create_custom_domain_resp = self.client.create_custom_domain(domain_name).data
        self.check_custom_domain_response(create_custom_domain_resp, domain_name)

        # 400
        with self.assertRaises(fc2.FcError):
            self.client.create_custom_domain(domain_name)

        # test get_custom_domain

        # 200
        logging.info('get custom domain: {0}'.format(self.domain_name))
        get_custom_domain_resp = self.client.get_custom_domain(self.domain_name).data
        self.check_custom_domain_response(get_custom_domain_resp, self.domain_name)

        # test update_custom_domain
        routeConfig = {
            'routes': [
                {
                    'serviceName': 's1',
                    'functionName': 'f1',
                    'path': '/a',
                    'qualifier': None
                },
                {
                    'serviceName': 's2',
                    'functionName': 'f2',
                    'path': '/b',
                    'qualifier': None
                }
            ]
        }
        # 200
        logging.info('update custom domain: {0}'.format(self.domain_name))
        update_custom_domain_resp = self.client.update_custom_domain(self.domain_name, 'HTTP', routeConfig).data
        self.check_custom_domain_response(update_custom_domain_resp, self.domain_name, routeConfig)

        # test list_custom_domains
        # 200
        logging.info('list custom domains: {0}'.format(self.domain_name))
        list_custom_domains_resp = self.client.list_custom_domains(prefix='pythonSDK').data
        self.assertEqual(1, len(list_custom_domains_resp))

    def check_custom_domain_response(self, resp, domain_name, route_config=None):
        self.assertEqual(resp['domainName'], domain_name)
        self.assertTrue('createdTime' in resp)
        self.assertTrue('lastModifiedTime' in resp)
        if route_config:
            self.assertEqual(resp['routeConfig'], route_config)
