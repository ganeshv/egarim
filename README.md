# egarim
Lenovo Mirage VR180 Camera API client - remote control and custom live streaming

## Introduction

The Lenovo Mirage Camera with Daydream is a twin-sensor VR180 camera which does 3D photos, videos and livestreaming at 4k. It uses the VR180 format popularised by Google for use with VR headsets. Unfortunately, the format and the camera seem to have been abandoned, but it's still available for about $100 and is great value for what it does. The camera lacks a viewfinder or preview screen and needs a smartphone companion app (Google's VR180 app available on Android and iOS) to function as a viewfinder, setup the parameters for livestreaming, etc. Only Youtube livestreaming is enabled by the VR180 app.

The reference implementation of the camera firmware has been open-sourced by Google (https://github.com/google/vr180), but the companion app is not . This project provides a Linux/Python utilities which can function as a "companion app" to pair with the camera, issue API commands, setup live streaming with custom end-points.

## Installation

## Basic Usage

The camera uses an application level pairing protocol over Bluetooth which uses ECDH key agreement to establish a shared key. This key is then used to encrypt further API calls over Bluetooth, and/or to sign HTTP API calls over Wi-Fi.

Before using the camera we must pair it using `bluestrap.py` (works only on Linux). Once paired, the shared key may be used with `egarim.py` to issue API requests over Wi-Fi on any machine (Linux/MacOS)

The LED surrounding the shutter button is in one of 4 states:
  1. Off - the camera is sleeping/powere off.
  2. Blinking green - the camera is booting.
  3. Solid blue - the camera is booted/awake and ready for action.
  4. Blinking green/blue - the camera is in pairing mode.
  
### Pairing

Once the shutter LED is in the solid blue state, hold the shutter button down for 5 seconds, until the LED enters the blinking blue/green state. Run

`python bluestrap.py pair`

If successful, you will see a series of messages like

```
```

Press the shutter once when asked, and the pairing will continue and generate the shared key file, `me_cam.skey`. This file will be needed for all further communication with the camera.

### Bluetooth API calls

### HTTP API calls

## Advanced Usage

Read `camera_api.proto` and implement new commands `¯\_(ツ)_/¯`

## Technical details

## Credits

  1. Google's VR180 reference camera implementation: https://github.com/google/vr180
  2. Dash Zhou's ECDH key agreement project https://github.com/zhoupeng6d/openssl-key-exchange, which uses the same key generation mechanism, but very well-explained.
  3. Adafruit's BLE project for Bluetooth/Linux details: https://github.com/adafruit/Adafruit_Python_BluefruitLE
