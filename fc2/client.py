# -*- coding: utf-8 -*-

from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import base64
import email
import io
import json
import logging
import platform
import sys
import websocket
from urllib.parse import quote
import threading

import requests

from . import __version__
from . import auth
from . import fc_exceptions
from . import util

_ver = sys.version_info
if _ver[0] == 2:
    from urllib import unquote as unescape
elif _ver[0] == 3:
    from urllib.parse import unquote as unescape


retries = 5
backoff_factor = 1
status_forcelist = (500, 502, 504)
delimiter = '.'


def makeQuery(queries):
    array = []
    for key, item in queries.items():
        k = quote(str(key))
        if type(item) != list:
            item = [item]
        for value in item:
            array.append(k + '=' + quote(str(value)))
    return '&'.join(array)


def requestWithTry(method, url, **kwargs):
    with requests.Session() as session:
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session.request(method=method, url=url, **kwargs)


class Client(object):
    def __init__(self, **kwargs):
        endpoint = kwargs.get('endpoint', None)
        if not endpoint:
            raise ValueError(
                'A valid Endpoint parameter must be specified to construct the Client object.')
        access_key_id = kwargs.get("accessKeyID", None)
        if not access_key_id:
            raise ValueError(
                'A valid AccessKeyID parameter must be specified to construct the Client object.')
        access_key_secret = kwargs.get('accessKeySecret', None)
        if not access_key_secret:
            raise ValueError(
                'A valid AccessKeySecret parameter must be specified to construct the Client object.')
        security_token = kwargs.get('securityToken', '')
        self.endpoint = Client._normalize_endpoint(endpoint)
        self.host = Client._get_host(endpoint)
        self.api_version = '2016-08-15'
        self.user_agent = \
            'aliyun-fc-sdk-v{0}.python-{1}.{2}-{3}-{4}'. \
            format(__version__, platform.python_version(),
                   platform.system(), platform.release(), platform.machine())
        self.auth = auth.Auth(access_key_id, access_key_secret, security_token)
        self.timeout = kwargs.get('Timeout', 60)

    @staticmethod
    def _normalize_endpoint(url):
        if not url.startswith('http://') and not url.startswith('https://'):
            return 'https://{0}'.format(url)
        return url.strip()

    @staticmethod
    def _get_host(endpoint):
        """ Extract host from endpoint. """
        if endpoint.startswith('http://'):
            return endpoint[7:].strip()

        if endpoint.startswith('https://'):
            return endpoint[8:].strip()

        return endpoint.strip()

    def _build_common_headers(self, method, path, customHeaders={}, unescaped_queries=None):
        headers = {
            'host': self.host,
            'date': email.utils.formatdate(usegmt=True),
            'content-type': 'application/json',
            'content-length': '0',
            'user-agent': self.user_agent,
        }
        if self.auth.security_token != '':
            headers['x-fc-security-token'] = self.auth.security_token

        if customHeaders:
            headers.update(customHeaders)

        # Sign the request and set the signature to headers.
        headers['authorization'] = self.auth.sign_request(
            method, path, headers, unescaped_queries)

        return headers

    def do_http_request(self, method, serviceName, functionName, path, headers={}, params=None, body=None):
        params = {} if params is None else params
        if not isinstance(params, dict):
            raise TypeError('`None` or `dict` required for params')
        path = '/{0}/proxy/{1}/{2}{3}'.format(
            self.api_version, serviceName, functionName, path if path != "" else "/")
        url = '{0}{1}'.format(self.endpoint, path)
        headers = self._build_common_headers(
            method, unescape(path), headers, params)
        logging.debug(
            'Do http request. Method: {0}. URL: {1}. Params: {2}. Headers: {3}'.format(method, url, params, headers))
        r = requestWithTry(method, url, headers=headers,
                           params=params, data=body, timeout=self.timeout)
        return r

    def _do_request(self, method, path, headers, params=None, body=None):
        url = '{0}{1}'.format(self.endpoint, path)
        logging.debug('Perform http request. Method: {0}. URL: {1}. Headers: {2}'.format(
            method, url, headers))
        r = requestWithTry(method, url, headers=headers,
                           params=params, data=body, timeout=self.timeout)

        if r.status_code < 400:
            logging.debug(
                'Http status code: {0}. Method: {1}. URL: {2}. Headers: {3}'.format(
                    r.status_code, method, url, r.headers))
        elif 400 <= r.status_code < 500:
            errmsg = \
                'Client error: {0}. Message: {1}. Method: {2}. URL: {3}. Request headers: {4}. Response headers: {5}'. \
                format(r.status_code, r.json(),
                       method, url, headers, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)
        elif 500 <= r.status_code < 600:
            errmsg = \
                'Server error: {0}. Message: {1}. Method: {2}. URL: {3}. Request headers: {4}. Response headers: {5}'. \
                format(r.status_code, r.json(),
                       method, url, headers, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)

        return r

    def __gen_request_err(self, r):
        try:
            err_d = r.json()
        except json.JSONDecodeError:
            err_d = {
                'ErrorMessage': r.text,
                'ErrorType': r.headers.get('x-fc-error-type', ''),
                'RequestId': r.headers.get('X-Fc-Request-Id', 'unknown'),
                'ErrorCode': r.headers.get('ErrorCode', '')
            }
            err_code = err_d.get('ErrorCode', '')
            err_msg = json.dumps(err_d)
            return fc_exceptions.get_fc_error(err_msg, r.status_code, err_code, err_d['RequestId'])

        err_d['RequestId'] = r.headers.get('X-Fc-Request-Id', 'unknown')
        err_code = err_d.get('ErrorCode', '')
        err_msg = json.dumps(err_d)
        return fc_exceptions.get_fc_error(err_msg, r.status_code, err_code, err_d['RequestId'])

    def websocket(self, url, queries={}, headers={}):
        header = self._build_common_headers(
            "GET", url, headers
        )
        del header["host"]

        url = '{0}{1}?{2}'.format(
            self.endpoint.replace("http", "ws"),
            url, makeQuery(queries)
        )

        ws = websocket.WebSocketApp(
            url,
            header=header,
        )

        return ws

    def get_account_settings(self,  headers={}):
        """
        :return FcHttpResponse
        headers: dict
        data: dict
        {
            'availableAZs': ['zone-id']
        }
        """
        method = 'GET'
        path = '/{0}/account-settings'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def create_service(self, serviceName, description=None, logConfig=None, role=None, headers={}, internetAccess=None,
                       vpcConfig=None, nasConfig=None, tracingConfig=None):
        """
        Create a service.
        :param serviceName: name of the service.
        :param description: (optional, string), detail description of the service.
        :param logConfig: (optional, dict), log configuration.
        {
            'project': 'string',
            'logStore': 'string',
            'enableRequestMetrics' : 'bool',
            'enableInstanceMetrics' : 'bool'
        }
        :param role: The Aliyun Resource Name (ARN) of the RAM role that FunctionCompute assumes when it executes
        your function to access any other Aliyun resources.
        For more information, see: https://help.aliyun.com/document_detail/52885.html
        :param headers, oprional, 'x-fc-trace-id': string (a uuid to do the request tracing), etc
        :param internetAccess, optional, the ability to access the internet, default true, you can set it false if you would like to disable the internet access
        :param vpcConfig, (optional, dict), vpc configuration
        {
            "vpcId": "string",
            "vSwitchIds": [ "string" ],
            "securityGroupId": "string"
        }
        :param nasConfig, (optional, dict), nas configuration
        {
            "userId": int,
            "groupId": int,
            "mountPoints": [
                {
                    "serverAddr" : string,
                    "mountDir" : string
                }
             ],
        }
        :param tracingConfig, (optional, dict), tracing configuration
        {
            "type": string, Supported: Jaeger.
            "params": dict,
         }
        :param traceId:(optional, string) a uuid to do the request tracing.
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict. For more information, see: https://help.aliyun.com/document_detail/52877.html#createservice
        {
            'createdTime': 'string',
            'description': 'string',
            'lastModifiedTime': 'string',
            'logConfig': {
                'project': 'string',
                'log_store': 'string',
                'enableRequestMetrics' : 'bool',
                'enableInstanceMetrics' : 'bool'
            },
            'role': 'string',
            'serviceId': 'string',
            'serviceName': 'string',
        }
        """
        method = 'POST'
        path = '/{0}/services'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        payload = {'serviceName': serviceName, 'description': description}
        if logConfig:
            payload['logConfig'] = logConfig
        if role:
            payload['role'] = role
        if vpcConfig:
            payload['vpcConfig'] = vpcConfig
        if internetAccess != None:
            payload['internetAccess'] = internetAccess
        if nasConfig:
            payload['nasConfig'] = nasConfig
        if tracingConfig:
            payload['tracingConfig'] = tracingConfig

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def delete_service(self, serviceName, headers={}):
        """
        Delete the specified service.
        :param service_name: name of the service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/services/{1}'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def update_service(self, serviceName, description=None, logConfig=None, role=None, headers={}, internetAccess=None,
                       vpcConfig=None, nasConfig=None, tracingConfig=None):
        """
        Update the service attributes.
        :param serviceName: name of the service.
        :param description: (optional, string), detail description of the service.
        :param logConfig: (optional, dict), log configuration.
        {
            'project': 'string',
            'logStore': 'string',
            'enableRequestMetrics': 'bool',
            'enableInstanceMetrics': 'bool'
        }
        :param role: The Aliyun Resource Name (ARN) of the RAM role that FunctionCompute assumes when it executes
        your function to access any other Aliyun resources.
        For more information, see: https://help.aliyun.com/document_detail/52885.html
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (update the service only when matched the given etag.)
            3, user define key value
        :param internetAccess, optional, the ability to access the internet, default true, you can set it false if you would like to disable the internet access
        :param vpcConfig, (optional, dict), vpc configuration
        {
            "vpcId": "string",
            "vSwitchIds": [ "string" ],
            "securityGroupId": "string"
        }
        :param nasConfig, (optional, dict), nas configuration
        {
            "userId": int,
            "groupId": int,
            "mountPoints": [
                {
                    "serverAddr" : string,
                    "mountDir" : string
                }
             ],
        }
        :param tracingConfig, (optional, dict), tracing configuration
        {
            "type": string, Supported: Jaeger.
            "params": dict,
         }
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data:dict. For more information, see: https://help.aliyun.com/document_detail/52877.html#createservice
        {
            'createdTime': 'string',
            'description': 'string',
            'lastModifiedTime': 'string',
            'logConfig': {
                'project': 'string',
                'log_store': 'string',
                'enableRequestMetrics': 'bool',
                'enableInstanceMetrics': 'bool'
            },
            'role': 'string',
            'serviceId': 'string',
            'serviceName': 'string',
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if description:
            payload['description'] = description
        if logConfig:
            payload['logConfig'] = logConfig
        if role:
            payload['role'] = role
        if internetAccess is not None:
            payload['internetAccess'] = internetAccess
        if vpcConfig:
            payload['vpcConfig'] = vpcConfig
        if nasConfig:
            payload['nasConfig'] = nasConfig
        if tracingConfig is not None:
            payload['tracingConfig'] = tracingConfig

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def get_service(self, serviceName, headers={}, qualifier=None):
        """
        Get the service configuration.
        :param serviceName: (string) name of the service.
        :param qualifier: (optional, string) qualifier of service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict service configuration.
        """
        method = 'GET'
        if qualifier:
            serviceName += '{0}{1}'.format(delimiter, qualifier)
        path = '/{0}/services/{1}'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_services(self, limit=None, nextToken=None, prefix=None, startKey=None, headers={}, tags=None):
        """
        List the services in the current account.
        :param limit: (optional, integer) the total number of the returned services.
        :param nextToken: (optional, string) continue listing the service from the previous point.
        :param prefix: (optional, string) list the services with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all service information.
        {
            'services':
            [
                {
                    'createdTime': 'string',
                    'description': 'string',
                    'lastModifiedTime': 'string',
                    'logConfig': {
                        'project': 'string',
                        'log_store': 'string',
                        'enableRequestMetrics' : 'bool',
                        'enableInstanceMetrics' : 'bool'
                    },
                    'role': 'string',
                    'serviceId': 'string',
                    'serviceName': 'string',
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/services'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)

        if tags:
            for k, v in tags.items():
                params["tag_" + k] = v

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def _check_function_param_valid(self, codeZipFile, codeDir, codeOSSBucket, codeOSSObject):
        code_d = {}
        if codeZipFile:
            code_d['codeZipFile'] = codeZipFile
        if codeDir:
            code_d['codeDir'] = codeDir
        if codeOSSBucket:
            if not codeOSSObject:
                raise Exception(
                    'codeOSSBucket and codeOSSObject must to exist at the same time')
            code_d['oss'] = (codeOSSBucket, codeOSSObject)

        if len(code_d) == 0:
            raise Exception(
                'codeZipFile, codeDir, (codeOSSBucket, codeOSSObject) , these three parameters must have an assignment')

        if len(code_d) > 1:
            raise Exception(
                'codeZipFile, codeDir, (codeOSSBucket, codeOSSObject) , these three parameters need only one paramet$er assignment')

        return True

    def create_function(
            self, serviceName, functionName, runtime, handler,
            initializer=None, initializationTimeout=30,
            codeZipFile=None, codeDir=None, codeOSSBucket=None, codeOSSObject=None,
            description=None, memorySize=256, timeout=60, headers={}, environmentVariables=None,
            instanceConcurrency=None, customContainerConfig=None, caPort=None, instanceType=None):
        """
        Create a function.
        :param serviceName: (required, string) the name of the service that the function belongs to.
        :param functionName: (required, string) the name of the function.
        :param runtime: (required, string) the runtime type. For example, nodejs4.4, python2.7 and etc.
        :param handler: (required, string) the entry point of the function.
        :param initializer: (required, string) the entry point of the initializer.
        :param codeZipFile: (optional, string) the file path of the zipped code.
        :param codeDir: (optional, string) the directory of the code.
        :param codeOSSBucket: (optional, string) the oss bucket where the code located in.
        :param codeOSSObject: (optional, string) the zipped code stored as a OSS object.
        :param description: (optional, string) the readable description of the function.
        :param memorySize: (optional, integer) the memory size of the function, in MB.
        :param timeout: (optional, integer) the max execution time of the function, in second.
        :param initializationTimeout: (optional, integer) the max execution time of the initializer, in second.
        :param environmentVariables: (optional, dict) the environment variables of the function, both key and value are string type.
        :param instanceConcurrency: (optional, integer) the instance concurrency of the function
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict of the function attributes.
        {
            'codeChecksum': 'string',     // CRC64 checksum
            'codeSize': 1024,             // in byte
            'createdTime': 'string',
            'description': 'string',
            'functionId': 'string',
            'functionName': 'string',
            'handler': 'string',
            'initializer': 'string',
            'lastModifiedTime': 'string',
            'memorySize': 512,            // in MB
            'runtime': 'string',
            'timeout': 60,                // in second
            'initializationTimeout': 30   // in second
        }
        """
        serviceName, functionName, runtime, handler, memorySize, timeout = \
            str(serviceName), str(functionName), str(runtime), str(
                handler), int(memorySize), int(timeout)

        initializer = str(initializer) if initializer else initializer
        initializationTimeout = int(
            initializationTimeout) if initializationTimeout else initializationTimeout
        instanceType = str(instanceType) if instanceType else instanceType

        method = 'POST'
        path = '/{0}/services/{1}/functions'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        payload = {'functionName': functionName,
                   'runtime': runtime, 'handler': handler}

        if runtime != "custom-container":
            codeZipFile = str(codeZipFile) if codeZipFile else codeZipFile
            codeDir = str(codeDir) if codeDir else codeDir
            codeOSSBucket = str(
                codeOSSBucket) if codeOSSBucket else codeOSSBucket
            codeOSSObject = str(
                codeOSSObject) if codeOSSObject else codeOSSObject
            self._check_function_param_valid(
                codeZipFile, codeDir, codeOSSBucket, codeOSSObject)

            if codeZipFile:
                # codeZipFile has highest priority.
                file = open(codeZipFile, 'rb')
                data = file.read()
                encoded = base64.b64encode(data).decode('utf-8')
                payload['code'] = {'zipFile': encoded}
            elif codeDir:
                bytesIO = io.BytesIO()
                util.zip_dir(codeDir, bytesIO)
                encoded = base64.b64encode(bytesIO.getvalue()).decode('utf-8')
                payload['code'] = {'zipFile': encoded}
            else:
                payload['code'] = {'ossBucketName': codeOSSBucket,
                                   'ossObjectName': codeOSSObject}
        else:
            if not customContainerConfig:
                raise Exception(
                    'customContainerConfig is required if runtime is custom-container')

            payload['customContainerConfig'] = customContainerConfig

        if runtime in ["custom", "custom-container"] and caPort:
            payload['caPort'] = caPort

        if description:
            payload['description'] = description

        if memorySize:
            payload['memorySize'] = memorySize

        if initializer:
            payload['initializer'] = initializer

        if timeout:
            payload['timeout'] = timeout

        if initializationTimeout:
            payload['initializationTimeout'] = initializationTimeout

        if environmentVariables != None:
            payload['environmentVariables'] = environmentVariables

        if instanceConcurrency != None:
            payload['instanceConcurrency'] = instanceConcurrency

        if instanceType:
            payload['instanceType'] = instanceType

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def update_function(
            self, serviceName, functionName,
            initializer=None, initializationTimeout=None,
            codeZipFile=None, codeDir=None, codeOSSBucket=None, codeOSSObject=None,
            description=None, handler=None, memorySize=None, runtime=None, timeout=None,
            headers={}, environmentVariables=None, instanceConcurrency=None, customContainerConfig=None, caPort=None, instanceType=None):
        """
        Update the function.
        :param serviceName: (required, string) the name of the service that the function belongs to.
        :param functionName: (required, string) the name of the function.
        :param runtime: (required, string) the runtime type. For example, nodejs4.4, python2.7 and etc.
        :param handler: (required, string) the entry point of the function.
        :param initializer: (required, string) the entry point of the initializer.
        :param codeZipFile: (optional, string) the file path of the zipped code.
        :param codeDir: (optional, string) the directory of the code.
        :param codeOSSBucket: (optional, string) the oss bucket where the code located in.
        :param codeOSSObject: (optional, string) the zipped code stored as a OSS object.
        :param description: (optional, string) the readable description of the function.
        :param memorySize: (optional, integer) the memory size of the function, in MB.
        :param timeout: (optional, integer) the max execution time of the function, in second.
        :param initializationTimeout: (optional, integer) the max execution time of the initializer, in second.
        :param etag: (optional, string) delete the service only when matched the given etag.
        :param environmentVariables: (optional, dict) the environment variables of the function, both key and value are string type.
        :param instanceConcurrency: (optional, integer) the instance concurrency of the function
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (update the function only when matched the given etag.)
            3, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict of the function attributes.
        {
            'codeChecksum': 'string',     // CRC64 checksum
            'codeSize': 1024,             // in byte
            'createdTime': 'string',
            'description': 'string',
            'functionId': 'string',
            'functionName': 'string',
            'handler': 'string',
            'initializer': 'string',
            'lastModifiedTime': 'string',
            'memorySize': 512,            // in MB
            'runtime': 'string',
            'timeout': 60,                // in second
            'initializationTimeout': 30,  // in second
        }
        """
        serviceName, functionName = str(serviceName), str(functionName)
        handler = str(handler) if handler else handler
        initializer = str(initializer) if initializer else initializer
        instanceType = str(instanceType) if instanceType else instanceType
        runtime = str(runtime) if runtime else runtime
        memorySize = int(memorySize) if memorySize else memorySize
        timeout = int(timeout) if timeout else timeout
        initializationTimeout = int(
            initializationTimeout) if initializationTimeout else initializationTimeout
        codeZipFile = str(codeZipFile) if codeZipFile else codeZipFile
        codeDir = str(codeDir) if codeDir else codeDir
        codeOSSBucket = str(codeOSSBucket) if codeOSSBucket else codeOSSBucket
        codeOSSObject = str(codeOSSObject) if codeOSSObject else codeOSSObject

        method = 'PUT'
        path = '/{0}/services/{1}/functions/{2}'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if runtime:
            payload['runtime'] = runtime

        if handler:
            payload['handler'] = handler

        if initializer:
            payload['initializer'] = initializer

        if codeZipFile:
            # codeZipFile has highest priority.
            file = open(codeZipFile, 'rb')
            data = file.read()
            encoded = base64.b64encode(data).decode('utf-8')
            payload['code'] = {'zipFile': encoded}
        elif codeDir:
            bytesIO = io.BytesIO()
            util.zip_dir(codeDir, bytesIO)
            encoded = base64.b64encode(bytesIO.getvalue()).decode('utf-8')
            payload['code'] = {'zipFile': encoded}
        elif codeOSSBucket and codeOSSObject:
            payload['code'] = {'ossBucketName': codeOSSBucket,
                               'ossObjectName': codeOSSObject}

        if customContainerConfig:
            payload['customContainerConfig'] = customContainerConfig

        if ((runtime and runtime in ["custom", "custom-container"]) or (not runtime)) and caPort:
            payload['caPort'] = caPort

        if description:
            payload['description'] = description

        if memorySize:
            payload['memorySize'] = memorySize

        if timeout:
            payload['timeout'] = timeout

        if initializationTimeout:
            payload['initializationTimeout'] = initializationTimeout

        if environmentVariables != None:
            payload['environmentVariables'] = environmentVariables

        if instanceConcurrency != None:
            payload['instanceConcurrency'] = instanceConcurrency

        if instanceType:
            payload['instanceType'] = instanceType

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def delete_function(self, serviceName, functionName, headers={}):
        """
        Delete the specified function.
        :param serviceName: name of the service.
        :param serviceName: name of the function.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the function only when matched the given etag.)
            3, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/services/{1}/functions/{2}'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def get_function(self, serviceName, functionName, headers={}, qualifier=None):
        """
        Get the function configuration.
        :param serviceName: (required, string) name of the service.
        :param functionName: (required, string) name of the function.
        :param qualifier: (optional, string) qualifier of service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict function configuration.
        """
        method = 'GET'
        if qualifier:
            serviceName += '{0}{1}'.format(delimiter, qualifier)
        path = '/{0}/services/{1}/functions/{2}'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def get_function_code(self, serviceName, functionName, headers={}, qualifier=None):
        """
        Get the function code.
        :param serviceName: (required, string) name of the service.
        :param functionName: (required, string) name of the function.
        :param qualifier: (optional, string) qualifier of service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including function code information.
        {
            'checksum': 'string',  // CRC64 checksum
            'url': 'string',       // a download url of the code package
        }
        """
        method = 'GET'
        if qualifier:
            serviceName += '{0}{1}'.format(delimiter, qualifier)
        path = '/{0}/services/{1}/functions/{2}/code'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_functions(self, serviceName, limit=None, nextToken=None, prefix=None, startKey=None, headers={}, qualifier=None):
        """
        List the functions of the specified service.
        :param limit: (optional, integer) the total number of the returned services.
        :param nextToken: (optional, string) continue listing the service from the previous point.
        :param prefix: (optional, string) list the services with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param qualifier: (optional, string) qualifier of service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all function information.
        {
            'functions':
            [
                {
                    'codeChecksum': 'string',     // CRC64 checksum
                    'codeSize': 1024,             // in byte
                    'createdTime': 'string',
                    'description': 'string',
                    'functionId': 'string',
                    'functionName': 'string',
                    'handler': 'string',
                    'initializer': 'string',
                    'lastModifiedTime': 'string',
                    'memorySize': 512,            // in MB
                    'runtime': 'string',
                    'timeout': 60,                // in second
                    'initializationTimeout': 30,  // in second
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        if qualifier:
            serviceName += '{0}{1}'.format(delimiter, qualifier)
        path = '/{0}/services/{1}/functions'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def invoke_function(self, serviceName, functionName, payload=None, headers={}, qualifier=None):
        """
        Invoke the function synchronously or asynchronously., default is synchronously.
        :param serviceName: (required, string) the name of the service.
        :param functionName: (required, string) the name of the function.
        :param qualifier: (optional, string) qualifier of service.
        :param payload: (optional, bytes or seekable file-like object): the input of the function.
        :param logType: (optional, string) 'None' or 'Tail'. When invoke a function synchronously,
        you can set the log type to 'Tail' to get the last 4KB base64-encoded function log.
        :param traceId: (optional, string) a uuid to do the request tracing.
        :param headers: (optional, dict) user-defined request header.
                            'x-fc-invocation-type' : require, 'Sync'/'Async' ,only two choice
                            'x-fc-trace-id' : option
                            # other can add user define header
        :return: function output FcHttpResponse object.
        """
        method = 'POST'
        if qualifier:
            serviceName += '{0}{1}'.format(delimiter, qualifier)
        path = '/{0}/services/{1}/functions/{2}/invocations'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers, body=payload)
        if r.headers.get('x-fc-error-type', ''):
            # For custom runtime Error exception
            try:
                errmsg = 'Function execution error: {0}. Path: {1}. Headers: {2}'.format(
                    r.json(), path, r.headers)
            except json.JSONDecodeError:
                errmsg = 'Function execution error. Path: {0}. Headers: {1}'.format(
                    path, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)

        return FcHttpResponse(r.headers, r.content)

    def create_trigger(self, serviceName, functionName, triggerName, triggerType, triggerConfig, sourceArn,
                       invocationRole, headers={}, qualifier=None, description=''):
        """
        Create a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param description: (optional, string), description of trigger.
        :param triggerType: (required, string), the type of trigger. 'oss','log','timer'
        :param triggerConfig: (required, dict), the config of the trigger, different types of trigger has different config.
        :param sourceArn: (optional, string), Aliyun Resource Name（ARN）of the event.In addition to timetrigger, other trigger parameters are required
        :param invocationRole: (optional, string), the role that event source uses to invoke the function.In addition to timetrigger, other trigger parameters are required.
        :param qualifier: (optional, string) qualifier of service.

        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict of the trigger attributes.
        {
            'createdTime': 'string',
            'invocationRole': 'string',
            'lastModifiedTime ': 'string',
            'sourceArn': 'string',
            'triggerConfig': 'dict',
            'triggerName': 'string',
            'triggerType': 'string',
        }
        """
        method = 'POST'
        path = '/{0}/services/{1}/functions/{2}/triggers'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)
        payload = {'triggerName': triggerName, 'description': description, 'triggerType': triggerType, 'triggerConfig': triggerConfig,
                   'sourceArn': sourceArn, 'invocationRole': invocationRole, 'qualifier': qualifier}
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def delete_trigger(self, serviceName, functionName, triggerName, headers={}):
        """
        Delete a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the trigger only when matched the given etag.)
            3, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName,
                                                                     triggerName)
        headers = self._build_common_headers(method, path, headers)
        self._do_request(method, path, headers)

    def update_trigger(self, serviceName, functionName, triggerName, triggerConfig=None, invocationRole=None,
                       headers={}, qualifier=None, description=None):
        """
        Update a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param description: (optional, string), description of trigger.
        :param triggerConfig: (optional, dict), the config of the trigger, different types of trigger has different config.
        :param invocationRole: (optional, string), the role that event source uses to invoke the function.
        :param qualifier: (optional, string) qualifier of service.

        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (update the trigger only when matched the given etag.)
            3, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict of the trigger attributes.
        {
            'createdTime': 'string',
            'invocationRole': 'string',
            'lastModifiedTime ': 'string',
            'sourceArn': 'string',
            'triggerConfig': 'dict',
            'triggerName': 'string',
            'triggerType': 'string',
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName,
                                                                     triggerName)
        headers = self._build_common_headers(method, path, headers)
        payload = {}
        if description:
            payload['description'] = description
        if triggerConfig:
            payload['triggerConfig'] = triggerConfig
        if invocationRole:
            payload['invocationRole'] = invocationRole
        if qualifier:
            payload['qualifier'] = qualifier
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def get_trigger(self, serviceName, functionName, triggerName, headers={}):
        """
        Get a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict of the trigger attributes.
        {
            'createdTime': 'string',
            'invocationRole': 'string',
            'lastModifiedTime ': 'string',
            'sourceArn': 'string',
            'triggerConfig': 'dict',
            'triggerName': 'string',
            'triggerType': 'string',
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName,
                                                                     triggerName)
        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_triggers(self, serviceName, functionName, limit=None, nextToken=None, prefix=None, startKey=None,
                      headers={}):
        """
        List the triggers of the specified function.
        :param limit: (optional, integer) the total number of the returned triggerss.
        :param nextToken: (optional, string) continue listing the triggers from the previous point.
        :param prefix: (optional, string) list the triggers with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all function information.
        {
            'triggers':
            [
                {
                    'createdTime': 'string',
                    'invocationRole': 'string',
                    'lastModifiedTime ': 'string',
                    'sourceArn': 'string',
                    'triggerConfig': 'dict',
                    'triggerName': 'string',
                    'triggerType': 'string',
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/functions/{2}/triggers'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)
        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)
        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def create_custom_domain(self, domainName, protocol=None, routeConfig=None, headers={}, certConfig=None):
        """
        ref: https://help.aliyun.com/document_detail/52877.html?spm=a2c4g.11186623.6.696.1e6d2d2dz4duTM#createCustomDomain
        Create a custom domain.
        :param domainName: name of the custom domain.
        :param protocol: (optional, string), HTTP.
        :param routeConfig: (optional, dict), route configuration, mapping of path and function.
        {
            'routes': [
                {
                    'path': 'string',
                    'serviceName': 'string',
                    'functionName': 'string',
                },
                ...
            ]
        }
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict. For more information, see: https://help.aliyun.com/document_detail/52877.html#createCustomDomain
        {
            'createdTime': 'string',
            'lastModifiedTime': 'string',
            'routeConfig': {
                'routes': 'pathConfig array',
            },
            'protocol': 'string',
            'serviceId': 'string',
            'domainName': 'string',
        }
        """
        method = 'POST'
        path = '/{0}/custom-domains'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        payload = {'domainName': domainName}
        if protocol:
            payload['protocol'] = protocol
        if routeConfig:
            payload['routeConfig'] = routeConfig
        if certConfig:
            payload['certConfig'] = certConfig

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def delete_custom_domain(self, domainName, headers={}):
        """
        Delete the specified custom domain.
        :param domain_name: name of the custom domain.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            3, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/custom-domains/{1}'.format(self.api_version, domainName)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def update_custom_domain(self, domainName, protocol=None, routeConfig=None, headers={}, certConfig=None):
        """
        Update the custom domain attributes.
        :param domainName: name of the custom domain.
        :param protocol: (optional, string), HTTP.
        :param routeConfig: (optional, dict), route configuration, mapping of path and function.
        {
            'routes': [
                {
                    'path': 'string',
                    'serviceName': 'string',
                    'functionName': 'string',
                },
                ...
            ]
        }
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict. For more information, see: https://help.aliyun.com/document_detail/52877.html#createCustomDomain
        {
            'createdTime': 'string',
            'lastModifiedTime': 'string',
            'routeConfig': {
                'routes': 'dict',
            },
            'protocol': 'string',
            'domainName': 'string',
        }
        """
        method = 'PUT'
        path = '/{0}/custom-domains/{1}'.format(self.api_version, domainName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if protocol:
            payload['protocol'] = protocol
        if routeConfig:
            payload['routeConfig'] = routeConfig
        if certConfig:
            payload['certConfig'] = certConfig

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def get_custom_domain(self, domainName, headers={}):
        """
        Get the custom domain configuration.
        :param domainName: (string) name of the custom domain.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict custom domain configuration.
        """
        method = 'GET'
        path = '/{0}/custom-domains/{1}'.format(self.api_version, domainName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_custom_domains(self, limit=None, nextToken=None, prefix=None, startKey=None, headers={}):
        """
        List the custom domains in the current account.
        :param limit: (optional, integer) the total number of the returned services.
        :param nextToken: (optional, string) continue listing the service from the previous point.
        :param prefix: (optional, string) list the services with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all service information.
        {
            'services':
            [
                {
                    'createdTime': 'string',
                    'lastModifiedTime': 'string',
                    'routeConfig': {
                        'routes': 'dict',
                    },
                    'protocol': 'string',
                    'domainName': 'string',
                 },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/custom-domains'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def publish_version(self, serviceName, description=None, headers={}):
        """
        Publish a version.
        :param serviceName: (required, string), name of the service.
        :param description: (optional, string) the readable description of the version.

        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (publish the version only when matched the given etag.)
            3, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict of the version attributes.
        {
            'versionId': 'string',
            'description': 'string',
            'createdTime': 'string',
            'lastModifiedTime ': 'string',
        }
        """
        method = 'POST'
        path = '/{0}/services/{1}/versions'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if description:
            payload['description'] = description

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def list_versions(self, serviceName, limit=None, nextToken=None, startKey=None, direction=None, headers={}):
        """
        List the versions of the current service.
        :param serviceName: (required, string), name of the service.
        :param limit: (optional, integer) the total number of the returned versions.
        :param nextToken: (optional, string) continue listing the version from the previous point.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param direction: (optional, string, default: BACKWARD) list the version with the given direction, "BACKWARD" or "FORWARD".
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all function information.
        {
            'versions':
            [
                {
                    'versionId': 'string',
                    'description': 'string',
                    'createdTime': 'string',
                    'lastModifiedTime': 'string',
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/versions'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('nextToken', nextToken),
                    ('startKey', startKey), ('direction', direction)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def delete_version(self, serviceName, versionId, headers={}):
        """
        Delete a version.
        :param serviceName: (required, string), name of the service.
        :param versionId: (required, string), Id of the version.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/services/{1}/versions/{2}'.format(
            self.api_version, serviceName, versionId)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def create_alias(self, serviceName, aliasName, versionId, description=None, additionalVersionWeight=None, headers={}):
        """
        Create an alias.
        :param serviceName: (required, string), name of the service.
        :param aliasName: (required, string), name of the alias.
        :param versionId: (required, string), versionId referred by the alias.
        :param description: (optional, string) the readable description of the alias.
        :param additionalVersionWeight: (optional, dict), alias can shift some traffic to additional version by specified weight.
            key is versionId, string type.
            Value is weight, float64 type, range [0, 1].

        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict of the version attributes.
        {
            'aliasName': 'string'
            'versionId': 'string',
            'description': 'string',
            'additionalVersionWeight': 'dict',
            'createdTime': 'string',
            'lastModifiedTime': 'string',
        }
        """
        method = 'POST'
        path = '/{0}/services/{1}/aliases'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        payload = {'aliasName': aliasName, 'versionId': versionId}
        if description:
            payload['description'] = description
        if additionalVersionWeight != None:
            payload['additionalVersionWeight'] = additionalVersionWeight
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))

        return FcHttpResponse(r.headers, r.json())

    def get_alias(self, serviceName, aliasName, headers={}):
        """
        Get the alias.
        :param serviceName: (required, string) name of the service.
        :param aliasName: (required, string) name of the alias.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {}
        data: dict alias attributes.
        {
            'aliasName': 'string'
            'versionId': 'string',
            'description': 'string',
            'additionalVersionWeight': 'dict',
            'createdTime': 'string',
            'lastModifiedTime': 'string',
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/aliases/{2}'.format(
            self.api_version, serviceName, aliasName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def update_alias(self, serviceName, aliasName, versionId, description=None, additionalVersionWeight=None, headers={}):
        """
        Update an alias.
        :param serviceName: (required, string), name of the service.
        :param aliasName: (required, string), name of the alias.
        :param versionId: (required, string), versionId referred by the alias.
        :param description: (optional, string) the readable description of the alias.
        :param additionalVersionWeight: (optional, dict), alias can shift some traffic to additional version by specified weight.
            key is versionId, string type.
            Value is weight, float64 type, range [0, 1].

        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (update the alias only when matched the given etag.)
            3, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict of the version attributes.
        {
            'aliasName': 'string'
            'versionId': 'string',
            'description': 'string',
            'additionalVersionWeight': 'dict',
            'createdTime': 'string',
            'lastModifiedTime': 'string',
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}/aliases/{2}'.format(
            self.api_version, serviceName, aliasName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if versionId:
            payload['versionId'] = versionId
        if description:
            payload['description'] = description
        if additionalVersionWeight != None:
            payload['additionalVersionWeight'] = additionalVersionWeight

        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def list_aliases(self, serviceName, limit=None, nextToken=None, prefix=None, startKey=None, headers={}):
        """
        List the aliases in the current service.
        :param serviceName: (required, string), name of the service.
        :param limit: (optional, integer) the total number of the returned aliases.
        :param nextToken: (optional, string) continue listing the aliase from the previous point.
        :param prefix: (optional, string) list the aliases with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all aliase information.
        {
            'aliases':
            [
                {
                    'aliasName': 'string'
                    'versionId': 'string',
                    'description': 'string',
                    'additionalVersionWeight': 'dict',
                    'createdTime': 'string',
                    'lastModifiedTime': 'string',
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/aliases'.format(
            self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def delete_alias(self, serviceName, aliasName, headers={}):
        """
        Delete an aliase.
        :param serviceName: (required, string), name of the service.
        :param aliasName: (required, string), name of the alias.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the alias only when matched the given etag.)
            3, user define key value
        :return: None
        """
        method = 'DELETE'
        path = '/{0}/services/{1}/aliases/{2}'.format(
            self.api_version, serviceName, aliasName)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def tag_resource(self, resourceArn, tags, headers={}):
        """
        Tag on a resource, Currently only services are supported
        :param resourceArn: (required string), Resource ARN. Either full ARN or partial ARN
        :param tags:(required dict), A list of tag keys. At least 1 tag is required. At most 20. Tag key is required, but tag value is optional
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all aliase information.
        {
            'requestId': 'string'
        }
        """
        method = 'POST'
        path = '/{0}/tag'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)
        payload = {
            'resourceArn': resourceArn,
            'tags': tags
        }
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def untag_resource(self, resourceArn, tagKeys, deleteAll=False, headers={}):
        """
        unTag on a resource, Currently only services are supported
        :param resourceArn: (required string), Resource ARN. Either full ARN or partial ARN
        :param tagKeys:(optinal dict), A list of tag keys.
        :param deletaAll: (optinal bool), when tagKeys is empty and deleteAll be True can take effect.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all aliase information.
        {
            'requestId': 'string'
        }
        """
        method = 'DELETE'
        path = '/{0}/tag'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)
        payload = {
            'resourceArn': resourceArn,
            'tagKeys': tagKeys,
            'all': deleteAll
        }
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def get_resource_tags(self, resourceArn,  headers={}):
        """
        get a resource's tags, Currently only services are supported
        :param resourceArn: (required string), Resource ARN. Either full ARN or partial ARN
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all aliase information.
        {
            "requestId": "rid",
            "resourceArn": "acs:fc:cn-shanghai:123456:services/foo",
            "tags": {
                "key1": "value1",
                "key2": ""
            }
        }
        """
        method = 'GET'
        path = '/{0}/tag'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        params = {"resourceArn": resourceArn}
        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def list_reserved_capacities(self, limit=None, nextToken=None, headers={}):
        """
        List the reserved capacities in the current account.
        :param limit: (optional, integer) the total number of the returned reservedCapacities.
        :param nextToken: (optional, string) continue listing the reservedCapacities from the previous point.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict, including all reservedCapacities informations.
        {
            'reservedCapacities':
            [
                {
                    'instanceId': 'string',
                    'cu': 'int',
                    'deadline': 'string',
                    'createdTime': 'string',
                    'lastModifiedTime': 'string',
                    'isRefunded': 'string',
                 },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/reservedCapacities'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('nextToken', nextToken)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def put_on_demand_config(self, serviceName, alias, functionName, maximumInstanceCount, headers={}):
        """
        put on demand config
        :param service_name: name of the service.
        :param alias: name of the service's alias.
        :param functionName: name of the funtion.
        :param maximumInstanceCount: maximumInstanceCount
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        :return dict
        {
            "resource": "services/serviceName.alias/functions/functionName",
            "maximumInstanceCount": 10
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}.{2}/functions/{3}/on-demand-config'.format(
            self.api_version, serviceName, alias, functionName)

        headers = self._build_common_headers(method, path, headers)
        payload = {
            'maximumInstanceCount': maximumInstanceCount,
        }
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def get_on_demand_config(self, serviceName, alias, functionName, headers={}):
        """
        get on demand config
        :param service_name: name of the service.
        :param alias: name of the service's alias.
        :param functionName: name of the funtion.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        :return dict
        {
            "resource": "services/serviceName.alias/functions/functionName",
            "maximumInstanceCount": 10
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}.{2}/functions/{3}/on-demand-config'.format(
            self.api_version, serviceName, alias, functionName)

        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def delete_on_demand_config(self, serviceName, alias, functionName, headers={}):
        """
        delete on demand config
        :param service_name: name of the service.
        :param alias: name of the service's alias.
        :param functionName: name of the funtion.
        :param maximumInstanceCount: maximumInstanceCount
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        """
        method = 'DELETE'
        path = '/{0}/services/{1}.{2}/functions/{3}/on-demand-config'.format(
            self.api_version, serviceName, alias, functionName)

        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, None)

    def list_on_demand_config(self, limit=100, nextToken=None, prefix=None, startKey=None, headers={}):
        """
        list on demand config
        :param limit: (optional, integer) the total number of the returned configs.
        :param nextToken: (optional, string) continue listing the configs from the previous point.
        :param prefix: (optional, string) list the resource with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        :return dict
        {
            "configs": [
                {
                    "resource": "services/serviceName1.qualifier1/functions/functionName1",
                    "maximumInstanceCount": 5
                },
                {
                    "resource": "services/serviceName2.qualifier1/functions/functionName2",
                    "maximumInstanceCount": 10
                }
            ],
            "nextToken": "token"
        }
        """
        method = 'GET'
        path = '/{0}/on-demand-configs'.format(self.api_version)

        paramlst = [('limit', limit), ('prefix', prefix),
                    ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)

        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def put_provision_config(self, serviceName, qualifier, functionName, target, headers={}):
        """
        put provision config
        :param service_name: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param target: number of provision
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (delete the service only when matched the given etag.)
            3, user define key value
        :return dict
        {
            "resource": "123456#service555#alias#testf1",
            "target": 10
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}.{2}/functions/{3}/provision-config'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)
        payload = {
            'target': target,
        }
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def get_provision_config(self, serviceName, qualifier, functionName, headers={}):
        """
        get provision config
        :param service_name: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return dict
        {
            "resource": "123456#service555#alias#testf1",
            "target": 10 ,
            "current": 0,
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}.{2}/functions/{3}/provision-config'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_provision_configs(self, serviceName, qualifier,  limit=None, nextToken=None, headers={}):
        """
        List the provision configin the current service.
        :param serviceName: (optional, string), name of the service.
        :param qualifier (optional, string): name of the service's alias.
        :param limit: (optional, integer) the total number of the returned aliases.
        :param nextToken: (optional, string) continue listing the aliase from the previous point.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict
        {
            "provisionConfigs": [
                {
                "resource": "123456#service555#alias#testf1",
                "target": 10,
                "current": 0
                }
            ],
            "nextToken": ""
        }
        """
        if qualifier and (not serviceName):
            raise Exception(
                'serviceName is required when qualifier is not empty')
        method = 'GET'
        path = '/{0}/provision-configs'.format(self.api_version)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('serviceName', serviceName), ('qualifier', qualifier),
                    ('limit', limit), ('nextToken', nextToken)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def put_function_async_invoke_config(self, serviceName, qualifier, functionName, asyncConfig, headers={}):
        """
        put function async invoke config
        :param serviceName: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param asyncConfig: config for async invocation
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return dict
        {
            "service": "service",
            "function": "function",
            "createTime": "",
            "qualifier": "LATEST",
            "destinationConfig": "",
            "maxAsyncEventAgeInSeconds": 5000,
            "maxAsyncRetryAttempts": 1,
            "lastModifiedTime": ""
        }
        """
        method = 'PUT'
        path = '/{0}/services/{1}.{2}/functions/{3}/async-invoke-config'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)
        payload = asyncConfig
        r = self._do_request(method, path, headers,
                             body=json.dumps(payload).encode('utf-8'))
        return FcHttpResponse(r.headers, r.json())

    def get_function_async_invoke_config(self, serviceName, qualifier, functionName, headers={}):
        """
        get function async invoke config
        :param serviceName: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return dict
        {
            "service": "service",
            "function": "function",
            "createTime": "",
            "qualifier": "LATEST",
            "destinationConfig": "",
            "maxAsyncEventAgeInSeconds": 5000,
            "maxAsyncRetryAttempts": 1,
            "lastModifiedTime": ""
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}.{2}/functions/{3}/async-invoke-config'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_function_async_invoke_configs(self, serviceName, functionName, limit=None, nextToken=None, headers={}):
        """
        List the async configs for the current service and function.
        :param serviceName: (optional, string), name of the service.
        :param functionName: name of the funtion.
        :param qualifier (optional, string): name of the service's alias.
        :param limit: (optional, integer) the total number of the returned aliases.
        :param nextToken: (optional, string) continue listing the aliase from the previous point.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict
        data: dict
        {
            "configs": [
                {
                  "service": "destination-suite",
                  "function": "function-py",
                  "createdTime": "",
                  "qualifier": "",
                  "lastModifiedTime": "xxx",
                  "destinationConfig": {
                    "onSuccess": {
                      "destination": "xxx"
                    },
                    "onFailure": {
                      "destination": "xxx"
                    }
                  },
                  "maxAsyncEventAgeInSeconds": 5,
                  "maxAsyncRetryAttempts": 0
                }
            ],
            "nextToken": ""
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/functions/{2}/async-invoke-configs'.format(
            self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit', limit), ('nextToken', nextToken)]
        params = dict((k, v) for k, v in paramlst if v)

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

    def delete_function_async_invoke_config(self, serviceName, qualifier, functionName, headers={}):
        """
        delete function async invoke config
        :param serviceName: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        """
        method = 'DELETE'
        path = '/{0}/services/{1}.{2}/functions/{3}/async-invoke-config'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def list_instances(self, serviceName, qualifier, functionName, params={}, headers={}):
        """
        list instances
        :param serviceName: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param params: 
            limit: limit the number of instances returned
            instanceIds: limit to return specified instances
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        """
        method = 'GET'
        path = '/{0}/services/{1}.{2}/functions/{3}/instances'.format(
            self.api_version, serviceName, qualifier, functionName)

        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers, params)
        return FcHttpResponse(r.headers, r.json())

    def instance_exec(self, serviceName, qualifier, functionName, instance_id, params={}, hooks={}, headers={}):
        """
        Execute the command within the instance
        :param serviceName: name of the service.
        :param qualifier: name of the service's alias.
        :param functionName: name of the funtion.
        :param instance_id: name of the instance 
        :param params
            command: initial command
            stdin: enable stdin
            stdout: enable stdout
            stderr: enable stderr
            tty: enable tty
            idleTimeout: no operation disconnect time 
        :param hooks
            on_open: callback on opened
            on_stdout: callback on got stdout
            on_stderr: callback on got stderr
            on_error: callback on got error
            on_close: callback on closed
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        """
        url = '/{0}/services/{1}.{2}/functions/{3}/instances/{4}/exec'.format(
            self.api_version,
            serviceName, qualifier,
            functionName, instance_id,
        )

        ws = self.websocket(url, params)
        return ExecWebsocket(
            ws,
            on_open=hooks.get('on_open'),
            on_stdout=hooks.get('on_stdout'),
            on_stderr=hooks.get('on_stderr'),
            on_error=hooks.get('on_error'),
            on_close=hooks.get('on_close'),
        )


class ExecWebsocket(object):
    def __init__(self, ws: websocket.WebSocketApp, on_open=None, on_stdout=None, on_stderr=None, on_error=None, on_close=None):
        self.ws = ws
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self.on_stdout = on_stdout
        self.on_stderr = on_stderr

        self.ws.on_open = self.__on_open
        self.ws.on_message = self.__on_message
        self.ws.on_error = self.__on_error
        self.ws.on_close = self.__on_close

    def __on_open(self, ws):
        if self.on_open != None:
            threading.Thread(target=self.on_open, args=(self,)).start()

    def __on_message(self, ws, msg):
        message_type = ord(msg[0])
        message = msg[1:]
        if message_type == 1:
            if self.on_stdout != None:
                self.on_stdout(self, message)
        elif message_type == 2:
            if self.on_stderr != None:
                self.on_stderr(self, message)
        elif message_type == 3:
            error = "Server error: %s" % message
            self.__on_error(ws, error)
        else:
            error = Exception('unknown message type: %s' % message_type)
            if self.on_error != None:
                self.on_error(self, error)

    def __on_error(self, ws, error):
        if self.on_error != None:
            self.on_error(self, error)

    def __on_close(self, ws, *arg):
        if self.on_close != None:
            self.on_close(self)

    def send(self, data):
        data = chr(0) + data
        self.ws.send(data)

    def start(self):
        self.ws.run_forever()

    def close(self):
        self.ws.close()


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
