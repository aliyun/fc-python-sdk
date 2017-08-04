# -*- coding: utf-8 -*-

import fc
import logging
import random
import requests
import string
import unittest
import uuid
import imghdr
import os


class TestFunction(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestFunction, self).__init__(*args, **kwargs)
        self.client = fc.Client(
            endpoint=os.environ['ENDPOINT'],
            accessKeyID=os.environ['ACCESS_KEY_ID'],
            accessKeySecret=os.environ['ACCESS_KEY_SECRET'],
        )
        serviceName = 'TestFunction_service_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        self.serviceName = serviceName
        self.client.create_service(self.serviceName)
        logging.info("create service: {0}".format(self.serviceName))

    def test_create(self):
        functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        function = self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world', description=desc)
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], 'python2.7')
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)
        self.assertTrue('codeChecksum' in function)
        self.assertTrue('codeSize' in function)
        self.assertTrue('createdTime' in function)
        self.assertTrue('lastModifiedTime' in function)
        self.assertTrue('functionId' in function)
        self.assertTrue('memorySize' in function)
        self.assertTrue('timeout' in function)
        etag = function['etag']
        checksum = function['codeChecksum']
        self.assertNotEqual(etag, '')

        function = self.client.get_function(self.serviceName, functionName, traceId=str(uuid.uuid4()))
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], 'python2.7')
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)

        code = self.client.get_function_code(self.serviceName, functionName)
        self.assertEqual(code['checksum'], checksum)
        self.assertTrue(code['url'] != '')

        # expect the delete function  failed because of invalid etag.
        with self.assertRaises(requests.HTTPError):
            self.client.delete_function(self.serviceName, functionName, etag='invalid etag')
        # now success with valid etag.
        self.client.delete_function(self.serviceName, functionName, etag=etag)

        # can not get the deleted function.
        with self.assertRaises(requests.HTTPError):
            self.client.get_function(self.serviceName, functionName)

        # TODO: test create with oss object code.

    def test_update(self):
        functionName = 'test_update_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('Create function: {0}'.format(functionName))
        self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world')

        desc = 'function description'
        func = self.client.update_function(self.serviceName, functionName, description=desc)
        self.assertEqual(func['description'], desc)
        etag = func['etag']

        # expect the delete service failed because of invalid etag.
        with self.assertRaises(requests.HTTPError):
            self.client.update_function(self.serviceName, functionName, description='invalid', etag='invalid etag')
        self.assertEqual(func['description'], desc)

        self.client.delete_function(self.serviceName, functionName)

    def test_list(self):
        # Use the prefix to isolate the services.
        prefix = 'test_list_'
        # Cleanup the resources.
        try:
            self.client.delete_function(self.serviceName, prefix + 'abc')
        except:
            pass
        try:
            self.client.delete_function(self.serviceName, prefix + 'abd')
        except:
            pass
        try:
            self.client.delete_function(self.serviceName, prefix + 'ade')
        except:
            pass
        try:
            self.client.delete_function(self.serviceName, prefix + 'bcd')
        except:
            pass
        try:
            self.client.delete_function(self.serviceName, prefix + 'bde')
        except:
            pass
        try:
            self.client.delete_function(self.serviceName, prefix + 'zzz')
        except:
            pass

        self.client.create_function(
            self.serviceName, prefix + 'abc',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self.serviceName, prefix + 'abd',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self.serviceName, prefix + 'ade',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self.serviceName, prefix + 'bcd',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self.serviceName, prefix + 'bde',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        self.client.create_function(
            self.serviceName, prefix + 'zzz',
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')

        r = self.client.list_functions(self.serviceName, limit=2, startKey=prefix + 'b')
        functions = r['functions']
        nextToken = r['nextToken']
        self.assertEqual(len(functions), 2)
        functions = r['functions']
        self.assertTrue(functions[0]['functionName'], prefix + 'bcd')
        self.assertTrue(functions[1]['functionName'], prefix + 'bde')

        r = self.client.list_functions(self.serviceName, limit=1, startKey=prefix + 'b', nextToken=nextToken)
        functions = r['functions']
        self.assertEqual(len(functions), 1)
        self.assertTrue(functions[0]['functionName'], prefix + 'zzz')

        # It's ok to omit the startKey and only provide continuationToken.
        # As long as the continuationToken is provided, the startKey is not considered.
        r = self.client.list_functions(self.serviceName, limit=1, nextToken=nextToken)
        functions = r['functions']
        self.assertEqual(len(functions), 1)
        self.assertTrue(functions[0]['functionName'], prefix + 'zzz')

        # If continuationToken is provided, along with a prefix, then the prefix is considered.
        r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'x', nextToken=nextToken)
        functions = r['functions']
        self.assertEqual(len(functions), 0)

        r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'a')
        functions = r['functions']
        self.assertEqual(len(functions), 2)
        self.assertTrue(functions[0]['functionName'], prefix + 'abc')
        self.assertTrue(functions[1]['functionName'], prefix + 'abd')

        # list functions with prefix and startKey
        r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'ab', startKey=prefix + 'abd')
        functions = r['functions']
        self.assertEqual(len(functions), 1)
        self.assertTrue(functions[0]['functionName'], prefix + 'abd')

    def test_invoke(self):
        helloWorld= 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('create function: {0}'.format(helloWorld))
        self.client.create_function(
            self.serviceName, helloWorld,
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        r = self.client.invoke_function(self.serviceName, helloWorld)
        self.assertEqual(r.decode('utf-8'), 'hello world')

        # read a image as invoke parameter.
        imageProcess = 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('create function: {0}'.format(imageProcess))
        self.client.create_function(
            self.serviceName, imageProcess,
            handler='image_process.resize', runtime='nodejs4.4', codeDir='test/image_process/code')
        sourceImage = open('test/image_process/data/serverless.png', 'rb')
        destImage = open('/tmp/serverless.png', 'wb')
        r = self.client.invoke_function(self.serviceName, imageProcess, payload=sourceImage)
        destImage.write(r)
        sourceImage.close()
        destImage.close()

        self.assertEqual(imghdr.what('/tmp/serverless.png'), 'png')

        self.client.delete_function(self.serviceName, helloWorld)
        self.client.delete_function(self.serviceName, imageProcess)


if __name__ == '__main__':
    unittest.main()

