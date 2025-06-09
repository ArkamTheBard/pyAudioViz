import math
import os
import numpy
import pygame
import re
import sounddevice as sd
import sys


def log_bins(spectrum, bars, sample_rate, chunk_size, bin_floor):
    freqs = numpy.fft.rfftfreq(chunk_size, 1 / sample_rate)
    min_freq = 40
    max_freq = min(10_000, freqs[-1])
    log_edges = numpy.logspace(math.log10(min_freq), math.log10(max_freq), bars + 1)
    bar_vals = []
    for i in range(bars):
        idx = numpy.where((freqs >= log_edges[i]) & (freqs < log_edges[i+1]))[0]
        if len(idx) > 0:
            bar_vals.append(max(numpy.mean(spectrum[idx]), bin_floor))
        else:
            bar_vals.append(bin_floor)
    return bar_vals

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def main():
    CHUNK = 512
    ANALYSIS_SIZE = 10240
    BARS = 64
    WIDTH, HEIGHT = 800, 600

    BIN_FLOOR = 0.1
    min_norm = 10.0
    FLOOR_OFFSET = 40
    GAIN = 2.0
    smoothing = 0.80
    volume = 0.25
    buffer = numpy.zeros(ANALYSIS_SIZE, dtype='float32')

    devices = sd.query_devices()
    cable_index = None
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and re.search(r'cable output', dev['name'], re.IGNORECASE):
            cable_index = idx
            break
    if cable_index is None:
        raise RuntimeError("No VB-Cable device found.")

    sample_rate = int(devices[cable_index]['default_samplerate'])

    pygame.init()
    icon_surface = pygame.image.load(resource_path("avatar_65ee593544d6_512.png"))
    pygame.mixer.init(frequency=sample_rate)
    pygame.display.set_caption("Arkam's Audio Visualizer")
    pygame.display.set_icon(icon_surface)
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

    prev_heights = [0] * BARS
    running = True

    window_size = [WIDTH, HEIGHT]

    def audio_callback(indata, frames, time, status):
        nonlocal prev_heights, running, volume, buffer
        WIDTH, HEIGHT = window_size
        BAR_WIDTH = WIDTH // BARS
        FLOOR = HEIGHT - FLOOR_OFFSET

        if not running:
            raise sd.CallbackStop

        buffer = numpy.roll(buffer, -CHUNK)
        buffer[-CHUNK:] = indata[:, 0]

        valid_len = min(numpy.count_nonzero(buffer), ANALYSIS_SIZE)
        if valid_len >= CHUNK:
            window = numpy.hanning(valid_len)
            windowed = buffer[-valid_len:] * window
            spectrum = numpy.abs(numpy.fft.rfft(windowed)) * GAIN
            spectrum = numpy.power(spectrum, 0.7)
            bars = log_bins(spectrum, BARS, sample_rate, valid_len, BIN_FLOOR)
            max_val = max(numpy.max(bars), min_norm)
            heights = [max(7, int((h / max_val) * (HEIGHT-FLOOR_OFFSET))) if volume > 0 else 0 for h in bars]
            heights = [int(smoothing * prev + (1 - smoothing) * curr) for prev, curr in zip(prev_heights, heights)]
            prev_heights = heights

            screen.fill((0,0,0))
            pygame.draw.line(screen, (200, 200, 200), (0, FLOOR), (WIDTH, FLOOR), 2)
            for j, h in enumerate(heights):
                bar_top = max(FLOOR - h, 0)
                pygame.draw.rect(screen, (0, 255, 0), (j*BAR_WIDTH, bar_top, BAR_WIDTH-2, h))
            pygame.display.flip()

    with sd.InputStream(
        samplerate=sample_rate,
        device=cable_index,
        channels=2,
        dtype='float32',
        blocksize=CHUNK,
        callback=audio_callback
    ):
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    window_size[0], window_size[1] = event.w, event.h
                    screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            pygame.time.wait(10)

    pygame.quit()


if __name__ == "__main__":
    main()