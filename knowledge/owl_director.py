"""
Owl Alpha LLM Director — Re:Zero Shorts edit kararlarını verir.
OpenRouter üzerinden Owl Alpha'ya tool calling ile bağlanır.
Kullanılamazsa kural tabanlı fallback'e düşer.
"""
import os
import json
from pathlib import Path

EDIT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "order_clips",
            "description": "Order clips for best emotional impact in a Shorts video",
            "parameters": {
                "type": "object",
                "properties": {
                    "clip_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Clip IDs in the desired edit order"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of the edit structure"
                    }
                },
                "required": ["clip_ids", "reasoning"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_music_track",
            "description": "Select the best music track for this edit",
            "parameters": {
                "type": "object",
                "properties": {
                    "track_name": {
                        "type": "string",
                        "description": "Filename of the selected music track"
                    },
                    "music_drop_at": {
                        "type": "number",
                        "description": "Seconds into the video where the music drop/climax should hit"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this track fits the edit"
                    }
                },
                "required": ["track_name", "music_drop_at", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_transitions",
            "description": "Set transition type between clips",
            "parameters": {
                "type": "object",
                "properties": {
                    "transitions": {
                        "type": "object",
                        "description": "Mapping of clip_id to transition type: cut|fade|flash|zoom_cut",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["transitions"]
            }
        }
    }
]


RE_ZERO_SYSTEM = """You are an expert Re:Zero anime Shorts editor.
You know all Re:Zero characters, arcs, and emotional moments deeply.
Key knowledge:
- Rem's scenes are fan favorites — always prioritize
- Arc 5 (Sanctuary) has the most psychological depth
- Subaru's breakdowns are iconic but use sparingly
- Fast action cuts work for battle scenes
- Slow transitions work for emotional moments
- A good Shorts: hook (0-5s) → build (5-40s) → climax (40-55s) → end (55-59s)
Use your tools to make editorial decisions. Be decisive."""


def _read_key_from_config() -> str:
    """Read API key from config.yaml, searching relative to this file and CWD."""
    for base in [Path(__file__).parent.parent, Path.cwd()]:
        p = base / "config.yaml"
        if p.exists():
            try:
                import yaml
                with open(p) as f:
                    cfg = yaml.safe_load(f)
                return cfg.get("api", {}).get("openrouter_key", "")
            except Exception:
                pass
    return ""


def _get_client():
    """Create OpenAI client pointing at OpenRouter with 10s timeout."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or _read_key_from_config()
    if not api_key:
        print("[Owl Director] API anahtari bulunamadi. OPENROUTER_API_KEY env var'ini ayarlayin "
              "veya config.yaml'daki openrouter_key alanini doldurun.")
        return None

    try:
        from openai import OpenAI
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=10.0,
        )
    except ImportError:
        print("[Owl Director] openai paketi yuklu degil. 'pip install openai' ile kurun.")
        return None


def direct_edit_owl(clips: list, available_music: list, target_duration: float = 59.0) -> dict:
    """
    Owl Alpha makes editorial decisions using tool calls.

    Args:
        clips: List of analyzed scene dicts
        available_music: List of available music file names
        target_duration: Target shorts duration

    Returns:
        Edit plan with ordered clips, transitions, music selection
    """
    client = _get_client()
    if client is None:
        return _fallback_edit_plan(clips, available_music, target_duration)

    clip_summary = []
    for i, c in enumerate(clips[:25]):
        clip_summary.append({
            "id": i,
            "duration": round(c.get("actual_duration", c.get("duration", 2.0)), 1),
            "type": c.get("scene_type", "unknown"),
            "intensity": round(c.get("intensity", 5.0), 1),
            "has_dialogue": c.get("has_dialogue", False),
            "score": round(c.get("final_score", 5.0), 1),
        })

    user_msg = f"""Edit these Re:Zero clips into a {target_duration}s Shorts.

Clips available:
{json.dumps(clip_summary, indent=2)}

Music available: {available_music}

Use your tools to:
1. Order clips for maximum impact (order_clips)
2. Select the best music track (select_music_track)
3. Set transitions between clips (set_transitions)
"""

    messages = [
        {"role": "system", "content": RE_ZERO_SYSTEM},
        {"role": "user", "content": user_msg},
    ]
    edit_plan = {
        "ordered_clip_ids": list(range(len(clips))),
        "transitions": {},
        "music_track": available_music[0] if available_music else None,
        "music_drop_at": 30.0,
        "reasoning": "Default edit plan"
    }

    try:
        for _ in range(3):
            response = client.chat.completions.create(
                model="openrouter/owl-alpha",
                messages=messages,
                tools=EDIT_TOOLS,
                tool_choice="auto",
                max_tokens=800,
                timeout=15.0,
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                        for tc in msg.tool_calls
                    ]
                })

                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments)

                    if tc.function.name == "order_clips":
                        edit_plan["ordered_clip_ids"] = args.get("clip_ids", list(range(len(clips))))
                        edit_plan["reasoning"] = args.get("reasoning", "")

                    elif tc.function.name == "select_music_track":
                        edit_plan["music_track"] = args.get("track_name", available_music[0] if available_music else None)
                        edit_plan["music_drop_at"] = args.get("music_drop_at", 30.0)

                    elif tc.function.name == "set_transitions":
                        edit_plan["transitions"] = args.get("transitions", {})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"status": "ok"})
                    })
            else:
                break

    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)[:150]
        if "auth" in err_msg.lower() or "unauthorized" in err_msg.lower() or "401" in err_msg:
            reason = "API anahtari gecersiz"
        elif "timeout" in err_msg.lower() or "connect" in err_msg.lower():
            reason = "baglanti zamani asimi (OpenRouter'a erisilemiyor)"
        elif "model" in err_msg.lower() and "not" in err_msg.lower():
            reason = "openrouter/owl-alpha modeli kullanilamiyor"
        else:
            reason = f"API hatasi ({err_type})"
        print(f"[Owl Director] {reason}")
        return _fallback_edit_plan(clips, available_music, target_duration)

    return edit_plan


def _fallback_edit_plan(clips: list, available_music: list, target_duration: float) -> dict:
    """Rule-based fallback when Owl is unavailable."""
    sorted_clips = sorted(
        enumerate(clips),
        key=lambda x: x[1].get("final_score", 5),
        reverse=True
    )
    ordered_ids = [i for i, _ in sorted_clips]

    return {
        "ordered_clip_ids": ordered_ids,
        "transitions": {},
        "music_track": available_music[0] if available_music else None,
        "music_drop_at": 30.0,
        "reasoning": "Rule-based fallback (Owl Alpha unavailable)"
    }
