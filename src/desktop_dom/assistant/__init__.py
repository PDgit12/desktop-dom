from __future__ import annotations
import sys
import logging
from typing import Optional

from desktop_dom.assistant.brain import AssistantBrain
from desktop_dom.assistant.audio import AudioManager
from desktop_dom.assistant.omnibar import FloatingOmnibar

logger = logging.getLogger("desktop_dom.assistant")

class DesktopAssistant:
    """
    Unified high-level entrypoint for the Personal Desktop Assistant (Aura).
    Orchestrates speech-to-text, local LLM brain, desktop-dom action dispatch, and floating HUD Omnibar.
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        preferred_model: Optional[str] = None,
        brain: Optional[AssistantBrain] = None,
        audio: Optional[AudioManager] = None,
    ):
        self.brain = brain or AssistantBrain(ollama_host=ollama_host, preferred_model=preferred_model)
        self.audio = audio or AudioManager()
        self.omnibar = None
        if sys.platform == "darwin":
            self.omnibar = FloatingOmnibar(brain=self.brain, audio=self.audio)

    def ask(self, prompt: str) -> str:
        """Processes a query and speaks confirmation."""
        res = self.brain.execute_intent(prompt)
        reply = res.get("response", "Task completed.")
        self.audio.speak(reply)
        return reply

    def launch_omnibar(self):
        """Launches the native floating Spotlight/Raycast Omnibar."""
        if not self.omnibar:
            raise RuntimeError("Floating Omnibar currently requires macOS Cocoa & WebKit.")
        self.omnibar.run()

    def run_cli_session(self):
        """Runs an interactive conversational terminal session."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt

        console = Console()
        console.print(Panel.fit(
            "[bold cyan]Aura: Personal Desktop Assistant[/bold cyan]\n"
            "[dim]Powered by desktop-dom & Local Ollama | Zero Cloud Overhead[/dim]\n\n"
            "• Speak or type: [italic]'Play Starboy on Spotify'[/italic]\n"
            "• Compute: [italic]'Calculate 125 * 40 + 15'[/italic]\n"
            "• App control: [italic]'Open Finder'[/italic] or [italic]'Search for quantum computing'[/italic]\n"
            "• Press [bold red]Ctrl+C[/bold red] to exit",
            title="Local Personal Assistant Active",
            border_style="cyan"
        ))

        self.audio.speak("Desktop assistant online and ready.")

        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                if not user_input or not user_input.strip():
                    continue
                if user_input.lower() in {"exit", "quit"}:
                    console.print("[dim]Goodbye![/dim]")
                    break

                with console.status("[bold green]Aura thinking & executing...[/bold green]"):
                    res = self.brain.execute_intent(user_input)
                    reply = res.get("response", "Done.")

                console.print(f"[bold magenta]Aura:[/bold magenta] {reply}")
                self.audio.speak(reply)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Session terminated.[/dim]")
                break

__all__ = ["DesktopAssistant", "AssistantBrain", "AudioManager", "FloatingOmnibar"]
