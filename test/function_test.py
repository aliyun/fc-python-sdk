# -*- coding: utf-8 -*-

import fc2
import logging
import random
import requests
import string
import unittest
import uuid
import imghdr
import os
import json
from aliyunsdkcore import client as AliyunSDK
from aliyunsdksts.request.v20150401 import AssumeRoleRequest

class TestFunction(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestFunction, self).__init__(*args, **kwargs)
        self.client = fc2.Client(
            endpoint=os.environ['ENDPOINT'],
            accessKeyID=os.environ['ACCESS_KEY_ID'],
            accessKeySecret=os.environ['ACCESS_KEY_SECRET'],
        )
        serviceName = 'TestFunction_service_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        self.serviceName = serviceName
        self.client.create_service(self.serviceName)
        self.runtimeSet = ['python2.7', 'python3']
        logging.info("create service: {0}".format(self.serviceName))

    def test_create(self):
        for runtime in self.runtimeSet:
            functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            desc = u'这是测试function'
            logging.info('Create function: {0}'.format(functionName))
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime=runtime, codeDir='test/hello_world', description=desc)
            self.check_function(function,functionName, desc, runtime)

    def check_function(self, function, functionName, desc, runtime = 'python2.7'):
        etag = function.headers['etag']
        self.assertNotEqual(etag, '')
        function = function.data
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], runtime)
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)
        self.assertTrue('codeChecksum' in function)
        self.assertTrue('codeSize' in function)
        self.assertTrue('createdTime' in function)
        self.assertTrue('lastModifiedTime' in function)
        self.assertTrue('functionId' in function)
        self.assertTrue('memorySize' in function)
        self.assertTrue('timeout' in function)
        
        checksum = function['codeChecksum']
        function = self.client.get_function(self.serviceName, functionName, customHeaders ={'x-fc-trace-id':str(uuid.uuid4())})
        function = function.data
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], runtime)
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)

        code = self.client.get_function_code(self.serviceName, functionName)
        code = code.data
        self.assertEqual(code['checksum'], checksum)
        self.assertTrue(code['url'] != '')

        # expect the delete function  failed because of invalid etag.
        with self.assertRaises(fc2.FcError):
            self.client.delete_function(self.serviceName, functionName, customHeaders ={'if-match': 'invalid etag'})
        
        # now success with valid etag.
        self.client.delete_function(self.serviceName, functionName, customHeaders ={'if-match': etag})

        # can not get the deleted function.
        with self.assertRaises(fc2.FcError):
            self.client.get_function(self.serviceName, functionName)

        # TODO: test create with oss object code.
       

    def test_create_from_zip(self):
        for runtime in self.runtimeSet:
            functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            desc = u'这是测试function'
            logging.info('Create function: {0}'.format(functionName))
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip', description=desc)
            self.check_function(function, functionName, desc, runtime)

    def test_update(self):
        for runtime in self.runtimeSet:
            functionName = 'test_update_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            logging.info('Create function: {0}'.format(functionName))
            self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime=runtime, codeDir='test/hello_world')

            desc = 'function description'
            func = self.client.update_function(self.serviceName, functionName, codeDir='test/hello_world', description=desc)
            etag = func.headers['etag']
            self.assertNotEqual(etag, '')
            func = func.data
            self.assertEqual(func['description'], desc)

            func = self.client.update_function(self.serviceName, functionName, codeZipFile='test/hello_world/hello_world.zip', description=desc)
            func = func.data
            self.assertEqual(func['description'], desc)

            # expect the delete service failed because of invalid etag.
            with self.assertRaises(fc2.FcError):
                self.client.update_function(self.serviceName, functionName, description='invalid', customHeaders ={'if-match':'invalid etag'})

            self.assertEqual(func['description'], desc)

            self.client.delete_function(self.serviceName, functionName)

    def test_list(self):
        for runtime in self.runtimeSet:
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
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            self.client.create_function(
                self.serviceName, prefix + 'abd',
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            self.client.create_function(
                self.serviceName, prefix + 'ade',
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            self.client.create_function(
                self.serviceName, prefix + 'bcd',
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            self.client.create_function(
                self.serviceName, prefix + 'bde',
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            self.client.create_function(
                self.serviceName, prefix + 'zzz',
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')

            r = self.client.list_functions(self.serviceName, limit=2, startKey=prefix + 'b')
            r = r.data
            functions = r['functions']
            nextToken = r['nextToken']
            self.assertEqual(len(functions), 2)
            functions = r['functions']
            self.assertTrue(functions[0]['functionName'], prefix + 'bcd')
            self.assertTrue(functions[1]['functionName'], prefix + 'bde')

            r = self.client.list_functions(self.serviceName, limit=1, startKey=prefix + 'b', nextToken=nextToken)
            r = r.data
            functions = r['functions']
            self.assertEqual(len(functions), 1)
            self.assertTrue(functions[0]['functionName'], prefix + 'zzz')

            # It's ok to omit the startKey and only provide continuationToken.
            # As long as the continuationToken is provided, the startKey is not considered.
            r = self.client.list_functions(self.serviceName, limit=1, nextToken=nextToken)
            r = r.data
            functions = r['functions']
            self.assertEqual(len(functions), 1)
            self.assertTrue(functions[0]['functionName'], prefix + 'zzz')

            # If continuationToken is provided, along with a prefix, then the prefix is considered.
            r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'x', nextToken=nextToken)
            r = r.data
            functions = r['functions']
            self.assertEqual(len(functions), 0)

            r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'a')
            r = r.data
            functions = r['functions']
            self.assertEqual(len(functions), 2)
            self.assertTrue(functions[0]['functionName'], prefix + 'abc')
            self.assertTrue(functions[1]['functionName'], prefix + 'abd')

            # list functions with prefix and startKey
            r = self.client.list_functions(self.serviceName, limit=2, prefix=prefix + 'ab', startKey=prefix + 'abd')
            r = r.data
            functions = r['functions']
            self.assertEqual(len(functions), 1)
            self.assertTrue(functions[0]['functionName'], prefix + 'abd')

    def test_invoke(self):
        for runtime in self.runtimeSet:
            helloWorld= 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            logging.info('create function: {0}'.format(helloWorld))
            self.client.create_function(
                self.serviceName, helloWorld,
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')
            r = self.client.invoke_function(self.serviceName, helloWorld)
            self.assertEqual(r.data.decode('utf-8'), 'hello world')

            self.client.delete_function(self.serviceName, helloWorld)

        # read a image as invoke parameter.
        # imageProcess = 'test_invoke_nodejs_image_resize'
        # logging.info('create function: {0}'.format(imageProcess))
        # self.client.create_function(
        #     self.serviceName, imageProcess,
        #     handler='image_process.resize', runtime='nodejs4.4', codeDir='test/image_process/code')
        # sourceImage = open('test/image_process/data/serverless.png', 'rb')
        # destImage = open('/tmp/serverless.png', 'wb')
        # r = self.client.invoke_function(self.serviceName, imageProcess, payload=sourceImage)
        # destImage.write(r.data)
        # sourceImage.close()
        # destImage.close()
        # self.assertEqual(imghdr.what('/tmp/serverless.png'), 'png')
        # self.client.delete_function(self.serviceName, imageProcess)

    def test_sts(self):
        for runtime in self.runtimeSet:
            helloWorld= 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
            logging.info('create function: {0}'.format(helloWorld))
            self.client.create_function(
                self.serviceName, helloWorld,
                handler='main.my_handler', runtime=runtime, codeZipFile='test/hello_world/hello_world.zip')

            sts_client = AliyunSDK.AcsClient(
                os.environ['ACCESS_KEY_ID'],
                os.environ['ACCESS_KEY_SECRET'],
                'cn-shanghai')
            request = AssumeRoleRequest.AssumeRoleRequest()
            request.set_RoleArn(os.environ['STS_ROLE'])
            request.set_RoleSessionName('fc-python-sdk')
            response = sts_client.do_action_with_exception(request)
            resp = json.loads(response)
            client = fc2.Client(
                endpoint=os.environ['ENDPOINT'],
                accessKeyID=resp['Credentials']['AccessKeyId'],
                accessKeySecret=resp['Credentials']['AccessKeySecret'],
                securityToken=resp['Credentials']['SecurityToken'],
            )
            r = client.invoke_function(self.serviceName, helloWorld)
            self.assertEqual(r.data.decode('utf-8'), 'hello world')
            self.client.delete_function(self.serviceName, helloWorld)

    def test_fc_error_code(self):
        with self.assertRaises(fc2.FcError) as cm:
            self.client.invoke_function(self.serviceName, "undefine_function")

        self.assertIn('RequestId', cm.exception.message)
        self.assertIn('ErrorCode', cm.exception.message)
        self.assertIn('ErrorMessage', cm.exception.message)

        self.assertEqual('FunctionNotFound', cm.exception.err_code)
        self.assertNotEqual('', cm.exception.request_id)

if __name__ == '__main__':
    unittest.main()
