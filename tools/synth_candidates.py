# -*- coding: utf-8 -*-
"""Candidate voice synthesis script: generate several "cutified" mp3 variants
for auditioning.
Usage: python synth_candidates.py [output_dir]
"""
import asyncio
import os
import sys

import edge_tts

TEXT_HURRAY = "Task done! I've been watching it for you~"
TEXT_CHAT = "Bullying a big blue whale?"

# (filename, voice, pitch, rate)
CANDIDATES = [
    ("01_xiaoyi_original", "zh-CN-XiaoyiNeural", "+0Hz", "+0%"),
    ("02_xiaoyi_loli30", "zh-CN-XiaoyiNeural", "+30Hz", "+10%"),
    ("03_xiaoyi_loli50", "zh-CN-XiaoyiNeural", "+50Hz", "+10%"),
    ("04_xiaoyi_super_loli50_fast", "zh-CN-XiaoyiNeural", "+50Hz", "+25%"),
    ("05_xiaoxiao_kid50", "zh-CN-XiaoxiaoNeural", "+50Hz", "+10%"),
    ("06_taiwanese_HsiaoYu", "zh-TW-HsiaoYuNeural", "+30Hz", "+10%"),
    ("07_cantonese_HiuMaan", "zh-HK-HiuMaanNeural", "+30Hz", "+10%"),
]


async def synth(name, voice, pitch, rate, out_dir):
    target = os.path.join(out_dir, f"{name}.mp3")
    com = edge_tts.Communicate(TEXT_HURRAY, voice, pitch=pitch, rate=rate)
    await com.save(target)
    return target


async def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, voice, pitch, rate in CANDIDATES:
        try:
            target = await synth(name, voice, pitch, rate, out_dir)
            print(f"OK  {name} ({voice} pitch={pitch} rate={rate}) "
                  f"-> {os.path.getsize(target)}B")
        except Exception as e:
            print(f"ERR {name}: {e}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "samples", "candidates")
    asyncio.run(main(out))
    print("done, output dir:", os.path.abspath(out))
