#!/usr/bin/env/ python
# coding:utf-8
"""
Go Agent local-server protocol 3.2

request:
POST /_gh/ HTTP/1.1
HOST: appid.appspot.com
content-length: xxx

http content:
body
{
    pack_req_head_len: 2 byte, #post 时使用
    pack_req_head: deflate{ 此为负载
        original request line
        original request headers,
        X-URLFETCH-kwargs HEADS, {
            password,
            maxsize, defined in config AUTO RANGE MAX SIZE
            timeout, request timeout for GAE urlfetch.
        }
    }
    body
}
response:
200 OK
http-Heads:
Content-type: image/gif
headers from real_server
# real_server 为gae让客户以为的服务器
# 可能被gae改变,但对客户端不可见
# 未分片body也直接发给客户端
# body 分为下面两个部分
http-content:{
    response_head{
        data_len:  2 byte,
        data: deflate{
            HTTP/1.1 status, status_code headers
            content = error_message, if GAE server fail  
        }
    }
    body
}
"""
import errno
import time
import xstruct as struct
import re
import string
import ssl
import urllib.parse
import threading
import zlib
import traceback
from mimetypes import guess_type
from . import check_local_network
from .front import front
import utils
from xlog import getLogger
xlog = getLogger("gae_proxy")

def inflate(data):
    return zlib.decompress(data, -zlib.MAX_WBITS)

def deflate(data):
    return zlib