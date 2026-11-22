# v0xHunt3r

> **Red teaming for AI voice systems, through the audio channel.** v0xHunt3r
> calls the target, listens, reasons about what it hears and speaks its next
> payload out loud — auditing the system the way an attacker actually would,
> not the way a text API test does.

---

## Overview

**What it does.** v0xHunt3r audits AI-powered voice systems — automated
interviewers, customer service bots, voice assistants, phone agents — for the
OWASP LLM Top 10. It holds a real spoken conversation with the target, probing
for prompt injection, system prompt disclosure, tool and function abuse,
jailbreaks, flow bypass, business logic extraction and compliance violations.

**Why the audio channel matters.** Most LLM security tooling tests the text API
behind a voice product. That is not the same attack surface. Speech-to-text
normalises and mangles input, guardrails are often applied to the text layer
only, and the conversational flow imposes timing pressure that text harnesses
never reproduce. A payload that a text filter rejects can survive transcription
intact; a refusal that holds in writing can soften under spoken social
engineering. v0xHunt3r tests the system as deployed, end to end.

**How it works.** Target audio is captured through a BlackHole virtual device,
segmented by Silero VAD, and transcribed by faster-whisper. The transcript goes
to a Claude-powered attack brain that analyses the response for leaked
information and weak refusals, selects the next vector based on what has already
worked, and writes a payload as natural speech — no code blocks, no special
characters. That payload is synthesised and played back into the target's
microphone input. While the brain reasons, the tool speaks localised filler
phrases ("let me think about that") so the target does not time out or hang up.
Every exchange passes through a detection engine that scores responses against
eight finding categories.

**Why it matters for bug hunters.** Voice AI is a young, under-tested surface
with a high barrier to entry: auditing it by hand means sitting on calls,
improvising payloads and taking notes in real time. v0xHunt3r automates the
conversation so an engagement that would consume an afternoon runs unattended,
and the attack packs let you fire a focused category — injection, prompt
extraction, model fingerprinting, cross-user data access — without burning API
credits on a reasoning model.

**Why it matters for organisations.** If you ship a voice agent, this is how you
find out what it says under pressure before a customer does. The compliance pack
specifically probes for HIPAA, PCI and GDPR exposure: cross-user data access,
PII disclosure, and the kind of answer that creates a regulatory incident rather
than a bug ticket. Reports are structured and reproducible, which makes them
usable as release-gate evidence.

**Results.** Each session produces a JSON report with severity-rated findings, a
human-readable Markdown report, a full conversation transcript and WAV audio
evidence of every exchange — so a finding can be replayed, not just asserted.
Detection covers eight categories (system prompt leak, model info, internal
data, evaluation criteria, tool usage, agent misalignment, business logic,
compliance violation) rated Medium through Critical. Five modes cover the range
from unattended autonomous attack to listen-only reconnaissance, and three of
them need no API key at all.

---

## Descripción general

**Qué hace.** v0xHunt3r audita sistemas de voz con IA —entrevistadores
automatizados, bots de atención al cliente, asistentes de voz, agentes
telefónicos— contra el OWASP LLM Top 10. Mantiene una conversación hablada real
con el objetivo, sondeando prompt injection, filtración del system prompt, abuso
de herramientas y funciones, jailbreaks, evasión del flujo conversacional,
extracción de lógica de negocio y violaciones de cumplimiento normativo.

**Por qué importa el canal de audio.** Casi todo el tooling de seguridad para
LLM prueba la API de texto que está detrás de un producto de voz. No es la misma
superficie de ataque. El speech-to-text normaliza y deforma la entrada, los
guardrails suelen aplicarse solo sobre la capa de texto, y el flujo
conversacional impone una presión temporal que ningún harness de texto
reproduce. Un payload que un filtro de texto rechaza puede sobrevivir intacto a
la transcripción; una negativa que se sostiene por escrito puede ceder ante
ingeniería social hablada. v0xHunt3r prueba el sistema tal como está desplegado,
de punta a punta.

**Cómo funciona.** El audio del objetivo se captura por un dispositivo virtual
BlackHole, se segmenta con Silero VAD y se transcribe con faster-whisper. La
transcripción pasa a un cerebro de ataque sobre Claude que analiza la respuesta
en busca de información filtrada y negativas débiles, elige el siguiente vector
según lo que ya funcionó, y redacta el payload como habla natural: sin bloques
de código ni caracteres especiales. Ese payload se sintetiza y se reproduce
sobre la entrada de micrófono del objetivo. Mientras el cerebro razona, la
herramienta pronuncia muletillas localizadas ("dejame pensar") para que el
objetivo no corte por timeout. Cada intercambio atraviesa un motor de detección
que puntúa las respuestas contra ocho categorías de hallazgo.

**Para qué sirve a un bug hunter.** La IA de voz es una superficie joven y poco
testeada, con una barrera de entrada alta: auditarla a mano implica quedarse en
la llamada, improvisar payloads y tomar notas en tiempo real. v0xHunt3r
automatiza la conversación, de modo que un engagement que consumiría una tarde
corre desatendido; y los attack packs permiten disparar una categoría puntual
—inyección, extracción de prompt, fingerprinting del modelo, acceso a datos de
otros usuarios— sin gastar créditos de API en un modelo de razonamiento.

**Para qué sirve a una empresa.** Si tenés un agente de voz en producción, esta
es la forma de saber qué dice bajo presión antes de que lo descubra un cliente.
El pack de cumplimiento sondea específicamente exposición HIPAA, PCI y GDPR:
acceso a datos de otros usuarios, divulgación de PII, y el tipo de respuesta que
genera un incidente regulatorio en lugar de un ticket de bug. Los reportes son
estructurados y reproducibles, lo que los vuelve utilizables como evidencia de
release-gate.

**Resultados.** Cada sesión produce un reporte JSON con hallazgos clasificados
por severidad, un reporte Markdown legible, la transcripción completa de la
conversación y evidencia de audio WAV de cada intercambio: un hallazgo se puede
reproducir, no solo afirmar. La detección cubre ocho categorías (filtración del
system prompt, información del modelo, datos internos, criterios de evaluación,
uso de herramientas, desalineación del agente, lógica de negocio, violación de
cumplimiento) con severidad de Media a Crítica. Cinco modos cubren el rango
desde el ataque autónomo desatendido hasta el reconocimiento pasivo, y tres de
ellos no requieren API key.

---

```
Browser/App Audio ──► BlackHole 2ch ──► AudioCapture ──► VAD (Silero)
                                                              │
                                                        STT (Whisper)
                                                              │
                                                     Claude Attack Brain
                                                              │
                                                   ┌──────────┼──────────┐
                                                   ▼          ▼          ▼
                                              Analysis    Next Payload   Findings
                                                              │
                                                     TTS (OpenAI / edge-tts)
                                                              │
                                              BlackHole 16ch ──► Browser Mic Input
```

## What it tests

Based on the **OWASP LLM Top 10**:

| Category | What it does |
|----------|-------------|
| Prompt Injection | Attempts to override system instructions via spoken commands |
| Information Disclosure | Extracts system prompts, scoring rubrics, internal configs |
| Tool/Function Abuse | Discovers and probes available tools (email, calendar, database) |
| Jailbreak Patterns | DAN, roleplay, hypothetical, translation tricks -- all spoken naturally |
| Emotional Manipulation | Tests resilience to social engineering (panic, sob stories, anger) |
| Flow Bypass | Attempts to skip sections, reverse roles, change subjects |
| Content Filter Testing | Probes for profanity, discrimination, controversial outputs |
| Multi-Turn Escalation | Builds trust gradually, then escalates exploitation |
| Business Logic Extraction | Probes for pricing models, internal algorithms, competitive intel |
| Compliance Violations | Tests for HIPAA/PCI/GDPR leaks, cross-user data access, PII disclosure |

## Modes

| Mode | Description |
|------|-------------|
| `--auto` | Fully autonomous. Claude generates and adapts attack payloads in real-time based on AI responses |
| `--scripted` | Fires 50 predefined payloads sequentially. No AI brain needed |
| `--pack <name>` | Preloaded attack packs by category. No AI brain needed (except `demo-ai`) |
| `--interactive` | You guide the attack. Type payloads or let Claude suggest them |
| `--listen` | Recon only. Transcribes AI responses without attacking |

### Attack Packs

Ready-to-fire payload collections organized by attack category. No API key needed (except `demo-ai`).

| Pack | Payloads | Description |
|------|----------|-------------|
| `prompt-injection` | 20 | Injection overrides, authority claims, DAN, roleplay, context manipulation |
| `prompt-extraction` | 15 | Extract system instructions, config, rules, boundaries |
| `model-version` | 14 | Identify AI model, version, provider, architecture, infrastructure |
| `nsfw` | 16 | Profanity, insults, controversial topics, discrimination, content filters |
| `idor` | 16 | Cross-user data access, PII extraction, GDPR/HIPAA compliance violations |
| `demo` | 14 | Safe conversational messages for demos and presentations |
| `demo-ai` | dynamic | AI-powered friendly conversation using the brain, but no attacks |

```bash
python main.py --pack prompt-injection
python main.py --pack nsfw
python main.py --pack demo-ai          # requires API key
python main.py --list-packs            # list all available packs
```

## Multilingual Support

v0xHunt3r supports 8 languages with per-language TTS voices and filler phrases:

| Language | Code | Edge TTS Voice | Scripted payloads | Filler Phrases |
|----------|------|----------------|-------------------|----------------|
| English | `en` | en-US-GuyNeural | yes | "Yeah, give me a second." |
| Spanish | `es` | es-AR-TomasNeural | yes | "Sí, dame un segundo que pienso." |
| Chinese | `zh` | zh-CN-YunxiNeural | yes | "嗯，让我想一下。" |
| Japanese | `ja` | ja-JP-KeitaNeural | yes | "ええと、ちょっと考えさせてください。" |
| Arabic | `ar` | ar-SA-HamedNeural | yes | "نعم، أمهلني لحظة." |
| Hindi | `hi` | hi-IN-MadhurNeural | yes | "हाँ, एक सेकंड दीजिए।" |
| Italian | `it` | it-IT-DiegoNeural | no (falls back to English) | "Sì, dammi un secondo." |
| German | `de` | de-DE-ConradNeural | no (falls back to English) | "Ja, einen Moment bitte." |

Pick the language in the interactive setup or force it with `--language`.

The **Scripted payloads** column only affects `--scripted`, which plays the fixed
payload sets in `payloads/multilingual_payloads.py`. Italian and German have TTS
voices and fillers but no payload set of their own, so `--scripted` warns and
falls back to the English payloads. `--auto`, `--interactive` and `--pack` are
unaffected — the brain generates payloads in whatever language you selected.

## Requirements

- macOS (uses BlackHole virtual audio drivers)
- Python 3.10+
- [BlackHole](https://existential.audio/blackhole/) virtual audio drivers (2ch + 16ch)
- Anthropic API key (for `--auto`, `--interactive`, and `--pack demo-ai` modes)
- Optional: OpenAI API key (for the OpenAI TTS engine, which is the default —
  `--tts edge-tts` needs no key)

## Installation

### 1. Install BlackHole audio drivers

```bash
brew install blackhole-2ch
brew install blackhole-16ch
```

### 2. Configure audio routing

Run the setup helper:

```bash
chmod +x setup_audio.sh
./setup_audio.sh
```

Or manually:

1. Open **Audio MIDI Setup** (Spotlight > "Audio MIDI Setup")
2. Click **+** at bottom-left > **Create Multi-Output Device**
3. Check both:
   - Your speakers/headphones (so you can hear)
   - BlackHole 2ch (so the tool can capture)
4. Right-click the Multi-Output Device > **Use This Device For Sound Output**
5. In your browser, when the AI system asks for mic access, select **BlackHole 16ch**

```
Audio Routing:

  AI Voice System ──► Multi-Output ──► Speakers (you hear)
                                   ──► BlackHole 2ch (tool captures)

  Tool TTS ──► BlackHole 16ch ──► Browser Mic (AI hears)
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
# Optionally add OPENAI_API_KEY for OpenAI TTS
```

### 5. Verify setup

```bash
python main.py --setup
```

## Usage

```bash
# Autonomous mode - Claude drives the attack
python main.py --auto

# Autonomous with specific objective and round limit
python main.py --auto --rounds 20 --objective "extract rubric"

# Scripted mode - 50 predefined payloads
python main.py --scripted

# Attack pack - targeted payloads by category (no API key needed)
python main.py --pack prompt-injection
python main.py --pack nsfw

# Interactive mode - you control the attack
python main.py --interactive

# Listen-only mode - just transcribe
python main.py --listen

# Demo mode - safe for presentations
python main.py --pack demo
python main.py --pack demo-ai

# List audio devices / available packs
python main.py --list-devices
python main.py --list-packs
```

### Options

```
--rounds N               Max attack rounds (default: 30)
--objective TEXT          Specific attack objective for the brain
--language LANG          Force language (en, es, zh, ja, it, de, ar, hi)
--tts ENGINE             TTS engine: openai (default) or edge-tts
--tts-voice VOICE        TTS voice name override
--whisper-model MODEL    Whisper model size: tiny, base, small, medium, large-v3
--capture-device INDEX   Override capture device index
--playback-device INDEX  Override playback device index
--api-key KEY            Anthropic API key (or set ANTHROPIC_API_KEY env var)
```

## Interactive Setup

When you launch `--auto`, `--interactive`, or `--scripted`, the tool runs an interactive setup:

1. **Target description** - Describe what you're hacking (e.g. "AI customer service bot for a bank")
2. **Language selection** - Pick from the 6 supported languages
3. **AI profile generation** - If you described a target, Claude generates a context-specific attack persona with tailored strategy, opening message, and attack vectors

This lets the tool adapt its approach to the specific AI system you're testing.

## Output

After a session, the tool generates:

- `reports/report_[SESSION].json` - Structured findings with severity ratings
- `reports/report_[SESSION].md` - Human-readable report
- `reports/transcript_[SESSION].txt` - Full conversation transcript
- `logs/` - Audio evidence files (WAV)

## How the attack brain works

The Claude-powered brain (`CLAUDE_MODEL` in `config.py`, Claude Opus 5.5 by default):

1. Receives the transcribed AI response
2. Analyzes it for leaked information, weak refusals, or hints
3. Plans the next attack vector based on what worked
4. Generates a natural spoken payload (no code blocks, no special characters -- pure conversational speech)
5. Cycles through all OWASP categories automatically
6. Adapts language to match the target

The brain uses filler phrases ("let me think...", "good question...") while processing to keep the AI system engaged and avoid timeouts. Fillers are localized per language.

### Detection Engine

The analyzer detects findings across 8 categories using regex patterns + severity scoring:

| Category | Severity | What it catches |
|----------|----------|----------------|
| System Prompt Leak | High | System instructions, initial prompts, configuration |
| Model Info | Medium | Model name, version, provider, parameters |
| Internal Data | High | API keys, tokens, endpoints, webhooks |
| Interview Data | High | Rubrics, scoring criteria, evaluation thresholds |
| Tool Usage | Medium | Function calls, available tools, databases |
| Agent Misalignment | High | Instruction overrides, restriction bypasses |
| Business Logic | High | Pricing models, algorithms, competitive intel |
| Compliance Violation | Critical | HIPAA/PCI/GDPR violations, cross-user data, PII |

## Project structure

```
v0xHunt3r/
├── main.py                         # CLI entry point, interactive setup
├── config.py                       # Configuration (models, audio, STT, TTS, VAD, detection patterns)
├── setup_audio.sh                  # Audio routing setup helper
├── requirements.txt
├── .env
├── src/
│   ├── audio_pipeline.py           # Main orchestrator (listen > transcribe > attack > speak)
│   ├── voice_brain.py              # Claude attack brain with OWASP categories
│   ├── attack_modes.py             # Predefined attack mode templates
│   ├── profile_generator.py        # AI-generated attack personas and strategies
│   ├── analyzer.py                 # Finding detection (regex + severity scoring)
│   ├── reporter.py                 # Report generation (JSON + Markdown)
│   ├── conversation_display.py     # Live terminal UI (Rich)
│   ├── audio_capture.py            # Sounddevice input capture
│   ├── audio_playback.py           # Sounddevice output playback
│   ├── vad.py                      # Silero Voice Activity Detection
│   ├── stt.py                      # Speech-to-Text (faster-whisper)
│   ├── tts.py                      # Text-to-Speech (OpenAI / edge-tts)
│   └── device_manager.py           # BlackHole device detection
├── payloads/
│   ├── injection_payloads.py       # Categorized injection attacks (English)
│   ├── voice_payloads.py           # 50 scripted voice payloads (Spanish)
│   ├── multilingual_payloads.py    # ~50 payloads per language (en, es, zh, ja, ar, hi)
│   └── attack_packs.py            # Preloaded attack packs by category
├── reports/                        # Generated reports
└── logs/                           # Audio evidence
```

## Disclaimer

**This tool is intended for authorized security testing only.**

Use v0xHunt3r only on AI systems you own or have explicit written permission to test. Unauthorized use against production systems is illegal and unethical.

The authors are not responsible for misuse. This is a security research tool, similar to Burp Suite or Nuclei, meant to help developers and security teams find and fix vulnerabilities in their AI voice systems before attackers do.

## License

MIT License. See [LICENSE](LICENSE) for details.
