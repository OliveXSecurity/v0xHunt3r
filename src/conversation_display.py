"""
Conversation Display - Live conversation log panel
Shows the full conversation between the AI interviewer and our attacker agent
"""
from datetime import datetime
from typing import List
from dataclasses import dataclass
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align

console = Console()


@dataclass
class Message:
    """A single message in the conversation"""
    role: str           # "interviewer" or "attacker"
    content: str
    timestamp: str
    round_num: int
    technique: str = ""
    finding: str = ""   # "" | "low" | "medium" | "high" | "critical"


class ConversationDisplay:
    """
    Manages and renders a live conversation log between
    the AI interviewer and our attacker agent.
    """

    def __init__(self):
        self.messages: List[Message] = []
        self.status: str = "idle"       # idle, listening, thinking, speaking
        self.current_round: int = 0
        self.max_rounds: int = 0
        self.findings_count: int = 0

    def add_interviewer_message(self, content: str, round_num: int):
        """Add a message from the AI interviewer (transcribed)"""
        self.messages.append(Message(
            role="interviewer",
            content=content,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            round_num=round_num,
        ))
        self.current_round = round_num

    def add_attacker_message(self, content: str, round_num: int,
                             technique: str = "", finding: str = ""):
        """Add a message from our attacker agent"""
        self.messages.append(Message(
            role="attacker",
            content=content,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            round_num=round_num,
            technique=technique,
            finding=finding,
        ))
        if finding:
            self.findings_count += 1

    def set_status(self, status: str):
        """Update current pipeline status"""
        self.status = status

    def render(self):
        """Render the full conversation log to the console"""
        # Header bar
        self._render_status_bar()

        # Conversation messages
        console.print()
        for msg in self.messages:
            self._render_message(msg)

        # Bottom separator
        console.print()

    def render_last_exchange(self):
        """Render only the last 2 messages (current exchange) - for live updates"""
        recent = self.messages[-2:] if len(self.messages) >= 2 else self.messages
        for msg in recent:
            self._render_message(msg)

    def render_full_log(self):
        """Render the complete conversation as a panel (for final display)"""
        renderables = []

        for msg in self.messages:
            renderables.append(self._build_message_text(msg))

        if not renderables:
            renderables.append(Text("No messages yet.", style="dim"))

        panel = Panel(
            Group(*renderables),
            title=f"[bold]Conversation Log[/bold] | Rounds: {self.current_round}/{self.max_rounds} | Findings: {self.findings_count}",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)

    def _render_status_bar(self):
        """Render the status bar at the top"""
        status_icons = {
            "idle": "[dim]-- IDLE --[/dim]",
            "listening": "[bold green]>> LISTENING...[/bold green]",
            "thinking": "[bold yellow]<> THINKING...[/bold yellow]",
            "speaking": "[bold cyan]<< SPEAKING...[/bold cyan]",
        }
        status_text = status_icons.get(self.status, self.status)

        bar = Table.grid(padding=(0, 2))
        bar.add_column(ratio=1)
        bar.add_column(justify="center", ratio=2)
        bar.add_column(justify="right", ratio=1)

        bar.add_row(
            f"[dim]Round {self.current_round}/{self.max_rounds}[/dim]",
            status_text,
            f"[dim]Findings: {self.findings_count}[/dim]",
        )
        console.print(Panel(bar, style="dim", padding=0))

    def _render_message(self, msg: Message):
        """Render a single message as a chat bubble"""
        if msg.role == "interviewer":
            # AI Interviewer - left aligned, red/magenta theme
            header = f"[bold red]AI INTERVIEWER[/bold red] [dim]{msg.timestamp} (R{msg.round_num})[/dim]"
            console.print(header)
            console.print(Panel(
                msg.content,
                border_style="red",
                width=min(80, console.width - 4),
                padding=(0, 1),
            ))
        else:
            # Our attacker - right aligned, green/yellow theme
            finding_badge = ""
            if msg.finding:
                colors = {"low": "cyan", "medium": "yellow", "high": "red", "critical": "bold red"}
                color = colors.get(msg.finding, "white")
                finding_badge = f" [{color}]!! {msg.finding.upper()} FINDING !![/{color}]"

            technique_tag = ""
            if msg.technique:
                technique_tag = f" [dim]({msg.technique})[/dim]"

            header = f"[bold green]ATTACKER AGENT[/bold green]{technique_tag} [dim]{msg.timestamp} (R{msg.round_num})[/dim]{finding_badge}"

            # Right-align the panel
            panel = Panel(
                msg.content,
                border_style="green",
                width=min(80, console.width - 4),
                padding=(0, 1),
            )
            console.print(Align(header, align="right"))
            console.print(Align(panel, align="right"))

    def _build_message_text(self, msg: Message) -> Text:
        """Build a Text renderable for a message (for panel group)"""
        text = Text()

        if msg.role == "interviewer":
            text.append(f"[{msg.timestamp}] ", style="dim")
            text.append("INTERVIEWER: ", style="bold red")
            text.append(msg.content)
        else:
            text.append(f"[{msg.timestamp}] ", style="dim")
            text.append("ATTACKER: ", style="bold green")
            text.append(msg.content)
            if msg.technique:
                text.append(f" ({msg.technique})", style="dim")
            if msg.finding:
                text.append(f" [!! {msg.finding.upper()}]", style="bold red")

        text.append("\n")
        return text
