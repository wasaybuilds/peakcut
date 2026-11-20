"""Word timings -> ASS subtitles with a word-by-word highlight, plus hook text and credit.

Rendered by ffmpeg's libass (subtitles filter), which is far faster than per-frame
Python text rendering.
"""

W, H = 1080, 1920

# ASS colours are &HAABBGGRR
WHITE = "&H00FFFFFF"
BLACK = "&H00000000"
YELLOW = "&H0000E1FF"  # #FFE100
GREEN = "&H0097DC3D"  # #3DDC97
PINK = "&H006E3DFF"  # #FF3D6E

STYLES = {
    # name: (font, size, primary, highlight, outline px, uppercase)
    "bold_pop": ("Arial Black", 84, WHITE, YELLOW, 7, True),
    "beast": ("Impact", 104, WHITE, GREEN, 8, True),
    "minimal": ("Segoe UI Semibold", 64, WHITE, YELLOW, 4, False),
}


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def group_words(words: list[dict], max_words: int = 3, max_chars: int = 18, max_gap: float = 0.6):
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            gap = w["s"] - cur[-1]["e"]
            chars = sum(len(x["w"]) + 1 for x in cur) + len(w["w"])
            ends_sentence = cur[-1]["w"][-1:] in ".!?,"
            if len(cur) >= max_words or chars > max_chars or gap > max_gap or ends_sentence:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    *,
    style: str = "bold_pop",
    hook: str = "",
    credit: str = "",
    hook_y: int = 300,
) -> str:
    """`hook_y`: distance of the hook box from the top (moves to the seam in the face cam layout)."""
    font, size, primary, hi, outline, upper = STYLES.get(style, STYLES["bold_pop"])
    dur = clip_end - clip_start
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{primary},{primary},{BLACK},&H80000000,-1,0,0,0,100,100,1,0,1,{outline},3,2,60,60,560,1
Style: Hook,Arial Black,64,{WHITE},{WHITE},{PINK},&H00000000,-1,0,0,0,100,100,0,0,3,18,0,8,80,80,300,1
Style: Credit,Segoe UI Semibold,34,&H40FFFFFF,&H40FFFFFF,&H80000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,3,40,48,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events: list[str] = []

    # captions: one event per word, current word highlighted + popped
    clip_words = [
        {"w": w["w"], "s": w["s"] - clip_start, "e": w["e"] - clip_start}
        for w in words
        if w["e"] > clip_start and w["s"] < clip_end
    ]
    groups = group_words(clip_words)
    for gi, g in enumerate(groups):
        next_start = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else dur
        group_end = min(next_start, g[-1]["e"] + 0.5)
        for wi, w in enumerate(g):
            a = w["s"]
            b = g[wi + 1]["s"] if wi + 1 < len(g) else group_end
            if b <= a:
                continue
            parts = []
            for j, x in enumerate(g):
                t = _esc(x["w"].upper() if upper else x["w"])
                if j == wi:
                    parts.append(
                        f"{{\\c{hi}\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}}{t}{{\\c{primary}}}"
                    )
                else:
                    parts.append(t)
            events.append(f"Dialogue: 1,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{' '.join(parts)}")

    if hook:
        text = _esc(hook.upper())
        events.append(
            "Dialogue: 2,0:00:00.00,"
            f"{_ts(min(2.8, dur))},Hook,,0,0,{hook_y},,{{\\fad(120,200)\\fscx85\\fscy85\\t(0,140,\\fscx100\\fscy100)}}{text}"
        )
    if credit:
        events.append(f"Dialogue: 0,0:00:00.00,{_ts(dur)},Credit,,0,0,0,,{_esc(credit)}")

    return header + "\n".join(events) + "\n"
