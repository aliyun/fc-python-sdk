# -*- coding: utf-8 -*-

import logging
import os
import random
import string
import unittest
import uuid

import fc2


class TestService(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestService, self).__init__(*args, **kwargs)
        self.vpcId = os.environ['VPC_ID']
        self.vSwitchIds = os.environ['VSWITCH_IDS']
        self.securityGroupId = os.environ['SECURITY_GROUP_ID']
        self.vpcRole = os.environ['VPC_ROLE']
        self.userId = os.environ['USER_ID']
        self.groupId = os.environ['GROUP_ID']
        self.nasServerAddr = os.environ['NAS_SERVER_ADDR']
        self.nasMountDir = os.environ['NAS_MOUNT_DIR']
        self.client = fc2.Client(
            endpoint=os.environ['ENDPOINT'],
            accessKeyID=os.environ['ACCESS_KEY_ID'],
            accessKeySecret=os.environ['ACCESS_KEY_SECRET'],
        )

    def test_create(self):
        name = 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
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

        service = self.client.get_service(name, headers={'x-fc-trace-id': str(uuid.uuid4())})
        service = service.data
        self.assertEqual(service['serviceName'], name)
        self.assertEqual(service['description'], desc)

        # expect the delete service failed because of invalid etag.
        with self.assertRaises(fc2.FcError):
            self.client.delete_service(name, headers={'if-match': 'invalid etag'})

        # now success with valid etag.
        self.client.delete_service(name, headers={'if-match': etag})

        # TODO: test create with logConfig and role.

    def test_update(self):
        name = 'test_update_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('Create service: {0}'.format(name))
        self.client.create_service(name)

        desc = 'service description'
        service = self.client.update_service(name, desc)
        self.assertEqual(service.data['description'], desc)
        etag = service.headers['etag']

        # TODO: test create with logConfig and role.

        # expect the delete service failed because of invalid etag.
        with self.assertRaises(fc2.FcError):
            self.client.update_service(name, description='invalid', headers={'if-match': 'invalid etag'})

        self.assertEqual(service.data['description'], desc)

        self.client.delete_service(name)

    def test_vpcConfig(self):
        name = 'test_vpcConfig'
        try:
            self.client.delete_service(name)
        except:
            pass
        vpcConfig = {
            'vpcId': self.vpcId,
            'vSwitchIds': [self.vSwitchIds],
            'securityGroupId': self.securityGroupId
        }

        # create vpcConfig when creating the service
        logging.info('Create service: {0}'.format(name))
        service = self.client.create_service(name, role=self.vpcRole, vpcConfig=vpcConfig)
        service = service.data
        self.assertEqual(service['serviceName'], name)
        self.assertTrue('createdTime' in service)
        self.assertTrue('lastModifiedTime' in service)
        self.assertTrue('logConfig' in service)
        self.assertTrue('role' in service)
        self.assertTrue('serviceId' in service)
        self.assertEqual(service['internetAccess'], True)
        self.assertEqual(service['vpcConfig']['vpcId'], self.vpcId)
        self.assertEqual(service['vpcConfig']['vSwitchIds'], [self.vSwitchIds])
        self.assertEqual(service['vpcConfig']['securityGroupId'], self.securityGroupId)

        # update service
        service = self.client.update_service(name, internetAccess=False).data
        self.assertEqual(service['internetAccess'], False)
        self.client.delete_service(name)

        # create vpcConfig for an existing service
        service = self.client.create_service(name).data
        self.assertEqual(service['internetAccess'], True)
        service = self.client.update_service(name, role=self.vpcRole, vpcConfig=vpcConfig).data
        self.assertEqual(service['internetAccess'], True)
        self.assertEqual(service['vpcConfig']['vpcId'], self.vpcId)
        self.assertEqual(service['vpcConfig']['vSwitchIds'], [self.vSwitchIds])
        self.assertEqual(service['vpcConfig']['securityGroupId'], self.securityGroupId)

    def test_nasConfig(self):
        name = 'test_nasConfig'
        try:
            self.client.delete_service(name)
        except:
            pass
        vpcConfig = {
            'vpcId': self.vpcId,
            'vSwitchIds': [self.vSwitchIds],
            'securityGroupId': self.securityGroupId
        }
        nasConfig = {
            "userId": int(self.userId),
            "groupId": int(self.groupId),
            "mountPoints": [
                {
                    "serverAddr": self.nasServerAddr,
                    "mountDir": self.nasMountDir
                }
            ]
        }

        # create vpcConfig when creating the service
        logging.info('Create service: {0}'.format(name))
        service = self.client.create_service(name, role=self.vpcRole, vpcConfig=vpcConfig, nasConfig=nasConfig)
        service = service.data
        self.assertEqual(service['serviceName'], name)
        self.assertTrue('createdTime' in service)
        self.assertTrue('lastModifiedTime' in service)
        self.assertTrue('logConfig' in service)
        self.assertTrue('role' in service)
        self.assertTrue('serviceId' in service)
        self.assertEqual(service['internetAccess'], True)
        self.assertEqual(service['vpcConfig']['vpcId'], self.vpcId)
        self.assertEqual(service['vpcConfig']['vSwitchIds'], [self.vSwitchIds])
        self.assertEqual(service['vpcConfig']['securityGroupId'], self.securityGroupId)
        logging.info('Create service reply: {0}'.format(service))
        self.assertEqual(service['nasConfig']['userId'], int(self.userId))
        self.assertEqual(service['nasConfig']['groupId'], int(self.groupId))
        self.assertEqual(service['nasConfig']['mountPoints'][0]["serverAddr"], self.nasServerAddr)
        self.assertEqual(service['nasConfig']['mountPoints'][0]["mountDir"], self.nasMountDir)

        # update service
        nasConfig = {
            "userId": -1,
            "groupId": -1,
            "mountPoints": [
                {
                    "serverAddr": self.nasServerAddr,
                    "mountDir": self.nasMountDir
                }
            ]
        }
        service = self.client.update_service(name, nasConfig=nasConfig).data
        self.assertEqual(service['nasConfig']['userId'], -1)
        self.assertEqual(service['nasConfig']['groupId'], -1)
        self.client.delete_service(name)

    def _clear_list_service(self):
        # Use the prefix to isolate the services.
        prefix = 'test_list_'
        # Cleanup the resources.
        try:
            self.client.delete_service(prefix + 'abc')
        except:
            pass
        try:
            self.client.delete_service(prefix + 'abd')
        except:
            pass
        try:
            self.client.delete_service(prefix + 'ade')
        except:
            pass
        try:
            self.client.delete_service(prefix + 'bcd')
        except:
            pass
        try:
            self.client.delete_service(prefix + 'bde')
        except:
            pass
        try:
            self.client.delete_service(prefix + 'zzz')
        except:
            pass

    def test_list(self):
        self._clear_list_service()
        prefix = 'test_list_'
        self.client.create_service(prefix + 'abc')
        self.client.create_service(prefix + 'abd')
        self.client.create_service(prefix + 'ade')
        self.client.create_service(prefix + 'bcd')
        self.client.create_service(prefix + 'bde')
        self.client.create_service(prefix + 'zzz')

        r = self.client.list_services(limit=2, startKey=prefix + 'b')
        r = r.data
        services = r['services']
        nextToken = r['nextToken']
        self.assertEqual(len(services), 2)
        self.assertTrue(services[0]['serviceName'], prefix + 'bcd')
        self.assertTrue(services[1]['serviceName'], prefix + 'bde')

        r = self.client.list_services(limit=1, startKey=prefix + 'b', nextToken=nextToken)
        r = r.data
        services = r['services']
        self.assertEqual(len(services), 1)
        self.assertTrue(services[0]['serviceName'], prefix + 'zzz')

        # It's ok to omit the startKey and only provide continuationToken.
        # As long as the continuationToken is provided, the startKey is not considered.
        r = self.client.list_services(limit=1, nextToken=nextToken)
        r = r.data
        services = r['services']
        self.assertEqual(len(services), 1)
        self.assertTrue(services[0]['serviceName'], prefix + 'zzz')

        # If continuationToken is provided, along with a prefix, then the prefix is considered.
        r = self.client.list_services(limit=2, prefix=prefix + 'x', nextToken=nextToken)
        r = r.data
        services = r['services']
        self.assertEqual(len(services), 0)

        r = self.client.list_services(limit=2, prefix=prefix + 'a')
        r = r.data
        services = r['services']
        self.assertEqual(len(services), 2)
        self.assertTrue(services[0]['serviceName'], prefix + 'abc')
        self.assertTrue(services[1]['serviceName'], prefix + 'abd')

        # list services with prefix and startKey
        r = self.client.list_services(limit=2, prefix=prefix + 'ab', startKey=prefix + 'abd')
        r = r.data
        services = r['services']
        self.assertEqual(len(services), 1)
        self.assertTrue(services[0]['serviceName'], prefix + 'abd')
        self._clear_list_service()


if __name__ == '__main__':
    unittest.main()
