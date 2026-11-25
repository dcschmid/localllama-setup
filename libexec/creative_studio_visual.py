"""Story illustration profiles and the installed Studio image catalog contract."""

import json
import math
import re
import time

import creative_studio_organizer as organizer
from creative_studio_plan import PlanError

# Guided recipe names are preferences. The runtime catalog is authoritative.
TEMPLATES = {
    "anima-aesthetic": ("Anima Aesthetic", "anima", "anima-film",
        "Expressive illustrated anime film frame with clean contours and atmospheric depth."),
    "painterly-storybook": ("Painterly Storybook", "anima", "anima-storybook",
        "Hand-painted gouache, soft watercolor edges, translucent washes and visible paper grain."),
    "graphic-novel": ("Graphic Novel", "moss", "moss-comic",
        "Confident ink contours, deliberate halftones, graphic shadow shapes and selective color."),
    "soft-cinematic-anime": ("Soft Cinematic Anime", "anima", "anima-film",
        "Quiet anime film frame, delicate lines, soft motivated light and natural color grading."),
    "low-poly-concept-art": ("Low-Poly Concept Art", "moss", "lowpoly-retro",
        "Stylized three-dimensional game illustration with broad angular facets and readable silhouettes."),
    "high-poly-stylized": ("High-Poly Stylized", "z-image", "",
        "Stylized three-dimensional game key art with shaped curves, distinct materials and controlled cinematic light."),
    "riff-racers-low-poly": ("Riff Racers – Game Art · Low-Poly", "moss", "lowpoly-retro",
        "True low-poly arcade kart racing. Faceted color blocks, chunky karts, bold silhouettes and world-specific lighting."),
    "riff-racers-high-poly": ("Riff Racers – Game Art · High-Poly", "z-image", "",
        "Stylized 3D kart-racing key art. Preserve arcade proportions, driver identity and kart silhouette with more detailed materials."),
}
FIELDS = ("name", "description", "style", "model", "recipe", "ratio", "palette", "lighting",
          "composition", "consistency_rules", "negative", "extra")
RECORDS = {
    "characters": ("name", "appearance", "hair", "eyes", "clothing", "proportions", "features", "objects"),
    "locations": ("name", "architecture", "landscape", "materials", "lighting", "colors", "features"),
}
ALIASES = {
    "graphic-novel": r"graphic[ -]novel|comic[ -]stil",
    "soft-cinematic-anime": r"soft cinematic anime",
    "anima-aesthetic": r"anima(?: aesthetic)?",
    "painterly-storybook": r"painterly storybook|gouache|storybook|bilderbuchstil",
    "high-poly-stylized": r"high[ -]poly",
    "low-poly-concept-art": r"low[ -]poly",
}
STYLE_CHANGE = re.compile(r"\b(?:ab jetzt|ab sofort|von jetzt an|from now on|henceforth|"
                          r"bildstil|visual profile|style for (?:this|the) story|"
                          r"(?:verwende|nutze|use|switch)\b.{0,80}\b(?:für (?:diese|die) geschichte|for (?:this|the) story))\b", re.I)
VARIANT = re.compile(r"\b(?:varianten?|variations?|erneut|regenerate|heller|dunkler|brighter|darker|stärkeres mondlicht)\b", re.I)
RATIO = re.compile(r"\b(\d{1,2}):(\d{1,2})\b")
REQUESTED_RATIO = re.compile(r"\b(?:bildformat|seitenverhältnis|aspect(?: ratio)?|format)\s*(?:of |von |in )?(\d{1,2}:\d{1,2})\b", re.I)
SIZE = re.compile(r"([1-9]\d{2,3})x([1-9]\d{2,3})")
RIFF = re.compile(r"\briff[ -]?racers\b", re.I)
KINDS = {"story", "novel"}
PALETTES = (
    (r"schnee|winter|snow|frost|glacier|eis(?:ig|blau)", "Blue-gray and ice-blue, with warm window or fire accents where present"),
    (r"sonnenuntergang|abendrot|sunset|dusk|twilight|abend|dämmerung", "Amber highlights, violet transitions and deep blue shadows"),
    (r"mondlicht|moonlight|midnight|mitternacht|nacht|night", "Midnight blue and restrained silver light, with local practical highlights"),
    (r"metallwelt|metal world|foundry|gießerei|industrial|industrie", "Warm industrial lights on graphite and exposed steel, with clean color accents"),
    (r"wald|forest|woods|jungle|dschungel", "Natural greens and bark colors, balanced with the actual sky and reflected light"),
    (r"sonnig|sunny|daylight|garden|garten|strand|beach", "Clear local colors, light sky tones and warm sunlit surfaces"),
)


def clean(value, limit=800):
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise PlanError("visual_profile_invalid")
    return value.strip()


def choice(text, riff=False):
    if not isinstance(text, str):
        return None
    for key, pattern in ALIASES.items():
        if re.search(r"\b(?:" + pattern + r")\b", text, re.I):
            if riff and key in ("low-poly-concept-art", "high-poly-stylized"):
                return "riff-racers-low-poly" if key == "low-poly-concept-art" else "riff-racers-high-poly"
            return key
    return "riff-racers-low-poly" if not riff and RIFF.search(text) else None


def requested_ratio(text):
    if explicit := REQUESTED_RATIO.search(text):
        return explicit[1]
    return next((match[0] for match in RATIO.finditer(text)
                 if match[0] in ("16:9", "1:1", "4:3", "3:2", "3:4", "2:3", "9:16")), None)


def template(key):
    if not isinstance(key, str) or key not in TEMPLATES:
        raise PlanError("visual_profile_invalid")
    name, model, recipe, style = TEMPLATES[key]
    return dict(template=key, name=name, description=style, style=style, model=model, recipe=recipe,
                ratio="16:9", palette="", lighting="", composition="", consistency=True, consistency_rules="",
                negative="", extra="", bible={key: [] for key in RECORDS})


def default_profile(pid, name):
    key = "riff-racers-low-poly" if RIFF.search(name) else "anima-aesthetic"
    return {**template(key), "id": pid, "version": 0}


def ensure(conn, pid):
    value = load(conn, pid)
    conn.execute("""UPDATE projects SET meta=json_set(meta,'$.visual_profile',json(?))
                    WHERE id=? AND json_type(meta,'$.visual_profile') IS NULL""",
                 (json.dumps(value, ensure_ascii=False), pid))
    return value


def load(conn, pid):
    row = organizer.require(conn, "project", pid)
    if row["kind"] not in KINDS:
        raise PlanError("visual_story_required")
    saved = json.loads(row["meta"] or "{}").get("visual_profile")
    if saved:
        return saved
    return default_profile(pid, row["name"])


def available(catalog, profile):
    model = next((m for m in catalog.get("models", []) if m["id"] == profile["model"] and m.get("installed")), None)
    if model is None:
        raise PlanError("visual_model_unavailable")
    formats = supported_formats(model)
    if profile["ratio"] not in formats:
        raise PlanError("visual_format_unavailable")
    if profile["recipe"]:
        recipe = next((item for item in catalog.get("recipes", []) if item["id"] == profile["recipe"]), None)
        if not recipe or recipe.get("model") != model["id"]:
            raise PlanError("visual_recipe_unavailable")
    return model, formats


def supported_formats(model):
    formats = {}
    for fmt in model.get("formats", []):
        for key in ("size", "preview_size"):
            size = fmt.get(key)
            if valid_ratio(size, fmt.get("id")) and size in model.get("sizes", []):
                formats[fmt["id"]] = size
                break
    return formats


def valid_ratio(size, ratio):
    if not isinstance(size, str) or not isinstance(ratio, str):
        return False
    dims, aspect = SIZE.fullmatch(size), RATIO.fullmatch(ratio)
    if not dims or not aspect:
        return False
    w, h = map(int, dims.groups())
    a, b = map(int, aspect.groups())
    return a > 0 and b > 0 and w * b == h * a


def ratio_for(size):
    match = SIZE.fullmatch(size or "")
    if not match:
        return None
    w, h = map(int, match.groups())
    factor = math.gcd(w, h)
    return f"{w // factor}:{h // factor}"


def save(conn, pid, body, catalog):
    current = load(conn, pid)
    if type(body.get("version")) is not int or body["version"] != current["version"]:
        raise organizer.OrganizerError("visual_profile_changed", 409)
    if copy := body.get("copy_from"):
        profile = load(conn, copy)
        profile = {**profile, "bible": {
            group: [{k: v for k, v in row.items() if k not in ("attachment", "use_image")} for row in rows]
            for group, rows in profile["bible"].items()}}
    elif "template" in body and body["template"] != current["template"]:
        profile = {**template(body["template"]), **{key: current[key]
                    for key in ("bible", "ratio", "consistency", "consistency_rules")}}
    else:
        profile = current
    profile = {**profile, **{key: clean(body[key], 800) for key in FIELDS if key in body},
               "id": pid, "version": current["version"] + 1}
    profile["consistency"] = body.get("consistency", profile["consistency"])
    if type(profile["consistency"]) is not bool or not profile["name"] or not profile["style"]:
        raise PlanError("visual_profile_invalid")
    bible = body.get("bible", profile["bible"])
    if not isinstance(bible, dict) or set(bible) - RECORDS.keys():
        raise PlanError("visual_profile_invalid")
    profile["bible"] = {}
    for group, fields in RECORDS.items():
        rows = bible.get(group, [])
        if not isinstance(rows, list) or len(rows) > 40:
            raise PlanError("visual_profile_invalid")
        result = []
        for row in rows:
            if not isinstance(row, dict) or not row.get("name") or set(row) - {*fields, "from", "to", "attachment", "use_image"}:
                raise PlanError("visual_profile_invalid")
            first, last = row.get("from", 1), row.get("to", 150)
            if type(first) is not int or type(last) is not int or not 1 <= first <= last <= 150:
                raise PlanError("visual_profile_invalid")
            record = {key: clean(row[key], 500) for key in fields if key in row}
            if attachment := row.get("attachment"):
                image = organizer.require(conn, "attachment", attachment, include_data=True)
                if image["project_id"] != pid or not image["name"].lower().endswith((".png", ".jpeg", ".jpg", ".webp")):
                    raise PlanError("visual_reference_invalid")
                record["attachment"] = attachment
            use_image = row.get("use_image", False)
            if type(use_image) is not bool or (use_image and "attachment" not in record):
                raise PlanError("visual_reference_invalid")
            result.append({**record, "from": first, "to": last, "use_image": use_image})
        profile["bible"][group] = result
    available(catalog, profile)
    conn.execute("UPDATE projects SET meta=json_set(meta,'$.visual_profile',json(?)),updated=? WHERE id=?",
                 (json.dumps(profile, ensure_ascii=False), time.time(), pid))
    return profile


def records(profile, chapter, scene=""):
    if not profile["consistency"]:
        return []
    rows = [row for group in RECORDS for row in profile["bible"][group]
            if row["from"] <= (chapter or 1) <= row["to"]]
    # The latest state within the illustration's chronology supersedes older descriptions.
    latest = {row["name"].casefold(): row for row in sorted(rows, key=lambda row: row["from"])}
    if not scene:
        return list(latest.values())
    return [row for name, row in latest.items()
            if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", scene.casefold())]


def palette(scene, fallback):
    return next((colors for pattern, colors in PALETTES if re.search(pattern, scene, re.I)),
                fallback or "Scene-local colors with distinct values and a controlled focal accent")


def scene_kind(text):
    for kind, pattern in (
        ("portrait", r"\b(?:porträt|portrait|fahrerporträt|headshot)\b"),
        ("kart", r"\b(?:kart[- ]illustration|vehicle design|kart concept)\b"),
        ("track", r"\b(?:track overview|streckenübersicht|von oben|top-down)\b"),
        ("landscape", r"\b(?:landschaft|landscape|umgebungsbild|establishing shot)\b"),
        ("fantasy", r"\b(?:fantasy|magic|magie|zauber|dragon|drache)\b"),
    ):
        if re.search(pattern, text, re.I):
            return kind
    return "scene"


def prepare(profile, catalog, subject, passage, chapter, *, cover=False, seed=None, upload=None, observations=()):
    model, formats = available(catalog, profile)
    format_info = next(fmt for fmt in model["formats"] if fmt["id"] == profile["ratio"])
    quality = "standard" if format_info["size"] == formats[profile["ratio"]] else "preview"
    recipe = profile["recipe"]
    kind = scene_kind(subject + " " + passage)
    if recipe == TEMPLATES[profile["template"]][2]:
        options = {
            "anima-aesthetic": {"portrait": "anima-portrait", "landscape": "anima-landscape", "fantasy": "anima-fantasy"},
            "low-poly-concept-art": {"portrait": "lowpoly-character", "kart": "lowpoly-vehicle",
                                     "track": "lowpoly-track-overview", "landscape": "lowpoly-world"},
            "riff-racers-low-poly": {"portrait": "lowpoly-character", "kart": "lowpoly-vehicle",
                                     "track": "lowpoly-track-overview", "landscape": "lowpoly-world"},
        }
        preferred = options.get(profile["template"], {}).get(kind)
        if any(item["id"] == preferred and item.get("model") == model["id"] for item in catalog.get("recipes", [])):
            recipe = preferred
    refs = records(profile, chapter, subject + " " + passage)
    facts = " ".join(row["name"] + ": " + ", ".join(
        value for key, value in row.items() if key not in ("name", "attachment", "use_image", "from", "to")
    ) for row in refs)
    colors = palette(passage + " " + subject, profile["palette"])
    framing = ("Compose as a title image with calm negative space for later typesetting. " if cover else
               "Frame the main action with a clear foreground, middle distance and background. ")
    earlier = " ".join(entry["fact"] for entry in observations)
    details = " ".join(filter(None, [
        profile["style"], f"Palette: {colors}.", profile["lighting"], framing,
        f"Compose natively for {profile['ratio']}. Keep important subjects inside the frame.",
        profile["composition"], profile["consistency_rules"] if profile["consistency"] else "",
        "Fill the canvas edge to edge. Use a single scene, free of lettering, logos, frames or black bars.",
        facts[:800], profile["extra"], f"Earlier observed details, if still current: {earlier[:380]}." if earlier else "",
    ]))
    request = ({"recipe": recipe, "model": model["id"], "subject": subject[:1800],
                "scene": passage[:1400], "details": details[:1950], "aspect_ratio": profile["ratio"], "quality": quality}
               if recipe else {"model": model["id"], "size": formats[profile["ratio"]],
                   "prompt": "\n".join((subject[:1600], passage[:850], details[:1950])), "preset": "none"})
    if seed is not None:
        request["seed"] = seed
    primary = next((row for row in refs if row.get("use_image") and row.get("attachment")), None)
    if primary:
        if "img2img" not in model.get("verified_modes", []) or upload is None:
            raise PlanError("visual_reference_unavailable")
        request.update(mode="img2img", image_id=upload(primary["attachment"]), strength=0.72)
    metadata = {"id": profile["id"], "name": profile["name"], "version": profile["version"],
                "template": profile["template"], "model": model["id"], "recipe": recipe,
                "ratio": profile["ratio"], "palette": colors, "license": model.get("license"),
                "license_url": model.get("license_url") or model.get("source"),
                "references": [row["attachment"] for row in refs if row.get("attachment")],
                "image_conditioning": bool(primary)}
    return request, metadata, formats[profile["ratio"]]
