# -*- coding: utf-8 -*-
"""ChatTTS batch voice-seed scan: synthesize 50 seeds and auto-pick girlish/loli
voices by fundamental frequency (F0). Output: the top-10 candidates sorted by
F0 under samples/chattts_girls/ plus a selection log.
"""
import os
import sys

import numpy as np
import torch

import ChatTTS

TEXT = "Task done! I've been watching it for you~"
N_SEEDS = 50
TOP_N = 10


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    import librosa
    import scipy.io.wavfile as wavfile

    print("Loading ChatTTS...")
    chat = ChatTTS.Chat()
    chat.load(compile=False, source="huggingface")
    print(f"starting to synthesize {N_SEEDS} voice seeds (GPU, ~2-3 minutes)...")

    results = []
    for seed in range(N_SEEDS):
        torch.manual_seed(seed)
        spk = chat.sample_random_speaker()
        pi = ChatTTS.Chat.InferCodeParams(
            spk_emb=spk, temperature=0.3, top_P=0.7, top_K=20,
            prompt="[speed_5]")
        pr = ChatTTS.Chat.RefineTextParams(prompt="[oral_2][laugh_0]")
        try:
            wavs = chat.infer([TEXT], params_infer_code=pi,
                              params_refine_text=pr, use_decoder=True)
            w = wavs[0]
            if hasattr(w, "numpy"):
                arr = w.numpy()
            else:
                arr = np.asarray(w)
            arr = arr.reshape(-1).astype("float32")
            f0 = librosa.yin(arr, fmin=100, fmax=600, sr=24000,
                             frame_length=2048)
            voiced = f0[f0 > 0]
            mean_f0 = float(voiced.mean()) if len(voiced) else 0.0
            results.append((seed, mean_f0, arr))
            print(f"seed {seed:3d}: mean F0 {mean_f0:6.1f} Hz")
        except Exception as e:
            print(f"seed {seed:3d}: ERR {e}")

    results.sort(key=lambda x: -x[1])
    print(f"\n=== top {TOP_N} highest-F0 voices (girlish/loli candidates) ===")
    for i, (seed, f0, arr) in enumerate(results[:TOP_N]):
        target = os.path.join(out_dir, f"{i+1:02d}_seed{seed}_F0{f0:.0f}Hz.wav")
        wavfile.write(target, 24000, arr)
        print(f"  {i+1:2d}. seed={seed}  F0={f0:.0f}Hz -> {target}")
    print("done. output dir:", os.path.abspath(out_dir))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join("samples", "chattts_girls")
    main(out)
