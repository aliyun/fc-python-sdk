# -*- coding: utf-8 -*-

import fc2
import unittest


class TestRdsEventProto(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestRdsEventProto, self).__init__(*args, **kwargs)

    def test_rds_event_proto(self):
        target = fc2.rdsEvent_pb2.Message()
        with open('./test/proto.bin', 'rb') as f:
            bin_data = f.read()
            target.ParseFromString(bin_data)
            self.assertEqual(target.offset, 10000)
            self.assertEqual(target.db_type, 0)
            entry = target.entries[0]
            self.assertEqual(entry.operation, 4)
            self.assertEqual(entry.db_name, "test-db")
            self.assertEqual(entry.table_name, "test-table")
            self.assertEqual(entry.row[0].name, "id")
            self.assertEqual(entry.row[1].value, b"YWxpeXUgZmM=")
            self.assertEqual(entry.row[2].type_num, 4)

if __name__ == '__main__':
    unittest.main()
