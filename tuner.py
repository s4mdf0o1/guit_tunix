from math import isfinite
import numpy as np
import pyaudio

from gi.repository import GLib

import threading
import time

from ruamel.yaml import YAML
yaml = YAML(typ="safe")

class Tuner:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = self.__class__.__name__
        with open("config.yaml", "r") as f:
            self.cfg = yaml.load(f) 
        self.buffer = np.zeros(self.cfg['WIN_SIZE'], dtype='float32')
        self.buf_lock = threading.Lock()
        self.stop_flag = False
        self.detected_freq = 0.0
        self.prev_freq = 0.0
        self.noise_rms = 1e-8

    def get_closest_string(self, freq):
        return min(self.cfg['TARGET_FREQS'].items(), key=lambda x: abs(x[1] - freq))

    def lerp(self, a, b, t): return int(round(a + (b - a) * t))

    def yin_pitch(self, signal, fs, fmin=60, fmax=1000):
        threshold=self.cfg['YIN_THRESHOLD']
        N = len(signal)
        max_tau = int(fs / fmin)
        min_tau = int(fs / fmax)
        diff = np.zeros(max_tau)
        for tau in range(1, max_tau):
            diff[tau] = np.sum((signal[:N - tau] - signal[tau:N])**2)
        cum_sum = np.cumsum(diff[1:])
        cmndf = np.ones(max_tau)
        cmndf[1:] = diff[1:] * np.arange(1, max_tau) / (cum_sum + 1e-8)
        tau = min_tau
        while tau < max_tau:
            if cmndf[tau] < threshold:
                while tau+1 < max_tau and cmndf[tau+1] < cmndf[tau]:
                    tau += 1
                break
            tau += 1
        else:
            return 0.0
        if 1 < tau < max_tau-1:
            s0,s1,s2 = cmndf[tau-1],cmndf[tau],cmndf[tau+1]
            denom = (s0+s2-2*s1)
            if denom != 0:
                tau += 0.5*(s0-s2)/denom
        return fs/tau

    def audio_callback(self, indata, frames, time_info=None, status=None):
        # global buffer
        # if indata.ndim == 2:
            # indata = indata[:,0]  # prendre le premier canal
        # mono = indata.astype('float32')
        mono = indata[:,0].astype('float32') / 32768.0
        with self.buf_lock:
            f = len(mono)
            if f >= self.cfg['WIN_SIZE']: self.buffer[:] = mono[-self.cfg['WIN_SIZE']:]
            else:
                self.buffer[:-f] = self.buffer[f:]
                self.buffer[-f:] = mono

    def processing_thread(self, dialog=None):
        # global detected_freq, prev_freq, stop_flag
        while not self.stop_flag:

            time.sleep(self.cfg['HOP_TIME'])
            with self.buf_lock: x = self.buffer.copy()
            if np.max(np.abs(x)) < 1e-8: continue
            x -= np.mean(x)
            rms = np.sqrt(np.mean(x*x))

            if rms < self.cfg['RMS_ACTIVE_THRESHOLD']:
                self.noise_rms = self.cfg['ALPHA'] * self.noise_rms \
                        + (1.0 - self.cfg['ALPHA']) * rms

            adaptive_threshold = np.clip(
                    3 * self.noise_rms, 
                    self.cfg['RMS_MIN'], 
                    self.cfg['RMS_MAX']
                    )


            # print(f"{self.noise_rms=} {rms=} {adaptive_threshold}")
            if rms < adaptive_threshold:
                GLib.idle_add(
                        self.update_display, 
                        "--", 0.0, 0.0, 
                        "▢" * self.cfg['BAR_WIDTH']
                        )

                continue
            xw = x * np.hanning(len(x))
            freq = self.yin_pitch(xw, self.cfg['FS'])
            if freq <= 0 or not isfinite(freq):
                GLib.idle_add(self.update_display, 
                            "--", 0.0, 0.0, 
                            "▢" * self.cfg['BAR_WIDTH']
                            )

                continue
            out = freq if self.prev_freq==0.0 \
                    else self.cfg['SMOOTH_ALPHA']*freq \
                        +(1.0-self.cfg['SMOOTH_ALPHA'])*self.prev_freq
            self.prev_freq = out; self.detected_freq = out
            # if dialog:
            note,target = self.get_closest_string(out)
            offset = out - target
            bar = self.freq_to_bar_pango(out, target)
            GLib.idle_add(self.update_display, note, out, offset, bar)


