# -*- coding: utf-8 -*-

class FcError(Exception):
    def __init__(self, message, status_code, err_code = '', request_id = ''):
        super(Exception, self).__init__()
        self.message = message
        self.status_code = status_code
        self.err_code = err_code
        self.request_id = request_id


FC_ERR_CODE_LST = (
    'PathNotSupported',
    'InvalidArgument',
    'ResourceExhausted',
    'MalformedPOSTRequest',
    'ServiceAlreadyExists',
    'ServiceNotFound',
    'ServiceNotEmpty',
    'FunctionAlreadyExists',
    'FunctionNotFound',
    'FunctionNotEmpty',
    'TriggerAlreadyExists',
    'TriggerNotFound',
    'InternalServerError',
    'ConcurrentUpdateError',
    'PreconditionFailed',
    'AccessDenied',
    'EntityTooLarge',
    'CrossAccountAccessDenied',
    'SignatureNotMatch',
    'RequestTimeTooSkewed',
    'InvalidAccessKeyID',
    'UnsupportedMediaType',
    'MissingRequiredHeader',
    'ResourceThrottled',
)

_FC_ERROR_TO_EXCEPTION = {}

def _walk_fc_exceptions_class():
    for err_code in FC_ERR_CODE_LST:
        ErrorClass = type(err_code, (FcError, ), {})
        _FC_ERROR_TO_EXCEPTION[err_code] = ErrorClass

_walk_fc_exceptions_class()


def get_fc_error(message, status, err_code = '', request_id = ''):
    ErrorClass = _FC_ERROR_TO_EXCEPTION.get( str(err_code) )
    if ErrorClass:
        return ErrorClass(message, status, err_code, request_id)

    return FcError(message, status, err_code, request_id)