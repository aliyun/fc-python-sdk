import unittest
import os
import fc2

class TestReservedCapacity(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestReservedCapacity, self).__init__(*args, **kwargs)
        self.access_key_id = os.environ['ACCESS_KEY_ID']
        self.access_key_secret = os.environ['ACCESS_KEY_SECRET']
        self.endpoint = os.environ['ENDPOINT']
        self.client = fc2.Client(
            endpoint=self.endpoint,
            accessKeyID=self.access_key_id,
            accessKeySecret=self.access_key_secret,
        )

    def test_list_reserved_capacity(self):
        r = self.client.list_reserved_capacities(limit=5)
        r = r.data
        reserved_capacities = r['reservedCapacities']
        self.assertLessEqual(len(reserved_capacities), 5)
        
        for elem in reserved_capacities:
            self.assertEqual(len(elem['instanceId']), 22)
            self.assertGreater(elem['cu'], 0)
            self.assertGreater(elem['deadline'], elem['createdTime'])
            self.assertIsNotNone(elem['lastModifiedTime'])
            self.assertIsNotNone(elem['isRefunded'])
