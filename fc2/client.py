# -*- coding: utf-8 -*-

import base64
import requests
import logging
import email
import io
import json
from . import __version__
from . import auth
from . import util
from . import fc_exceptions
import platform
import sys

_ver = sys.version_info
if _ver[0] == 2:
    from urllib import unquote as unescape
elif _ver[0] == 3:
    from urllib.parse import unquote as unescape


class Client(object):
    def __init__(self, **kwargs):
        endpoint = kwargs.get('endpoint', None)
        if not endpoint:
            raise ValueError('A valid Endpoint parameter must be specified to construct the Client object.')
        access_key_id = kwargs.get("accessKeyID", None)
        if not access_key_id:
            raise ValueError('A valid AccessKeyID parameter must be specified to construct the Client object.')
        access_key_secret = kwargs.get('accessKeySecret', None)
        if not access_key_secret:
            raise ValueError('A valid AccessKeySecret parameter must be specified to construct the Client object.')
        security_token = kwargs.get('securityToken', '')
        self.endpoint = Client._normalize_endpoint(endpoint)
        self.host = Client._get_host(endpoint)
        self.api_version = '2016-08-15'
        self.user_agent = \
            'aliyun-fc-sdk-v{0}.python-{1}.{2}-{3}-{4}'.\
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

    def _build_common_headers(self, method, path, customHeaders = {}, unescaped_queries=None):
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
        headers['authorization'] = self.auth.sign_request(method, path, headers, unescaped_queries)

        return headers

    def do_http_request(self, method, serviceName, functionName, path, headers={}, params=None, body=None):
        path = '/{0}/proxy/{1}/{2}/{3}'.format(self.api_version, serviceName, functionName, path)
        url = '{0}{1}'.format(self.endpoint, path)
        headers = self._build_common_headers(method, unescape(path), headers, params)
        logging.debug('Do http request. Method: {0}. URL: {1}. Params: {2}. Headers: {3}'.format(method, url, params, headers))
        r = requests.request(method, url, headers=headers, params=params, data=body, timeout=self.timeout)
        return r

    def _do_request(self, method, path, headers, params=None, body=None):
        url = '{0}{1}'.format(self.endpoint, path)
        logging.debug('Perform http request. Method: {0}. URL: {1}. Headers: {2}'.format(method, url, headers))
        r = requests.request(method, url, headers=headers, params=params, data=body, timeout=self.timeout)

        if r.status_code < 400:
            logging.debug(
                'Http status code: {0}. Method: {1}. URL: {2}. Headers: {3}'.format(
                    r.status_code, method, url, r.headers))
        elif 400 <= r.status_code < 500:
            errmsg = \
                'Client error: {0}. Message: {1}. Method: {2}. URL: {3}. Request headers: {4}. Response headers: {5}'.\
                format(r.status_code, r.json(), method, url, headers, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)
        elif 500 <= r.status_code < 600:
            errmsg = \
                'Server error: {0}. Message: {1}. Method: {2}. URL: {3}. Request headers: {4}. Response headers: {5}'. \
                format(r.status_code, r.json(), method, url, headers, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)

        return r

    def __gen_request_err(self, r):
        err_d = r.json()
        err_d['RequestId'] = r.headers.get('X-Fc-Request-Id','unknown')
        err_code = err_d.get('ErrorCode', '')
        err_msg = json.dumps(err_d)
        return fc_exceptions.get_fc_error(err_msg, r.status_code, err_code, err_d['RequestId'])

    def create_service(self, serviceName, description=None, logConfig=None, role=None, headers={}):
        """
        Create a service.
        :param serviceName: name of the service.
        :param description: (optional, string), detail description of the service.
        :param logConfig: (optional, dict), log configuration.
        {
            'project': 'string',
            'logStore': 'string',
        }
        :param role: The Aliyun Resource Name (ARN) of the RAM role that FunctionCompute assumes when it executes
        your function to access any other Aliyun resources.
        For more information, see: https://help.aliyun.com/document_detail/52885.html
        :param headers, oprional, 'x-fc-trace-id': string (a uuid to do the request tracing), etc
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

        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
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

    def update_service(self, serviceName, description=None, logConfig=None, role=None, headers={}):
        """
        Update the service attributes.
        :param serviceName: name of the service.
        :param description: (optional, string), detail description of the service.
        :param logConfig: (optional, dict), log configuration.
        {
            'project': 'string',
            'logStore': 'string',
        }
        :param role: The Aliyun Resource Name (ARN) of the RAM role that FunctionCompute assumes when it executes
        your function to access any other Aliyun resources.
        For more information, see: https://help.aliyun.com/document_detail/52885.html
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, 'if-match': string (update the service only when matched the given etag.)
            3, user define key value
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

        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def get_service(self, serviceName, headers={}):
        """
        Get the service configuration.
        :param serviceName: (string) name of the service.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict service configuration.
        """
        method = 'GET'
        path = '/{0}/services/{1}'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_services(self, limit=None, nextToken=None, prefix=None, startKey=None, headers={}):
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

        paramlst = [('limit',  limit), ('prefix', prefix), ('nextToken', nextToken), ('startKey', startKey)]
        params = dict( (k,v) for k, v in paramlst if v )

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
                raise Exception('codeOSSBucket and codeOSSObject must to exist at the same time')
            code_d['oss'] = (codeOSSBucket, codeOSSObject)

        if len(code_d) == 0:
            raise Exception('codeZipFile, codeDir, (codeOSSBucket, codeOSSObject) , these three parameters must have an assignment')

        if len(code_d) > 1:
            raise Exception('codeZipFile, codeDir, (codeOSSBucket, codeOSSObject) , these three parameters need only one paramet$er assignment')

        return True


    def create_function(
            self, serviceName, functionName, runtime, handler,
            codeZipFile=None, codeDir=None, codeOSSBucket=None, codeOSSObject=None,
            description=None, memorySize=256, timeout=60, headers={}, environmentVariables=None):
        """
        Create a function.
        :param serviceName: (required, string) the name of the service that the function belongs to.
        :param functionName: (required, string) the name of the function.
        :param runtime: (required, string) the runtime type. For example, nodejs4.4, python2.7 and etc.
        :param handler: (required, string) the entry point of the function.
        :param codeZipFile: (optional, string) the file path of the zipped code.
        :param codeDir: (optional, string) the directory of the code.
        :param codeOSSBucket: (optional, string) the oss bucket where the code located in.
        :param codeOSSObject: (optional, string) the zipped code stored as a OSS object.
        :param description: (optional, string) the readable description of the function.
        :param memorySize: (optional, integer) the memory size of the function, in MB.
        :param timeout: (optional, integer) the max execution time of the function, in second.
        :param environmentVariables: (optional, dict) the environment variables of the function, both key and value are string type.
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
            'lastModifiedTime': 'string',
            'memorySize': 512,            // in MB
            'runtime': 'string',
            'timeout': 60,                // in second
        }
        """
        serviceName, functionName, runtime, handler, memorySize, timeout = \
             str(serviceName), str(functionName), str(runtime), str(handler), int(memorySize), int(timeout)

        codeZipFile = str(codeZipFile) if codeZipFile else codeZipFile
        codeDir = str(codeDir) if codeDir else codeDir
        codeOSSBucket = str(codeOSSBucket) if codeOSSBucket else codeOSSBucket
        codeOSSObject = str(codeOSSObject) if codeOSSObject else codeOSSObject
        self._check_function_param_valid(codeZipFile, codeDir, codeOSSBucket, codeOSSObject)

        method = 'POST'
        path = '/{0}/services/{1}/functions'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        payload = {'functionName': functionName, 'runtime': runtime, 'handler': handler}
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
            payload['code'] = {'ossBucketName': codeOSSBucket, 'ossObjectName': codeOSSObject}

        if description:
            payload['description'] = description

        if memorySize:
            payload['memorySize'] = memorySize

        if timeout:
            payload['timeout'] = timeout

        if environmentVariables != None:
            payload['environmentVariables'] = environmentVariables

        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def update_function(
            self, serviceName, functionName,
            codeZipFile=None, codeDir=None, codeOSSBucket=None, codeOSSObject=None,
            description=None, handler=None, memorySize=None, runtime=None, timeout=None,
            headers={}, environmentVariables=None):
        """
        Update the function.
        :param serviceName: (required, string) the name of the service that the function belongs to.
        :param functionName: (required, string) the name of the function.
        :param runtime: (required, string) the runtime type. For example, nodejs4.4, python2.7 and etc.
        :param handler: (required, string) the entry point of the function.
        :param codeZipFile: (optional, string) the file path of the zipped code.
        :param codeDir: (optional, string) the directory of the code.
        :param codeOSSBucket: (optional, string) the oss bucket where the code located in.
        :param codeOSSObject: (optional, string) the zipped code stored as a OSS object.
        :param description: (optional, string) the readable description of the function.
        :param memorySize: (optional, integer) the memory size of the function, in MB.
        :param timeout: (optional, integer) the max execution time of the function, in second.
        :param etag: (optional, string) delete the service only when matched the given etag.
        :param environmentVariables: (optional, dict) the environment variables of the function, both key and value are string type.
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
            'lastModifiedTime': 'string',
            'memorySize': 512,            // in MB
            'runtime': 'string',
            'timeout': 60,                // in second
        }
        """
        serviceName, functionName = str(serviceName), str(functionName)
        handler = str(handler) if handler else handler
        runtime = str(runtime) if runtime else runtime
        memorySize = int(memorySize) if memorySize else memorySize
        timeout = int(timeout) if timeout else timeout
        codeZipFile = str(codeZipFile) if codeZipFile else codeZipFile
        codeDir = str(codeDir) if codeDir else codeDir
        codeOSSBucket = str(codeOSSBucket) if codeOSSBucket else codeOSSBucket
        codeOSSObject = str(codeOSSObject) if codeOSSObject else codeOSSObject

        method = 'PUT'
        path = '/{0}/services/{1}/functions/{2}'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        payload = {}
        if runtime:
            payload['runtime'] = runtime

        if handler:
            payload['handler'] = handler

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
            payload['code'] = {'ossBucketName': codeOSSBucket, 'ossObjectName': codeOSSObject}

        if description:
            payload['description'] = description

        if memorySize:
            payload['memorySize'] = memorySize

        if timeout:
            payload['timeout'] = timeout

        if environmentVariables != None:
            payload['environmentVariables'] = environmentVariables

        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
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
        path = '/{0}/services/{1}/functions/{2}'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        self._do_request(method, path, headers)

    def get_function(self, serviceName, functionName, headers={}):
        """
        Get the function configuration.
        :param serviceName: (required, string) name of the service.
        :param functionName: (required, string) name of the function.
        :param headers, optional
            1, 'x-fc-trace-id': string (a uuid to do the request tracing)
            2, user define key value
        :return: FcHttpResponse
        headers: dict {'etag':'string', ...}
        data: dict function configuration.
        """
        method = 'GET'
        path = '/{0}/services/{1}/functions/{2}'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        # 'etag' now in headers
        return FcHttpResponse(r.headers, r.json())

    def get_function_code(self, serviceName, functionName, headers={}):
        """
        Get the function code.
        :param serviceName: (required, string) name of the service.
        :param functionName: (required, string) name of the function.
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
        path = '/{0}/services/{1}/functions/{2}/code'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_functions(self, serviceName, limit=None, nextToken=None, prefix=None, startKey=None, headers={}):
        """
        List the functions of the specified service.
        :param limit: (optional, integer) the total number of the returned services.
        :param nextToken: (optional, string) continue listing the service from the previous point.
        :param prefix: (optional, string) list the services with the given prefix.
        :param startKey: (optional, string) startKey is where you want to start listing from.
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
                    'lastModifiedTime': 'string',
                    'memorySize': 512,            // in MB
                    'runtime': 'string',
                    'timeout': 60,                // in second
                },
                ...
            ],
            'nextToken': 'string'
        }
        """
        method = 'GET'
        path = '/{0}/services/{1}/functions'.format(self.api_version, serviceName)
        headers = self._build_common_headers(method, path, headers)

        paramlst = [('limit',  limit), ('prefix', prefix), ('nextToken', nextToken), ('startKey', startKey)]
        params = dict( (k,v) for k, v in paramlst if v )

        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())


    def invoke_function(self, serviceName, functionName, payload=None, headers = {}):

        """
        Invoke the function synchronously or asynchronously., default is synchronously.
        :param serviceName: (required, string) the name of the service.
        :param functionName: (required, string) the name of the function.
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
        path = '/{0}/services/{1}/functions/{2}/invocations'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)

        r = self._do_request(method, path, headers, body=payload)
        if r.headers.get('x-fc-error-type', ''):
            errmsg = 'Function execution error: {0}. Path: {1}. Headers: {2}'.format(
                r.json(), path, r.headers)
            logging.error(errmsg)
            raise self.__gen_request_err(r)

        return FcHttpResponse(r.headers, r.content)

    def create_trigger(self, serviceName, functionName, triggerName, triggerType, triggerConfig, sourceArn, invocationRole, headers={}):
        """
        Create a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param triggerType: (required, string), the type of trigger. 'oss','log','timer'
        :param triggerConfig: (required, dict), the config of the trigger, different types of trigger has different config.
        :param sourceArn: (optional, string), Aliyun Resource Name（ARN）of the event.In addition to timetrigger, other trigger parameters are required
        :param invocationRole: (optional, string), the role that event source uses to invoke the function.In addition to timetrigger, other trigger parameters are required.

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
        path = '/{0}/services/{1}/functions/{2}/triggers'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)
        payload = {'triggerName': triggerName, 'triggerType': triggerType, 'triggerConfig': triggerConfig, 'sourceArn': sourceArn, 'invocationRole': invocationRole}
        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
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
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName, triggerName)
        headers = self._build_common_headers(method, path, headers)
        self._do_request(method, path, headers)

    def update_trigger(self, serviceName, functionName, triggerName, triggerConfig=None, invocationRole=None, headers={}):
        """
        Update a trigger.
        :param serviceName: (required, string), name of the service that the trigger belongs to.
        :param functionName: (required, string), name of the function that the trigger belongs to.
        :param triggerName: (required, string), name of the trigger.
        :param triggerConfig: (optional, dict), the config of the trigger, different types of trigger has different config.
        :param invocationRole: (optional, string), the role that event source uses to invoke the function.

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
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName, triggerName)
        headers = self._build_common_headers(method, path, headers)
        payload = {}
        if triggerConfig:
            payload['triggerConfig'] = triggerConfig
        if invocationRole:
            payload['invocationRole'] = invocationRole
        r = self._do_request(method, path, headers, body=json.dumps(payload).encode('utf-8'))
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
        path = '/{0}/services/{1}/functions/{2}/triggers/{3}'.format(self.api_version, serviceName, functionName, triggerName)
        headers = self._build_common_headers(method, path, headers)
        r = self._do_request(method, path, headers)
        return FcHttpResponse(r.headers, r.json())

    def list_triggers(self, serviceName, functionName, limit=None, nextToken=None, prefix=None, startKey=None, headers={}):
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
        path = '/{0}/services/{1}/functions/{2}/triggers'.format(self.api_version, serviceName, functionName)
        headers = self._build_common_headers(method, path, headers)
        paramlst = [('limit', limit), ('prefix', prefix), ('nextToken', nextToken), ('startKey', startKey)]
        params = dict((k, v) for k, v in paramlst if v)
        r = self._do_request(method, path, headers, params=params)
        return FcHttpResponse(r.headers, r.json())

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
