import os
from front_base.config import ConfigBase
import simple_http_client
import utils

current_path=os.path.dirname(os.path.abspath(__file__))
root_path=os.path.abspath(os.path.join(current_path,os.pardir,os.pardir))
data_path=os.path.abspath(os.path.join(root_path, os.pardir, os.pardir,'data'))
module_data_path=os.path.join(data_path,'gae_proxy')

headers={"connection": "close"}
fqrouter=simple_http_client.request("GET", "http://127.0.0.1:2515/ping", headers=headers, timeout=0.5)
mobile= fqrouter and "PONG" in fqrouter.text
del headers, fqrouter

class Config(ConfigBase):
    def __init__(self, fn):
        super(Config, self).__init__(fn)
        # globa setting level
        # passive < conservative < normal < radical <extreme
        self.set_var("setting_level", "normal")
        # proxy
        self.set_var("listen_ip", "127.0.0.1")
        self.set_var("listen_port", 8087)
        # auto range
        self.set_var("AUTORANGE_THREADS", 10)
        self.set_var("AUTORANGE_MAXSIZE", 512 * 1024)
        if mobile:
            self.set_var("AUTORANGE_MAXBUFFERSIZE", 10*1024*1024/8)
        else:
            self.set_var("AUTORANGE_MAXBUFFERSiZE", 20*1024*1024)
        self.set_var("JS_MAXSIZE", 0)
        #gae
        self.set_var("GAE_PASSWORD", "")
        self.set_var("GAE_VALIDATE", 0)
        #host rules
        self.set_var("hosts_direct", [])
        self.set_var("hosts_direct_endswitch", [b".appspot.com"])
        self.set_var("hosts_gae",[b"accounts.google.com",b"mail.google.com"])
        self.set_var("hosts_gae_endswith", [b".googleapis.com"])
        # sites using br
        self.set_var("BR_SITES", [
            b"webcache.googleusercontent.com", 
            b"www.google.com", 
            b"www.google.com.hk", 
            b"www.google.com.cn", 
            b"fonts.googleapis.com"])
        self.set_var("BR_SITES_ENDSWITCH",[
            b".youtube.com",
            b".facebook.com",
            b".googlevideo.com"
        ])
        # some unsupport request like url length >2048, will go Direct
        self.set_var("google_endswith",[
            b".youtube.com",
            b".googleapis.com",
            b".googleusercontent.com",
            b".ytimg.com",
            b".doubleclick.net",
            b".google-analytics.com",
            b".googlegroups.com",
            b".googlesource.com",
            b".gstatic.com",
            b".appspot.com",
            b".gvt1.com",
            b".android.com",
            b".ggpht.com",
            b".googleadservices.com",
            b".googlesyndication.com",
            b".2mdn.net"
        ])
        # front
        self.set_var("front_continue_fail_num",10)
        self.set_var("front_continue_fail_block", 0)
        # http_dispatcher
        self.set_var("dispather_min_idle_workers", 3)
        self.set_var("dispather_work_min_idle_time", 0)
        self.set_var("dispather_work_max_score", 1000)
        self.set_var("dispather_min_workers", 20)
        self.set_var("dispather_max_workers", 50)
        self.set_var("dispather_max_idle_workers", 15)
        self.set_var("max_task_num", 80)
        # http 1 worker
        self.set_var("http1_first_ping_wait",5)
        self.set_var("http1_idle_time", 200)
        self.set_var("http1_ping_interval",0)
        # http 2 worker
        self.set_var("http2_max_concurrent",20)
        self.set_var("http2_target_concurrent",1)
        self.set_var("http2_max_timeout_tasks",1)
        self.set_var("http2_timeout_active",0)
        self.set_var("http2_ping_min_interval", 0)
        # connect_manager
        self.set_var("https_max_connect_thread", 10)
        self.set_var("ssl_first_use_timeout", 5)
        self.set_var("connection_pool_min", 1)
        self.set_var("https_connection_pool_min",0)
        self.set_var("https_connection_pool_max",10)
        self.set_var("https_new_connect_num", 3)
        self.set_var("https_keep_alive", 10)
        # check_ip
        self.set_var("check_ip_host", "xxnet-1.appspot.com")
        self.set_var("check_ip_accept_status", [200,503])
        self.set_var("check_ip_content", b"GoAgent")
        # host_manager
        self.set_var("GAE_APPIDS", [])
        # connect_creator
        self.set_var("check_pkp",[
            #  https://pki.goog/gsr2/GIAG3.crt
            #  https://pki.goog/gsr2/GTSGIAG3.crt
            b'''\
            -----BEGIN PUBLIC KEY-----
            MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAylJL6h7/ziRrqNpyGGjV
Vl0OSFotNQl2Ws+kyByxqf5TifutNP+IW5+75+gAAdw1c3UDrbOxuaR9KyZ5zhVA
Cu9RuJ8yjHxwhlJLFv5qJ2vmNnpiUNjfmonMCSnrTykUiIALjzgegGoYfB29lzt4
fUVJNk9BzaLgdlc8aDF5ZMlu11EeZsOiZCx5wOdlw1aEU1pDbcuaAiDS7xpp0bCd
c6LgKmBlUDHP+7MvvxGIQC61SRAPCm7cl/q/LJ8FOQtYVK8GlujFjgEWvKgaTUHF
k5GiHqGL8v7BiCRJo0dLxRMB3adXEmliK+v+IO9p+zql8H4p7u2WFvexH6DkkCXg
MwIDAQAB
-----END PUBLIC KEY-----            
            ''',

        ])