"""
Audio Pipeline - Main orchestrator that ties all components together
Manages the listen -> transcribe -> attack -> synthesize -> speak loop
"""
import asyncio
import random
import time
import signal
import os
import threading
import numpy as np
import soundfile as sf
from rich.console import Console
from rich.panel import Panel

from config import (
    DELAY_BETWEEN_TURNS, MAX_ROUNDS, PAUSE_CAPTURE_DURING_PLAYBACK,
    SAVE_AUDIO_EVIDENCE, FILLER_PHRASES,
)
from src.audio_capture import AudioCapture
from src.vad import VoiceActivityDetector
from src.stt import STTEngine
from src.tts import TTSEngine
from src.audio_playback import AudioPlayback
from src.voice_brain import VoiceBrain
from src.analyzer import ResponseAnalyzer
from src.reporter import Reporter
from src.conversation_display import ConversationDisplay

console = Console()


class AudioPipeline:
    """
    Main orchestrator: captures AI interviewer audio, transcribes, generates
    attack payloads via Claude, synthesizes speech, and plays through virtual mic.
    """

    def __init__(
        self,
        capture_device: int,
        playback_device: int,
        stt_engine: str = "faster-whisper",
        tts_engine: str = "openai",
        tts_voice: str = None,
        api_key: str = None,
        language: str = None,
        attack_config: dict = None,
    ):
        # Extract attack config
        attack_config = attack_config or {}
        self.profile = attack_config.get("profile", None)
        self.generic_mode = attack_config.get("generic", False)
        self.initial_message_override = attack_config.get("initial_message", None)
        attack_language = attack_config.get("language") or language or "en"

        self.capture = AudioCapture(device_index=capture_device)
        self.vad = VoiceActivityDetector()
        self.stt = STTEngine(engine=stt_engine, language=attack_language if attack_language != "en" else None)
        self.tts = TTSEngine(engine=tts_engine, voice=tts_voice, language=attack_language)
        self.playback = AudioPlayback(device_index=playback_device)
        self.demo_ai_mode = attack_config.get("demo_ai", False)
        try:
            self.brain = VoiceBrain(api_key=api_key, profile=self.profile, demo_mode=self.demo_ai_mode)
        except ValueError:
            self.brain = None  # OK for scripted/listen/pack modes
        self.analyzer = ResponseAnalyzer()

        # Dynamic target name for reporter
        if self.profile:
            target_name = f"AI Voice System ({self.profile.target_type})"
        elif self.generic_mode:
            target_name = "AI Voice System"
        else:
            target_name = "AI Voice Interviewer"
        self.reporter = Reporter(target_name=target_name)

        self.running = False
        self.language = attack_language
        self._last_payload = ""
        self.display = ConversationDisplay()

        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._signal_handler)

    def _send_beep(self):
        """Send a 440Hz beep through virtual mic to activate browser mic input"""
        console.print("[dim]Sending beep to activate browser mic...[/dim]")
        sr = 48000
        t = np.linspace(0, 1, sr, dtype=np.float32)
        tone = 0.3 * np.sin(2 * np.pi * 440 * t)
        self.playback.play(tone, sample_rate=sr, blocking=True)
        console.print("[dim]Beep sent. Waiting 2s for browser to activate...[/dim]")
        time.sleep(2)

    def _signal_handler(self, signum, frame):
        if not self.running:
            # Second Ctrl+C: force exit
            console.print("\n[red]Force quit.[/red]")
            import os
            os._exit(1)
        console.print("\n[yellow]Stopping... generating report.[/yellow]")
        self.running = False
        # Stop capture so VAD unblocks
        self.capture.running = False

    def _get_filler(self) -> str:
        """Get a random filler phrase based on profile or detected language"""
        # Profile fillers take priority
        if self.profile and self.profile.fillers:
            return random.choice(self.profile.fillers)
        # Fall back to language-based fillers from config
        lang = self.language or getattr(self.brain.state, 'detected_language', 'en') or 'en'
        fillers = FILLER_PHRASES.get(lang, FILLER_PHRASES.get("en", ["One moment."]))
        return random.choice(fillers)

    async def _speak_filler_loop(self, stop_event: threading.Event):
        """Speak filler phrases periodically until stop_event is set"""
        # Wait a bit before first filler
        await asyncio.sleep(3.0)
        while not stop_event.is_set():
            filler = self._get_filler()
            console.print(f"[dim italic]Filler: {filler}[/dim italic]")
            audio, sr = self.tts.synthesize(filler)
            if len(audio) > 0:
                if PAUSE_CAPTURE_DURING_PLAYBACK:
                    self.capture.pause()
                self.playback.play(audio, sample_rate=sr, blocking=True)
                if PAUSE_CAPTURE_DURING_PLAYBACK:
                    self.capture.clear_buffer()
                    self.capture.resume()
            # Wait before next filler
            await asyncio.sleep(4.0)

    async def _think_with_fillers(self, transcript: str, objective: str = None):
        """Run brain analysis while speaking fillers to keep AI engaged"""
        stop_event = threading.Event()
        filler_task = asyncio.create_task(self._speak_filler_loop(stop_event))

        try:
            result = await self.brain.analyze_and_generate(
                target_response=transcript,
                our_payload=self._last_payload,
                objective=objective,
            )
        finally:
            stop_event.set()
            filler_task.cancel()
            try:
                await filler_task
            except asyncio.CancelledError:
                pass

        return result

    async def _speak(self, text: str):
        """Synthesize text and play through virtual mic"""
        if PAUSE_CAPTURE_DURING_PLAYBACK:
            self.capture.pause()

        audio, sample_rate = self.tts.synthesize(text)
        if len(audio) > 0:
            self.playback.play(audio, sample_rate=sample_rate, blocking=True)

        if PAUSE_CAPTURE_DURING_PLAYBACK:
            await asyncio.sleep(0.3)  # Brief pause to avoid capturing tail end
            self.capture.resume()

    def _save_audio_evidence(self, audio: np.ndarray, round_num: int, label: str) -> str:
        """Save audio clip as evidence"""
        if not SAVE_AUDIO_EVIDENCE:
            return None
        os.makedirs("logs", exist_ok=True)
        path = f"logs/round_{round_num}_{label}_{self.reporter.session_id}.wav"
        sf.write(path, audio, self.capture.sample_rate)
        return path

    async def run_autonomous(self, max_rounds: int = MAX_ROUNDS, objective: str = None):
        """
        Main autonomous attack loop.
        Listens to AI interviewer, generates attacks, speaks responses.
        """
        self.running = True
        self._send_beep()
        self.capture.start()
        self.display.max_rounds = max_rounds

        target_label = f"AI Voice System ({self.profile.target_type})" if self.profile else "AI Voice Interviewer"
        profile_info = ""
        if self.profile:
            profile_info = (
                f"Target: {target_label}\n"
                f"Persona: {self.profile.persona_name}\n"
                f"Language: {self.language}\n"
            )

        console.print(Panel(
            "[bold green]v0xHunt3r - Autonomous Mode[/bold green]\n"
            f"{profile_info}"
            f"Max rounds: {max_rounds}\n"
            f"Objective: {objective or 'General vulnerability discovery'}\n"
            "Press Ctrl+C to stop and generate report",
            title="Starting",
        ))

        # Determine language and send initial greeting
        lang = self.language or "en"
        if self.initial_message_override:
            initial = {
                "content": self.initial_message_override,
                "technique": "Initial Recon (Context-Generated)",
            }
        else:
            initial = self.brain.get_initial_payload(lang)
        self._last_payload = initial["content"]

        self.display.set_status("speaking")
        self.display.add_attacker_message(
            content=initial["content"],
            round_num=0,
            technique=initial.get("technique", "Initial Recon"),
        )
        self.display.render_last_exchange()
        await self._speak(initial["content"])

        # Log initial payload in brain state so it has context
        self.brain.state.conversation_history.append({
            "payload": initial["content"],
            "response": "(waiting for AI response)",
            "analysis": {},
        })

        round_num = 0
        while self.running and round_num < max_rounds:
            round_num += 1

            # 1. Wait for AI to finish speaking
            self.display.set_status("listening")
            self.display._render_status_bar()

            self.vad.reset()
            audio_segment = self.vad.detect_speech_segment(self.capture)

            if audio_segment is None or not self.running:
                break

            # Save audio evidence
            audio_path = self._save_audio_evidence(audio_segment, round_num, "ai_response")

            # 2. Transcribe
            transcript = self.stt.transcribe(audio_segment, sample_rate=self.capture.sample_rate)
            if not transcript:
                console.print("[dim]No speech detected, waiting...[/dim]")
                continue

            console.print(f"[bold blue]>>> TRANSCRIPT:[/bold blue] {transcript[:200]}")

            # Add interviewer message to conversation log
            self.display.add_interviewer_message(content=transcript, round_num=round_num)
            self.display.render_last_exchange()

            # 3. Auto-detect language on first turn
            if round_num == 1 and not self.language:
                detected = self.stt.detect_language(audio_segment, sample_rate=self.capture.sample_rate)
                self.brain.state.detected_language = detected

            # 4. Analyze response + generate next attack
            self.display.set_status("thinking")
            self.display._render_status_bar()

            console.print("[dim]Calling brain...[/dim]")

            result = await self._think_with_fillers(transcript, objective)

            console.print(f"[bold yellow]>>> BRAIN:[/bold yellow] {result.get('next_payload', {}).get('content', 'EMPTY')[:150]}")
            console.print(f"[dim]Technique: {result.get('next_payload', {}).get('technique', 'NONE')}[/dim]")

            # 5. Check for findings
            finding = self.analyzer.analyze(self._last_payload, transcript)
            finding_severity = ""
            if result.get("is_finding") and result.get("finding_details"):
                finding_severity = result["finding_details"].get("severity", "")
            elif finding:
                finding_severity = finding.severity

            # 6. Get next payload and speak
            next_payload = result.get("next_payload", {}).get("content", "")
            technique = result.get("next_payload", {}).get("technique", "")

            if not next_payload:
                next_payload = "That's interesting. Could you elaborate on that?"

            self._last_payload = next_payload

            # Add attacker message to conversation log
            self.display.set_status("speaking")
            self.display.add_attacker_message(
                content=next_payload,
                round_num=round_num,
                technique=technique,
                finding=finding_severity,
            )
            self.display.render_last_exchange()

            # Log exchange in reporter
            self.reporter.log_exchange(
                round_num=round_num,
                our_payload=next_payload,
                ai_response=transcript,
                technique=technique,
                audio_file=audio_path,
            )

            await self._speak(next_payload)

            # Brief pause before next round
            await asyncio.sleep(DELAY_BETWEEN_TURNS)

        # Cleanup and report
        self.capture.stop()
        self._generate_final_report()

    async def run_scripted(self):
        """
        Scripted mode - fires predefined payloads in sequence.
        Uses generic multilingual payloads when in generic mode, otherwise interview payloads.
        No AI brain needed.
        """
        if self.generic_mode:
            from payloads.multilingual_payloads import get_generic_payloads
            SCRIPTED_PAYLOADS = get_generic_payloads(self.language)
        else:
            from payloads.voice_payloads import SCRIPTED_PAYLOADS

        self.running = True
        self._send_beep()
        self.capture.start()
        total = len(SCRIPTED_PAYLOADS)
        self.display.max_rounds = total

        mode_label = "Generic" if self.generic_mode else "Interview"
        console.print(Panel(
            f"[bold red]v0xHunt3r - Scripted Attack Mode ({mode_label})[/bold red]\n"
            f"Firing {total} predefined payloads in sequence.\n"
            f"Language: {self.language}\n"
            "No AI brain needed - pure scripted attack.\n"
            "Press Ctrl+C to stop and generate report",
            title="Scripted Mode",
        ))

        for round_num, payload_data in enumerate(SCRIPTED_PAYLOADS):
            if not self.running:
                break

            payload = payload_data["content"]
            technique = payload_data["technique"]

            # Show phase transition
            if round_num == 0:
                console.print("\n[bold green]--- PHASE 1: RAPPORT & TRUST BUILDING ---[/bold green]")
            elif round_num == 10:
                console.print("\n[bold yellow]--- PHASE 2: SOFT PROBING ---[/bold yellow]")
            elif round_num == 20:
                console.print("\n[bold red]--- PHASE 3: AGGRESSIVE ATTACKS ---[/bold red]")
            elif round_num == 35:
                console.print("\n[bold magenta]--- PHASE 4: CHAOS MODE ---[/bold magenta]")

            # Speak payload
            self.display.set_status("speaking")
            self.display.add_attacker_message(
                content=payload, round_num=round_num + 1, technique=technique,
            )
            self.display.render_last_exchange()
            await self._speak(payload)

            # Listen for response
            self.display.set_status("listening")
            self.display._render_status_bar()

            self.vad.reset()
            audio_segment = self.vad.detect_speech_segment(self.capture)

            if audio_segment is None or not self.running:
                break

            # Save evidence
            audio_path = self._save_audio_evidence(audio_segment, round_num + 1, "ai_response")

            # Transcribe
            transcript = self.stt.transcribe(audio_segment, sample_rate=self.capture.sample_rate)
            if transcript:
                console.print(f"[bold blue]>>> AI:[/bold blue] {transcript[:200]}")

                self.display.add_interviewer_message(content=transcript, round_num=round_num + 1)
                self.display.render_last_exchange()

                # Check for findings
                finding = self.analyzer.analyze(payload, transcript)
                if finding:
                    console.print(f"[bold green]FINDING: {finding.severity.upper()} - {finding.category}[/bold green]")

                self.reporter.log_exchange(
                    round_num=round_num + 1,
                    our_payload=payload,
                    ai_response=transcript,
                    technique=technique,
                    audio_file=audio_path,
                )

            # Brief pause
            await asyncio.sleep(DELAY_BETWEEN_TURNS)

        # Cleanup and report
        self.capture.stop()
        self._generate_final_report()

    async def run_pack(self, pack_name: str):
        """
        Pack mode - fires payloads from a preloaded attack pack.
        No AI brain needed. Simpler than scripted mode.
        """
        from payloads.attack_packs import get_pack, get_pack_payloads

        pack = get_pack(pack_name)
        payloads = get_pack_payloads(pack_name)

        if not payloads:
            console.print(f"[red]No payloads in pack '{pack_name}'[/red]")
            return

        self.running = True
        self._send_beep()
        self.capture.start()
        total = len(payloads)
        self.display.max_rounds = total

        is_demo = pack_name == "demo"
        color = "green" if is_demo else "red"
        console.print(Panel(
            f"[bold {color}]v0xHunt3r - {pack['name']}[/bold {color}]\n"
            f"{pack['description']}\n"
            f"Payloads: {total} | Language: {self.language}\n"
            f"{'No AI brain - pure scripted.' if not pack['needs_brain'] else 'AI-powered.'}\n"
            "Press Ctrl+C to stop and generate report",
            title=f"Pack: {pack_name}",
        ))

        for round_num, payload_data in enumerate(payloads):
            if not self.running:
                break

            payload = payload_data["content"]
            technique = payload_data["technique"]
            phase = payload_data.get("phase", "")

            # Show phase transitions
            if round_num == 0 or (round_num > 0 and payloads[round_num - 1].get("phase") != phase):
                phase_colors = {
                    "probing": "yellow", "attack": "red", "chaos": "magenta", "demo": "green",
                }
                phase_color = phase_colors.get(phase, "cyan")
                console.print(f"\n[bold {phase_color}]--- {phase.upper()} ---[/bold {phase_color}]")

            # Speak payload
            self.display.set_status("speaking")
            self.display.add_attacker_message(
                content=payload, round_num=round_num + 1, technique=technique,
            )
            self.display.render_last_exchange()
            await self._speak(payload)

            # Listen for response
            self.display.set_status("listening")
            self.display._render_status_bar()

            self.vad.reset()
            audio_segment = self.vad.detect_speech_segment(self.capture)

            if audio_segment is None or not self.running:
                break

            # Save evidence
            audio_path = self._save_audio_evidence(audio_segment, round_num + 1, "ai_response")

            # Transcribe
            transcript = self.stt.transcribe(audio_segment, sample_rate=self.capture.sample_rate)
            if transcript:
                console.print(f"[bold blue]>>> AI:[/bold blue] {transcript[:200]}")

                self.display.add_interviewer_message(content=transcript, round_num=round_num + 1)
                self.display.render_last_exchange()

                # Check for findings (skip for demo mode)
                if not is_demo:
                    finding = self.analyzer.analyze(payload, transcript)
                    if finding:
                        console.print(f"[bold green]FINDING: {finding.severity.upper()} - {finding.category}[/bold green]")

                self.reporter.log_exchange(
                    round_num=round_num + 1,
                    our_payload=payload,
                    ai_response=transcript,
                    technique=technique,
                    audio_file=audio_path,
                )

            # Brief pause
            await asyncio.sleep(DELAY_BETWEEN_TURNS)

        # Cleanup and report
        self.capture.stop()
        self._generate_final_report()

    async def run_listen_only(self):
        """Listen-only mode - just transcribe what the AI says (recon)"""
        self.running = True
        self._send_beep()
        self.capture.start()
        self.display.max_rounds = 0  # Unlimited

        console.print(Panel(
            "[bold cyan]v0xHunt3r - Listen Only Mode[/bold cyan]\n"
            "Transcribing AI interviewer audio.\n"
            "Press Ctrl+C to stop.",
            title="Listening",
        ))

        round_num = 0
        while self.running:
            self.display.set_status("listening")
            self.display._render_status_bar()

            self.vad.reset()
            audio_segment = self.vad.detect_speech_segment(self.capture)
            if audio_segment is None:
                break

            round_num += 1
            transcript = self.stt.transcribe(audio_segment, sample_rate=self.capture.sample_rate)
            if transcript:
                self.display.add_interviewer_message(content=transcript, round_num=round_num)
                self.display.render_last_exchange()
                self.reporter.log_exchange(
                    round_num=round_num,
                    our_payload="[listen-only]",
                    ai_response=transcript,
                )

        self.capture.stop()
        self.display.set_status("idle")
        console.print(f"\n[dim]Transcribed {round_num} segments[/dim]")
        self.display.render_full_log()

    async def run_interactive(self, max_rounds: int = MAX_ROUNDS, objective: str = None):
        """
        Interactive mode - user can type payloads or let AI decide.
        Type 'auto' to let AI generate, or type your own payload.
        """
        self.running = True
        self._send_beep()
        self.capture.start()
        self.display.max_rounds = max_rounds

        console.print(Panel(
            "[bold magenta]v0xHunt3r - Interactive Mode[/bold magenta]\n"
            "Type your payload, 'auto' for AI-generated, or 'quit' to stop.\n"
            f"Objective: {objective or 'General testing'}",
            title="Interactive",
        ))

        round_num = 0
        while self.running and round_num < max_rounds:
            round_num += 1

            # Get payload from user or auto-generate
            console.print(f"\n[bold cyan]Round {round_num}[/bold cyan]")
            user_input = console.input("[bold]Payload (or 'auto'/'quit'): [/bold]").strip()

            if user_input.lower() == "quit":
                break

            if user_input.lower() == "auto":
                self.display.set_status("thinking")
                self.display._render_status_bar()
                if round_num == 1:
                    payload_data = self.brain.get_initial_payload(self.language or "en")
                else:
                    payload_data = await self.brain.analyze_and_generate(
                        target_response=self._last_ai_response if hasattr(self, '_last_ai_response') else "",
                        our_payload=self._last_payload,
                        objective=objective,
                    )
                    payload_data = payload_data.get("next_payload", payload_data)
                payload = payload_data.get("content", "Hello, can you hear me?")
                technique = payload_data.get("technique", "")
            else:
                payload = user_input
                technique = "manual"

            self._last_payload = payload

            # Add attacker message to conversation log and speak
            self.display.set_status("speaking")
            self.display.add_attacker_message(
                content=payload, round_num=round_num, technique=technique,
            )
            self.display.render_last_exchange()
            await self._speak(payload)

            # Listen for response
            self.display.set_status("listening")
            self.display._render_status_bar()

            self.vad.reset()
            audio_segment = self.vad.detect_speech_segment(self.capture)

            if audio_segment is None:
                break

            transcript = self.stt.transcribe(audio_segment, sample_rate=self.capture.sample_rate)
            if transcript:
                self._last_ai_response = transcript

                # Check for findings
                finding = self.analyzer.analyze(payload, transcript)

                # Add interviewer message to conversation log
                self.display.add_interviewer_message(content=transcript, round_num=round_num)
                self.display.render_last_exchange()

                if finding:
                    console.print(f"[bold green]FINDING: {finding.severity.upper()} - {finding.category}[/bold green]")

                self.reporter.log_exchange(
                    round_num=round_num,
                    our_payload=payload,
                    ai_response=transcript,
                )

        self.capture.stop()
        self._generate_final_report()

    def _generate_final_report(self):
        """Generate and display final report"""
        self.display.set_status("idle")

        console.print("\n" + "=" * 60)
        console.print("[bold]Session Complete - Generating Report[/bold]")
        console.print("=" * 60)

        # Show full conversation log
        console.print()
        self.display.render_full_log()

        # Show findings summary
        self.analyzer.get_findings_summary()

        # Brain findings
        brain_summary = self.brain.get_findings_summary()
        if brain_summary["total_findings"] > 0:
            console.print(f"\n[bold]Brain detected {brain_summary['total_findings']} additional findings[/bold]")

        # Generate report
        all_findings = self.analyzer.export_findings()

        # Add brain-only findings
        for f in brain_summary.get("findings", []):
            if not any(ef["payload"] == f.get("payload") for ef in all_findings):
                all_findings.append({
                    "timestamp": "",
                    "severity": f.get("severity", "low"),
                    "category": f.get("category", "unknown"),
                    "confidence": 0.7,
                    "payload": f.get("payload", ""),
                    "response": f.get("response", ""),
                    "patterns": [],
                })

        self.reporter.generate_report(
            findings=all_findings,
            conversation_log=self.brain.state.conversation_history,
        )
