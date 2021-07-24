#!/user/bin/env python
#coding:utf-8
"""
GAEProxyHandler 是一个端口管理器,默认8087
如果http请求, do_METHOD
如果是https请求,do_connect

什么是直连模式:
如果用户连接google网站,比如www.google.com,client.google.com,我们不需要转发需求给GAE服务器.我们可以把原始需求直接发送给google ip.因为大多数google ip能起到前端服务器作用.
youtube内容服务器不支持直连模式
查阅direct_handler.py获取更多信息.

什么是GAE模式:
Google App Engine支持代理地址获取
每个google账号可以申请12个appid.
部署位于gae_proxy/server/gae目录内的服务器端代码到gae服务器之后,用户可以使用GAE服务器作为代理服务器.
下面是全局链接视图:
Browser=>GAE_proxy=>GAE server=>target http/https server.
查阅gae_handler.py获取更多信息.
"""
import errno
import socket
import ssl
import urllib.parse
import OpenSSL
NetWorkIOError=(socket.error,ssl.SSLError,OpenSSL.SSL.Error,OSError)
from xlog import getLogger
xlog=getLogger("gae_proxy")
import simple_http_client
import simple_http_server
from .cert_util import CertUtil