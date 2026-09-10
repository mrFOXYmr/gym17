#!/usr/bin/env python3
"""Generates clean, presentation-ready HTML slide decks from each week's конспект.

Transforms the teacher-facing Markdown конспект into audience-facing slides:
  * drops teacher-only / meta sections (goals, timing, HW pointers, archive index,
    oral quizzes, "run chorally", follow-up plans);
  * renders headings, lists, blockquotes, code fences, tables;
  * applies light inline Markdown (**bold**, `code`, [links]).
"""
import os, re, glob, html

SRC = "конспекты"
DST = "презентации"
os.makedirs(DST, exist_ok=True)

# ---------------------------------------------------------------- meta sections
# A section (## ...) whose heading matches is DROPPED from the deck entirely.
META_SECTIONS = [
    r"цели (?:урока|занятия|уроков|цикла)", r"тайминг", r"регламент", r"напутствие",
    r"домашн\w+ задани", r"домашк\w+", r"материал[ые]* из архив", r"архив",
    r"итог (?:занятия|урока|цикла|уроков)|^итог(?:[:—-]|\s)", r"что делать после", r"после 21\.10", r"личный план",
    r"план на январь", r"технологии и скорость", r"заметка для тренер",
    r"разбор (контрольной|пробного|контрольны|типовых решений)",
    r"мини-квиз", r"квиз", r"прогнать", r"рефлексия",
    r"важное напоминани", r"этап-1\. *дискусси",
]
META_SECTION_RE = re.compile("|".join(META_SECTIONS), re.IGNORECASE)

# ------------------------------------------------------ inline teacher phrases
# Sentences/fragments typical of the teacher-facing plan get stripped from
# paragraphs and list items.   (whole-line removal)
STRIP_LINE_RE = re.compile(
    r".*(?:" + "|".join([
        r"педагог проверяет", r"педагог задаёт", r"задача педагога",
        r"ученики разбирают", r"ученики фотографируют", r"ученики списывают",
        r"прогнать у доски", r"прогнать типов\w+ (?:решения|задания) у доски",
        r"разбор решений у доски", r"разбор у доски", r"у доски",
        r"зафиксировать эталон\w*", r"это первый срез уровня",
        r"точка отсчёта прогресса", r"отметить, кто что доработать",
        r"дома — таблица на стену", r"на стену как шпаргалку",
        r"записать в шпаргалку", r"в тетрадь", r"поднять ответ-карточку",
        r"ответ-карточку", r"каждый ученик должен убедиться",
        r"проверить подачу заявок", r"обратно/на тестах",
        r"сначала лёгкая теория", r"прогнать типовые задания",
        r"потом сверка", r"сверка", r"убедиться в доступе",
        r"прогнать у доски", r"считаем флаги, разбираем решения",
        r"считаем баллы", r"для тренера",
    ]) + r").*", re.IGNORECASE)

# Trim trailing "coach" fragments that may remain after inline keywords.
COACH_TAIL = re.compile(
    r"(\s*[—;–,·]\s*(?:разбираем[^.]*?|прогнать[^.]*?|педагог[^.]*?)\.?)\s*$",
    re.IGNORECASE)


def parse(md_text):
    lines = md_text.splitlines()
    title = None
    slides = []
    cur = []
    code_open = False
    code_buf = []
    tbl_buf = None
    section_is_meta = False
    drop_slide = False   # set when a meta ## header ends the slide body

    def flush_code():
        nonlocal code_buf
        if code_buf:
            cur.append(("raw", "<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>"))
            code_buf = []

    def flush_tbl():
        nonlocal tbl_buf
        if not tbl_buf:
            return
        rows = tbl_buf
        head = rows[0]
        data = rows[2:] if len(rows) > 1 and re.match(r'^\s*[|:\- ]+\s*$', rows[1]) else rows[1:]
        h = "".join(f"<th>{inline(html.escape(c.strip()))}</th>" for c in head.split("|")[1:-1])
        body = ""
        for r in data:
            cells = r.split("|")[1:-1]
            body += "<tr>" + "".join(f"<td>{inline(html.escape(c.strip()))}</td>" for c in cells) + "</tr>"
        cur.append(("raw", f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"))
        tbl_buf = None

    def close_slide():
        nonlocal cur, drop_slide
        if cur and not drop_slide:
            slides.append(cur)
        cur = []
        drop_slide = False

    reveal_state = None   # (label, target_dest, title_of_parent?) — currently one-level
    reveal_stack = []     # list of dicts to support nesting
    prev_cur = None       # saved outer block list while a reveal is open

    inline = _inline_md

    def reveal_finish():
        """Flush accumulated reveal content into a <details> block appended to outer list."""
        nonlocal cur, reveal_stack, prev_cur
        # unwrap current cur back
        if not reveal_stack:
            return
        frame = reveal_stack.pop()
        label, inner = frame["label"], cur
        details = "<details><summary>" + inline(html.escape(label or "Ответ")) + "</summary><div class='reveal'>"
        details += "".join(render_block(b) for b in inner)
        details += "</div></details>"
        cur = prev_cur
        prev_cur = None
        cur.append(("raw", details))

    for ln in lines:
        s = ln.rstrip()

        # --- reveal (collapsible answer) block: :::answer ... :::
        if not code_open and s.strip() == ":::":
            if reveal_stack:
                flush_code(); flush_tbl()
                reveal_finish()
            else:
                continue
            continue
        if not code_open and s.startswith(":::"):
            # open a reveal, e.g. ":::answer", "::: Ответ", "::: [Разбор]"
            if reveal_stack:
                flush_code(); flush_tbl()
                reveal_finish()
            flush_code(); flush_tbl()
            label = s[3:].strip() or "Ответ"
            reveal_stack.append({"label": label})
            prev_cur = cur
            cur = []
            continue

        # --- inside a code fence: collect verbatim (incl. anything starting with #, etc.)
        if code_open and s.startswith("```"):
            flush_code()
            code_open = False
            continue
        if code_open:
            code_buf.append(s)
            continue

        # table row collection
        if re.match(r'^\s*\|', s):
            if tbl_buf is None:
                flush_code()
                tbl_buf = []
            tbl_buf.append(s)
            continue
        else:
            if tbl_buf is not None:
                flush_tbl()

        if s.startswith("# "):
            title = s[2:].strip()
        elif s.startswith("## "):
            flush_code(); flush_tbl()
            close_slide()
            heading = s[3:].strip()
            section_is_meta = bool(META_SECTION_RE.search(heading))
            if section_is_meta:
                drop_slide = True
            else:
                cur.append(("h2", strip_coach(heading)))
        elif s.startswith("### "):
            flush_code()
            if not drop_slide:
                cur.append(("h3", strip_coach(s[4:].strip())))
        elif s.startswith("> "):
            flush_code()
            if not drop_slide:
                cur.append(("raw", "<blockquote>" + inline(html.escape(s[2:].strip())) + "</blockquote>"))
        elif s.startswith("```"):
            flush_code(); flush_tbl()
            code_open = True; code_buf = []
        else:
            t = s.strip()
            if not t:
                continue
            if drop_slide:
                continue
            if STRIP_LINE_RE.search(t):
                continue
            if re.match(r'^\s*[-*]\s', s):
                flush_code()
                item = re.sub(r'^\s*[-*]\s*', '', s)
                item = strip_coach(item)
                if item:
                    cur.append(("li", inline(html.escape(item))))
            elif re.match(r'^\s*\d+\.\s', s):
                flush_code()
                item = re.sub(r'^\s*\d+\.\s*', '', s)
                item = strip_coach(item)
                if item:
                    cur.append(("li", inline(html.escape(item))))
            else:
                flush_code()
                item = strip_coach(t)
                if item:
                    cur.append(("p", inline(html.escape(item))))
    while reveal_stack:
        flush_code(); flush_tbl()
        reveal_finish()
    flush_code(); flush_tbl()
    close_slide()
    return title, slides


# Strip timing / logistics parentheses such as "(25 мин)", "(2 часа)", "(на время)".
TIMING_RE = re.compile(
    r"\s*[\(\[(]?\s*(?:на время|по времени|~)?\s*\d+(?:[–\-–]\d+)?\s?(?:мин|час|часа|часов|минуты?)[^)\]]*[\)\]}]?\s*",
    re.IGNORECASE)


# Leading coach-intro prefixes: strip the words, keep any useful tail.
PREFIX_RE = re.compile(
    r"^\s*(?:разбираем\s*(?:вслух\s*)?[:,]?\s*|"
    r"прогнать хором\s*[,;]?\s*|"
    r"педагог\s*[^.]*?[:,]\s*|"
    r"ученики\s+по\s+очереди\s+пишут\s+в\s+ide\s*:\s*|"
    r"игра-тренировка\s*[::]?\s*|"
    r"итог\s*[::]?\s*|"
    r"заметка\s+для\s+тренера\s*[::]?\s*)",
    re.IGNORECASE)


def strip_coach(t):
    t = PREFIX_RE.sub("", t)
    t = STRIP_LINE_RE.sub("", t)
    t = COACH_TAIL.sub("", t)
    t = TIMING_RE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _inline_md(t):
    """Very small inline-markdown helper: **bold**, `code`."""
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def render_block(b):
    kind = b[0]
    if kind == "raw":
        return b[1]
    if kind == "h2":
        return f"<h2>{b[1]}</h2>"
    if kind == "h3":
        return f"<h3>{b[1]}</h3>"
    if kind == "li":
        return f"<li>{b[1]}</li>"
    if kind == "p":
        return f"<p>{b[1]}</p>"
    return ""


def main():
    for f in sorted(glob.glob(os.path.join(SRC, "нед-*.md"))):
        with open(f, encoding="utf-8") as fh:
            md = fh.read()
        title, slides = parse(md)
        title = re.sub(r"^\s*Конспект\s*", "", title, flags=re.IGNORECASE).strip()
        title = strip_coach(title)
        # drop "неделя N" numeral but keep the theme name clean
        title = re.sub(r"^\s*Конспект\s*", "", title, flags=re.IGNORECASE).strip()
        title = strip_coach(title)
        m = re.match(r"^\s*[Нн]едел\w*\s*(\d+)\s*[—\-–]\s*(.+)$", title)
        if m:
            title = f"Неделя {m.group(1)} · {m.group(2).strip()}"
        else:
            title = re.sub(r"^\s*[Нн]едел[яи]\.?\s*", "", title).strip()
        if title and title[0].islower():
            title = title[0].upper() + title[1:]
        if title:
            slides = [[("raw", f"<h1>{html.escape(title)}</h1>")]] + slides
        if not slides:
            print(f"!! {os.path.basename(f)}: 0 slides")
            continue
        sections = []
        for slide in slides:
            inner = "".join(render_block(b) for b in slide)
            sections.append(f"<section>{inner}</section>")
        doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title or '')}</title>
<link rel="stylesheet" href="../slide.css">
</head>
<body>
{chr(10).join(sections)}
<div class="nav">
  <button onclick="nav(-1)" aria-label="Назад">&#8592;</button>
  <span id="pg">1 / {len(sections)}</span>
  <button onclick="nav(1)" aria-label="Вперёд">&#8594;</button>
</div>
<script src="../slide.js"></script>
</body>
</html>"""
        base = os.path.splitext(os.path.basename(f))[0]
        with open(os.path.join(DST, base + ".html"), "w", encoding="utf-8") as fh:
            fh.write(doc)
        print(f"{base}.html  ->  {len(slides)} слайдов")


if __name__ == "__main__":
    main()