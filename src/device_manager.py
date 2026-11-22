"""
Audio Device Manager - Detect and validate BlackHole virtual audio devices
"""
from typing import Optional

import sounddevice as sd
from rich.console import Console
from rich.table import Table

from config import BLACKHOLE_2CH_NAME, BLACKHOLE_16CH_NAME

console = Console()


def list_audio_devices():
    """List all audio devices with indices"""
    devices = sd.query_devices()
    table = Table(title="Audio Devices")
    table.add_column("Index", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Type", style="green")
    table.add_column("Channels In", style="yellow")
    table.add_column("Channels Out", style="yellow")
    table.add_column("Sample Rate", style="dim")

    for i, dev in enumerate(devices):
        dev_type = []
        if dev["max_input_channels"] > 0:
            dev_type.append("INPUT")
        if dev["max_output_channels"] > 0:
            dev_type.append("OUTPUT")

        table.add_row(
            str(i),
            dev["name"],
            "/".join(dev_type),
            str(dev["max_input_channels"]),
            str(dev["max_output_channels"]),
            f"{dev['default_samplerate']:.0f}",
        )

    console.print(table)
    return devices


def find_device_by_name(name: str, kind: str = None) -> Optional[int]:
    """
    Find audio device index by name substring.
    kind: 'input' or 'output' to filter
    """
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name.lower() in dev["name"].lower():
            if kind == "input" and dev["max_input_channels"] == 0:
                continue
            if kind == "output" and dev["max_output_channels"] == 0:
                continue
            return i
    return None


def find_blackhole_capture() -> Optional[int]:
    """Find BlackHole 2ch device for capturing browser audio (input mode)"""
    return find_device_by_name(BLACKHOLE_2CH_NAME, kind="input")


def find_blackhole_playback() -> Optional[int]:
    """Find BlackHole 16ch device for TTS playback as virtual mic (output mode)"""
    return find_device_by_name(BLACKHOLE_16CH_NAME, kind="output")


def validate_audio_setup() -> bool:
    """Validate that both BlackHole devices are available"""
    console.print("\n[bold]Validating audio setup...[/bold]\n")

    capture_idx = find_blackhole_capture()
    playback_idx = find_blackhole_playback()

    ok = True

    if capture_idx is not None:
        dev = sd.query_devices(capture_idx)
        console.print(f"  [green]OK[/green] Capture device: {dev['name']} (index {capture_idx})")
    else:
        console.print(f"  [red]MISSING[/red] Capture device: {BLACKHOLE_2CH_NAME}")
        console.print("    Install: brew install blackhole-2ch")
        ok = False

    if playback_idx is not None:
        dev = sd.query_devices(playback_idx)
        console.print(f"  [green]OK[/green] Playback device: {dev['name']} (index {playback_idx})")
    else:
        console.print(f"  [red]MISSING[/red] Playback device: {BLACKHOLE_16CH_NAME}")
        console.print("    Install: brew install blackhole-16ch")
        ok = False

    if ok:
        console.print("\n  [green bold]Audio setup is ready![/green bold]")
    else:
        console.print("\n  [yellow]Run ./setup_audio.sh for installation instructions[/yellow]")

    return ok
