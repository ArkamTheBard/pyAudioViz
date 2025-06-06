import math
import numpy
import pygame
import re
import sounddevice as sd


def log_bins(spectrum, bars, sample_rate, chunk_size, bin_floor):
    freqs = numpy.fft.rfftfreq(chunk_size, 1 / sample_rate)
    min_freq, max_freq = freqs[1], freqs[-1]
    log_edges = numpy.logspace(math.log10(min_freq), math.log10(max_freq), bars + 1)
    bar_vals = []
    for i in range(bars):
        idx = numpy.where((freqs >= log_edges[i]) & (freqs < log_edges[i+1]))[0]
        if len(idx) > 0:
            bar_vals.append(max(numpy.mean(spectrum[idx]), bin_floor))
        else:
            bar_vals.append(bin_floor)
    return bar_vals

def main():
    CHUNK = 2048
    BARS = 64
    WIDTH, HEIGHT = 800, 600
    BAR_WIDTH = WIDTH // BARS

    BIN_FLOOR = 0.1
    min_norm = 10.0
    FLOOR = HEIGHT - 40
    GAIN = 2.0
    smoothing = 0.80
    volume = 0.25

    # Below code works with Audacity Stereo Mix passthrough

    devices =  sd.query_devices()
    stereo_mix_index = None
    for idx, dev, in enumerate(devices):
        if dev['max_input_channels'] > 0 and re.search(r'stereo ?mix', dev['name'], re.IGNORECASE):
            stereo_mix_index = idx
            break
    if stereo_mix_index is None:
        raise RuntimeError("No Stereo Mix device found. Please enable it in your sound settings.")

    sample_rate = int(devices[stereo_mix_index]['default_samplerate'])

    pygame.init()
    icon_surface = pygame.image.load("avatar_65ee593544d6_512.png")
    pygame.mixer.init(frequency=sample_rate)
    pygame.display.set_caption("Arkam's Audio Visualizer")
    pygame.display.set_icon(icon_surface)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    prev_heights = [0] * BARS
    running = True

    def audio_callback(indata, frames, time, status):
        nonlocal prev_heights, running, volume
        if not running:
            raise sd.CallbackStop
        chunk = indata[:, 0]
        window = numpy.hanning(len(chunk))
        chunk = chunk * window
        spectrum = numpy.abs(numpy.fft.rfft(chunk)) * GAIN
        spectrum = numpy.power(spectrum, 0.7)
        bars = log_bins(spectrum, BARS, sample_rate, len(chunk), BIN_FLOOR)
        max_val = max(numpy.max(bars), min_norm)
        heights = [max(7, int((h / max_val) * (HEIGHT-40))) if volume > 0 else 0 for h in bars]
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
        device=stereo_mix_index,
        channels=2,
        dtype='float32',
        blocksize=CHUNK,
        callback=audio_callback
    ):
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            pygame.time.wait(10)

    pygame.quit()


if __name__ == "__main__":
    main()