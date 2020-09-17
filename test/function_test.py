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
    client = None
    service_name = ""

    def __init__(self, *args, **kwargs):
        super(TestFunction, self).__init__(*args, **kwargs)

    @classmethod
    def setUpClass(cls):
        logging.info("This setUpClass() method only called once.")
        cls.client = fc2.Client(
            endpoint=os.environ['ENDPOINT'],
            accessKeyID=os.environ['ACCESS_KEY_ID'],
            accessKeySecret=os.environ['ACCESS_KEY_SECRET'],
        )
        service_name = 'TestFunction_service_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        cls.serviceName = service_name
        cls.client.create_service(service_name)
        logging.info("create service: {0}".format(service_name))

    @classmethod
    def tearDownClass(cls):
        logging.info("This tearDownClass() method only called once too.")
        service_name = cls.serviceName
        r = cls.client.list_functions(cls.serviceName)
        functions = r.data['functions']
        assert len(functions)==0
        cls.client.delete_service(service_name)

    def test_create(self):
        functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc1 = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        function1 = self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world', description=desc1, environmentVariables={'testKey': 'testValue'})
        self.check_function(function1, functionName, desc1, 'python2.7')
        function1 = function1.data
        self.assertEqual(function1['environmentVariables']['testKey'], 'testValue')

        # test create function with initializer
        functionName2= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc2 = u'test for initializer'
        function2 = self.client.create_function(
            self.serviceName, functionName2,
            handler='main.my_handler', runtime='python2.7', codeDir='test/counter', initializer='main.my_initializer',
            description=desc2, environmentVariables={'testKey': 'testValue'})
        self.check_function(function2, functionName2, desc2, 'python2.7', 'main.my_initializer')
        function2 = function2.data
        self.assertEqual(function2['environmentVariables']['testKey'], 'testValue')

        # test create function with instanceType
        functionName3 = 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc3 = u'test for InstanceType'
        function3 = self.client.create_function(
            self.serviceName, functionName3,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world',
            description=desc3, environmentVariables={'testKey': 'testValue'}, instanceType="e1")
        self.check_function(function3, functionName3, desc3, 'python2.7')
        function3 = function3.data
        self.assertEqual(function3['environmentVariables']['testKey'], 'testValue')

    def test_instance_concurrency(self):
        # test create function with instanceConcurrency
        function_name= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'test for initializer'
        resp = self.client.create_function(
            self.serviceName, function_name,
            handler='main.my_handler', runtime='nodejs10', codeDir='test/counter', initializer='main.my_initializer',
            description=desc, environmentVariables={'testKey': 'testValue'}, instanceConcurrency=2)
        self.assertEqual(2, resp.data['instanceConcurrency'])

        # update function with instanceConcurrency
        resp = self.client.update_function(self.serviceName, function_name, instanceConcurrency=10)
        self.assertEqual(10, resp.data['instanceConcurrency'])

        # delete the function
        self.client.delete_function(self.serviceName, function_name)

    def check_function(self, function, functionName, desc, runtime = 'python2.7', initializer = None, initializationTimeout = None):
        etag = function.headers['etag']
        self.assertNotEqual(etag, '')
        function = function.data
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], runtime)
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)
        self.assertEqual(function['instanceType'], "e1")
        self.assertTrue('codeChecksum' in function)
        self.assertTrue('codeSize' in function)
        self.assertTrue('createdTime' in function)
        self.assertTrue('lastModifiedTime' in function)
        self.assertTrue('functionId' in function)
        self.assertTrue('memorySize' in function)
        self.assertTrue('timeout' in function)
        if desc == u'test for initializer':
            self.assertEqual(function['initializer'], initializer)
            self.assertEqual(function['initializationTimeout'], 30)

        checksum = function['codeChecksum']
        function = self.client.get_function(self.serviceName, functionName, headers ={'x-fc-trace-id':str(uuid.uuid4())})
        function = function.data
        self.assertEqual(function['functionName'], functionName)
        self.assertEqual(function['runtime'], runtime)
        self.assertEqual(function['handler'], 'main.my_handler')
        self.assertEqual(function['description'], desc)
        if desc == u'test for initializer':
            self.assertEqual(function['initializer'], initializer)
            self.assertEqual(function['initializationTimeout'], 30)

        code = self.client.get_function_code(self.serviceName, functionName)
        code = code.data
        self.assertEqual(code['checksum'], checksum)
        self.assertTrue(code['url'] != '')

        # expect the delete function  failed because of invalid etag.
        with self.assertRaises(fc2.FcError):
            self.client.delete_function(self.serviceName, functionName, headers ={'if-match': 'invalid etag'})
        
        # now success with valid etag.
        self.client.delete_function(self.serviceName, functionName, headers ={'if-match': etag})

        # can not get the deleted function.
        with self.assertRaises(fc2.FcError):
            self.client.get_function(self.serviceName, functionName)

        # TODO: test create with oss object code.
       

    def test_create_from_zip(self):
        functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))
        function = self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip', description=desc)
        self.check_function(function, functionName, desc, 'python2.7')

    def test_update(self):
        functionName = 'test_update_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('Create function: {0}'.format(functionName))
        self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7', codeDir='test/hello_world', environmentVariables={'testKey0':'testValue0', 'testKey1':'testValue1'})
        desc = 'function description'
        func = self.client.update_function(self.serviceName, functionName, codeDir='test/hello_world', description=desc, environmentVariables={'newTestKey':'newTestValue'})
        etag = func.headers['etag']
        self.assertNotEqual(etag, '')
        func = func.data
        self.assertEqual(func['description'], desc)
        self.assertEqual(func['environmentVariables'], {'newTestKey':'newTestValue'})
        func = self.client.update_function(self.serviceName, functionName, codeZipFile='test/hello_world/hello_world.zip', description=desc)
        func = func.data
        self.assertEqual(func['description'], desc)
        self.assertEqual(func['environmentVariables'], {'newTestKey':'newTestValue'})
        self.assertEqual(func['description'], desc)
        func = self.client.update_function(self.serviceName, functionName, codeDir='test/hello_world', description=desc, environmentVariables={})
        self.assertEqual(func.data['environmentVariables'], {})
        # expect the delete service failed because of invalid etag.
        with self.assertRaises(fc2.FcError):
            self.client.update_function(self.serviceName, functionName, description='invalid', headers ={'if-match':'invalid etag'})

        with self.assertRaises(Exception):
            self.client.update_function(self.serviceName, functionName, codeZipFile='test/hello_world/hello_world.zip', runtime = 10)
        self.client.delete_function(self.serviceName, functionName)

        # test update function with initializer
        functionName = 'test_update_with_initializer_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('Create function: {0}'.format(functionName))
        self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', initializer='main.my_initializer' ,runtime='python2.7', codeDir='test/counter', environmentVariables={'testKey0':'testValue0', 'testKey1':'testValue1'})
        desc = 'function description'
        func = self.client.update_function(self.serviceName, functionName, codeDir='test/counter', initializationTimeout=60, description=desc, environmentVariables={'newTestKey':'newTestValue'})
        etag = func.headers['etag']
        self.assertNotEqual(etag, '')
        func = func.data
        self.assertEqual(func['description'], desc)
        self.assertEqual(func['initializationTimeout'], 60)
        self.assertEqual(func['environmentVariables'], {'newTestKey':'newTestValue'})
        self.client.delete_function(self.serviceName, functionName)

    def _clear_list_function(self):
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
        except Exception as e:
            logging.error("_clear_list_function error {}".format(str(e)))


    def test_list(self):
        self._clear_list_function()
        # Use the prefix to isolate the services.
        prefix = 'test_list_'
        runtime = 'python2.7'

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
        self._clear_list_function()

    def test_initialize(self):
        functionName = 'test_invoke_counter_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('create function: {0}'.format(functionName))
        self.client.create_function(
            self.serviceName, functionName,
            handler='main.my_handler', runtime='python2.7',
            initializer='main.my_initializer',
            codeZipFile='test/counter/counter.zip')

        r = self.client.invoke_function(self.serviceName, functionName)
        self.assertEqual(r.data.decode('utf-8'), '2')
        r = self.client.invoke_function(self.serviceName, functionName)
        self.assertEqual(r.data.decode('utf-8'), '3')
        self.client.delete_function(self.serviceName, functionName)

    def test_invoke(self):
        helloWorld= 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('create function: {0}'.format(helloWorld))
        self.client.create_function(
            self.serviceName, helloWorld,
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')
        r = self.client.invoke_function(self.serviceName, helloWorld)
        self.assertEqual(r.data.decode('utf-8'), 'hello world')

        self.client.delete_function(self.serviceName, helloWorld)

        # read a image as invoke parameter.
        imageProcess = 'test_invoke_nodejs_image_resize'
        logging.info('create function: {0}'.format(imageProcess))
        self.client.create_function(
            self.serviceName, imageProcess,
            handler='image_process.resize', runtime='nodejs4.4', codeDir='test/image_process/code')
        sourceImage = open('test/image_process/data/serverless.png', 'rb')
        destImage = open('/tmp/serverless.png', 'wb')
        r = self.client.invoke_function(self.serviceName, imageProcess, payload=sourceImage)
        destImage.write(r.data)
        sourceImage.close()
        destImage.close()
        self.assertEqual(imghdr.what('/tmp/serverless.png'), 'png')
        self.client.delete_function(self.serviceName, imageProcess)

    def test_sts(self):
        helloWorld= 'test_invoke_hello_world_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        logging.info('create function: {0}'.format(helloWorld))
        self.client.create_function(
            self.serviceName, helloWorld,
            handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip')

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


    def test_check_op_function_param_check(self):
        functionName= 'test_create_' + ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
        desc = u'这是测试function'
        logging.info('Create function: {0}'.format(functionName))

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeDir=None, description=desc)
        
        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeZipFile='test/hello_world/hello_world.zip' , codeDir='test/hello_world', description=desc)
        
        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeOSSBucket='test-bucket' ,  description=desc)

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime=10, codeZipFile='test/hello_world/hello_world.zip')

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeZipFile=10 , description=desc)

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeDir=10, description=desc)

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeOSSBucket=10, codeOSSObject="hello", description=desc)

        with self.assertRaises(Exception):
            function = self.client.create_function(
                self.serviceName, functionName,
                handler='main.my_handler', runtime='python2.7', codeOSSBucket="hello", codeOSSObject=10, description=desc)

if __name__ == '__main__':
    unittest.main()
