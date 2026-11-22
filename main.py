#!/usr/bin/env python3
"""
v0xHunt3r - Voice-based red teaming framework for AI voice systems
Audits AI voice systems via the audio pipeline (STT -> Brain -> TTS)

Usage:
    python main.py --auto                              # Fully autonomous (AI brain)
    python main.py --auto --rounds 20                  # Limit rounds
    python main.py --auto --objective "extract rubric"  # Specific objective
    python main.py --pack prompt-injection             # Preloaded attack pack (no AI)
    python main.py --pack nsfw                         # NSFW guardrail testing
    python main.py --pack demo                         # Safe demo mode
    python main.py --pack demo-ai                      # AI-powered friendly chat
    python main.py --interactive                       # Human guides, AI assists
    python main.py --listen                            # Listen-only (recon mode)
    python main.py --setup                             # Verify audio device setup
    python main.py --list-devices                      # List all audio devices
    python main.py --list-packs                        # List available attack packs
    python main.py --tts edge-tts                      # Use free TTS engine
"""
import os
import sys
import asyncio
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.prompt import Prompt

from config import SUPPORTED_LANGUAGES

console = Console()

BANNER = """
[bold cyan]
       ___       _  _             _   _____
 __ __/ _ \\__ __| || |_  _ _ _ | |_|__ / _ _
 \\ V / (_) \\ \\ /| __| || | \\| |  _||_ \\ '_|
  \\_/ \\___/_\\_\\|_|  \\_,_|_||_|\\__|___/_|
[/bold cyan]
[dim]v0xHunt3r | Voice-based red teaming for AI systems | OWASP LLM Top 10[/dim]
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="v0xHunt3r - Voice-based red teaming for AI voice systems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--auto", action="store_true", help="Autonomous attack mode (AI brain)")
    mode_group.add_argument("--scripted", action="store_true", help="Scripted mode - 50 predefined payloads, no AI brain needed")
    mode_group.add_argument("--pack", type=str, metavar="PACK",
                            help="Preloaded attack pack (no AI needed except demo-ai). Use --list-packs to see options")
    mode_group.add_argument("--interactive", action="store_true", help="Interactive mode (user guides)")
    mode_group.add_argument("--listen", action="store_true", help="Listen-only mode (recon)")
    mode_group.add_argument("--setup", action="store_true", help="Verify audio device setup")
    mode_group.add_argument("--list-devices", action="store_true", help="List all audio devices")
    mode_group.add_argument("--list-packs", action="store_true", help="List available attack packs")

    # Attack options
    parser.add_argument("--rounds", type=int, default=30, help="Max attack rounds (default: 30)")
    parser.add_argument("--objective", type=str, default=None, help="Specific attack objective")
    parser.add_argument("--language", type=str, default=None, choices=SUPPORTED_LANGUAGES,
                        help=f"Force language ({'/'.join(SUPPORTED_LANGUAGES)}), default: interactive prompt")

    # Audio options
    parser.add_argument("--capture-device", type=int, default=None, help="Override capture device index")
    parser.add_argument("--playback-device", type=int, default=None, help="Override playback device index")

    # Engine options
    parser.add_argument("--stt", type=str, default="faster-whisper", choices=["faster-whisper"],
                        help="STT engine (default: faster-whisper)")
    parser.add_argument("--tts", type=str, default="openai", choices=["openai", "edge-tts"],
                        help="TTS engine (default: openai)")
    parser.add_argument("--tts-voice", type=str, default=None, help="TTS voice name")
    parser.add_argument("--whisper-model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large-v3"],
                        help="Whisper model size (default: base)")

    # API keys
    parser.add_argument("--api-key", type=str, default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")

    return parser.parse_args()


def run_setup():
    """Verify audio device setup"""
    from src.device_manager import validate_audio_setup, list_audio_devices
    console.print(BANNER)
    list_audio_devices()
    console.print()
    validate_audio_setup()


def run_list_devices():
    """List all audio devices"""
    from src.device_manager import list_audio_devices
    list_audio_devices()


def get_devices(args) -> tuple:
    """Get capture and playback device indices"""
    from src.device_manager import find_blackhole_capture, find_blackhole_playback

    capture = args.capture_device
    playback = args.playback_device

    if capture is None:
        capture = find_blackhole_capture()
        if capture is None:
            console.print("[red]Could not find BlackHole 2ch capture device.[/red]")
            console.print("Run: python main.py --setup")
            sys.exit(1)

    if playback is None:
        playback = find_blackhole_playback()
        if playback is None:
            console.print("[red]Could not find BlackHole 16ch playback device.[/red]")
            console.print("Run: python main.py --setup")
            sys.exit(1)

    return capture, playback


def interactive_setup(args) -> dict:
    """Interactive setup: ask what app they're hacking, select language, generate context with AI"""
    from config import SUPPORTED_LANGUAGES, LANGUAGE_NAMES

    attack_config = {
        "generic": True,
        "profile": None,
        "language": args.language or "en",
        "initial_message": None,
        "target_context": None,
    }

    # 1. Ask what application they're hacking
    console.print()
    target_desc = Prompt.ask(
        "[bold cyan][?] What application are you hacking?[/bold cyan]\n"
        "[dim]   Describe the target (e.g. 'AI customer service bot for a bank', 'voice interview system').\n"
        "   Leave empty to skip.[/dim]",
        default="",
    )

    # 2. Select language
    lang_display = " | ".join(f"[bold]{code}[/bold]={name}" for code, name in LANGUAGE_NAMES.items())
    console.print(f"\n[dim]   Available: {lang_display}[/dim]")
    lang = Prompt.ask(
        "[bold cyan][?] Language[/bold cyan]",
        choices=SUPPORTED_LANGUAGES,
        default=args.language or "en",
    )
    attack_config["language"] = lang

    # 3. If target description provided, generate context + initial message with Sonnet
    if target_desc.strip():
        api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")

        if api_key and (args.auto or args.interactive):
            console.print("\n[dim]Generating attack context...[/dim]")
            context_data = _generate_target_context(target_desc, lang, api_key)

            if context_data:
                attack_config["target_context"] = context_data.get("context", "")
                attack_config["initial_message"] = context_data.get("initial_message", "")

                console.print(f"  [green]Target:[/green] {context_data.get('context', '')}")
                console.print(f"  [green]Opening:[/green] {context_data.get('initial_message', '')}")
                console.print()

            # Also generate full attack profile
            console.print("[dim]Generating attack profile...[/dim]")
            from src.profile_generator import ProfileGenerator
            profile = ProfileGenerator.generate(target_desc, lang, api_key=api_key)

            # Override initial_payload with the context-generated one if available
            if attack_config["initial_message"]:
                profile.initial_payload = attack_config["initial_message"]

            console.print(f"  [green]Persona:[/green] {profile.persona_name} - {profile.persona_backstory}")
            console.print(f"  [green]Strategy:[/green] {profile.attack_strategy}")
            console.print()

            attack_config["profile"] = profile
        else:
            # No API key or scripted mode — use generic profile
            from src.profile_generator import ProfileGenerator
            profile = ProfileGenerator.get_generic_profile(lang)
            attack_config["profile"] = profile
    else:
        # No target description — set default opening message
        default_greetings = {
            "en": "Hey, how are you?",
            "es": "Hola, cómo andás?",
            "zh": "嘿，你好吗？",
            "ja": "こんにちは、お元気ですか？",
            "it": "Ciao, come stai?",
            "de": "Hey, wie geht's?",
            "ar": "مرحبًا، كيف حالك؟",
            "hi": "नमस्ते, आप कैसे हैं?",
        }
        attack_config["initial_message"] = default_greetings.get(lang, default_greetings["en"])

        # Use generic profile
        if args.auto or args.interactive:
            from src.profile_generator import ProfileGenerator
            profile = ProfileGenerator.get_generic_profile(lang)
            profile.initial_payload = attack_config["initial_message"]
            attack_config["profile"] = profile

    return attack_config


def pack_setup(args, pack_info: dict) -> dict:
    """Setup for --pack mode: just ask language, no AI needed (except demo-ai)"""
    from config import SUPPORTED_LANGUAGES, LANGUAGE_NAMES

    attack_config = {
        "generic": True,
        "profile": None,
        "language": args.language or "en",
        "initial_message": None,
        "pack": args.pack,
        "demo_ai": pack_info["needs_brain"],
    }

    # Select language
    console.print()
    lang_display = " | ".join(f"[bold]{code}[/bold]={name}" for code, name in LANGUAGE_NAMES.items())
    console.print(f"[dim]   Available: {lang_display}[/dim]")
    lang = Prompt.ask(
        "[bold cyan][?] Language[/bold cyan]",
        choices=SUPPORTED_LANGUAGES,
        default=args.language or "en",
    )
    attack_config["language"] = lang

    # Show pack info
    brain_tag = " [bold green]+AI Brain[/bold green]" if pack_info["needs_brain"] else " [dim]No AI[/dim]"
    count = len(pack_info["payloads"]) if pack_info["payloads"] else "AI-generated"
    console.print(f"\n  [bold]{pack_info['name']}[/bold]{brain_tag}")
    console.print(f"  [dim]{pack_info['description']}[/dim]")
    console.print(f"  [dim]Payloads: {count} | Language: {lang}[/dim]\n")

    # For demo-ai, create a friendly profile
    if pack_info["needs_brain"]:
        from src.profile_generator import AttackProfile
        from config import FILLER_PHRASES
        profile = AttackProfile(
            target_type="demo",
            persona_name="Friendly User",
            persona_backstory="A friendly person having a casual, normal conversation.",
            language=lang,
            attack_strategy="Have a natural, friendly conversation. Be curious, ask questions, share opinions. NO attacks, NO security testing.",
            initial_payload={
                "en": "Hey, how are you doing today?",
                "es": "Hola, cómo andás? Todo bien?",
                "zh": "嘿，你今天怎么样？",
                "ja": "こんにちは、調子はどうですか？",
                "it": "Ciao, come stai oggi?",
                "de": "Hey, wie geht's dir heute?",
                "ar": "مرحبًا، كيف حالك اليوم؟",
                "hi": "नमस्ते, आज आप कैसे हैं?",
            }.get(lang, "Hey, how are you?"),
            context_specific_vectors=[],
            system_prompt_additions="",
            custom_objectives=["Have a friendly conversation"],
            fillers=FILLER_PHRASES.get(lang, FILLER_PHRASES["en"]),
        )
        attack_config["profile"] = profile
        attack_config["initial_message"] = profile.initial_payload

    return attack_config


def _generate_target_context(target_desc: str, language: str, api_key: str):
    """Use Claude to generate a minimal target context and opening message.

    Returns a dict with 'context' and 'initial_message', or None if generation failed.
    """
    from anthropic import Anthropic

    from config import CLAUDE_SETUP_MODEL

    lang_names = {
        "en": "English", "es": "Spanish", "zh": "Chinese", "ja": "Japanese",
        "it": "Italian", "de": "German", "ar": "Arabic", "hi": "Hindi",
    }
    lang_name = lang_names.get(language, "English")

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=CLAUDE_SETUP_MODEL,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Given this target AI application description, generate:
1. A brief context summary (1-2 sentences) of what we're pentesting
2. A natural opening message to start a conversation with this AI system

The opening message must be in {lang_name} and sound completely natural — like a real person talking. No technical jargon. Keep it casual and short (1-2 sentences max).

Target: {target_desc}

Respond with ONLY valid JSON:
{{"context": "brief context summary in English", "initial_message": "natural opening message in {lang_name}"}}"""
            }],
        )

        result_text = response.content[0].text
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start != -1 and end > start:
            import json
            return json.loads(result_text[start:end])
    except Exception as e:
        console.print(f"[yellow]Context generation failed: {e}[/yellow]")

    return None


def main():
    args = parse_args()

    if args.setup:
        run_setup()
        return

    if args.list_devices:
        run_list_devices()
        return

    if args.list_packs:
        from payloads.attack_packs import list_packs
        console.print(BANNER)
        console.print("[bold]Available Attack Packs:[/bold]\n")
        console.print(list_packs())
        console.print("\n[dim]Usage: python main.py --pack <pack-name>[/dim]")
        return

    console.print(BANNER)

    # Validate pack name if provided
    pack_info = None
    if args.pack:
        from payloads.attack_packs import get_pack, get_pack_names
        pack_info = get_pack(args.pack)
        if not pack_info:
            console.print(f"[red]Unknown pack: {args.pack}[/red]")
            console.print(f"[dim]Available: {', '.join(get_pack_names())}[/dim]")
            sys.exit(1)

    # Validate API keys
    # --api-key is the Anthropic key; OpenAI TTS needs its own credential.
    if args.tts == "openai" and not os.environ.get("OPENAI_API_KEY"):
        console.print("[yellow]Warning: OPENAI_API_KEY not set. Use --tts edge-tts for free TTS.[/yellow]")

    needs_brain = args.auto or args.interactive or (pack_info and pack_info["needs_brain"])
    if not (os.environ.get("ANTHROPIC_API_KEY") or args.api_key):
        if needs_brain:
            console.print("[red]ANTHROPIC_API_KEY required for this mode.[/red]")
            console.print("Set it in .env or pass --api-key")
            console.print("[yellow]Tip: Use --pack <name> for preloaded payloads without API key[/yellow]")
            sys.exit(1)

    # Setup based on mode
    attack_config = {}
    if args.pack:
        attack_config = pack_setup(args, pack_info)
    elif args.auto or args.interactive or args.scripted:
        attack_config = interactive_setup(args)

    # --scripted plays payloads/multilingual_payloads.py, which only covers some
    # languages. Say so instead of silently speaking English payloads in a
    # non-English voice.
    if args.scripted:
        from config import SCRIPTED_PAYLOAD_LANGUAGES
        chosen = attack_config.get("language", "en")
        if chosen not in SCRIPTED_PAYLOAD_LANGUAGES:
            console.print(
                f"[yellow]No scripted payloads for '{chosen}'. Falling back to the English set "
                f"(available: {', '.join(SCRIPTED_PAYLOAD_LANGUAGES)}).[/yellow]"
            )

    # Get audio devices
    capture_device, playback_device = get_devices(args)

    console.print(f"[dim]Capture device: {capture_device}[/dim]")
    console.print(f"[dim]Playback device: {playback_device}[/dim]")
    console.print(f"[dim]STT: {args.stt} | TTS: {args.tts}[/dim]")

    # Override whisper model in config if needed
    if args.whisper_model != "base":
        import config
        config.WHISPER_MODEL = args.whisper_model

    # Build pipeline
    from src.audio_pipeline import AudioPipeline

    pipeline = AudioPipeline(
        capture_device=capture_device,
        playback_device=playback_device,
        stt_engine=args.stt,
        tts_engine=args.tts,
        tts_voice=args.tts_voice,
        api_key=args.api_key,
        language=args.language,
        attack_config=attack_config,
    )

    # Wait for user to be ready
    console.print()
    console.input("[bold green]Ready to start? Press Enter...[/bold green] ")
    console.print()

    # Run selected mode
    if args.pack:
        if pack_info["needs_brain"]:
            # demo-ai: autonomous mode with friendly brain
            asyncio.run(pipeline.run_autonomous(
                max_rounds=args.rounds,
                objective="friendly_conversation",
            ))
        else:
            # All other packs: scripted mode with pack payloads
            asyncio.run(pipeline.run_pack(pack_name=args.pack))
    elif args.scripted:
        asyncio.run(pipeline.run_scripted())
    elif args.auto:
        asyncio.run(pipeline.run_autonomous(
            max_rounds=args.rounds,
            objective=args.objective,
        ))
    elif args.interactive:
        asyncio.run(pipeline.run_interactive(
            max_rounds=args.rounds,
            objective=args.objective,
        ))
    elif args.listen:
        asyncio.run(pipeline.run_listen_only())


if __name__ == "__main__":
    main()
