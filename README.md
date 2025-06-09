# pyAudioViz
Custom built audio visualizer written in Python with pygame.

Creates a window that displays a real-time audio visualization of the audio being played on your computer built in Python

Audio must be piped through Stereo Mix recording device.

Most HDMI/DisplayPort/USB audio devices do not support loopback audio streams

The workaround I had to use was to set my motherboard's audio card to the default output device then set Audacity to 
act as a Windows WASAPI host. Then from there set Audacity to play the audio back live to my preferred device as it
records the sound from Stereo Mix.

The above workaround is still viable as well as Stereo Mix, but I added compatibility with VB-Audio Virtual Cable since
it is a more seamless and easier solution for loopback audio on Windows.

# Requirements
**WINDOWS**
---
Windows 10 or later

Python 3.10 or later

Audacity (for loopback audio) and/or Stereo Mix device enabled

**OR**

VB-Audio Virtual Cable for loopback audio