Aliyun FunctionCompute Python SDK
=================================

.. image:: https://badge.fury.io/py/aliyun-fc.svg
    :target: https://badge.fury.io/py/aliyun-fc
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


Installation
----------

Install the official release version through PIP (taking Linux as an example):

.. code-block:: bash

    $ pip install aliyun-fc

You can also install the unzipped installer package directly:

.. code-block:: bash

    $ sudo python setup.py install


Getting started
---------------

.. code-block:: python

    # -*- coding: utf-8 -*-

    import fc

    # To know the endpoint and access key id/secret info, please refer to:
    # https://help.aliyun.com/document_detail/52984.html
    client = fc.Client(
        endpoint='<Your Endpoint>',
        accessKeyID='<Your AccessKeyID>',
        accessKeySecret='<Your AccessKeySecret>')

    # Create service.
    client.create_service('service_name')

    # Create function.
    # the current directory has a main.zip file (main.py which has a function of myhandler)
    client.create_function('service_name', 'function_name', 'main.my_handler', codeZipFile = 'main.zip')

    # Invoke function synchronously.
    client.invoke_function('service_name', 'function_name')

    # Invoke a function with a input parameter.
    client.invoke_function('service_name', 'function_name', payload=bytes('hello_world'))

    # Read a image and invoke a function with the file data as input parameter.
    src = open('src_image_file_path', 'rb') # Note: please open it as binary.
    r = client.invoke_function('service_name', 'function_name', payload=src)
    # save the result as the output image.
    dst = open('dst_image_file_path', 'wb')
    dst.write(r)
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
