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

Python 3.6

Installation
-------------------

Install the official release version through PIP (taking Linux as an example):

.. code-block:: bash

    $ pip install xl-aliyun-fc2

You can also install the unzipped installer package directly:

.. code-block:: bash

    $ sudo python setup.py install

Getting started
-------------------

.. code-block:: python

    # -*- coding: utf-8 -*-
    import fc2
    import zipfile
    import base64

    # To know the endpoint and access key id/secret info, please refer to:
    # https://help.aliyun.com/document_detail/52984.html
    client = fc2.Client(
        endpoint='<Your Endpoint>',
        accessKeyID='<Your AccessKeyID>',
        accessKeySecret='<Your AccessKeySecret>')

    # Create service.
    client.create_service('service_name')

    zipFileBase64 = ''
    with zipfile.ZipFile('file.zip', 'r') as archive:
        content = archive.read()
        zipFileBase64 = base64.b64encode(content).decode('utf-8')

    # Create function.
    client.create_function('service_name', {
    'functionName':'python3',  
    'runtime': 'main.my_handler', 
    'code': {
        'zipFile': zipFileBase64
    },
    'environmentVariables': {'testKey': 'testValue'}
    })

    # Invoke function synchronously.
    client.invoke_function('service_name', 'function_name')

More resources
--------------
- `Aliyun FunctionCompute docs <https://help.aliyun.com/product/50980.html>`_

Contacting us
-------------
- `Links <https://help.aliyun.com/document_detail/53087.html>`_

License
-------
- `MIT <https://github.com/aliyun/fc-python-sdk/blob/master/LICENSE>`_
