Aliyun FunctionCompute Python SDK
=================================

.. image:: https://badge.fury.io/py/aliyun-fc2.svg
    :target: https://badge.fury.io/py/aliyun-fc2
.. image:: https://travis-ci.org/aliyun/fc-python-sdk.svg?branch=master
    :target: https://travis-ci.org/aliyun/fc-python-sdk
.. image:: https://coveralls.io/repos/github/aliyun/fc-python-sdk/badge.svg?branch=master
    :target: https://coveralls.io/github/aliyun/fc-python-sdk?branch=master

Overview
--------

The SDK of this version is dependent on the third-party HTTP library `requests <https://github.com/kennethreitz/requests>`_.


Running environment
-------------------

Python 2.7, Python 3.6


Notice
-------------------
fc and fc2 are not compatible, now master repo is fc2, if you still use fc, 1.x branch is what you need.
We suggest using fc2, The main difference between fc and fc2 is:

1, all http request fuction can set headers

.. code-block:: python

    def invoke_function(self, serviceName, functionName, payload=None, 
            headers = {'x-fc-invocation-type': 'Sync', 'x-fc-log-type' : 'None'}):                                           
        ...

Attention: abandon async_invoke_function, there is only one function interface invoke_function, distinguish between synchronous and asynchronous by x-fc-invocation-type parameters.


2, The all http response returned by the user is the following object

.. code-block:: python

    class FcHttpResponse(object):
        def __init__(self, headers, data):
            self._headers = headers
            self._data = data

        @property
        def headers(self):
            return self._headers

        @property
        def data(self):
            return self._data

Note: for invoke function, data is bytes, for other apis, data is dict

Installation
-------------------

Install the official release version through PIP (taking Linux as an example):

.. code-block:: bash

    $ pip install aliyun-fc2

You can also install the unzipped installer package directly:

.. code-block:: bash

    $ sudo python setup.py install


if you still use fc, you can install the official fc1 release version through PIP (taking Linux as an example):

.. code-block:: bash

    $ pip install aliyun-fc

Getting started
-------------------

.. code-block:: python

    # -*- coding: utf-8 -*-

    import fc2


    # To know the endpoint and access key id/secret info, please refer to:
    # https://help.aliyun.com/document_detail/52984.html
    client = fc2.Client(
        endpoint='<Your Endpoint>',
        accessKeyID='<Your AccessKeyID>',
        accessKeySecret='<Your AccessKeySecret>')

    # Create service.
    client.create_service('service_name')

    # Create function.
    # the current directory has a main.zip file (main.py which has a function of myhandler)
    # set environment variables {'testKey': 'testValue'}
    client.create_function('service_name', 'function_name', 'python3',  'main.my_handler', codeZipFile = 'main.zip', environmentVariables = {'testKey': 'testValue'})

    # Invoke function synchronously.
    client.invoke_function('service_name', 'function_name')

    # Create trigger
    # Create oss trigger
    oss_trigger_config = {
            'events': ['oss:ObjectCreated:*'],
            'filter': {
                'key': {
                    'prefix': 'prefix',
                    'suffix': 'suffix'
                }
            }
    }
    source_arn = 'acs:oss:cn-shanghai:12345678:bucketName'
    invocation_role = 'acs:ram::12345678:role/aliyunosseventnotificationrole'
    client.create_trigger('service_name', 'function_name', 'trigger_name', 'oss',
                                                         oss_trigger_config, source_arn, invocation_role)

    # Create log trigger
    log_trigger_config = {
            'sourceConfig': {
                'logstore': 'log_store_source'
            },
            'jobConfig': {
                'triggerInterval': 60,
                'maxRetryTime': 10
            },
            'functionParameter': {},
            'logConfig': {
                'project': 'log_project',
                'logstore': 'log_store'
            },
            'enable': False
    }
    source_arn = 'acs:log:cn-shanghai:12345678:project/log_project'
    invocation_role = 'acs:ram::12345678:role/aliyunlogetlrole'
    client.create_trigger('service_name', 'function_name', 'trigger_name', 'oss',
                                                         log_trigger_config, source_arn, invocation_role)
    # Create time trigger
    time_trigger_config = {
            'payload': 'awesome-fc'
            'cronExpression': '0 5 * * * *'
            'enable': true
    }
    client.create_trigger('service_name', 'function_name', 'trigger_name', 'timer', time_trigger_config, '', '')

    # Invoke a function with a input parameter.
    client.invoke_function('service_name', 'function_name', payload=bytes('hello_world'))

    # Read a image and invoke a function with the file data as input parameter.
    src = open('src_image_file_path', 'rb') # Note: please open it as binary.
    r = client.invoke_function('service_name', 'function_name', payload=src)
    # save the result as the output image.
    dst = open('dst_image_file_path', 'wb')
    dst.write(r.data)
    src.close()
    dst.close()

    # Invoke function asynchronously.
    client.async_invoke_function('service_name', 'function_name')

    # List services.
    client.list_services()

    # List functions with prefix and limit.
    client.list_functions('service_name', prefix='the_prefix', limit=10)

    # Delete service.
    client.delete_service('service_name')

    # Delete function.
    client.delete_function('service_name', 'function_name')


Testing
-------

To run the tests, please set the access key id/secret, endpoint as environment variables.
Take the Linux system for example:

.. code-block:: bash

    $ export ENDPOINT=<endpoint>
    $ export ACCESS_KEY_ID=<AccessKeyId>
    $ export ACCESS_KEY_SECRET=<AccessKeySecret>
    $ export STS_TOKEN=<roleARN>

Run the test in the following method:

.. code-block:: bash

    $ nosetests                          # First install nose

More resources
--------------
- `Aliyun FunctionCompute docs <https://help.aliyun.com/product/50980.html>`_

Contacting us
-------------
- `Links <https://help.aliyun.com/document_detail/53087.html>`_

License
-------
- `MIT <https://github.com/aliyun/fc-python-sdk/blob/master/LICENSE>`_
