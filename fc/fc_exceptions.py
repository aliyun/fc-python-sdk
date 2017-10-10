# -*- coding: utf-8 -*-

class FcError(Exception):
    def __init__(self, message, status):
        super(Exception, self).__init__(message, status)
        self.message = message
        self.status = status