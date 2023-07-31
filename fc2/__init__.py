# -*- coding: utf-8 -*-

"""
Aliyun FunctionCompute SDK.
https://www.aliyun.com/product/fc
"""

__author__ = "xiliu Aliyun Function Compute"
__version__ = "0.0.1"

from .client import Client
from .fc_exceptions import FcError

# Set default logging handler to avoid "No handler found" warnings.
import logging

try:  # Python2.7+
    from logging import NullHandler
except ImportError:

    class NullHandler(logging.Handler):
        def emit(self, record):
            pass


logging.getLogger(__name__).addHandler(NullHandler())
