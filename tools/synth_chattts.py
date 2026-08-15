# -*- coding: utf-8 -*-
"""ChatTTS local audition: synthesize candidates with different voice seeds and
write them to samples/chattts/.
ChatTTS highlights: oral (colloquial), laugh (natural laughter), break (pauses)
-- closest to natural human speech.
"""
import os
import sys

import torch
import torchaudio

import ChatTTS


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    print("Loading the ChatTTS model (first run downloads it, ~1GB)...")
    chat = ChatTTS.Chat()
    chat.load(compile=False, source="huggingface")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"inference device: {device} (CUDA: {torch.cuda.is_available()})")

    texts = [
        "Task done! I've been watching it for you~",
        "Hey, come here! I need you to take a quick look~",
    ]

    candidates = [
        # (name, seed, temperature, speed, oral, laugh)
        ("seed01_normal", 1, 0.3, 5, 2, 0),
        ("seed07_normal", 7, 0.3, 5, 2, 0),
        ("seed33_oral", 33, 0.3, 5, 5, 0),
        ("seed33_oral_laugh", 33, 0.3, 5, 5, 1),
        ("seed66_oral", 66, 0.4, 6, 5, 0),
        ("seed99_lively", 99, 0.5, 6, 6, 1),
        ("seed777_slow_cute", 777, 0.3, 4, 4, 0),
        ("seed2024_oral", 2024, 0.4, 5, 5, 0),
    ]

    for name, seed, temp, speed, oral, laugh in candidates:
        torch.manual_seed(seed)
        spk = chat.sample_random_speaker()
        params_infer = ChatTTS.Chat.InferCodeParams(
            spk_emb=spk,
            temperature=temp,
            top_P=0.7,
            top_K=20,
            prompt=f"[speed_{speed}]",
        )
        params_refine = ChatTTS.Chat.RefineTextParams(
            prompt=f"[oral_{oral}][laugh_{laugh}]")
        try:
            wavs = chat.infer(texts, params_infer_code=params_infer,
                              params_refine_text=params_refine, use_decoder=True)
            for i, w in enumerate(wavs):
                # Compatible with both tensor and numpy returns
                if hasattr(w, "squeeze"):
                    w = w.squeeze()
                if hasattr(w, "numpy"):
                    arr = w.numpy()
                else:
                    import numpy as np
                    arr = np.asarray(w)
                arr = arr.reshape(-1).astype("float32")
                target = os.path.join(out_dir, f"{name}_{i}.wav")
                import scipy.io.wavfile as wavfile
                wavfile.write(target, 24000, arr)
            print(f"OK  {name} (seed={seed} temp={temp} speed={speed} "
                  f"oral={oral} laugh={laugh})")
        except Exception as e:
            import traceback
            print(f"ERR {name}: {e}")
            traceback.print_exc()

    print("done, output dir:", os.path.abspath(out_dir))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "samples", "chattts")
    main(out)
