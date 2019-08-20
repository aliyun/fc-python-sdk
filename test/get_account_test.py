import unittest
import os
import fc2
import logging



class TestGetAccountSetting(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestGetAccountSetting, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']

        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )

    def test_get_account_setting(self):
        resp = self.client.get_account_settings().data
        self.assertEqual(resp['availableAZs'], [u'cn-hongkong-c'])


