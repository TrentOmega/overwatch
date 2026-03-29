import re


_WEAK_ENDINGS = {"a", "an", "the", "to", "of", "in", "on", "for", "and", "or", "with", "by", "at", "its"}


def extract_outline_candidates(content):
    """Extract concise, human-meaningful candidates for filenames and display titles."""
    candidates = []
    seen = set()

    def add(text):
        cleaned = _clean_text(text)
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(cleaned)

    for signal in _extract_summary_signals(content):
        add(signal)

    for headline in re.findall(r"\*\*(.+?)\*\*", content):
        add(headline)

    for bullet_title in re.findall(r"^- \d{4}-\d{2}-\d{2} \| \[([^\]]+)\]", content, flags=re.MULTILINE):
        add(bullet_title)

    return candidates


def generate_slug_outline(content, max_items=3, max_len=60):
    """Generate a short slug suffix from extracted outline candidates."""
    slugs = []
    seen = set()
    for candidate in extract_outline_candidates(content):
        slug = _slugify(_shorten_for_slug(candidate))
        if not slug or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug[:25].rstrip("-"))
        if len(slugs) >= max_items:
            break

    outline = "_".join(slugs)
    return outline[:max_len].rstrip("-_")


def generate_display_outline(content, max_items=3, max_len=90):
    """Generate a display-friendly short title from extracted outline candidates."""
    selected = []
    for candidate in extract_outline_candidates(content):
        short = _shorten_headline(candidate, max_len=40)
        if short:
            selected.append(short)
        if len(selected) >= max_items:
            break

    if not selected:
        return ""

    for count in range(len(selected), 0, -1):
        result = "; ".join(selected[:count])
        if len(result) <= max_len:
            return result

    return selected[0][:max_len].rstrip()


def _extract_summary_signals(content):
    signals = []
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            continue
        if not cells[0].isdigit():
            continue
        signal = cells[2]
        if _is_nstr_signal(signal):
            continue
        signals.append(signal)
    return signals


def _clean_text(text):
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_#]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -|:;,.")
    if len(text) <= 5:
        return ""
    if text.startswith(("Classification", "Date", "Link", "Summary", "Key", "Top")):
        return ""
    return text


def _slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _trim_weak_ending(text):
    words = text.rsplit(" ", 1)
    if len(words) == 2 and words[1].lower() in _WEAK_ENDINGS:
        return words[0]
    return text


def _shorten_for_slug(text, max_len=40):
    text = _shorten_headline(text, max_len=max_len)
    return _trim_weak_ending(text)


def _shorten_headline(headline, max_len=40):
    if len(headline) <= max_len:
        return headline

    for sep in (":", " — ", " – ", " | ", " - ", " (", " “", ' "'):
        if sep in headline:
            first_part = _trim_weak_ending(headline.split(sep)[0].strip())
            if 10 < len(first_part) <= max_len:
                return first_part

    truncated = headline[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > 15:
        return _trim_weak_ending(truncated[:last_space])

    return truncated.rstrip()


def _is_nstr_signal(signal):
    normalized = re.sub(r"\s+", " ", signal.strip().rstrip(".")).lower()
    if normalized == "nstr":
        return True

    patterns = (
        r"no .+ confirmed(?: in supplied material)?",
        r"no .+ provided",
        r"no .+ identified",
        r"no .+ reported",
    )
    return any(re.fullmatch(pattern, normalized) for pattern in patterns)
