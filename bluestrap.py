#!/usr/bin/env python3

# Lenovo Mirage camera API client for pairing and control over Bluetooth on Linux.

import dbus
import dbus.mainloop.glib
try:
  from gi.repository import GObject
except ImportError:
  import gobject as GObject
import uuid
import time
import sys
import functools
import queue
import threading
import argparse
import os
import google.protobuf.json_format
from mirage_api import *

SERVICE_NAME = 'org.bluez'
ADAPTER_INTERFACE = SERVICE_NAME + '.Adapter1'
DEVICE_INTERFACE = SERVICE_NAME + '.Device1'
CHARACTERISTIC_INTERFACE = SERVICE_NAME + '.GattCharacteristic1'
DESCRIPTOR_INTERFACE = SERVICE_NAME + '.GattDescriptor1'
SERVICE_INTERFACE = SERVICE_NAME + '.GattService1'
PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

CAMERA_SERVICE_UUID = '49eabc2a-73b0-411e-a26d-75415dd7708e'
CAMERA_PAIRING_UUID = '18723f72-8c4e-4dd7-8f3e-b93b9c29481f'
CAMERA_API_REQUEST_CHARACTERISTIC_UUID = '48f03338-852e-4dd5-aa44-cd1b32fcaeb9'
CAMERA_API_RESPONSE_CHARACTERISTIC_UUID = '9f14e1da-4add-4ec7-aa34-6106669e2c12'
CAMERA_API_STATUS_CHARACTERISTIC_UUID = 'a03fedd3-0923-4398-854e-e2806d159a7f'

state = {
    'responseq': queue.Queue(),
    'main_loop': None,
    'exitval': 0,
    'adapter': None,
    'devpath': None
}

# Threads, blah. We use polling most of the time to keep it simple, except for
# notifications, which are pushed into a queue by the callback and retrieved
# from the main thread.

def main(opts):
    GObject.threads_init()
    dbus.mainloop.glib.threads_init()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    state['main_loop'] = main_loop = GObject.MainLoop()
    user_thread = threading.Thread(target=bzz, args=(opts,))
    user_thread.daemon = True
    user_thread.start()

    try:
        main_loop.run()
    except Exception as e:
        print(e)
        cleanup(state['adapter'], state['devpath'])
        main_loop.quit()
        sys.exit(0)

    cleanup(state['adapter'], state['devpath'])
    sys.exit(state['exitval'])

# Dbus entities are organised in a hierarchical namespace with pathnames
# (like filesystem pathnames). Each dbus "file" has multiple interfaces,
# one for setting/getting properties, one for its own functionality
# (e.g. adapters have start/stop discovery methods)
#
# Lookup operations give us the pathname of the entity and a snapshot of
# its properties. We poll for property changes by looking up entities at
# intervals, instead of subscribing to changes.

def bzz(opts):
    main_loop = state['main_loop']
    while True:
        if main_loop.is_running():
            break
        time.sleep(0)

    bus = dbus.SystemBus()

    service_uuid = CAMERA_PAIRING_UUID if opts.subcommand == 'pair' else CAMERA_SERVICE_UUID
    try:
        state['adapter'] = adapter = find_adapter()
        clear_cache(adapter)
        scan_filter = {'UUIDs': [service_uuid]}

        adapter.SetDiscoveryFilter(scan_filter)
        adapter.StartDiscovery()
        dev = find_dev_by_uuid(service_uuid)
        adapter.StopDiscovery()
        if dev is None:
            print('sadface')
            raise Exception('camera not found')

        print('found camera')
        state['devpath'] = devpath = dev[0]
        connect(devpath)
        service_path, x = find_service(devpath, service_uuid)
        request_path, x = find_characteristic(service_path, CAMERA_API_REQUEST_CHARACTERISTIC_UUID)
        response_path, x = find_characteristic(service_path, CAMERA_API_RESPONSE_CHARACTERISTIC_UUID)
        req = get_obj(request_path, CHARACTERISTIC_INTERFACE)
        setup_response_queue(response_path)

        if opts.subcommand == 'pair':
            pair(req, opts)
        elif opts.subcommand == 'status':
            status(req, opts)
        elif opts.subcommand in SIMPLE_CMDS:
            simple_cmd(req, opts, SIMPLE_CMDS[opts.subcommand])
        else:
            print('wtf, unknown subcommand')

        disconnect(devpath)
    except Exception as e:
        print(e)
        state['exitval'] = 1

    main_loop.quit()


def pair(req, opts):
    respq = state['responseq']
    key = opts.key
    camkey = opts.camkey
    key_init_request = key_init(key)
    print('key init request', key_init_request)
    req.WriteValue(mm_encode(key_init_request.SerializeToString()), {})
    response = parse_response(mm_decode(respq.get()))
    print('key response', response)
    if key_response(response, camkey) == False:
        print('error received while pairing')
        return

    print('Pairing response received; press shutter key once within 5 seconds to confirm')
    time.sleep(5)
    key_finalize_request = key_finalize(key)
    print('key finalize request', key_finalize_request)
    req.WriteValue(mm_encode(key_finalize_request.SerializeToString()), {})
    response = parse_response(mm_decode(respq.get()))
    print('key finalize response', response)
    if finalize_response(response):
        genshared(opts.key, opts.camkey)
        print('Pairing finalized! Shared encryption key written to ', key + '_' + camkey + '.skey')
    else:
        print('Pairing failed!')

def status(req, opts):
    resp = simple_cmd(req, opts, SIMPLE_CMDS['status'])
    with open(os.path.join(os.path.expanduser('~'), '.egarim-status'), 'w') as f:
        f.write(google.protobuf.json_format.MessageToJson(resp))

def simple_cmd(req, opts, request):
    respq = state['responseq']

    r = request(opts)
    print('request', r)
    rbytes = mm_encode(encrypt(r.SerializeToString(), opts.skey))
    req.WriteValue(rbytes, {})
    response = parse_response(decrypt(mm_decode(respq.get()), opts.skey))
    print(response)
    return response

def setup_response_queue(path):

    def change_received(interface, changed_props, invalidated_props):
        data = changed_props.get('Value', None)
        if interface != CHARACTERISTIC_INTERFACE or data is None:
            return
        response = b''.join([bytes([x]) for x in data])
        state['responseq'].put(response)

    resp = get_obj(path, CHARACTERISTIC_INTERFACE)
    resp_prop = get_obj(path, PROPERTIES_INTERFACE)
    resp_prop.connect_to_signal('PropertiesChanged', change_received)
    resp.StartNotify()

def cleanup(adapter, devpath):
    print('cleaning up..')
    try:
        if devpath:
            disconnect(devpath)
        if adapter:
            adapter.StopDiscovery()
    except:
        pass

def poll(repeat=30, interval=1, notfound=None, msg='waitingggg..'):
    def decorator_poll(func):
        @functools.wraps(func)
        def wrap_poll(*args, **kwargs):
            iters = 1
            while iters <= repeat:
                value = func(*args, **kwargs)
                if value != notfound:
                    return value
                if msg:
                    print(msg, '(attempt %d of %d)' % (iters, repeat))
                time.sleep(interval)
                iters += 1
            return notfound
        return wrap_poll
    return decorator_poll


def connect(path):
    device = get_obj(path, DEVICE_INTERFACE)
    device.Connect()

    return poll(msg='connecting...')(check_prop)(path, 'Connected', True)

def disconnect(path):
    device = get_obj(path, DEVICE_INTERFACE)
    device.Disconnect()

    return poll(msg='disconnecting...')(check_prop)(path, 'Connected', False)
    
def check_prop(path, prop, val):
    devs = find_interfaces(DEVICE_INTERFACE, lambda d: d.get(prop, None) == val, path)
    return len(devs.items()) == 1

def clear_cache(adapter):
    devs = find_interfaces(DEVICE_INTERFACE, lambda d: d['Connected'] == False)
    for path, dev in devs.items():
        print('clear_cache', path)
        adapter.RemoveDevice(path)

@poll(msg='waiting for device')
def find_dev_by_uuid(ustr):
    u = uuid.UUID(ustr)
    condition = lambda d: u in map(uuid.UUID, d.get('UUIDs', []))
    devs = find_interfaces(DEVICE_INTERFACE, condition)
    return next(iter(devs.items()), None)

@poll(msg='waiting for service endpoint')
def find_service(devpath, ustr):
    return find_path(SERVICE_INTERFACE, ustr, devpath)

@poll(msg='waiting for API endpoints')
def find_characteristic(devpath, ustr):
    return find_path(CHARACTERISTIC_INTERFACE, ustr, devpath)

def find_adapter():
    items = find_interfaces(ADAPTER_INTERFACE)
    apath, x = next(iter(items.items()), None)
    return get_obj(apath, ADAPTER_INTERFACE)

def find_path(interface, ustr, ppath):
    u = uuid.UUID(ustr)
    condition = lambda d: u == uuid.UUID(d['UUID'])
    items = find_interfaces(interface, condition, ppath)
    return next(iter(items.items()), None)

def find_interfaces(itype, condition=lambda x: True, path=''):
    objects = get_managed_objects()
    ppath = path.lower()
    devs = {path: interfaces[itype] for path, interfaces in objects.items() if path.lower().startswith(ppath)
        and itype in interfaces and condition(interfaces[itype])}
    return devs

def get_obj(path, interface=DEVICE_INTERFACE):
    bus = dbus.SystemBus()
    obj = bus.get_object(SERVICE_NAME, path)
    return dbus.Interface(obj, interface)

def get_managed_objects():
    bus = dbus.SystemBus()
    manager = dbus.Interface(bus.get_object(SERVICE_NAME, '/'), 'org.freedesktop.DBus.ObjectManager')
    return manager.GetManagedObjects()

def process_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subcommand')

    parser_pair = subparsers.add_parser('pair')
    parser_pair.add_argument('--key', help='the file key.pub corresponds to our public key', default='me')
    parser_pair.add_argument('--camkey', help='output file for the  camera\'s public key', default='cam')

    parser_status = subparsers.add_parser('status')
    parser_status.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')

    parser_time = subparsers.add_parser('config_time')
    parser_time.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')

    parser_wifi = subparsers.add_parser('config_wifi')
    parser_wifi.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')
    parser_wifi.add_argument('--ssid', help='SSID to be used', required=True)
    parser_wifi.add_argument('--password', help='WPA2/PSK password', required=True)

    parser_reset = subparsers.add_parser('factory_reset')
    parser_reset.add_argument('--skey', help='shared encryption key file', default='me_cam.skey')
    
    opts = parser.parse_args()
    if opts.subcommand is None:
        print(parser.print_help())
        sys.exit(1)

    if hasattr(opts, 'key') and (not os.path.exists(opts.key + '.pub') or not os.path.exists(opts.key + '.salt')):
        print('Generating key...')
        genkey(opts.key)
        
    if hasattr(opts, 'skey') and not os.path.exists(opts.skey):
        print("%s doesn't exist, pair first?" % (opts.skey,))
        sys.exit(1)

    return opts

if __name__ == '__main__':
    n = process_args()
    main(n)
