# deepseek-whale-pet

[![CI](https://github.com/alexcarterio/deepseek-whale-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/alexcarterio/deepseek-whale-pet/actions/workflows/ci.yml)

![Three views of the whale pet](assets/pet-showcase.png)
![Walking animation](assets/pet-walk.gif)

A transparent, always-on-top desktop pet for Windows — a cute whale companion
that lives on your desktop, walks around, talks, and keeps an eye on your
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) (DSH)
sessions. When a DSH work turn finishes, it pops a speech bubble and announces
it in a cute voice; when DSH is waiting for your approval or a question, it
nudges you to act. It can also look up your DeepSeek API balance, launch DSH
for you, and forward DSH events to your phone via ntfy.

The pet reads DSH's session data in a **read-only** way and never modifies or
restarts DSH.

---

## Features

### Desktop pet

- Three-view walking: side (auto-mirrored), back (walking up), front (walking down).
- Three movement modes: **Free roam / Follow cursor / Stay put**.
- Interactions: drag (with voice lines), single-click bounce + sass + chat entry,
  double-click feeding (dried fish, cake, lollipop, dumplings, diamond).
- Speech-bubble system: random lines, reaction lines, and an inner "chain-of-thought"
  voice shown in a gray italic bubble.
- Detail animations: breathing, swaying, jumping, eating, direction cross-fade,
  acceleration/deceleration inertia, and random resting.
- AI chat: click the 💬 entry to chat via the DeepSeek `deepseek-chat` model,
  keeping up to 40 messages of context.
- Weather lookup (right-click menu, data from [wttr.in](https://wttr.in)).
- System monitoring: bubbles when CPU > 90%, RAM > 95%, or NVIDIA GPU > 80 °C.
- Tray icon, always-on-top, click-through (mouse passthrough), start-on-boot,
  and remembered position/settings.

### DSH integration

- **DSH session-done notification**: when one DSH work turn finishes, the pet
  shows a bubble and speaks it aloud.
- **DSH waiting-for-user notification**: when DSH is waiting for an approval or a
  question, the pet prompts you to act.
- **DeepSeek balance lookup**: "View DeepSeek Balance" in the right-click menu,
  with a bubble + voice readout, plus an automatic low-balance alert (silent
  hourly patrol).
- **Auto-launch DSH**: a few seconds after startup, the pet probes
  `127.0.0.1:<dsh_port>` and, if DSH Web is not running, launches it. It only
  *starts* DSH — it never stops or restarts it.
- **Phone push notifications (optional)**: forward DSH session events to your
  phone via [ntfy](https://ntfy.sh) (`dsh_push.py`).

---

## Requirements

- **Windows 10 or 11**
- **Python 3.11+** (tested with 3.13)
- **DSH (DeepSeek Harness)** — optional, required only for the DSH integration
  features
- An internet connection for the DeepSeek API, edge-tts voices, and weather

---

## Installation

### Option A — one-command installer

Double-click `install.bat`. It:

1. installs Python dependencies (`pip install -r requirements.txt`),
2. enables start-on-boot (which also enables the auto-launch-DSH behavior),
3. starts the pet.

### Option B — manual

```bat
py -3 -m pip install -r requirements.txt
py -3 desktop_pet.py
```

For daily use, just double-click `start_pet.bat`.

> **Start on boot** can also be toggled from the right-click menu
> ("Start on Boot"). To remove it from a command line, run:
> `py -3 desktop_pet.py --uninstall-autostart` (or double-click `uninstall.bat`).

---

## Configuration

The default configuration template is
[`config.example.json`](config.example.json). On first run the pet creates the
actual `config.json` next to the script (in source mode) or under
`%APPDATA%\WhalePet\config.json` (in a frozen `.exe` build).

| Key | Default | Description |
|---|---|---|
| `mode` | `"wander"` | Movement mode: `wander` / `follow` / `still`. |
| `size` | `0.7` | Pet scale: `0.55` (small) / `0.7` (medium) / `0.9` (large). |
| `topmost` | `true` | Keep the pet always on top. |
| `passthrough` | `false` | Click-through (the pet becomes unclickable). |
| `autostart` | `false` | Start on boot (the installer sets this to `true`). |
| `x`, `y` | `0` | Saved window position (overwritten on exit). |
| `ds_api_key` | `""` | DeepSeek API key for chat and balance lookup. Leave empty to fall back to the DSH credentials file (`~/.dsh/.credentials.yaml`). |
| `city` | `""` | City name for the weather lookup (wttr.in). |
| `voice_enabled` | `true` | Voice announcements on/off. |
| `voice_name` | `""` | SAPI voice name (empty = system default). |
| `voice_engine` | `"edge"` | Voice engine: `edge` (online) or `sapi` (offline). |
| `say_voice` | `true` | Voice everyday lines (full voice mode only). |
| `voice_mode` | `"full"` | `full` (voiced pet) or `notify` (task notifications only). |
| `voice_preset` | `"Xiaoyi - Sweet (recommended)"` | edge-tts voice preset (see the "Voice Preset" menu). |
| `dsh_launch` | `true` | Auto-launch DSH after startup. |
| `dsh_dir` | `""` | DSH install directory (empty = auto-detect). |
| `dsh_port` | `3080` | DSH Web port. |
| `dsh_startup_delay` | `10` | Seconds after startup before probing DSH. |
| `dsh_notify_done` | `true` | Notify when a DSH session turn finishes. |
| `dsh_notify_waiting` | `true` | Notify when DSH is waiting for user action. |
| `dsh_notify_balance_low` | `true` | Auto-alert on low balance. |
| `balance_low_threshold` | `5.0` | Low-balance threshold (in CNY). |

---

## Privacy & Security

This is a pure client-side desktop app: it opens no listening ports and has no
inbound attack surface. Outbound data is limited to the following, all sent over
HTTPS:

| Data | Destination | Notes |
|---|---|---|
| Chat content + context (max 40 messages, in memory only) | DeepSeek API | Sent only while you use chat. |
| City name | wttr.in | Inherent to the weather lookup. |
| Voice announcement text | Microsoft Edge TTS | Fixed phrases and lines only — **never includes DSH session titles**. |
| DSH session data | none | Read-only access to local state files; nothing is written or transmitted. |

**API key storage:** your API key is stored in plaintext in `config.json`
(readable only by your own Windows account by default). To avoid this, leave
`ds_api_key` empty and keep the key in the DSH credentials file instead; more
advanced setups can use the Windows Credential Manager (DPAPI).

**Phone notifications (ntfy):** when `dsh_push.py` is enabled, session titles
are included in the notification body sent to the ntfy server. If that matters
to you, self-host ntfy by setting `NTFY_URL` to your own server.

**DSH access:** the pet only reads DSH's local session data. It never modifies,
stops, or restarts DSH.

---

## Usage

### Starting

- `start_pet.bat` — start the pet normally.
- `install.bat` — install dependencies + enable start-on-boot + first start.
- `py -3 desktop_pet.py` — start directly from a terminal.

### Interactions

| Action | Effect |
|---|---|
| Left-button drag | Drag the pet (it turns to face the direction and talks on release). |
| Single click | Bounce + a reaction line + the 💬 chat entry. |
| Double click | Open the feeding panel. |
| Right click (pet or tray icon) | Full menu. |

### Menu highlights

- **View DeepSeek Balance** — bubble + voice readout of your remaining balance.
- **DSH Status** — list the working state of recent DSH sessions.
- **Open DSH Web** — open the DSH Web UI at `http://127.0.0.1:<dsh_port>`.
- **Voice Announcements** / **Voice Mode** / **Voice Preset** — control voice output.
- **Auto-launch DSH** — toggle auto-launching DSH on startup.

### Voice announcements

The pet can speak through two engines:

- **edge** — Microsoft Edge online TTS (free, no key). Results are cached under
  `%APPDATA%\WhalePet\voice_cache\`.
- **sapi** — the built-in Windows offline voice, used automatically as a fallback
  when edge-tts is unreachable.

In **Notification only** voice mode, the pet stays quiet during normal use and
only speaks for task events (done / waiting / balance alerts).

### DSH integration

The pet polls DSH's session data every 2 seconds (read-only):

- `~/.dsh/storages/session_projcache.json` — session titles.
- `~/.dsh/sessions/<workspace>/<session-id>/session.jsonl.zstd` — the event log,
  used to detect exactly when a turn finishes (`turn/end`) and when the model is
  waiting for you (an `ask_user_question` call or a pending approval).

Set `DSH_HOME` to override the `~/.dsh` location. `dsh_dir` (or auto-detection)
tells the pet where DSH is installed so it can launch DSH Web if it is not
already running.

---

## Phone Notifications (optional)

`dsh_push.py` watches the same DSH session events and pushes them to your phone
via [ntfy](https://ntfy.sh). Run it with:

```bat
start_push.bat
```

or:

```bat
py -3 dsh_push.py
```

Test the channel with:

```bat
py -3 dsh_push.py --test
```

### Configuration

Set the environment variables before starting (or in your shell profile):

| Variable | Default | Description |
|---|---|---|
| `NTFY_URL` | `https://ntfy.sh` | The ntfy server to use. |
| `NTFY_TOPIC` | `YOUR_NTFY_TOPIC` | **Required.** Your ntfy topic name. A topic acts like a password — pick a long, random value. |
| `NTFY_TOKEN` | `""` | Optional ntfy account access token. |
| `NTFY_CLICK` | `""` | Optional URL opened when a notification is tapped (e.g. your DSH web entrypoint). |

To subscribe: install the ntfy app (or use the web UI at
[https://ntfy.sh](https://ntfy.sh)), subscribe to your topic, and set
`NTFY_TOPIC` to that exact value.

---

## Developer tools

The `tools/` directory contains helper scripts used during development to
audition voices, rework sprites, and package a release. They are **not required
to run the pet** — ordinary users can ignore them.

| Script | Purpose | Dependencies | Example |
|---|---|---|---|
| `tools/synth_candidates.py` | Generate several edge-tts "cutified" audition variants. | `edge-tts` (in `requirements.txt`) | `py tools/synth_candidates.py` |
| `tools/synth_kids.py` | Generate gentle kids-voice pitch variants with edge-tts. | `edge-tts` (in `requirements.txt`) | `py tools/synth_kids.py` |
| `tools/synth_chattts.py` | Synthesize ChatTTS audition candidates with different voice seeds. | `torch`, `torchaudio`, `ChatTTS` | `py tools/synth_chattts.py [out_dir]` |
| `tools/synth_chattts_loli.py` | Pitch-shift the highest-F0 ChatTTS seeds into "loli" variants. | `torch`, `torchaudio`, `ChatTTS` | `py tools/synth_chattts_loli.py [out_dir]` |
| `tools/synth_chattts_scan.py` | Scan 50 ChatTTS seeds and auto-pick girlish voices by F0. | `torch`, `torchaudio`, `ChatTTS` | `py tools/synth_chattts_scan.py [out_dir]` |
| `tools/preprocess.py` | Rebuild three-view sprites from front/side/back source images. | `Pillow` (PIL) | `py tools/preprocess.py [src_dir] [out_dir]` |
| `tools/preprocess2.py` | Edge decontamination + premultiplied-alpha sprite scaling. | `Pillow` (PIL) | `py tools/preprocess2.py [src_dir] [out_dir]` |
| `tools/make_zip.py` | Package the runtime source into a shareable zip. | none | `py tools/make_zip.py` |

The ChatTTS scripts need `torch`, `torchaudio`, and
[2noise/ChatTTS](https://github.com/2noise/ChatTTS) installed (via pip or per its
repository instructions); they are heavy and optional.

---

## Voice samples

The `samples/` directory holds audition recordings of candidate voices: edge-tts
variants (Xiaoyi / Xiaoxiao and friends) and ChatTTS multi-seed auditions. The
pet's default voice is built in, so it runs fine **without** `samples/`. To
regenerate the candidates, run the corresponding `tools/` script — the edge-tts
scripts need nothing extra, while the ChatTTS scripts require installing `torch`
and `ChatTTS` first.

---

## Running the tests

```bat
py tests/test_watch.py
```

The test requires `zstandard` (`pip install zstandard`). It drives the DSH
event-state machine with fake (zstd-compressed) session logs and verifies that
ordinary tool activity is not misreported as "waiting", that only questions and
approvals report "waiting", and that only turn end reports "done".

---

## FAQ / Troubleshooting

**1. The pet does not speak.**

- Make sure `voice_enabled` is `true` in `config.json` (or check the
  "Voice Announcements" menu item).
- The **edge** engine needs internet access; if it is offline, it falls back to
  the Windows SAPI voice. Check that Windows has a voice installed
  (Settings → Time & Language → Speech). You can force offline voice via the
  menu: Voice Preset → "System offline voice (no network)".

**2. DSH integration shows no notifications.**

- Confirm DSH is installed and running (or that `dsh_dir` points to it, and
  `dsh_launch` is enabled).
- The pet reads `~/.dsh`; if your DSH home is elsewhere, set the `DSH_HOME`
  environment variable to that location before starting the pet.
- A session must be *recent* (written within the last 24 hours) to be tracked.

**3. How do I remove start-on-boot?**

- Right-click the pet or tray icon → untick "Start on Boot", **or**
- double-click `uninstall.bat`, **or**
- run `py -3 desktop_pet.py --uninstall-autostart`.

**4. The balance query fails.**

- Set `ds_api_key` in `config.json` (or set `DEEPSEEK_API_KEY` in
  `~/.dsh/.credentials.yaml`). The key must be a valid DeepSeek Open Platform
  key. The balance endpoint needs a working internet connection.

---

## License

Released under the [MIT License](LICENSE).

---

## Credits & References

This project builds on the work of the following projects:

- **dafeiyu-pet** — the pet behavior, sprites, and base application derive from
  [1190fasheqi/dafeiyu-pet](https://github.com/1190fasheqi/dafeiyu-pet)
  ([MIT License](LICENSE)). See `NOTICE` for details.
- **edge-tts** — online voice synthesis via
  [rany2/edge-tts](https://github.com/rany2/edge-tts).
- **ChatTTS** — the audition scripts use
  [2noise/ChatTTS](https://github.com/2noise/ChatTTS).
- **ntfy** — push notifications via
  [binwiederhier/ntfy](https://github.com/binwiederhier/ntfy).
- **wttr.in** — weather data from [wttr.in](https://wttr.in).
- **DeepSeek Harness** — the DSH session state this pet watches is produced by
  [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness).
