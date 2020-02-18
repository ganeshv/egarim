# Lenovo Mirage camera API client over HTTP
# Before using this tool, you need to have generated the shared encryption key 
# using bluestrap.py

from mirage_api import *
import urllib.request
import sys
import os
import argparse
import ssl
import base64
import hmac
import shutil
import datetime
import json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def main(opts):
    with open(opts.skey, 'rb') as f:
        skey = f.read()

    if opts.subcommand == 'list_media':
        list_media(skey, opts)
    elif opts.subcommand == 'get_media':
        get_media(skey, opts)
    elif opts.subcommand == 'delete_media':
        delete_media(skey, opts)
    elif opts.subcommand in SIMPLE_CMDS:
        resp = simple_cmd(skey, opts, SIMPLE_CMDS[opts.subcommand])
        print(resp)
    else:
        print('subcommand not implemented:', opts.subcommand)
        sys.exit(1)

def sign(req, skey):
    h = hmac.new(skey, digestmod='sha256')
    h.update(req.method.encode('utf-8'))
    h.update(req.selector.encode('utf-8'))
    if req.data:
        h.update(req.data)
    auth = base64.urlsafe_b64encode(h.digest()).decode('ascii')
    return auth
    
def simple_cmd(skey, opts, request):
    headers = {
        'Content-Type': 'application/octet-stream'
    }
    r = request(opts)
    if opts.debug:
        print('request', r)
    data = r.SerializeToString()
    req = urllib.request.Request('https://%s:%s/daydreamcamera' % (opts.host, opts.port), data=data, headers=headers, method='POST')
    signature = sign(req, skey)
    req.add_header('Authorization', 'daydreamcamera ' + signature)
    with urllib.request.urlopen(req, context=ctx) as f:
        data = f.read()
        return parse_response(data)

def list_media(skey, opts):
    resp = simple_cmd(skey, opts, SIMPLE_CMDS[opts.subcommand])
    if opts.debug:
        print(resp)
    for item in resp.media.media:
        print('%s %d %d %d %d' % (item.filename, item.size, item.duration, item.width, item.height))

def get_media(skey, opts):
    req = urllib.request.Request('https://%s:%s/media/%s' % (opts.host, opts.port, opts.path), method='GET')
    signature = sign(req, skey)
    req.add_header('Authorization', 'daydreamcamera ' + signature)
    outfile = os.path.join(opts.dest, os.path.basename(opts.path))
    print('copying ', opts.path)
    with urllib.request.urlopen(req, context=ctx) as f, open(outfile, 'wb') as out:
        shutil.copyfileobj(f, out)
        
def delete_media(skey, opts):
    req = urllib.request.Request('https://%s:%s/media/%s' % (opts.host, opts.port, opts.path), method='DELETE')
    signature = sign(req, skey)
    req.add_header('Authorization', 'daydreamcamera ' + signature)
    print('deleting ', opts.path)
    with urllib.request.urlopen(req, context=ctx) as f:
        data = f.read()

def process_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='camera hostname/IP')
    parser.add_argument('--port', help='camera https port', default=8443)
    parser.add_argument('--debug', help='verbose debugging', action='store_true')
    parser.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')

    subparsers = parser.add_subparsers(dest='subcommand', title='Subcommands')

    subparsers.add_parser('status')
    subparsers.add_parser('get_capabilities')
    subparsers.add_parser('factory_reset')
    subparsers.add_parser('get_st3dbox')
    subparsers.add_parser('get_sv3dbox')

    
    capture = subparsers.add_parser('config_capture')
    capture.add_argument('--mode', help='capture mode (video/photo/live)', choices=['video', 'photo', 'live'])
    capture.add_argument('--rtmp_endpoint')
    capture.add_argument('--stream_name_key')
    capture.add_argument('--projection', choices=['fisheye', 'equirect'])
    capture.add_argument('--width', type=int)
    capture.add_argument('--height', type=int)


    start_capture = subparsers.add_parser('start_capture')
    start_capture.add_argument('--auto_stop', help='auto stop after x milliseconds', type=int)

    subparsers.add_parser('stop_capture')

    list_media = subparsers.add_parser('list_media')
    list_media.add_argument('--start', type=int)
    list_media.add_argument('--count', type=int, default=100)

    get_media = subparsers.add_parser('get_media')
    get_media.add_argument('--dest', default='.')
    get_media.add_argument('path')

    delete_media = subparsers.add_parser('delete_media')
    delete_media.add_argument('path')

    opts = parser.parse_args()
    if opts.subcommand is None:
        print(parser.print_help())
        sys.exit(1)

    if not os.path.exists(opts.skey):
        print('%s doesn\'t exist; pair using btmirage.py to generate the shared encryption key' % (opts.skey,))
        sys.exit(1)

    if not opts.host:
        status_file = os.path.join(os.path.expanduser('~'), '.egarim-status')
        if not os.path.exists(status_file):
            print('no host specified and no status file; run "python bluestrap.py status" to retrieve camera IP')
            sys.exit(1)
        with open(status_file, 'r') as f:
            status = json.loads(f.read())
            opts.host = status['cameraStatus']['httpServerStatus']['cameraHostname'][0]
            opts.port = status['cameraStatus']['httpServerStatus']['cameraPort']

    return opts

if __name__ == '__main__':
    n = process_args()
    main(n)
