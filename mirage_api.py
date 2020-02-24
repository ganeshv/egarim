import datetime
from camera_api_pb2 import *
import subprocess
import io
import json

JMIRAGE = "java -cp . MirageCrypto "
counter = 2000

# The camera uses \x00\x00 as an end-of-message marker for Bluetooth messages.
# These need to be escaped and encoded/decoded before applying encryption/decryption.

def mm_encode(msg):
    out = b''
    for i in range(len(msg)):
        if i > 0 and msg[i - 1] == 0 and (msg[i] == 0 or msg[i] == 1):
            out += b'\x01'
        out += msg[i:i+1]
    out += b'\x00\x00'
    return out

def mm_decode(msg):
    if len(msg) < 2 or msg[-1] != 0 or msg[-2] != 0:
        raise Exception('no EOM marker found')
    out = b''
    for i in range(len(msg) - 2):
        if i > 0 and msg[i - 1] == 0 and msg[i] == 1:
            continue
        out += msg[i:i+1]
    return out

# Bluetooth messages (other than key initiate/finalize) are encrypted by the shared key

def encrypt(msg, key):
    return subprocess.check_output(JMIRAGE + " encrypt " + key, input=msg, shell=True)

def decrypt(msg, key):
    return subprocess.check_output(JMIRAGE + " decrypt " + key, input=msg, shell=True)

# Generate shared key from the ECDH public key of the camera + our key
def genshared(me, cam):
    return subprocess.check_output(JMIRAGE + " genshared %s %s " % (me, cam), shell=True)

# Generate our ECDH key
def genkey(me):
    return subprocess.check_output(JMIRAGE + " genkey %s" % (me,), shell=True)

def new_request():
    global counter
    counter = counter + 1
    req = CameraApiRequest()    
    req.header.expiration_timestamp = int((datetime.datetime.timestamp(datetime.datetime.now()) + 40000) * 1000)
    req.header.request_id = counter
    return req

def config_wifi_request(opts):
    if opts.ssid is None or opts.password is None:
        raise Exception('ssid and password must be set')
    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    req.configuration_request.local_wifi_info.ssid = opts.ssid
    req.configuration_request.local_wifi_info.password = opts.password
    return req

def config_time_request(opts):
    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    req.configuration_request.time_configuration.timestamp = int(datetime.datetime.now().replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    if opts.timezone:
        req.configuration_request.time_configuration.timezone = opts.timezone
    return req

def config_capture_request(opts):
    modes = {
        'live': CaptureMode.LIVE,
        'photo': CaptureMode.PHOTO,
        'video': CaptureMode.VIDEO
    }
    projections = {
        'fisheye': ProjectionType.DEFAULT_FISHEYE,
        'equirect': ProjectionType.EQUIRECT
    }

    req = new_request()
    req.type = CameraApiRequest.CONFIGURE
    if opts.mode and opts.mode != 'viewfinder':
        req.configuration_request.capture_mode.active_capture_type = modes[opts.mode]
    if opts.rtmp_endpoint:
        req.configuration_request.capture_mode.configured_live_mode.rtmp_endpoint = opts.rtmp_endpoint
    if opts.stream_name_key:
        req.configuration_request.capture_mode.configured_live_mode.stream_name_key = opts.stream_name_key
    # projection doesn't seem to work though
    if opts.mode == 'live':
        if opts.projection:
            req.configuration_request.capture_mode.configured_live_mode.video_mode.projection_type = projections[opts.projection]
        if opts.width:
            req.configuration_request.capture_mode.configured_live_mode.video_mode.frame_size.frame_width = opts.width
        if opts.height:
            req.configuration_request.capture_mode.configured_live_mode.video_mode.frame_size.frame_height = opts.height
    if opts.mode == 'video':
        if opts.projection:
            req.configuration_request.capture_mode.configured_video_mode.projection_type = projections[opts.projection]
        if opts.width:
            req.configuration_request.capture_mode.configured_video_mode.frame_size.frame_width = opts.width
        if opts.height:
            req.configuration_request.capture_mode.configured_video_mode.frame_size.frame_height = opts.height
    if opts.mode == 'photo':
        if opts.width:
            req.configuration_request.capture_mode.configured_photo_mode.frame_size.frame_width = opts.width
        if opts.height:
            req.configuration_request.capture_mode.configured_photo_mode.frame_size.frame_height = opts.height
    if opts.mode == 'viewfinder':
        if opts.width:
            req.configuration_request.capture_mode.viewfinder_mode.frame_size.frame_width = opts.width
        if opts.height:
            req.configuration_request.capture_mode.viewfinder_mode.frame_size.frame_height = opts.height
        if opts.stereo:
            req.configuration_request.capture_mode.viewfinder_mode.stereo_mode = ViewfinderMode.STEREO_MODE_STEREO_LONG_SIDE
        req.configuration_request.capture_mode.viewfinder_mode.frames_per_second = 30.0
    return req

def start_capture_request(opts):
    req = new_request()
    req.type = CameraApiRequest.START_CAPTURE
    if opts.auto_stop:
        req.start_capture_request.auto_stop_duration_ms = opts.auto_stop
    return req

def stop_capture_request(opts):
    req = new_request()
    req.type = CameraApiRequest.STOP_CAPTURE
    return req

def get_capabilities_request(opts):
    req = new_request()
    req.type = CameraApiRequest.GET_CAPABILITIES
    return req

def get_st3dbox_request(opts):
    req = new_request()
    req.type = CameraApiRequest.GET_CAMERA_ST3D_BOX
    return req

def get_sv3dbox_request(opts):
    req = new_request()
    req.type = CameraApiRequest.GET_CAMERA_SV3D_BOX
    return req

def list_media_request(opts):
    req = new_request()
    req.type = CameraApiRequest.LIST_MEDIA
    if opts.start:
        req.list_media_request.start_index = opts.start
    if opts.count:
        req.list_media_request.media_count = opts.count
    return req

def status_request(opts):
    req = new_request()
    req.type = CameraApiRequest.STATUS
    return req

def factory_reset_request(opts):
    req = new_request()
    req.type = CameraApiRequest.FACTORY_RESET
    return req

def start_viewfinder_request(opts):
    req = new_request()
    req.type = CameraApiRequest.START_VIEWFINDER_WEBRTC
    req.webrtc_request.session_name = "foo"
    req.webrtc_request.offer.session_description = opts.sdp
    ice = req.webrtc_request.offer.ice_candidate.add()
    return req

def stop_viewfinder_request(opts):
    req = new_request()
    req.type = CameraApiRequest.STOP_VIEWFINDER_WEBRTC
    req.webrtc_request.session_name = "foo"
    return req

def get_debug_logs_request(opts):
    req = new_request()
    req.type = CameraApiRequest.GET_DEBUG_LOGS
    req.debug_logs_request.max_count = opts.count

    return req

def key_init(name, mode='initiate'):
    with open(name + '.pub', mode='rb') as f:
        pk = f.read()
    with open(name + '.salt', mode='rb') as f:
        salt = f.read()

    req = CameraApiRequest()    
    req.type = CameraApiRequest.KEY_EXCHANGE_INITIATE \
        if mode == 'initiate' else CameraApiRequest.KEY_EXCHANGE_FINALIZE

    req.key_exchange_request.public_key = pk
    req.key_exchange_request.salt = salt

    return req

def key_response(resp, peer_name):
    if resp.response_status.status_code == CameraApiResponse.ResponseStatus.OK:
        with open(peer_name + '.pub', mode='wb') as f:
            f.write(resp.key_exchange_response.public_key)
        with open(peer_name + '.salt', mode='wb') as f:
            f.write(resp.key_exchange_response.salt)
        return True
    return False

def finalize_response(resp):
    return resp.response_status.status_code == CameraApiResponse.ResponseStatus.OK

def parse_response(data):
    resp = CameraApiResponse()
    resp.ParseFromString(data)
    return resp

def key_finalize(name):
    return key_init(name, mode='finalize')

# Simple one-shot requests (unlike pairing)
SIMPLE_CMDS = {
    'config_wifi': config_wifi_request,
    'config_time': config_time_request,
    'config_capture': config_capture_request,
    'start_capture': start_capture_request,
    'stop_capture': stop_capture_request,
    'get_capabilities': get_capabilities_request,
    'status': status_request,
    'get_st3dbox': get_st3dbox_request,
    'get_sv3dbox': get_sv3dbox_request,
    'factory_reset': factory_reset_request,
    'list_media': list_media_request,
    'start_viewfinder': start_viewfinder_request,
    'stop_viewfinder': stop_viewfinder_request,
    'get_debug_logs': get_debug_logs_request
}
