#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
from base import BaseServer
from main import MainServer
from stream import MisuraDirectory
from misura.canon import determine_path
cert_dir = determine_path(__file__)