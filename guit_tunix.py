#!/usr/bin/env python3
"""
Accordeur avec YIN + barre colorée (bleu => rouge) + fréquence mesurée
"""

import numpy as np
import sounddevice as sd
import threading
import time
from math import isfinite

# ---------- paramètres ----------
FS = 44100
WINDOW_SIZE = 8192
BLOCKSIZE = 1024
HOP_TIME = 0.04
RMS_THRESHOLD = 1e-4
SMOOTH_ALPHA = 0.6
BAR_SPAN = 10.0
BAR_WIDTH = 56
YIN_THRESHOLD = 0.1  # plus petit = plus précis mais + sensible au bruit

TARGET_FREQS = {
    'E2': 82.41,
    'A2': 110.00,
    'D3': 146.83,
    'G3': 196.00,
    'B3': 246.94,
    'E4': 329.63
}

RESET = '\033[0m'

# ---------- buffers ----------
buffer = np.zeros(WINDOW_SIZE, dtype='float32')
buf_lock = threading.Lock()
stop_flag = False
detected_freq = 0.0
prev_freq = 0.0

# ---------- outils ----------
def get_closest_string(freq):
    return min(TARGET_FREQS.items(), key=lambda x: abs(x[1] - freq))

def lerp(a, b, t):
    return int(round(a + (b - a) * t))

def rgb_for_diff(diff_hz, span):
    t = max(-1.0, min(1.0, diff_hz / span))
    if t <= -0.5:
        s = (t + 1.0) / 0.5
        r = lerp(0, 0, s)
        g = lerp(0, 255, s)
        b = lerp(255, 255, s)
    elif t <= 0.0:
        s = (t + 0.5) / 0.5
        r = lerp(0, 0, s)
        g = lerp(255, 255, s)
        b = lerp(255, 0, s)
    elif t <= 0.5:
        s = (t - 0.0) / 0.5
        r = lerp(0, 255, s)
        g = lerp(255, 255, s)
        b = lerp(0, 0, s)
    else:
        s = (t - 0.5) / 0.5
        r = lerp(255, 255, s)
        g = lerp(255, 0, s)
        b = lerp(0, 0, s)
    return r, g, b

def ansi_truecolor(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def freq_to_bar_colored(current, target, width=BAR_WIDTH, span=BAR_SPAN):
    low = target - span / 2
    high = target + span / 2
    rng = high - low
    center = width // 2
    chars = []
    for i in range(width):
        pos_freq = low + (i / (width - 1)) * rng
        diff_pos = pos_freq - target
        r, g, b = rgb_for_diff(diff_pos, span/2)
        col = ansi_truecolor(r, g, b)
        ch = '+' if i == center else '-'
        chars.append((col, ch))
    cur_pos = int(round((current - low) / rng * (width - 1)))
    cur_pos = max(0, min(width - 1, cur_pos))
    cur_diff = current - target
    cr, cg, cb = rgb_for_diff(cur_diff, span/2)
    cursor_col = ansi_truecolor(cr, cg, cb)
    cursor_sym = '│ ' if cur_pos == center else '⭢ '
    chars[cur_pos] = (cursor_col, cursor_sym)
    return ''.join(f"{col}{ch}{RESET}" for col, ch in chars)

# ---------- implémentation de YIN ----------
def yin_pitch(signal, fs, fmin=60, fmax=1000, threshold=YIN_THRESHOLD):
    N = len(signal)
    max_tau = int(fs / fmin)
    min_tau = int(fs / fmax)

    # étape 1 : différence cumulée
    diff = np.zeros(max_tau)
    for tau in range(1, max_tau):
        diff[tau] = np.sum((signal[:N - tau] - signal[tau:N]) ** 2)

    # étape 2 : normalisation cumulative
    cum_sum = np.cumsum(diff[1:])
    cmndf = np.ones(max_tau)
    cmndf[1:] = diff[1:] * np.arange(1, max_tau) / (cum_sum + 1e-8)

    # étape 3 : recherche du premier minimum sous le seuil
    tau = min_tau
    while tau < max_tau:
        if cmndf[tau] < threshold:
            while tau + 1 < max_tau and cmndf[tau + 1] < cmndf[tau]:
                tau += 1
            break
        tau += 1
    else:
        return 0.0

    # étape 4 : interpolation parabolique
    if tau > 1 and tau < max_tau - 1:
        s0, s1, s2 = cmndf[tau - 1], cmndf[tau], cmndf[tau + 1]
        denom = (s0 + s2 - 2 * s1)
        if denom != 0:
            tau += 0.5 * (s0 - s2) / denom

    return fs / tau

# ---------- callback audio ----------
def audio_callback(indata, frames, time_info, status):
    global buffer
    if status:
        print(status, flush=True)
    mono = indata[:, 0].astype('float32')
    with buf_lock:
        f = len(mono)
        if f >= WINDOW_SIZE:
            buffer[:] = mono[-WINDOW_SIZE:]
        else:
            buffer[:-f] = buffer[f:]
            buffer[-f:] = mono

# ---------- thread de traitement ----------
def processing_thread():
    global detected_freq, prev_freq, stop_flag
    while not stop_flag:
        time.sleep(HOP_TIME)
        with buf_lock:
            x = buffer.copy()
        if np.max(np.abs(x)) < 1e-8:
            continue
        x -= np.mean(x)
        rms = np.sqrt(np.mean(x * x))
        if rms < RMS_THRESHOLD:
            continue
        w = np.hanning(len(x))
        xw = x * w
        freq = yin_pitch(xw, FS)
        if freq <= 0 or not isfinite(freq):
            continue
        if prev_freq == 0.0:
            out = freq
        else:
            out = SMOOTH_ALPHA * freq + (1.0 - SMOOTH_ALPHA) * prev_freq
        prev_freq = out
        detected_freq = out

# ---------- affichage ----------
def main():
    global stop_flag
    print("Accordeur YIN — barre colorée (bleu => rouge). Ctrl+C pour quitter.")
    t = threading.Thread(target=processing_thread, daemon=True)
    t.start()
    with sd.InputStream(channels=1, samplerate=FS, blocksize=BLOCKSIZE, callback=audio_callback):
        try:
            while True:
                f = detected_freq
                if f <= 0:
                    disp = "--"
                    note = "--"
                    bar = " " * (BAR_WIDTH * 2)
                else:
                    note, target = get_closest_string(f)
                    disp = f"{f:6.2f}"
                    bar = freq_to_bar_colored(f, target, width=BAR_WIDTH, span=BAR_SPAN)
                print(f"{note}: {disp} Hz {bar}   ", end='\r')
                time.sleep(HOP_TIME)
        except KeyboardInterrupt:
            stop_flag = True
            t.join()
            print("\nFin.")

if __name__ == "__main__":
    main()

