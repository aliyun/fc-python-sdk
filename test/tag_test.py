import unittest
import os
import fc2
import logging

class TestTag(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestTag, self).__init__(*args, **kwargs)
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

    def test_all_tag_op(self):
        prefix = "test_tag_"
        for i in range(3):
            try:
                self.client.delete_service(prefix + str(i))
            except:
                pass
        
        for i in range(3):
            self.client.create_service(prefix + str(i))
            resourceArn = "acs:fc:{0}:{1}:services/{2}".format(self.region, self.account_id, prefix + str(i))
            self.client.tag_resource(resourceArn, { "k3": "v3"})
            if i % 2 == 0:
                self.client.tag_resource(resourceArn, {"k1": "v1"})
            else:
                self.client.tag_resource(resourceArn, {"k2": "v2"})
                
            resp = self.client.get_resource_tags(resourceArn).data
            self.assertEqual(resourceArn, resp['resourceArn'])
            if i % 2 == 0:
                self.assertEqual(resp['tags'], {"k1": "v1", "k3" : "v3"})
            else:
                self.assertEqual(resp['tags'], {"k2": "v2", "k3": "v3"})
                
            self.client.untag_resource(resourceArn, ["k3"])
            
            resp = self.client.get_resource_tags(resourceArn).data
            self.assertEqual(resourceArn, resp['resourceArn'])
            if i % 2 == 0:
                self.assertEqual(resp['tags'], {"k1": "v1"})
            else:
                self.assertEqual(resp['tags'], {"k2": "v2"})
                
            self.client.untag_resource(resourceArn, [], True)
            resp = self.client.get_resource_tags(resourceArn).data
            self.assertEqual(resourceArn, resp['resourceArn'])
            self.assertEqual(0, len(resp['tags']))
