# -*- coding: utf-8 -*-

import requests
import hashlib
import hmac
import base64


class Auth(object):
    def __init__(self, access_key_id, access_key_secret, security_token=""):
        self.id = access_key_id.strip()
        self.secret = access_key_secret.strip()
        self.security_token = security_token.strip()

    def __call__(self, r):
        return r

    def sign_request(self, method, path, headers):
        """
        Sign the request. See the spec for reference.
        https://help.aliyun.com/document_detail/52877.html
        :param method: method of the http request.
        :param headers: headers of the http request.
        :param path: path of the http request.
        :return: the signature string.
        """
        content_md5 = headers.get('content-md5', '')
        content_type = headers.get('content-type', '')
        date = headers.get('date', '')
        canonical_headers = Auth._build_canonical_headers(headers)
        canonical_resource = path
        string_to_sign = '\n'.join(
            [method.upper(), content_md5, content_type, date, canonical_headers + canonical_resource])
        h = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256)
        signature = 'FC ' + self.id + ':' + base64.b64encode(h.digest()).decode('utf-8')
        return signature

    @staticmethod
    def _build_canonical_headers(headers):
        """
        :param headers: :class:`Request` object
        :return: Canonicalized header string.
        :rtype: String
        """
        canonical_headers = []
        for k, v in headers.items():
            lower_key = k.lower()
            if lower_key.startswith('x-fc-'):
                canonical_headers.append((lower_key, v))
        canonical_headers.sort(key=lambda x: x[0])
        if canonical_headers:
            return '\n'.join(k + ':' + v for k, v in canonical_headers) + '\n'
        else:
            return ''


