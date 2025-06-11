import math
import os
import numpy
import platform
import pygame
import re
import threading
import sounddevice as sd
import sys


def get_enabled_input_devices():
    devices = sd.query_devices()
    enabled = []
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            try:
                with sd.InputStream(device=idx, channels=1, samplerate=int(dev['default_samplerate']), blocksize=32):
                    enabled.append((idx, dev['name']))
            except Exception:
                continue
    return enabled


def find_loopback_device(devices):
    system = platform.system().lower()
    patterns = []
    if system == 'windows':
        patterns = [r"stereo ?mix", r"cable output"]
    elif system == 'darwin':
        patterns = [r"blackhole", r"loopback", r"soundflower"]

    for idx, name in devices:
        for pat in patterns:
            if re.search(pat, name, re.IGNORECASE):
                return idx
    return None


def select_device_pygame(devices, screen, font):
    selected = 0
    running = True
    clock = pygame.time.Clock()

    while running:
        screen.fill((30,30,30))
        title = font.render("Select Audio Input Device (Up/Down, Enter):", True, (255, 255, 255))
        screen.blit(title, (20, 20))
        for i, (idx, name) in enumerate(devices):
            color = (0, 255, 0) if i == selected else (200, 200, 200)
            text = font.render(f"{idx}: {name}", True, color)
            screen.blit(text, (40, 60 + i * 30))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(devices)
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(devices)
                elif event.key == pygame.K_RETURN:
                    return devices[selected][0]
        clock.tick(30)


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

def make_audio_callback(screen, window_size, BARS, FLOOR_OFFSET, GAIN, min_norm, BIN_FLOOR, smoothing, buffer, prev_heights, volume, log_bins, sample_rate, CHUNK):
    def audio_callback(indata, frames, time, status):
        nonlocal prev_heights, buffer, volume
        WIDTH, HEIGHT = window_size
        BAR_WIDTH = WIDTH // BARS
        FLOOR = HEIGHT - FLOOR_OFFSET

        buffer = numpy.roll(buffer, -CHUNK)
        if platform.system().lower() == 'linux':
            samples = indata[:, 0]
            if len(samples) < CHUNK:
                padded = numpy.zeros(CHUNK, dtype=samples.dtype)
                padded[-len(samples):] = samples
                buffer[-CHUNK:] = padded
            else:
                buffer[-CHUNK:] = samples[-CHUNK:]
        else:
            buffer[-CHUNK:] = indata[:, 0]

        valid_len = min(numpy.count_nonzero(buffer), len(buffer))
        if valid_len >= CHUNK:
            window = numpy.hanning(valid_len)
            windowed = buffer[-valid_len:] * window
            spectrum = numpy.abs(numpy.fft.rfft(windowed)) * GAIN
            spectrum = numpy.power(spectrum, 0.7)
            bars = log_bins(spectrum, BARS, sample_rate, valid_len, BIN_FLOOR)
            max_val = max(numpy.max(bars), min_norm)
            heights = [max(7, int((h / max_val) * (HEIGHT-FLOOR_OFFSET))) if volume > 0 else 0 for h in bars]
            heights = [int(smoothing * prev + (1 - smoothing) * curr) for prev, curr in zip(prev_heights, heights)]
            prev_heights[:] = heights

            screen.fill((0,0,0))
            pygame.draw.line(screen, (200, 200, 200), (0, FLOOR), (WIDTH, FLOOR), 2)
            for j, h in enumerate(heights):
                bar_top = max(FLOOR - h, 0)
                pygame.draw.rect(screen, (0, 255, 0), (j*BAR_WIDTH, bar_top, BAR_WIDTH-2, h))
            pygame.display.flip()
    return audio_callback

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
    prev_heights = [0] * BARS
    running = True
    window_size = [WIDTH, HEIGHT]

    if platform.system().lower() == 'linux':
        import jack
        sample_rate = 48000
        channels = 2
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
        prev_heights = [0] * BARS
        running = True
        window_size = [WIDTH, HEIGHT]

        pygame.init()
        icon_surface = pygame.image.load(resource_path("avatar_65ee593544d6_512.png"))
        pygame.display.set_caption("Arkam's Audio Visualizer")
        pygame.display.set_icon(icon_surface)
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        font = pygame.font.SysFont(None, 28)
        pygame.mixer.init(frequency=sample_rate)

        audio_callback = make_audio_callback(
            screen, window_size, BARS, FLOOR_OFFSET, GAIN, min_norm, BIN_FLOOR, smoothing, buffer, prev_heights,
            volume, log_bins, sample_rate, CHUNK
        )

        client = jack.Client("AudioVisualizer")
        inports = [client.inports.register(f'input_{i+1}') for i in range(channels)]

        buffer_lock = threading.Lock()
        latest_indata = numpy.zeros((CHUNK, channels), dtype='float32')

        def process(frames):
            nonlocal buffer, latest_indata
            indata = numpy.stack([port.get_array() for port in inports], axis=-1)
            samples = indata[:, 0]
            buffer = numpy.roll(buffer, -CHUNK)
            if len(samples) < CHUNK:
                padded = numpy.zeros(CHUNK, dtype=samples.dtype)
                padded[-len(samples):] = samples
                buffer[-CHUNK:] = padded
            else:
                buffer[-CHUNK:] = samples[-CHUNK:]
            with buffer_lock:
                # latest_indata[:] = indata
                if indata.shape[0] < latest_indata.shape[0]:
                    indata_padded = numpy.zeros_like(latest_indata)
                    indata_padded[-indata.shape[0]:] = indata
                    latest_indata = indata_padded
                else:
                    latest_indata[:] = indata[-latest_indata.shape[0]:]

        client.set_process_callback(process)
        client.activate()

        all_ports = client.get_ports(is_output=True)
        system_audio_ports = [p for p in all_ports if "playback" in p.name.lower() or "loopback" in p.name.lower() or "spotify" in p.name.lower()]
        if len(system_audio_ports) >= len(inports):
            for i, inport in enumerate(inports):
                client.connect(system_audio_ports[i], inport)

        try:
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.VIDEORESIZE:
                        window_size[0], window_size[1] = event.w, event.h
                        screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                with buffer_lock:
                    indata_copy = latest_indata.copy()
                audio_callback(indata_copy, CHUNK, None, None)
                pygame.time.wait(10)
        finally:
            client.deactivate()
            client.close()
            pygame.quit()

        return

    devices = get_enabled_input_devices()


    pygame.init()
    icon_surface = pygame.image.load(resource_path("avatar_65ee593544d6_512.png"))
    pygame.display.set_caption("Arkam's Audio Visualizer")
    pygame.display.set_icon(icon_surface)
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    font = pygame.font.SysFont(None, 28)

    device_index = find_loopback_device(devices)
    if device_index is None:
        device_index = select_device_pygame(devices, screen, font)
    sample_rate = int(sd.query_devices()[device_index]['default_samplerate'])

    pygame.mixer.init(frequency=sample_rate)

    audio_callback = make_audio_callback(
        screen, window_size, BARS, FLOOR_OFFSET, GAIN, min_norm, BIN_FLOOR, smoothing, buffer, prev_heights,
        volume, log_bins, sample_rate, CHUNK
    )

    with sd.InputStream(
        samplerate=sample_rate,
        device=device_index,
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