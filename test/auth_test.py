# -*- coding: utf-8 -*-

import fc2
import unittest


class TestAuth(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestAuth, self).__init__(*args, **kwargs)

    def test_get_sign_resource(self):
        queries = {
            'key3': [],
            'key2': ['123'],
            'foo': 'bar',
            'key4-with /escaped~chars_here.ext':'value-with /escaped~chars_here.ext',
            'key1': ['xyz', 'abc'],
        }
        sign_resource = fc2.auth.Auth._get_sign_resource('/path/action with-escaped~chars_here.ext', queries)
        self.assertEqual(sign_resource, '/path/action with-escaped~chars_here.ext\nfoo=bar\nkey1=abc\nkey1=xyz\nkey2=123\nkey3\nkey4-with /escaped~chars_here.ext=value-with /escaped~chars_here.ext')

    def test_empty_queries(self):
        sign_resource = fc2.auth.Auth._get_sign_resource('/path/action with-escaped~chars_here.ext', {})
        self.assertEqual(sign_resource, '/path/action with-escaped~chars_here.ext\n')

    def test_error_type_queries(self):
        with self.assertRaises(TypeError):
            fc2.auth.Auth._get_sign_resource('/path/action with-escaped~chars_here.ext', False)

        with self.assertRaises(TypeError):
            sign_resource = fc2.auth.Auth._get_sign_resource('/path/action with-escaped~chars_here.ext', None)
            self.assertEqual(sign_resource, '/path/action with-escaped~chars_here.ext')

if __name__ == '__main__':
    unittest.main()
