# -*- coding: utf-8 -*-

class FcError(Exception):
    def __init__(self, message, status):
        super(Exception, self).__init__(message, status)
        self.message = message
        self.status = status


def get_fc_error(message, status):
    if isinstance(message, dict):
        err_code = message.get('ErrorCode')
        if err_code:
            ErrorClass = type(str(err_code), (FcError, ), {})
            return ErrorClass(message, status)

    return FcError(message, status)