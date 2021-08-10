import os
import shlex
import subprocess
from .pteredor import teredo_prober

import utils
from xlog import getLogger
xlog = getLogger("gae_proxy")

current_path = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.abspath(os.path.join(current_path, os.pardir, os.pardir, os.pardir))
data_path = os.path.abspath(os.path.join(root_path, os.pardir, os.pardir, 'data', "gae_proxy"))
if not os.path.isdir(data_path):
    data_path = current_path

log_file = os.path.join(data_path, "ipv6_tunnel.log")

if os.path.isfile(log_file):
    os.remove(log_file)

class Log(object):
    def __init__(self):
        self.fd = open(log_file, "a")
    
    def write(self, content):
        self.fd.write(content + "\n")
        self.fd.flush()
    
    def close(self):
        self.fd.close()

pteredor_is_running = False

def new_pteredor(probe_nat = True):
    if os.path.isfile(log_file):
        try:
            os.remove(log_file)
        except Exception as e:
            xlog.warn("remove %s fail:%r", log_file, e)
    
    global pteredor_is_running, usable
    pteredor_is_running = probe_nat
    prober = teredo_prober(probe_nat=probe_nat)

    if prober.nat_type in ('cone', 'restricted'):
        usable = 'usable'
    elif probe.nat_type == 'offline':
        usable = 'unusable'
    else:
        usable = 'unknown'
    
    if probe_nat:
        pteredor_is_running = False
        log = Log()
        log.write('qualified')