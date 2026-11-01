"""Decide the real player slide sequence and attach embedded states as layers.

Rules:
- The player order of a module is the slide order of its interactions package.
- A storyboard slide that is a *state of* another slide (storyboard `interaction.state_of`,
  or named as `from_slide` by a parent's interaction layers) is NOT a player slide.
  It is attached to its parent and its content becomes that parent's interaction layers.
- Navigation is rebuilt from the player order. Source navigation that points at an
  embedded slide is reported and kept as `source_navigation`.
"""


def slide_key(source_id):
    """'1.04' -> 'slide_1_04'"""
    return "slide_" + source_id.replace(".", "_")


def module_key(number):
    return f"module_{int(number):02d}"


def map_slides(normalized):
    issues = []
    out_modules = []

    for m in normalized["modules"]:
        src, pkg, recs = m["source"], m["package"], m["slides"]

        embedded_into = {}  # child id -> parent id
        for sid, r in recs.items():
            parent = (r.get("storyboard_interaction") or {}).get("state_of")
            if parent:
                embedded_into[sid] = parent
            for layer in (r.get("interaction") or {}).get("layers", []):
                if layer.get("from_slide"):
                    embedded_into.setdefault(layer["from_slide"], sid)

        if pkg:
            order = [sid for sid in pkg["slide_order"] if sid in recs]
        else:
            order = [sid for sid in src["slide_order"] if sid not in embedded_into]

        for sid in order:
            if sid in embedded_into:
                issues.append({"slide": sid, "problem":
                               f"is an embedded state of {embedded_into[sid]} but also listed as a player slide"})

        player_slides = []
        for i, sid in enumerate(order):
            r = recs[sid]
            nav = {
                "prev": slide_key(order[i - 1]) if i > 0 else None,
                "next": slide_key(order[i + 1]) if i + 1 < len(order) else None,
                "home": slide_key(order[0]),
            }
            src_nav = r.get("navigation")
            nav_issue = None
            if src_nav:
                expected = {k: (v.replace("slide_", "").replace("_", ".") if v else None) for k, v in nav.items()}
                if any(src_nav.get(k) != expected[k] for k in expected):
                    nav_issue = dict(src_nav)
                    issues.append({"slide": sid, "field": "navigation", "source": src_nav,
                                   "used": expected,
                                   "resolution": "rebuilt from player order; source pointed at an embedded or missing slide"})
            player_slides.append({
                "record": r,
                "slide_id": slide_key(sid),
                "order": i + 1,
                "navigation": nav,
                "source_navigation": nav_issue,
                "embedded": [recs[c] for c, p in embedded_into.items() if p == sid and c in recs],
            })

        out_modules.append({
            "module_id": module_key(src["number"]),
            "source": src,
            "package": pkg,
            "player_slides": player_slides,
            "embedded_ids": sorted(embedded_into),
        })

    return {"modules": out_modules, "issues": issues}
