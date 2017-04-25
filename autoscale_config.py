#!/usr/bin/env python
# encoding: utf-8

import ConfigParser
import os


def getConfig(section, key):
    config = ConfigParser.ConfigParser()
    path = os.path.split(os.path.realpath(__file__))[0] + '/autoscale.conf'
    config.read(path)
    return config.get(section, key)
