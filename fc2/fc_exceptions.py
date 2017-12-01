# -*- coding: utf-8 -*-

class FcError(Exception):
    def __init__(self, message, status_code, err_code = '', request_id = ''):
        super(FcError, self).__init__(message, status_code, err_code, request_id)
        self.message = message
        self.status_code = status_code
        self.err_code = err_code
        self.request_id = request_id

def get_fc_error(message, status, err_code = '', request_id = ''):
    return FcError(message, status, err_code, request_id)