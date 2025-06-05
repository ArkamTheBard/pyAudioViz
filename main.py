import math
import numpy
import pygame
import time
import threading

from pydub import AudioSegment
from pydub.playback import play


def log_bins(spectrum, bars, sample_rate, chunk_size, bin_floor=10.0):
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


def draw_slider(screen, value, SLIDER_X, SLIDER_Y, SLIDER_WIDTH, SLIDER_HEIGHT):
    pygame.draw.rect(screen, (100, 100, 100), (SLIDER_X, SLIDER_Y, SLIDER_WIDTH, SLIDER_HEIGHT))
    handle_x = SLIDER_X + int(value * (SLIDER_WIDTH - 10))
    pygame.draw.rect(screen, (0, 200, 0), (handle_x, SLIDER_Y - 5, 10, SLIDER_HEIGHT + 10))

def main():
    CHUNK = 2048
    BARS = 64
    WIDTH, HEIGHT = 800, 600
    BAR_WIDTH = WIDTH // BARS

    SLIDER_WIDTH = 300
    SLIDER_HEIGHT = 20
    SLIDER_X = (WIDTH - SLIDER_WIDTH) // 2
    SLIDER_Y = HEIGHT - 30

    BIN_FLOOR = 10.0
    min_norm = 100.0
    FLOOR = HEIGHT - 40
    GAIN = 2.0


    audio = AudioSegment.from_mp3("lightson.mp3").set_channels(1)
    samples = numpy.array(audio.get_array_of_samples())
    sample_rate = audio.frame_rate
    total_chunks = len(samples) // CHUNK

    audio.export('temp.wav', format='wav')

    pygame.init()
    icon_surface = pygame.image.load("avatar_65ee593544d6_512.png")
    pygame.mixer.init(frequency=sample_rate)
    pygame.display.set_caption("Arkam's Audio Visualizer")
    pygame.display.set_icon(icon_surface)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    pygame.mixer.music.load('temp.wav')
    pygame.mixer.music.play()

    prev_heights = [0] * BARS
    smoothing = 0.80

    volume = .25
    pygame.mixer.music.set_volume(volume)
    dragging = False

    running = True
    while running and pygame.mixer.music.get_busy():
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if SLIDER_X <= mx <= SLIDER_X + SLIDER_WIDTH and SLIDER_Y <= my <= SLIDER_Y + SLIDER_HEIGHT:
                    dragging = True
            elif event.type == pygame.MOUSEBUTTONUP:
                dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                mx = event.pos[0]
                value = min(max((mx - SLIDER_X) / (SLIDER_WIDTH - 10), 0), 1)
                volume = value
                pygame.mixer.music.set_volume(volume)

        ms = pygame.mixer.music.get_pos()
        i = int((ms / 1000) * sample_rate // CHUNK)
        if i >= total_chunks:
            break

        chunk = samples[i * CHUNK:(i + 1) * CHUNK]
        if len(chunk) < CHUNK:
            chunk = numpy.pad(chunk, (0, CHUNK - len(chunk)), 'constant')

        window = numpy.hanning(CHUNK)
        chunk = chunk * window

        spectrum = numpy.abs(numpy.fft.rfft(chunk)) * GAIN
        spectrum = numpy.power(spectrum, 0.7)
        bars = log_bins(spectrum, BARS, sample_rate, CHUNK, BIN_FLOOR)
        max_val = max(numpy.max(bars), min_norm)
        heights = [max(8, int((h / max_val) * (HEIGHT-40) * volume)) if volume > 0 else 0 for h in bars]

        heights = [int(smoothing * prev + (1 - smoothing) * curr) for prev, curr in zip(prev_heights, heights)]
        prev_heights = heights

        screen.fill((0, 0, 0))
        pygame.draw.line(screen, (200, 200, 200), (0, FLOOR), (WIDTH, FLOOR), 2)
        for j,h in enumerate(heights):
            bar_top = max(FLOOR - h, 0)
            pygame.draw.rect(screen, (0, 255, 0), (j*BAR_WIDTH, bar_top, BAR_WIDTH-2, h))

        draw_slider(screen, volume, SLIDER_X, SLIDER_Y, SLIDER_WIDTH, SLIDER_HEIGHT)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()