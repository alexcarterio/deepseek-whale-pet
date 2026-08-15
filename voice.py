# -*- coding: utf-8 -*-
"""
Voice announcements (Whale Pet capability layer).

Dual engine, cute voices:
  edge  -- Microsoft Edge online TTS (free, no key). Default preset is the
           Xiaoyi "sweet" voice: Xiaoyi female voice + a strong pitch lift
           (+15Hz) + a light, quick rate -> a cheerful, playful feel.
           Synthesized output is cached by (voice + pitch + rate + text) hash
           under %APPDATA%\\WhalePet\\voice_cache\\, so fixed phrases replay
           instantly and work offline once generated.
  sapi  -- Windows offline voice (fallback; used automatically when edge hits
           a network error, or switchable manually).

Threading model:
  Synthesis runs on a background thread (edge-tts is async). Playback is driven
  by the GUI main thread calling poll() periodically (QMediaPlayer must be used
  on the GUI thread). The queue is FIFO and holds at most 3 items to avoid noise.
"""
import asyncio
import hashlib
import os
import threading

CACHE_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                         "WhalePet", "voice_cache")

# Voice presets: name -> (edge voice, pitch, rate)
EDGE_VOICES = {
    "Xiaoyi - Sweet (recommended)": ("zh-CN-XiaoyiNeural", "+15Hz", "-5%"),
    "Xiaoyi - Younger": ("zh-CN-XiaoyiNeural", "+20Hz", "-5%"),
    "Xiaoyi - Lively": ("zh-CN-XiaoyiNeural", "+0Hz", "+5%"),
    "Xiaoxiao - Soft": ("zh-CN-XiaoxiaoNeural", "+20Hz", "-5%"),
    "HsiaoYu - Taiwanese": ("zh-TW-HsiaoYuNeural", "+15Hz", "-5%"),
}
EDGE_DEFAULT = "Xiaoyi - Sweet (recommended)"


class Voice:
    def __init__(self, enabled=True, engine="edge", preset=EDGE_DEFAULT):
        self.enabled = bool(enabled)
        self.engine = engine if engine in ("edge", "sapi") else "edge"
        self.preset = preset if preset in EDGE_VOICES else EDGE_DEFAULT
        self.voice_name, self.pitch, self.rate = EDGE_VOICES[self.preset]
        self._lock = threading.Lock()
        self._synth_thread = None
        self._pending = []            # pending synthesis queue (max 3 items)
        self._ready = []              # [(src, text)] synthesized and ready to play
        self._player = None           # QMediaPlayer (created lazily on main thread)
        self._audio = None
        self._playing = False
        self._sapi_lock = threading.Lock()   # serialize SAPI fallback playback

    # ---------- GUI-facing API ----------
    def speak(self, text, preset=None):
        """Non-blocking: enqueue synthesis (FIFO, max 3 items); poll() plays them.

        preset: optional preset name (a key of EDGE_VOICES), used for emotional
        segmentation -- e.g. a cheer phrase uses the "Lively" voice (higher pitch
        and faster rate) while the main text uses the default sweet voice, so a
        continuous read sounds lively and varied.
        """
        if not self.enabled or not text or not text.strip():
            return False
        with self._lock:
            self._pending.append((text.strip(), preset))
            while len(self._pending) > 3:
                self._pending.pop(0)
            alive = self._synth_thread is not None and self._synth_thread.is_alive()
        if not alive:
            self._synth_thread = threading.Thread(target=self._synth_worker,
                                                  daemon=True, name="pet-voice-synth")
            self._synth_thread.start()
        return True

    def poll(self):
        """Called periodically by the GUI main thread (pet tick): plays finished
        audio serially."""
        if not self.enabled or self._playing:
            return
        with self._lock:
            item = self._ready.pop(0) if self._ready else None
        if item is not None:
            self._play(item)

    def stop(self):
        with self._lock:
            self._pending.clear()
            self._ready.clear()
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
        self._playing = False

    def set_engine(self, engine, preset=None):
        with self._lock:
            self.engine = engine if engine in ("edge", "sapi") else "edge"
            if preset and preset in EDGE_VOICES:
                self.preset = preset
                self.voice_name, self.pitch, self.rate = EDGE_VOICES[preset]

    # ---------- background synthesis ----------
    def _params_for(self, preset):
        """Actual (voice, pitch, rate) used for this utterance."""
        if preset and preset in EDGE_VOICES:
            return EDGE_VOICES[preset]
        return self.voice_name, self.pitch, self.rate

    def _cache_path(self, text, preset=None):
        voice, pitch, rate = self._params_for(preset)
        key = hashlib.md5(
            f"{self.engine}|{voice}|{pitch}|{rate}|{text}"
            .encode("utf-8")).hexdigest()
        return os.path.join(CACHE_DIR, f"{key}.mp3")

    def _synth_worker(self):
        while True:
            with self._lock:
                item = self._pending.pop(0) if self._pending else None
            if item is None:
                with self._lock:
                    if not self._pending:
                        break
                continue
            text, preset = item
            if self.engine == "sapi":
                with self._lock:
                    self._ready.append(("sapi:" + text, text))
                continue
            voice, pitch, rate = self._params_for(preset)
            cache = self._cache_path(text, preset)
            if not os.path.exists(cache) or os.path.getsize(cache) == 0:
                try:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                    asyncio.run(self._synth_edge(text, cache, voice, pitch, rate))
                except Exception:
                    # edge failed -> fall back to offline SAPI playback
                    with self._lock:
                        self._ready.append(("sapi:" + text, text))
                    continue
            with self._lock:
                self._ready.append((cache, text))
                while len(self._ready) > 3:
                    self._ready.pop(0)

    async def _synth_edge(self, text, path, voice=None, pitch=None, rate=None):
        import edge_tts
        com = edge_tts.Communicate(
            text,
            voice or self.voice_name,
            pitch=pitch if pitch is not None else self.pitch,
            rate=rate if rate is not None else self.rate)
        await com.save(path)

    # ---------- main-thread playback ----------
    def _play(self, item):
        src, text = item
        if src.startswith("sapi:"):
            threading.Thread(target=self._sapi_speak, args=(text,),
                             daemon=True, name="pet-voice-sapi").start()
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            if self._player is None:
                self._player = QMediaPlayer()
                self._audio = QAudioOutput()
                self._audio.setVolume(0.9)
                self._player.setAudioOutput(self._audio)
                self._player.mediaStatusChanged.connect(self._on_media_status)
            self._player.stop()
            self._player.setSource(QUrl.fromLocalFile(src))
            self._playing = True
            self._player.play()
        except Exception:
            self._playing = False
            threading.Thread(target=self._sapi_speak, args=(text,),
                             daemon=True, name="pet-voice-sapi").start()

    def _on_media_status(self, status):
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if status in (QMediaPlayer.MediaStatus.EndOfMedia,
                          QMediaPlayer.MediaStatus.InvalidMedia):
                self._playing = False
        except Exception:
            self._playing = False

    def _sapi_speak(self, text):
        """SAPI fallback playback (serialized to avoid overlap)."""
        try:
            with self._sapi_lock:
                import win32com.client
                v = win32com.client.Dispatch("SAPI.SpVoice")
                v.Speak(text)
        except Exception:
            pass


# ---------- self-check: synthesize samples (does not play them) ----------
if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "samples"
    os.makedirs(out_dir, exist_ok=True)
    for label, (name, pitch, rate) in EDGE_VOICES.items():
        v = Voice(enabled=True, engine="edge", preset=label)
        target = os.path.join(out_dir, f"sample_{label}.mp3")
        try:
            asyncio.run(v._synth_edge("Task done! I've been watching it for you~", target))
            print(f"OK  {label} ({name} pitch={pitch}) -> {os.path.getsize(target)}B")
        except Exception as e:
            print(f"ERR {label}: {e}")
