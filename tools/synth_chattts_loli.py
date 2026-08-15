# -*- coding: utf-8 -*-
"""Pitch-shift the highest ChatTTS female-voice seeds into "loli" variants and
write audition candidates. librosa pitch_shift: three levels +4/+6/+8 semitones.
"""
import os
import sys

import numpy as np
import torch

import ChatTTS

TEXT = "Task done! I've been watching it for you~"
GIRL_SEEDS = [10, 31, 49]   # highest-F0 female seeds found during scanning


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    import librosa
    import scipy.io.wavfile as wavfile

    print("Loading ChatTTS...")
    chat = ChatTTS.Chat()
    chat.load(compile=False, source="huggingface")

    for seed in GIRL_SEEDS:
        torch.manual_seed(seed)
        spk = chat.sample_random_speaker()
        pi = ChatTTS.Chat.InferCodeParams(
            spk_emb=spk, temperature=0.3, top_P=0.7, top_K=20,
            prompt="[speed_5]")
        pr = ChatTTS.Chat.RefineTextParams(prompt="[oral_2][laugh_0]")
        wavs = chat.infer([TEXT], params_infer_code=pi,
                          params_refine_text=pr, use_decoder=True)
        w = wavs[0]
        arr = w.numpy().reshape(-1) if hasattr(w, "numpy") else np.asarray(w).reshape(-1)
        arr = arr.astype("float32")
        # original
        wavfile.write(os.path.join(out_dir, f"seed{seed}_original.wav"), 24000, arr)
        # three pitch-shift levels
        for n_semi in (4, 6, 8):
            shifted = librosa.effects.pitch_shift(arr, sr=24000, n_steps=n_semi)
            wavfile.write(os.path.join(out_dir, f"seed{seed}_loli_p{n_semi}.wav"),
                          24000, shifted.astype("float32"))
            print(f"OK seed{seed} +{n_semi} semitones")
    print("done, output dir:", os.path.abspath(out_dir))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "samples", "chattts_loli")
    main(out)
