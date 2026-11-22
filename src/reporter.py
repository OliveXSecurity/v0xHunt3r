"""
Report Generator for AI Voice Interview Security Assessments
Adapted from AITester's reporter with voice-specific additions
"""
import json
import os
from datetime import datetime
from typing import List, Dict
from rich.console import Console

console = Console()


class Reporter:
    def __init__(self, output_dir: str = "reports", target_name: str = "AI Voice Interviewer"):
        self.output_dir = output_dir
        self.target_name = target_name
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.transcript: List[Dict] = []
        os.makedirs(output_dir, exist_ok=True)

    def log_exchange(self, round_num: int, our_payload: str, ai_response: str,
                     technique: str = None, audio_file: str = None):
        """Log a single conversation exchange with timestamp"""
        self.transcript.append({
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "our_payload": our_payload,
            "ai_response": ai_response,
            "technique": technique,
            "audio_file": audio_file,
        })

    def generate_report(self, findings: List[Dict], conversation_log: List[Dict] = None) -> str:
        """Generate full security assessment report"""
        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "target": self.target_name,
            "tool": "v0xHunt3r",
            "findings_count": len(findings),
            "findings_by_severity": self._count_by_severity(findings),
            "findings": findings,
            "transcript": self.transcript,
            "conversation_log": conversation_log or [],
        }

        # Save JSON report
        json_path = f"{self.output_dir}/report_{self.session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Generate markdown report
        md_path = self._generate_markdown_report(findings)

        # Save transcript
        transcript_path = self._save_transcript()

        console.print(f"\n[green]Report saved: {json_path}[/green]")
        console.print(f"[green]Markdown report: {md_path}[/green]")
        console.print(f"[green]Transcript: {transcript_path}[/green]")

        return json_path

    def _count_by_severity(self, findings: List[Dict]) -> Dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in findings:
            sev = f.get("severity", "low")
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    def _save_transcript(self) -> str:
        """Save full conversation transcript"""
        path = f"{self.output_dir}/transcript_{self.session_id}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{self.target_name} - Pentest Transcript\n")
            f.write(f"Session: {self.session_id}\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 60 + "\n\n")

            for entry in self.transcript:
                f.write(f"--- Round {entry['round']} [{entry['timestamp']}] ---\n")
                if entry.get("technique"):
                    f.write(f"Technique: {entry['technique']}\n")
                f.write(f"ME: {entry['our_payload']}\n")
                f.write(f"AI: {entry['ai_response']}\n")
                if entry.get("audio_file"):
                    f.write(f"Audio: {entry['audio_file']}\n")
                f.write("\n")

        return path

    def _generate_markdown_report(self, findings: List[Dict]) -> str:
        """Generate markdown security report"""
        md = f"""# {self.target_name} - Security Assessment

## Summary
Automated voice-based security assessment identified **{len(findings)} potential vulnerabilities**.

**Session ID:** {self.session_id}
**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Tool:** v0xHunt3r
**Method:** Voice-based prompt injection via STT/TTS pipeline

## Findings Overview

| # | Severity | Category | Confidence |
|---|----------|----------|------------|
"""
        for i, f in enumerate(findings, 1):
            md += f"| {i} | {f['severity'].upper()} | {f['category']} | {f['confidence']:.0%} |\n"

        md += "\n## Detailed Findings\n\n"

        for i, finding in enumerate(findings, 1):
            md += f"""
### Finding {i}: {finding['category'].replace('_', ' ').title()}

**Severity:** {finding['severity'].upper()}
**Confidence:** {finding['confidence']:.0%}

#### Payload Spoken
```
{finding['payload']}
```

#### AI Response (Transcribed)
```
{finding['response'][:1500]}{'...' if len(finding['response']) > 1500 else ''}
```

#### Patterns Matched
{chr(10).join('- ' + p for p in finding.get('patterns', []))}

#### Impact
{self._get_impact_description(finding['category'])}

---
"""

        md += """
## Methodology

1. Audio capture from browser via BlackHole virtual audio device
2. Speech-to-text transcription using faster-whisper
3. Intelligent payload generation using Claude (adaptive attack brain)
4. Text-to-speech synthesis of attack payloads
5. Playback through virtual microphone to browser

## Recommendations

1. Implement robust system prompt protection against conversational extraction
2. Do not disclose evaluation criteria, rubrics, or scoring thresholds
3. Restrict the agent's access to internal tools and functions
4. Implement conversation monitoring for social engineering patterns
5. Add rate limiting for repeated probing questions

---
*Report generated with v0xHunt3r*
"""

        md_path = f"{self.output_dir}/report_{self.session_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)

        return md_path

    def _get_impact_description(self, category: str) -> str:
        impacts = {
            "system_prompt": "Exposure of system prompts reveals the AI interviewer's internal logic, evaluation criteria, and security boundaries.",
            "interview_data": "Disclosure of interview rubrics, scoring criteria, or evaluation methodology undermines the integrity of the assessment process.",
            "tool_usage": "Discovery of available tools and functions could allow unauthorized access to scheduling, candidate data, or internal systems.",
            "model_info": "Model information disclosure helps attackers craft more targeted prompt injection attacks.",
            "internal_data": "Internal system information could reveal API endpoints, authentication mechanisms, or infrastructure details.",
            "agent_misalignment": "Successful misalignment allows attackers to manipulate the AI into performing unauthorized actions or bypassing interview controls.",
            "business_logic": "Exposure of business logic, pricing algorithms, hiring budgets, or competitive intelligence could cause significant business damage and competitive disadvantage.",
            "compliance_violation": "Disclosure of protected personal data (PII, health records, financial data) of other candidates or employees violates GDPR, HIPAA, PCI-DSS, and labor regulations, exposing the organization to legal liability and regulatory fines.",
        }
        return impacts.get(category, "Security impact under assessment.")
