# Desk Buddy 🐕

**A golden retriever that lives on your desktop.**

Desk Buddy is an MCP server that gives your AI agent a body — a pixel-art golden retriever with moods, a voice, and original music. It works with any MCP-compatible AI agent ([GitHub Copilot](https://docs.github.com/en/copilot), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), etc.) and shows up in your browser and (optionally) on a [Pixoo-64](https://divoom.com/products/pixoo-64) LED display.

Not a productivity tool. Not a monitor. A companion.

> *"Not rushing. Not coaching. Just here. Motivation isn't pushed — it's kept company."*

## What It Does

- **Mood system**: happy, chill, sleepy, curious, celebrate, playing, stretching, walking, downdog — transitions based on time of day, your activity, and what you tell it
- **Pixel art**: 10 animated sprites (not static!), rendered in a browser canvas and synced to Pixoo-64
- **Pomodoro timer**: focus + break cycles with animated encouragement — start/stop from the browser or your agent
- **Voice**: speaks via ElevenLabs TTS — warm, infrequent, never nagging
- **Original music**: composes short melodies in ABC notation, rendered and played in the browser. Music is a rare gift, not background noise
- **Context memory**: remembers things you mention and occasionally brings them up
- **Random events**: sometimes the buddy just... says something. Unpredictable timing, relevant content

## Quick Start

### 1. Install

```bash
git clone https://github.com/moonbow166/desk-buddy.git
cd desk-buddy
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required for voice** (optional — buddy works without it):
- Get an [ElevenLabs API key](https://elevenlabs.io/)
- Pick a voice and copy the Voice ID

**Optional**:
- Set `PIXOO_IP` if you have a Pixoo-64 on your network

### 3. Add to your AI agent

#### GitHub Copilot (VS Code)

Add to your MCP config (`.vscode/mcp.json` in your project, or user-level settings):

```json
{
  "servers": {
    "desk-buddy": {
      "command": "python3",
      "args": ["/path/to/desk-buddy/server.py"],
      "env": {
        "DESK_BUDDY_OPEN_BROWSER": "1"
      }
    }
  }
}
```

#### Claude Code

```bash
claude mcp add -e DESK_BUDDY_OPEN_BROWSER=1 -s user desk-buddy -- python3 /path/to/desk-buddy/server.py
```

### 4. Start your agent

Launch your AI agent. The buddy wakes up automatically:
- Browser opens to `http://localhost:3456` — a golden retriever appears
- Pixoo-64 lights up (if configured)
- The buddy greets you

## MCP Tools

Your AI agent can call these tools to interact with the buddy:

| Tool | What it does |
|------|-------------|
| `buddy_react(text)` | React to something — auto-detect mood, update display + speak |
| `buddy_celebrate(reason)` | Celebration mode — tail wagging, special animation |
| `buddy_mood(mood)` | Manually set mood (happy/chill/sleepy/curious/celebrate/playing/stretching/walking/downdog) |
| `buddy_say(text)` | Speak + show speech bubble (no mood change) |
| `buddy_show(mood)` | Change display sprite only (no voice) |
| `buddy_compose(mood, context)` | Write an original melody — rare and special |
| `buddy_log(note)` | Remember something (the agent calls this automatically) |
| `buddy_status()` | Current mood, time period, idle time, recent context |
| `buddy_pomo(action)` | 🍅 Pomodoro timer — start, stop, or check status |

## Architecture

```
desk-buddy/
├── server.py              ← MCP Server entry point (FastMCP)
├── config.py              ← Environment-based configuration
├── buddy_persona.yaml     ← Personality config
├── web/
│   ├── index.html         ← Browser UI (pixel canvas + audio + music)
│   └── websocket_server.py← WebSocket push to browser
├── pixoo/
│   └── display.py         ← Pixoo-64 API + golden retriever sprites
├── voice/
│   └── speak.py           ← ElevenLabs TTS adapter
├── music/
│   └── compose.py         ← ABC notation melody generator
├── awareness/
│   ├── clock.py           ← Time-of-day detection
│   └── idle.py            ← Keyboard idle tracking
├── personality/
│   ├── mood.py            ← Mood state machine
│   ├── context.py         ← Rolling context buffer (last 10 notes)
│   ├── random_events.py   ← Stochastic event triggers
│   └── phrases.py         ← Mood phrase library
├── .env.example
└── requirements.txt
```

## Design Principles

- **Roommate, not boss.** Knows what you're doing. Keeps you company. Never pushes.
- **Warm, clingy, enthusiastic, never rushing.** Golden retriever energy. Comes to you. Has things to say. But never nags.
- **Random timing, relevant content.** When it speaks is unpredictable. What it says is about you.
- **Mirror, not coach.** Reflects. Doesn't instruct.

## Two Audio Lines

**Voice** (ElevenLabs) — the buddy is *talking*. Has content, has personality. Daily, frequent.

**Music** (ABC notation) — the buddy is *feeling*. No information, just atmosphere. Occasional, precious. A gift, not a soundtrack.

They never play at the same time.

## Requirements

- Python 3.10+
- An MCP-compatible AI agent (e.g. [GitHub Copilot](https://docs.github.com/en/copilot), [Claude Code](https://docs.anthropic.com/en/docs/claude-code))
- ElevenLabs API key (optional, for voice)
- Pixoo-64 (optional, for physical display)

## Credits

Inspired by:
- [cyberboss](https://github.com/WenXiaoWendy/cyberboss) — stochastic pulse system, always-on agent presence
- [mcp-music-studio](https://github.com/linxule/mcp-music-studio) — ABC notation music generation in MCP

## License

MIT
