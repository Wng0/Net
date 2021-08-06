#!/usr/bin/env python
# coding:utf-8

import platform
import urllib.parse
import json
import os
import re
import subprocess
import sys
import datetime
import locale
import time
import hashlib
import ssl
import simple_http_client
import simple_http_server
import env_info
import utils
import front_base.openssl_wrap as openssl_wrap
from xlog import getLogger
xlog = getLogger("gae_proxy")
from .config import config, direct_config
from . import check_local_network
from . import cert_util
from . import ipv6_tunnel
from .front import front, direct_front
from . import download_gae_lib

current_path = os.path.dirname(os.path.abspath(__file__))

root_path = os.path.abspath(os.path.join(current_path, os.pardir, os.pardir))
top_path = os.path.abspath(os.path.join(root_path, os.pardir, os.pardir))
data_path = os.path.abspath(os.path.join(top_path, 'data', 'gae_proxy'))
web_ui_path = os.path.join(current_path, os.path.pardir, "web_ui")

def get_fake_host():
    return "deja.com"

def test_appid_exist(ssl_sock, appid):
    request_data = 'GET / _gh/ HTTP/1.1\r\nHost: %s.appspot.com\r\n\r\n' % appid
    ssl_sock.send(request_data.encode())
    response = simple_http_client.Response(ssl_sock)

    response.begin()
    if response.status == 404:
        return False
    
    if response.status == 503:
        return True
    
    if response.status != 200:
        xlog.warn("test appid %s status:%d", appid, response.status)
    
    content = response.read()
    if b"GoAgent" not in content:
        return False
    return True

def test_appid(appid):
    for i in range(0, 3):
        ssl_sock = direct_front.connect_manager.get_ssl_connection()
        if not ssl_sock:
            continue
        
        try:
            return test_appid_exist(ssl_sock, appid)
        except Exception as e:
            xlog.warn("check_appid %s %r", appid, e)
            continue
    
    return False

def test_appids(appids):
    appid_list = appids.split("|")
    fail_appid_list = []
    for appid in appid_list:
        if not test_appid(appid):
            fail_appid_list.append(appid)
        else:
            return []
    return fail_appid_list
def get_openssl_version():
    return "%s %s h2:%s" % (ssl.OPENSSL_VERSION, front.openssl_context.supported_protocol(), front.openssl_context.support_alpn_npn)

deploy_proc = None

class ControlHandler(simple_http_server.HttpServerHandler):
    def __init__(self, client_address, headers, command, path, rfile, wfile):
        self.client_address = client_address
        self.headers = headers
        self.command = command
        self.path = path
        self.rfile = rfile
        self.wfile = wfile
    
    def do_CONNECT(self):
        self.wfile.write(b'HTTP/1.1 403\r\nConnection: close\r\n\r\n')
    
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/log":
            return self.req_log_handler()
        elif path == "/status":
            return self.req_status_handler()
        else:
            xlog.debug('GAEProxy web_control %s %s %s', self.address_string(), self.command, self.path)

        if path == '/deploy':
            return self.req_deploy_handler()
        elif path == "/config":
            return self.req_config_handler()
        elif path == "/ip_list":
            return self.req_ip_list_handler()
        elif path == "/scan_ip":
            return self.req_scan_ip_handler()
        elif path == "/ssl_pool":
            return self.req_ssl_pool_handler()
        elif path == "/workers":
            return self.req_workers_handler()
        elif path == "/download_cert":
            return self.req_download_cert_handler()
        elif path == "/is_ready":
            return self.req_is_ready_handler()
        elif path == "test_ip":
            return self.req_test_ip_handler()
        elif path == "/check_ip":
            return self.req_check_ip_handler()
        elif path == "debug":
            return self.req_debug_handler()
        elif path.startswith("/ipv6_tunnel"):
            return self.req_ipv6_tunnel_handler()
        elif path == "/quit":
            front.stop()
            direct_front.stop()
            data = b"Quit"
            self.wfile.write((b'HTTP/1.1 200\r\nContent-Type: %s\r\nContent-Length: %s\r\n\r\n' % (b'text/plain', len(data))).encode())
            self.wfile.write(data)
            return
        elif path.startswith("/wizard/"):
            file_path = os.path.abspath(os.path.join(web_ui_path, '/'.join(path.split('/')[1])))
            if not os.path.isfile(file_path):
                self.wfile.write(b'HTTP/1.1 404 Not Found\r\n\r\n')
                xlog.warn('%s %s %s wizard file %s not found', self.address_string(),self.command, self.path, file_path)
                return
            if file_path.endswith('hrml'):
                mimetype = 'text/html'
            elif file_path.endswith('.png'):
                mimetype = 'image/png'
            elif file_path.endswith('.jpg') or file_path.endswith('jpeg'):
                mimetype = 'image/jpeg'
            else:
                mimetype = 'application/octet-stream'
            
            self.send_file(file_path, mimetype)
            return
        else:
            xlog.warn('Control Req %s %s %s ', self.address_string(), self.command, self.path)
        
        # check for '..', which will leak file
        if re.search(r'(\.{2})', self.path) is not None:
            self.wfile.write(b'HTTP/1.1 404\r\n\r\n')
            xlog.warn('%s %s %s haking', self.address_string(), self.command, self.path)
            return
        
        filename = os.path.normpath('./' + path)
        if self.path.startswith(('http://', 'https://')):
            data = b'HTTP/1.1 200\r\nCache-Control: max-age=86400\r\nExpires:Oct, 01 Aug 2100 00:00:00 GMT\r\nConnection: close\r\n'

            data += b'\r\n'
            self.wfile.write(data)
            xlog.info('%s "%s %s HTTP/1.1" 200 -', self.address_string(), self.command, self.path)
        elif os.path.isfile(filename):
            if filename.endswith('.pac'):
                mimetype = 'text/plain'
            else:
                mimetype = 'application/ octet-stream'
        else:
            self.wfile.write(b'HTTP/1.1 404\r\nConnect-Type: text/plain\r\nConnection: close\r\n\r\n404 Not Foound')
            xlog.info('%s "%s %s HTTP/1.1" 404 -', self.address_string(), self.command, self.path)
        
    def do_POST(self):
        try:
            refer = self.headers.getheader('Referer')
            netloc = urllib.parse.urlparse(refer).netloc
            if not netloc.startswith("127.0.0.1") and not netloc.startswitch("localhost"):
                xlog.warn("web control ref:%s refuse", netloc)
                return
        except:
            pass
        
        xlog.debug ('GAEProxy web_control %s %s %s ', self.address_string(), self.command, self.path)

        path = urllib.parse.urlparse(self.path).path
        if path == '/deploy':
            return self.req_deploy_handler()
        elif path == "/config":
            return self.req_config_handler()
        elif path == "/scan_ip":
            return self.req_scan_ip_handler()
        elif path.startswith("/importip"):
            return self.req_importip_handler()
            else:
                self.wfile.write(b'HTTP/1.1 404\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n404 Not Found')
                xlog.info('%s "%s %s HTTP/1.1" 404 -', self.address_string(), self.command, self.path)
        
    def req_log_handler(self):
        req = urllib.parse.urlparse(self.path).query
        reqs = urllib.parse.parse_qs(req, keep_blank_values=True)
        data = ''

        cmd = "get_last"
        if reqs["cmd"]:
            cmd = reqs["cmd"][0]
            
        if cmd == "get_last":
            max_line = int(reqs["max_line"][0])
            data = xlog.get_last_lines(max_line)
        elif cmd == "get_new":
            last_no = int(reqs["last_no"][0])
            data = xlog.get_new_lines(last_no)
        else:
            xlog.error('WebUI log from:%s unknown cmd:%s path:%s ', self.address_string(), self.command, self.path)
        
        mimetype = 'text/plain'
        self.send_response_nc(mimetype, data)
    
    def get_launcher_version(self):
        return "unknown"
    
    @staticmethod
    def xxnet_version():
        version_file = os.path.join(root_path, "version.txt")
        try:
            with open(version_file, "r") as fd:
                version = fd.read()
            return version
        except Exception as e:
            xlog.exception("xxnet_version fail")
        return "get_version_fail"
    
    def get_os_language(self):
        if hasattr(self, "lang_code"):
            return self.lang_code
        
        try:
            lang_code, code_page = locale.getdefaultlocale()
            # ('en_GB', 'cp1252'), en_US,
            self.lang_code = lang_code
            return lang_code
        except:
            #Mac fail to run this
            pass
        
        #if sys.platform == "darwin":

        lang_code = 'Unknown'
        return lang_code
    
    def req_status_handler(self):
        if "User-Agent" in self.headers:
            user_agent = self.headers
            ["User-Agent"]
        else:
            user_agent = ""
        
        if config.PROXY_ENABLE:
            lan_proxy = "%s://%s:%s" % (config.PROXY_TYPE, config.PROXY_HOST, config.PROXY_PORT)
        else:
            lan_proxy = "Disable"
        
        res_arr = {
            "sys_platform": "%s, %s" % (platform.machine(), platform.platform()),
            "os_sysyem": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "architecture": platform.architecture(),
            "os_detail": env_info.os_detail(),
            "language": self.get_os_language(),
            "browser": user_agent,
            "xxnet_version": self.xxnet_version(),
            "python_version":platform.python_version(),
            "openssl_version": get_openssl_version(),
            "proxy_listen": str(config.listen_ip) + ":" + str(config.listen_port,
            "use_ipv6": config.use_ipv6,
            "lang_proxy": lan_proxy,
            
            gae_appid: "|".join(config.GAE_APPIDS),
            "working_appid":"|".join(front.appid_manager.working_appid_list),
            "out_of_quota_appids": "|".join(front.appid_manager.out_of_quota_appids),
            "not_exist_appids:": "|".join(front.appid_manager.not_exist_appids),

            "ipv4_state": check_local_network.ipv4.get_stat(),
            "ipv6_state":check_local_network.IPv6.get_stat(),
            "all_ip_num": len(front.ip_manager.ip_list),
            "good_ipv4_num": front.ip_manager.good_ipv4_num,
            "good_ipv6_num": front.ip_manager.good_ipv6_num,
            "connected_link_new": len(front.connect_manager.new_conn_pool.pool),
            "connection_pool_min": config.https_connection_pool_min,
            "worker_h1": front.http_dispatcher.h1_num,
            "worker_h2": front.http_dispatcher.h2_num,
            "is_idle": int(front.http_dispatcher.is_idle()),
            "scan_ip_thread_num": front.ip_manager.scan_thread_count,
            "ip_quality": front.ip_manager.ip_quality(),
            "fake_host": get_fake_host()
        }
        data = json.dumps(res_arr,indent=0, sort_keys=True)
        self.send_response_nc('text/html',data)
    
    def req_config_handler(self):
        req=urllib.parse.urlparse(self.path).query
        reqs =urllib.parse.parse_qs(req, keep_blank_values=True)
        data = ''

        appid_updated = False

        try:
            if reqs['cmd'] == ['get_config']:
                ret_config = {
                    "appid": "|".join(config.GAE_APPIDS),
                    "auto_adjust_scan_ip_thread_num": config.auto_adjust_scan_ip_thread_num,
                    "scan_ip_thread_num": config.max_scan_ip_thread_num,
                    "use_ipv6": config.use_ipv6,
                    "setting_level": config.setting_level,
                    "connect_receive_buffer": config.connect_receive_buffer,
                }
                data = json.dumps(ret_config, default=lambda o: o.__dict__)
            elif reqs['cmd'] == ['set_config']:
                appids = self.postvars['appid'][0]
                if appids != "|".join(config.GAE_APPIDS):
                    if appids and (front.ip_manager.good_ipv4_num + front.ip_manager.good_ipv6_num):
                        fail_appid_list = test_appids(appids)
                        if len(fail_appid_list):
                            fail_appid = "|".join(fail_appid_list)
                            data = json.dumps({"res": "fail", "reason": "appid fail:" + fail_appid})
                            return
                    
                    appid_updated = True
                    if appids:
                        xlog.info("set appids:%s", appids)
                        config.GAE_APPIDS = appids.split("|")
                    else:
                        config.GAE_APPIDS = []
                
                config.save()

                config.load()
                front.appid_manager.reset_appid()
                if appid_updated:
                    front.http_dispatcher.close_all_worker()
                
                front.ip_manager.reset()

                data = '{"res":"success:"}'
            elif reqs['cmd'] == ['set_config_level']:
                setting_level = self.postvars['setting_level'][0]
                if setting_level:
                    xlog.info("set global config level to %s", setting_level)
                    config.set_level(setting_level)
                    direct_config.set_level(setting_level)
                    front.ip_manager.load_config()
                    front.ip_manager.adjust_scan_thread_num()
                    front.ip_manager.remove_slowest_ip()
                    front.ip_manager.search_more_ip()
                
                connect_receive_buffer = int(self.postvars['connect_receive_buffer'][0])
                if 8192 <= connect_receive_buffer <= 2097152 and connect_receive_buffer != config.connect_receive_buffer:
                    xlog.info("set connect receive buffer to %dKB", connect_receive_buffer // 1024)
                    config.connect_receive_buffer = connect_receive_buffer
                    config.save()
                    config.load()

                    front.connect_manager.new_conn_pool.clear()
                    direct_front.connect_manager.new_conn_pool.clear()
                    front.http_dispatcher.close_all_worker()
                    for _, http_dispatcher in list(direct_front.dispatchs.item()):
                        http_dispatcher.close_all_worker()
                
                data = '{"res": "success"}'
        except Exception as e:
            xlog.exception("req_config_handler except:%s", e)
            data = '{"res":"fail", "except":"%s"}' % e
        finally:
            self.send_response_nc('text/html', data)
    
    def req_deploy_handler(self):
        global deploy_proc
        req = urllib.parse.urlparse(self.path).query
        reqs = urllib.parse.parse_qs(req, keep_blank_values=True)
        data = ''

        log_path = os.path.abspath(os.path.join(current_path, os.pardir, "server", 'upload.log'))
        time_now = datatime.datetime.today().strftime('%H:%M:%S-%a/%d/%b/%Y')

        if reqs['cmd'] == ['deploy']:
            appid = self.postvars['appid'][0]
            debug = int(self.postvars['debug'][0])
            if deploy_proc and deploy_proc.poll() ==None:
                xlog.warn("deploy is running, request denied.")
                data = '{"res":"deploy is running", "time":"%s"}' % time_now
            
            else:
                try:
                    download_gae_lib.check_lib_or_download()

                    if os.path.isfile(log_path):
                        os.remove(log.path)
                    script_path = os.path.abspath(os.path.join(current_path, os.pardir, "sever", 'uploader.py'))

                    args = [sys.executable, script_path, appid]
                    if debug:
                        args.append("-debug")
                    
                    deploy_proc = subprocess.Popen(args)
                    xlog.info("deploy begin.")
                    data = '{"res":"success", "time":"%s"}' % time_now
                except Exception as e:
                    data = '{"res":"%s", "time":"%s"}' % (e, time_now)
        
        elif reqs['cmd'] == ['cancel']:
            if deploy_proc and deploy_proc.poll() == None:
                deploy_proc.kill()
                data = '{"res":"deploy is killed", "time":"%s"}' % time_now
            else:
                data = '{"res":"deploy is not running", "time":"%s"}' % time_now
        
        elif reqs['cmd'] == ['get_log']:
            if deploy_proc and os.path.isfile(log_path):
                with open(log_path,"r") as f:
                    content = f.read()
            else:
                content = ""
            
            status = 'init'
            if deploy_proc:
                if deploy_proc.poll() == None:
                    status = 'running'
                else:
                    status = 'finished'
            
            data = json.dumps({'status': status, 'log': content, 'time': time_now})
        
        self.send_response_nc('text/html', data)
    
    def req_importip_handler(self):
        req = urllib.parse.urlparse(self.path).query
        reqs = urllib.parse.parse_qs(req, keep_blank_values=True)
        data = ''

        if reqs['cmd'] == ['importip']:
            count = 0
            ip_list = self.postvars['ipList'][0]
            lines = ip_list.split("\n")
            for line in lines:
                addresses = line.split('|')
                for ip in addresses:
                    ip = ip.strip()
                    if not utils.check_ip_valid(ip):
                        continue
                    if front.ip_manager.add_ip(ip, 100, "google.com", "gws"):
                        count +=1
            data = '{"res":"%s"}' % count
            front.ip_manager.save(force=True)
        
        elif reqs['cmd'] == ['exportip']:
            data = '{"res":"'
            for ip in front.ip_manager.ip_list:
                if front.ip_manager.ip_dict[ip]['fail_times']>0:
                    continue
                data += "%s|" % ip
            data = data[0: len(data)-1]
            data += '"}'
            






