# -*- coding: utf-8 -*-

import logging

counter = 0
def my_initializer(context):
    logger = logging.getLogger()
    global counter
    counter += 1
    logger.info(counter)

def my_handler(event, context):
    logger = logging.getLogger()
    global counter
    counter += 1
    logger.info(counter)
    return counter