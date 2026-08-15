# -*- coding: utf-8 -*-
"""Kids voice candidates v2: gentle Hz pitch levels (edge-tts only supports Hz)."""
import asyncio
import os
import sys

import edge_tts

TEXT = "Task done! I've been watching it for you~ Hey, come take a quick look!"

# (filename, voice, pitch, rate)
CANDIDATES = [
    ("01_xiaoyi_p15Hz", "zh-CN-XiaoyiNeural", "+15Hz", "+5%"),
    ("02_xiaoyi_p20Hz", "zh-CN-XiaoyiNeural", "+20Hz", "+5%"),
    ("03_xiaoyi_p25Hz", "zh-CN-XiaoyiNeural", "+25Hz", "+0%"),
    ("04_xiaoyi_original_fast", "zh-CN-XiaoyiNeural", "+0Hz", "+15%"),
    ("05_xiaoxiao_p20Hz", "zh-CN-XiaoxiaoNeural", "+20Hz", "+0%"),
    ("06_xiaoxiao_p25Hz", "zh-CN-XiaoxiaoNeural", "+25Hz", "-5%"),
    ("07_taiwan_HsiaoYu_p15Hz", "zh-TW-HsiaoYuNeural", "+15Hz", "+5%"),
    ("08_xiaoyi_p30Hz_soft", "zh-CN-XiaoyiNeural", "+30Hz", "-5%"),
]


async def synth(name, voice, pitch, rate, out_dir):
    target = os.path.join(out_dir, f"{name}.mp3")
    com = edge_tts.Communicate(TEXT, voice, pitch=pitch, rate=rate)
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
        os.path.dirname(os.path.abspath(__file__)), "..", "samples", "kids2")
    asyncio.run(main(out))
    print("done, output dir:", os.path.abspath(out))
