"""Build voiceover.json: narration text, audio files, reveal cues and playback rules.

Audio filenames, word counts and approximate durations come from the interactions
audio_manifest. Nothing is invented: a slide with no narration gets `base: null`.
`approxSeconds` is the source's estimate (140 wpm), not a measured duration.
"""


def _line_index(lines, text):
    if text is None:
        return None
    try:
        return lines.index(text)
    except ValueError:
        return None


def _expected_reveal_texts(comp):
    """Text the source reveal list should contain for this component, item by item."""
    p, t = comp["props"], comp["type"]
    if t == "cardGrid":
        return [c["title"] + (" — " + c["body"] if c.get("body") else "") for c in p["cards"]]
    if t == "definition":
        return [d["term"] + (" — " + d["description"] if d.get("description") else "") for d in p["terms"]]
    if t == "comparison":
        return [c["title"] + " — " + c["body"] for c in p["columns"]]
    if t == "iconGrid":
        return [i["label"] for i in p["items"]]
    if t in ("bulletList",):
        return p["items"]
    if t == "summary":
        return p["points"]
    if t == "references":
        return p["items"]
    if t == "results":
        return p["lines"]
    if t == "process":
        return [s["label"] for s in p["steps"]]
    if t == "table":
        return [" | ".join(r) for r in [p["headers"]] + p["rows"]]
    if t == "sequence":
        # source reveal text is "label — answer key"; the player must not display the key
        return [f"{i['label']} — {i['correctPosition']}" for i in p["items"]]
    if t == "objectivesList":
        return [o["text"] for o in p["items"]]
    if t == "multipleChoice":
        return [o["text"] for o in p["options"]]
    if t == "matching":
        return [f"{i['label']} — {i['matchText']}" for i in p["items"]]
    if t == "trueFalse":
        return [o["text"] for o in p["options"]]
    if t == "multiSelect":
        return [o["text"] for o in p["options"]]
    return None


def generate_voiceover(components_doc, context, interactions, issues):
    audio = interactions["audio"]
    used_audio = set()
    modules = []
    comp_index = {c["id"]: c for m in components_doc["modules"] for s in m["slides"] for c in s["components"]}

    for m in components_doc["modules"]:
        vslides = []
        for s in m["slides"]:
            ctx = context[s["slideId"]]
            rec = ctx["record"]
            lines = rec["narration"]

            # ---- reveal cues -> component items ----
            target = ctx["reveal_target"]
            cues = []
            expected = _expected_reveal_texts(comp_index[target]) if target else None
            for k, r in enumerate(rec["reveal"]):
                cue = {"order": r["order"], "componentId": target, "itemIndex": k,
                       "lineIndex": _line_index(lines, r.get("cue_narration_line"))}
                if r.get("cue_narration_line") and cue["lineIndex"] is None:
                    cue["cueText"] = r["cue_narration_line"]
                    issues.append({"slide": rec["id"], "field": "reveal cue",
                                   "problem": "cue line not found in narration; kept as cueText"})
                if expected is None or k >= len(expected) or expected[k] != r["text"]:
                    cue["text"] = r["text"]   # keep the source text when it doesn't map cleanly
                    issues.append({"slide": rec["id"], "field": f"reveal item {r['order']}",
                                   "problem": "reveal text does not match a component item; source text kept on cue"})
                cues.append(cue)

            base = None
            if lines or rec["audio_file"]:
                a = audio.get((rec["id"], None), {})
                if rec["audio_file"]:
                    used_audio.add((rec["id"], None))
                if rec["audio_file"] and a and a.get("file") != rec["audio_file"]:
                    issues.append({"slide": rec["id"], "field": "audio_file",
                                   "problem": f"base_layer {rec['audio_file']} vs manifest {a.get('file')}"})
                base = {
                    "audioFile": rec["audio_file"],
                    "words": a.get("words"),
                    "approxSeconds": a.get("approx_seconds"),
                    "lines": lines,
                    "reveal": {"mode": rec["reveal_mode"], "note": rec["reveal_note"], "cues": cues},
                }

            # ---- interaction layers ----
            layers = []
            ix = rec.get("interaction") or {}
            if ctx["layers"]:
                owner, lmap = ctx["layers"]
                for L in ix.get("layers", []):
                    a = audio.get((rec["id"], L["index"]), {})
                    if L.get("audio_file"):
                        used_audio.add((rec["id"], L["index"]))
                    layers.append({
                        "layerId": lmap[L["index"]],
                        "componentId": owner,
                        "index": L["index"],
                        "audioFile": L.get("audio_file"),
                        "words": a.get("words"),
                        "approxSeconds": a.get("approx_seconds"),
                        "lines": L.get("narration", []),
                    })

            sequence = (["base"] if base else []) + [f"on_open:{L['layerId']}" for L in layers]
            playback = {
                "autoplayBase": bool(base and base["audioFile"]),
                "sequence": sequence,
                "pauseBaseOnLayerOpen": bool(ix.get("pause_base_audio_on_layer_open")) if layers else None,
                "resumeBaseOnLayerClose": True if layers else None,
                "stopLayerAudioOnLayerSwitch": True if layers else None,
            }
            q = rec.get("question")
            if q and q.get("on_submit_audio"):
                playback["onSubmit"] = q["on_submit_audio"]
            if not base and not layers:
                playback["note"] = "No narration on this slide in the source."

            vslides.append({"slideId": s["slideId"], "sourceSlideId": rec["id"],
                            "base": base, "layers": layers, "playback": playback})
        modules.append({"moduleId": m["moduleId"], "title": m["title"], "slides": vslides})

    unused = [a for k, a in audio.items() if k not in used_audio]
    for a in unused:
        issues.append({"slide": a["slide"], "field": "audio_manifest",
                       "problem": f"{a['file']} is in the manifest but not referenced by any slide or layer"})

    return {
        "specVersion": "v1",
        "course": components_doc["course"]["title"],
        "audio": {
            "basePath": "audio/",
            "format": "mp3",
            "filesSupplied": False,
            "note": ("Filenames come from the source audio_manifest. The audio itself was not supplied, "
                     "so every file is unresolved until recorded. approxSeconds is the source's 140 wpm estimate."),
        },
        "playerRules": {
            "revealWithoutAudio": "show all items immediately",
            "revealTiming": ("line start = audio duration x (words before the line / total words); "
                             "an item with lineIndex null takes the previous item's cue, or shows at start"),
            "missingAudio": "do not block navigation; show the narration text instead",
        },
        "manifestEntries": len(interactions["audio_manifest"]),
        "modules": modules,
    }
