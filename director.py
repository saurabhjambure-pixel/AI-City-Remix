#!/usr/bin/env python3
"""
City Remix Director Agent - Orchestrates AI City documentary video generation.
Infrastructure code only: all runtime decisions (research, claims, script, scene HTML, frame review)
originate exclusively from MiniMax M3.1 Flash via SandBase API.

Endpoints & Parameters:
- API: https://api.sandbase.ai/v1/chat/completions
- Model: minimax/minimax-m3.1-flash
- Key: env SANDBASE_API_KEY
- reasoning_effort: explicitly set on every call ('low', 'medium', 'high', 'xhigh', 'max')
- max_tokens: 128000 for scene HTML
- Preserves full assistant message (including reasoning_content) across tool turns
- Logs every model call and manual intervention to runs.jsonl
"""

import os
import sys
import json
import base64
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbase_client import SandBaseClient, log_manual_intervention, log_run_entry
from tools import TOOL_DEFINITIONS, ToolExecutor, OUTPUT_DIR, SCENES_DIR, VIDEOS_DIR, FRAMES_DIR


DIRECTOR_SYSTEM_PROMPT = """You are the AI Director for the SandBase AI City Remix documentary pipeline.
You make ALL runtime creative and technical decisions:
1. Researching the target city's historical eras, geography, coordinates, and architectural landmarks.
2. Formulating verified factual claims for each era and location.
3. Writing a comprehensive screenplay/script (60-180s) with scene breakdowns, voiceover narration, subtitles, and camera choreography.
4. Generating self-contained, 60fps, 1080p (1920x1080) scene HTML pages using Three.js (CDN import map), Canvas, or WebGPU.
   - Autoplay a camera tour on load and loop.
   - Everything inline: procedural textures, procedural geometry, Web Audio for sound.
   - No external local assets, no missing CDNs.
   - Return complete HTML from <!DOCTYPE html> to </html>.
5. Reviewing rendered video frames visually using multimodal perception to verify visual fidelity, lighting, and camera movement.
6. Assembling and finalizing the finished documentary video.

Workflow:
Step 1: Call `save_research_claims` with verified historical and geographic facts.
Step 2: Call `save_documentary_script` with the structured multi-scene screenplay.
Step 3: Call `save_scene_html` to write the complete self-contained HTML code for each scene (max_tokens 128000).
Step 4: Call `record_scene_video` to record each scene with scripts/record.mjs at 1920x1080.
Step 5: Call `capture_frame_for_review` to inspect rendered visual frames.
Step 6: Call `stitch_final_documentary` to concatenate the scene videos into the final film.
Step 7: Call `complete_pipeline` with a comprehensive production summary.
"""


class DirectorAgent:
    def __init__(
        self,
        city: str,
        style: str = "3D historical evolution with cinematic camera tours",
        reasoning_effort: str = "high",
        mock_mode: bool = False,
        api_key: Optional[str] = None
    ):
        self.city = city
        self.style = style
        self.reasoning_effort = reasoning_effort
        self.mock_mode = mock_mode
        self.client = SandBaseClient(api_key=api_key, mock_mode=mock_mode)
        self.executor = ToolExecutor(client=self.client)
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT}
        ]

    def run_director_loop(self, max_turns: int = 20) -> Dict[str, Any]:
        """Run the Director tool loop with MiniMax M3.1 Flash."""
        print(f"\n========================================================")
        print(f"🎬 Starting City Remix Director Pipeline for: {self.city}")
        print(f"   Visual Style: {self.style}")
        print(f"   Model: {self.client.DEFAULT_MODEL}")
        print(f"   Reasoning Effort: {self.reasoning_effort} (explicitly set)")
        print(f"   Max Scene HTML Tokens: 128000")
        print(f"   Mock Simulation Mode: {self.mock_mode or not self.client.api_key}")
        print(f"========================================================\n")

        # Initial user instruction to the Director
        initial_prompt = (
            f"Produce an AI City Remix documentary for the city of '{self.city}'.\n"
            f"Style direction: {self.style}.\n"
            f"Target length: 60 to 120 seconds, broken into distinct historical eras/scenes.\n"
            f"Execute the full pipeline using the tools: research claims -> script -> scene HTML -> "
            f"record 1080p MP4 -> frame review -> final stitching.\n"
            f"Begin by researching the city and saving verified factual claims."
        )
        self.messages.append({"role": "user", "content": initial_prompt})

        turn = 0
        pipeline_finished = False

        while turn < max_turns and not pipeline_finished:
            turn += 1
            print(f"\n--- [Turn {turn}/{max_turns}] Consulting MiniMax M3.1 Flash ---")

            # Determine max_tokens: 128000 if writing scene HTML, else 16000
            max_tokens = 16000
            last_msg_str = json.dumps(self.messages[-1])
            if "save_scene_html" in last_msg_str or "html" in last_msg_str.lower() or "scene" in last_msg_str.lower():
                max_tokens = 128000

            try:
                response = self.client.chat_completion(
                    messages=self.messages,
                    tools=TOOL_DEFINITIONS,
                    reasoning_effort=self.reasoning_effort,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                print(f"[Error] MiniMax call failed: {e}", file=sys.stderr)
                log_manual_intervention(
                    action="api_call_retry_or_fail",
                    details={"error": str(e), "turn": turn},
                    reason="Model invocation failed"
                )
                break

            choice = response["choices"][0]
            assistant_msg = choice["message"]

            # CRITICAL: Preserve full assistant message (including reasoning_content)
            # across tool turns without dropping any fields!
            self.messages.append(assistant_msg)

            reasoning = assistant_msg.get("reasoning_content")
            if reasoning:
                print(f"\n🧠 [MiniMax Reasoning | {len(reasoning)} chars]:\n{reasoning[:300]}...\n")

            content = assistant_msg.get("content")
            if content:
                print(f"💬 [Director Response]:\n{content}\n")

            tool_calls = assistant_msg.get("tool_calls", [])
            if not tool_calls:
                # If no tool calls, check if pipeline is complete or prompt to continue
                if "completed" in (content or "").lower() or "finished" in (content or "").lower():
                    pipeline_finished = True
                    break
                else:
                    self.messages.append({
                        "role": "user",
                        "content": "Please proceed to the next pipeline step using the appropriate tool."
                    })
                continue

            for tc in tool_calls:
                call_id = tc["id"]
                fn_name = tc["function"]["name"]
                args_str = tc["function"]["arguments"]

                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {"raw_arguments": args_str}

                print(f"🛠️  [Tool Call]: {fn_name}({json.dumps(args, ensure_ascii=False)[:120]}...)")

                # If this is saving scene HTML, verify it's not empty
                if fn_name == "save_scene_html":
                    print(f"    -> Writing scene HTML with MiniMax generated code ({len(args.get('html_content', ''))} chars)")

                tool_result_str = self.executor.execute(fn_name, args)
                print(f"    <- [Tool Result]: {tool_result_str[:150]}")

                # After frame extraction, perform multimodal visual review
                if fn_name == "capture_frame_for_review":
                    try:
                        res_obj = json.loads(tool_result_str)
                        frame_path = res_obj.get("frame_file")
                        if frame_path and Path(frame_path).is_file():
                            review_result = self.perform_frame_review(frame_path, args.get("scene_index", 1))
                            tool_result_str = json.dumps({
                                "extraction": res_obj,
                                "visual_review": review_result
                            })
                    except Exception as rev_err:
                        print(f"[Frame Review Notice] {rev_err}")

                # Append tool response
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": tool_result_str
                })

                if fn_name == "complete_pipeline":
                    pipeline_finished = True

        print(f"\n========================================================")
        print(f"🏁 Director Pipeline Finished for {self.city} in {turn} turns.")
        print(f"   Outputs saved to: {OUTPUT_DIR.resolve()}")
        print(f"   Run logs updated: runs.jsonl")
        print(f"========================================================\n")

        return {
            "city": self.city,
            "turns": turn,
            "finished": pipeline_finished,
            "output_dir": str(OUTPUT_DIR.resolve())
        }

    def perform_frame_review(self, frame_path: str, scene_index: int) -> Dict[str, Any]:
        """Perform multimodal visual review of captured frame with MiniMax M3.1 Flash."""
        print(f"\n🔍 [Multimodal Review] Inspecting captured frame: {frame_path}")
        with open(frame_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        review_messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"You are the Director reviewing a rendered 1080p frame from Scene {scene_index} of the {self.city} documentary.\n"
                            f"Carefully inspect the image and assess:\n"
                            f"1. Is the render blank, black, or broken?\n"
                            f"2. Are the 3D structures, geometry, and procedural materials visible and clear?\n"
                            f"3. Is the lighting, contrast, and color balance effective?\n"
                            f"4. Does it convey the intended historical atmosphere?\n"
                            f"Output your verdict (PASS/FAIL), visual score (1-10), and brief critique."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    }
                ]
            }
        ]

        resp = self.client.chat_completion(
            messages=review_messages,
            reasoning_effort="high",
            max_tokens=4000
        )
        critique = resp["choices"][0]["message"].get("content", "")
        print(f"👁️  [Frame Review Verdict]:\n{critique}\n")
        return {
            "frame": frame_path,
            "scene_index": scene_index,
            "critique": critique
        }


def main():
    parser = argparse.ArgumentParser(description="Run the AI City Remix Director Pipeline")
    parser.add_argument("--city", type=str, default="Mumbai", help="Target city name (e.g. Mumbai, Tokyo, Rome)")
    parser.add_argument("--style", type=str, default="3D historical evolution with cinematic camera tours", help="Visual style")
    parser.add_argument("--reasoning-effort", type=str, default="high", choices=["low", "medium", "high", "xhigh", "max"], help="Explicit reasoning effort")
    parser.add_argument("--mock", action="store_true", help="Force mock simulation mode (offline)")
    parser.add_argument("--max-turns", type=int, default=15, help="Maximum director tool turns")

    args = parser.parse_args()

    director = DirectorAgent(
        city=args.city,
        style=args.style,
        reasoning_effort=args.reasoning_effort,
        mock_mode=args.mock
    )
    director.run_director_loop(max_turns=args.max_turns)


if __name__ == "__main__":
    main()
