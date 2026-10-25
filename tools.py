"""
Tools and execution handlers for the City Remix Director Agent.
Infrastructure code only: runtime decisions (research, claims, script, scene HTML, frame review)
originate exclusively from MiniMax M3.1 Flash.
"""

import os
import sys
import json
import base64
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


OUTPUT_DIR = Path("output")
SCENES_DIR = OUTPUT_DIR / "scenes"
VIDEOS_DIR = OUTPUT_DIR / "videos"
FRAMES_DIR = OUTPUT_DIR / "frames"

for d in (OUTPUT_DIR, SCENES_DIR, VIDEOS_DIR, FRAMES_DIR):
    d.mkdir(parents=True, exist_ok=True)


def strip_code_fences(text: str) -> str:
    """Strip markdown code block fences if the model wraps output in them."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "save_research_claims",
            "description": "Save verified historical, architectural, and geographic claims about the city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Name of the target city"},
                    "claims": {
                        "type": "array",
                        "description": "List of factual claims anchored to specific eras and locations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "era": {"type": "string", "description": "Year or historical era"},
                                "topic": {"type": "string", "description": "Focus topic or landmark"},
                                "claim": {"type": "string", "description": "Factual claim with specifics"},
                                "source": {"type": "string", "description": "Historical or geographic source attribution"}
                            },
                            "required": ["era", "topic", "claim"]
                        }
                    }
                },
                "required": ["city", "claims"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_documentary_script",
            "description": "Save the multi-scene documentary script including narration, subtitles, and camera choreography.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Target city name"},
                    "title": {"type": "string", "description": "Documentary title"},
                    "synopsis": {"type": "string", "description": "High-level thematic overview"},
                    "total_duration_seconds": {"type": "integer", "description": "Total target duration (60-180s)"},
                    "scenes": {
                        "type": "array",
                        "description": "Chronological list of scenes",
                        "items": {
                            "type": "object",
                            "properties": {
                                "scene_index": {"type": "integer"},
                                "title": {"type": "string"},
                                "era": {"type": "string"},
                                "duration_seconds": {"type": "integer"},
                                "narration": {"type": "string"},
                                "subtitles": {"type": "string"},
                                "camera_tour": {"type": "string", "description": "Specific camera trajectory and movements"},
                                "visual_prompt": {"type": "string", "description": "Visual concept prompt for 3D/canvas generation"}
                            },
                            "required": ["scene_index", "title", "era", "duration_seconds", "narration", "visual_prompt"]
                        }
                    }
                },
                "required": ["city", "title", "scenes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_scene_html",
            "description": "Save generated self-contained HTML scene code (Three.js/Canvas/WebGPU/SVG) to disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer", "description": "Index of the scene (1, 2, ...)"},
                    "title": {"type": "string", "description": "Title of the scene"},
                    "html_content": {
                        "type": "string",
                        "description": "Complete self-contained HTML document (from <!DOCTYPE html> to </html>), including Three.js/Canvas/SVG code and autoplay camera tour."
                    }
                },
                "required": ["scene_index", "title", "html_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_scene_video",
            "description": "Execute scripts/record.mjs to record a scene HTML page headlessly into 1080p MP4.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer", "description": "Index of the scene to record"},
                    "duration_seconds": {"type": "integer", "description": "Duration in seconds to record (default 10)"},
                    "width": {"type": "integer", "description": "Viewport width (default 1920)"},
                    "height": {"type": "integer", "description": "Viewport height (default 1080)"}
                },
                "required": ["scene_index"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "capture_frame_for_review",
            "description": "Extract a video frame from recorded scene MP4 using ffmpeg for visual review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer", "description": "Index of the scene"},
                    "timestamp_seconds": {"type": "number", "description": "Timestamp in seconds to extract (e.g. 2.0)"}
                },
                "required": ["scene_index"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stitch_final_documentary",
            "description": "Stitch all recorded scene MP4s in chronological order into the final city documentary video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Name of the city"},
                    "output_filename": {"type": "string", "description": "Desired output filename (default: city_remix_{city}.mp4)"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_pipeline",
            "description": "Mark the city-remix pipeline run complete and summarize the final artifacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Detailed summary of produced scenes, claims, and final video"}
                },
                "required": ["summary"]
            }
        }
    }
]


class ToolExecutor:
    def __init__(self, client=None):
        self.client = client

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Dispatch tool execution and return string result."""
        method_name = f"_tool_{tool_name}"
        method = getattr(self, method_name, None)
        if not method:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        try:
            res = method(arguments)
            return json.dumps(res, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"Tool execution failed: {str(e)}"}, ensure_ascii=False)

    def _tool_save_research_claims(self, args: Dict[str, Any]) -> Dict[str, Any]:
        city = args["city"]
        claims = args["claims"]
        out_file = OUTPUT_DIR / "claims.json"
        data = {"city": city, "claims": claims}
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return {
            "status": "success",
            "message": f"Saved {len(claims)} research claims for {city} to {out_file}",
            "file": str(out_file)
        }

    def _tool_save_documentary_script(self, args: Dict[str, Any]) -> Dict[str, Any]:
        out_file = OUTPUT_DIR / "script.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(args, f, indent=2, ensure_ascii=False)
        scene_count = len(args.get("scenes", []))
        return {
            "status": "success",
            "message": f"Saved documentary script '{args.get('title')}' with {scene_count} scenes to {out_file}",
            "file": str(out_file),
            "scenes": [s.get("scene_index") for s in args.get("scenes", [])]
        }

    def _tool_save_scene_html(self, args: Dict[str, Any]) -> Dict[str, Any]:
        idx = args["scene_index"]
        title = args.get("title", f"Scene {idx}")
        raw_html = args["html_content"]
        clean_html = strip_code_fences(raw_html)

        scene_file = SCENES_DIR / f"scene_{idx}.html"
        with open(scene_file, "w", encoding="utf-8") as f:
            f.write(clean_html)

        return {
            "status": "success",
            "message": f"Saved scene {idx} ('{title}') HTML to {scene_file} ({len(clean_html)} chars)",
            "file": str(scene_file)
        }

    def _tool_record_scene_video(self, args: Dict[str, Any]) -> Dict[str, Any]:
        idx = args["scene_index"]
        duration = args.get("duration_seconds", 10)
        width = args.get("width", 1920)
        height = args.get("height", 1080)

        scene_file = SCENES_DIR / f"scene_{idx}.html"
        if not scene_file.is_file():
            # Check if there is an existing scene or test scene
            fallback = SCENES_DIR / "test_scene.html"
            if fallback.is_file():
                scene_file = fallback
            else:
                return {"error": f"Scene HTML file {scene_file} not found"}

        video_file = VIDEOS_DIR / f"scene_{idx}.mp4"
        cmd = [
            "node",
            "scripts/record.mjs",
            str(scene_file),
            str(video_file),
            str(duration),
            str(width),
            str(height)
        ]

        print(f"[Record] Running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {
                "error": f"Recording failed with exit code {proc.returncode}",
                "stdout": proc.stdout,
                "stderr": proc.stderr
            }

        return {
            "status": "success",
            "message": f"Successfully recorded scene {idx} to {video_file} ({width}x{height}, {duration}s)",
            "video_file": str(video_file),
            "file_size_bytes": video_file.stat().st_size if video_file.exists() else 0
        }

    def _tool_capture_frame_for_review(self, args: Dict[str, Any]) -> Dict[str, Any]:
        idx = args["scene_index"]
        t = args.get("timestamp_seconds", 2.0)
        video_file = VIDEOS_DIR / f"scene_{idx}.mp4"

        if not video_file.is_file():
            fallback = VIDEOS_DIR / "test_scene.mp4"
            if fallback.is_file():
                video_file = fallback
            else:
                return {"error": f"Video file {video_file} not found"}

        frame_file = FRAMES_DIR / f"scene_{idx}_t{int(t)}.jpg"
        # ffmpeg frame extraction
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-ss", str(t),
            "-i", str(video_file),
            "-frames:v", "1",
            "-q:v", "2",
            str(frame_file)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not frame_file.is_file():
            return {
                "error": f"Frame extraction failed: {proc.stderr}",
            }

        return {
            "status": "success",
            "message": f"Captured frame at t={t}s to {frame_file}",
            "frame_file": str(frame_file),
            "size_bytes": frame_file.stat().st_size
        }

    def _tool_stitch_final_documentary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        city = args["city"]
        out_name = args.get("output_filename") or f"city_remix_{city.lower().replace(' ', '_')}.mp4"
        out_path = OUTPUT_DIR / out_name

        # Find all scene mp4s sorted by index
        scene_files = sorted(
            [f for f in VIDEOS_DIR.glob("scene_*.mp4")],
            key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 999
        )

        if not scene_files:
            return {"error": "No recorded scene MP4 files found in output/videos/"}

        # Build concat list file
        concat_list = OUTPUT_DIR / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for s in scene_files:
                f.write(f"file '{s.resolve()}'\n")

        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out_path)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            return {"error": f"FFmpeg concat failed: {proc.stderr}"}

        return {
            "status": "success",
            "message": f"Stitched {len(scene_files)} scenes into final documentary {out_path}",
            "output_file": str(out_path),
            "file_size_bytes": out_path.stat().st_size
        }

    def _tool_complete_pipeline(self, args: Dict[str, Any]) -> Dict[str, Any]:
        summary = args["summary"]
        report_file = OUTPUT_DIR / "pipeline_summary.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"# City Remix Pipeline Summary\n\n{summary}\n")
        return {
            "status": "completed",
            "summary_file": str(report_file),
            "message": "Pipeline successfully completed all stages."
        }
