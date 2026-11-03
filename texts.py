"""🖌 تنظیمات متون — ویرایش تمام متن‌های ربات (غیر از متن‌های ادمین) از داخل پنل مدیریت.

طرز کار:
  • کاتالوگ: متن‌های ثابت/f-string داخل bot_test.py و games.py با AST استخراج می‌شوند
    (هر تکه متن = یک «مورد» با کلید پایدار). بخش‌ها و توابع ادمین، لیبل دکمه‌ها و متن‌های فنی حذف می‌شوند.
  • ویرایش: ادمین پیام جدید را (با bold/italic/…/ایموجی پرمیوم) می‌فرستد؛ entityها دقیقاً به HTML تبدیل
    و در جدول text_overrides ذخیره می‌شود.
  • اعمال: tg() قبل از ارسال، متنِ نهایی را با الگوی هر مورد ویرایش‌شده تطبیق می‌دهد و آن بخش را عوض می‌کند.
    مقدارهای متغیر ({1}، {2}، …) از همان متن اصلی گرفته و در جایگاهشان گذاشته می‌شوند.
"""
import ast
import hashlib
import html as _h
import json
import logging
import os
import re
import threading
import time

B = None
_FA = re.compile(r"[؀-ۿ]")
_PH = re.compile(r"\{(\w+)\}")
_TOK = "%d"
_TOK_RE = re.compile("(\\d+)")

# ---------------- فیلتر (چه چیزهایی ادمین‌ی/فنی‌اند و وارد کاتالوگ نمی‌شوند) ----------------
_EXCL_FN = re.compile(
    r"admin|^render_|^v2_|^rep_|^_rp_|^rs_|^_rs_|^stats_text|^_so_card|^_inv_card|^_send_list|^_send_requests|"
    r"^_broadcast|^_bc_|^_fj_warn_admins|^rich_|^_ask|^_prompt_for|^_pack_input|^_pack_label|^_user_card|"
    r"^layout_text|^product_settings_text|^b$|^f$|^info$|^setup_bot_commands|^_cfg_page|^_rep_page|^_act_page|"
    r"^_user_page|^_mon_page|^_mcfg_page|^_mrep_page|^sponsor_docs|^_sponsor_info_text|^handle_receipt|"
    r"^handle_sponsor_channel|^notify_admins|^_label$|^_user_label|^_user_brief|^_invoice_detail_lines|"
    r"^invoice_watcher|^_fmt_dur|^_remaining_text|^sponsor_shift|^pay_item|^_jt_btn_label|^invoice_keyboard|"
    r"^referral_keyboard|^phone_keyboard|^link_changed_check|^_parse_num|^_fa2en|^_pick_label|^_mode_label|"
    r"^_plabel|^st$|^num$|^line$|^cooldown_text|^_art_line|^_progress_line|^_back_gm|^casino_day_block|"
    r"^zp_callback_page|^_fmt_wait|^_dice_block",
    re.I)
_EXCL_LINES = {
    "bot_test.py": [(1, 4), (45, 52), (75, 95), (205, 210), (1715, 1722), (1744, 1762), (1996, 1999), (1363, 1363), (1548, 1548), (3470, 3480), (5033, 5041), (1890, 1894), (2415, 2440),
                    (4235, 4246), (4300, 4310), (4795, 4800), (5310, 5320), (5545, 5560), (5705, 5712),
                    (6550, 6556), (6710, 6730)],
    "games.py": [(1, 3), (30, 35), (50, 62), (240, 250), (535, 540), (560, 568), (1222, 1228), (1925, 1945),
                 (2020, 2030), (2360, 2368), (3078, 3078), (2765, 2785)],
}
_CALL_SKIP = {"info", "warning", "error", "exception", "debug", "print", "Exception", "ValueError", "RuntimeError",
              "btn", "btn_inline", "_ab", "_kb", "re", "compile", "match", "fullmatch", "search", "sub",
              "startswith", "endswith", "set_state", "get", "execute", "ok", "_h", "OperationalError",
              "get_setting", "set_setting", "sbool", "sjson", "setdefault", "split", "join", "replace", "strip"}


def _tmpl(n):
    """(قالب، [عبارت‌ها]) — {1} {2} … برای مقدارهای f-string"""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value, []
    if isinstance(n, ast.JoinedStr):
        t = ""
        ex = []
        for v in n.values:
            if isinstance(v, ast.Constant):
                t += str(v.value)
            elif isinstance(v, ast.FormattedValue):
                ex.append(ast.unparse(v.value))
                t += "{%d}" % len(ex)
            else:
                return None
        return t, ex
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        a = _tmpl(n.left)
        b = _tmpl(n.right)
        if a is None or b is None:
            return None
        off = len(a[1])
        bt = re.sub(r"\{(\d+)\}", lambda m: "{%d}" % (int(m.group(1)) + off), b[0])
        return a[0] + bt, a[1] + b[1]
    return None


def _scan(path, fname):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    out = []
    fa_lines = []
    for a, b in _EXCL_LINES.get(fname, []):
        fa_lines.append((a, b))

    def line_excluded(ln):
        return any(a <= ln <= b for a, b in fa_lines)

    class V(ast.NodeVisitor):
        def __init__(s):
            s.fn = []

        def visit_FunctionDef(s, n):
            s.fn.append(n.name)
            body = n.body
            doc = body[0] if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) else None
            for st in body:
                if st is not doc:
                    s.visit(st)
            s.fn.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Expr(s, n):  # رشته‌ی تنها (docstring/کامنت) نه
            if isinstance(n.value, ast.Constant):
                return
            s.generic_visit(n)

        def root(s, n):
            t = _tmpl(n)
            if t is None:
                return
            tpl, ex = t
            fn = s.fn[-1] if s.fn else "<mod>"
            if _EXCL_FN.search(fn) or line_excluded(n.lineno) or not _FA.search(tpl):
                return
            lit = _PH.sub("", tpl)
            if len(lit.strip()) < 12 or len(_FA.findall(lit)) < 5:
                return
            if fn == "<mod>" and len(lit) < 30:
                return
            if _edge_unsafe(tpl):
                return
            out.append((fn, n.lineno, tpl, ex))

        def visit_Call(s, n):
            f = n.func.id if isinstance(n.func, ast.Name) else (n.func.attr if isinstance(n.func, ast.Attribute) else "")
            if f in _CALL_SKIP:
                return
            s.generic_visit(n)

        def visit_Raise(s, n):
            return

        def visit_Compare(s, n):
            return

        def visit_Subscript(s, n):
            s.visit(n.value)

        def visit_Dict(s, n):
            ks = {k.value for k in n.keys if isinstance(k, ast.Constant)}
            if ks & {"callback_data", "url", "web_app", "switch_inline_query", "request_contact"}:
                return  # دکمه
            for v in n.values:
                if v is not None:
                    s.visit(v)

        def visit_Constant(s, n):
            if isinstance(n.value, str):
                s.root(n)

        def visit_JoinedStr(s, n):
            s.root(n)

        def visit_BinOp(s, n):
            if isinstance(n.op, ast.Add) and _tmpl(n) is not None:
                s.root(n)
            else:
                s.generic_visit(n)

    V().visit(tree)
    return out


# ---------------- گروه‌بندی ----------------
_GROUPS = [
    ("🎗 JFJ (درخواست و شروع)", r"jfj|member_left|relink|refresh_request|found|handle_jfj|send_jfj"),
    ("👥 زیرمجموعه‌گیری", r"referral"),
    ("🆔 حساب من", r"account"),
    ("🛍 خرید شاهی و پرداخت", r"^pay_|invoice|^dc_|^zp_|apply_paid|_price_lines|handle_pay|start_jtoken|handle_dc|handle_zp"),
    ("⭐️ خرید ممبر و سین", r"react|svc|premium|services|^start_services"),
    ("🎗 اسپانسری", r"sponsor|sps"),
    ("🏦 بانک انتقال", r"bank"),
    ("🔍 سفارش من", r"send_orders"),
    ("☎️ پشتیبانی", r"support"),
    ("🔐 ورود و جوین اجباری", r"phone|contact|^fj_|gate|handle_fj|_fj_"),
    ("❌⭕ دوز شاهنشاهی", r"xo"),
    ("🪨 سنگ کاغذ قیچی", r"rps"),
    ("🎰 گردونه و تاس", r"slot|dice|result_text|casino_day|send_view"),
    ("💸 انتقال شاهی", r"xfer|transfer"),
    ("🏰 پروفایل و لیدربرد", r"profile|_lb_|_cb_lb"),
    ("🎃 هیولا", r"mon|_cb_mon"),
    ("🃏 بازی‌های گروهی", r"games|casino|_cb_|_on_|_menu_text|make_table|_cool_msg|on_callback|_rep_|join"),
]
_MOD_GROUP = {"bot_test.py": "📚 متن‌های ثابت (خوش‌آمد، راهنما، قوانین، خدمات)", "games.py": "🎃 هیولا و متن‌های ثابت بازی‌ها"}
_OTHER = "📦 سایر متن‌ها"


def _group(fn, fname):
    if fn == "<mod>":
        return _MOD_GROUP[fname]
    for g, rx in _GROUPS:
        if re.search(rx, fn):
            return g
    return _OTHER


# ---------------- کاتالوگ ----------------
_lock = threading.Lock()
_cat = None            # {key: item}
_order = []            # لیست کلیدها به ترتیب نمایش
_ov = {}               # key -> html
_rx = []               # [(item, compiled)] فقط ورودی‌های ویرایش‌شده


def _key(tpl):
    return hashlib.sha1(tpl.encode("utf-8")).hexdigest()[:8]


def _build():
    global _cat, _order
    here = os.path.dirname(os.path.abspath(__file__))
    cat = {}
    for fname in ("bot_test.py", "games.py"):
        p = os.path.join(here, fname)
        if not os.path.exists(p):
            continue
        for fn, ln, tpl, ex in _scan(p, fname):
            k = _key(tpl)
            it = cat.get(k)
            if it is None:
                cat[k] = it = {"key": k, "tpl": tpl, "ex": ex, "fns": [], "group": _group(fn, fname), "line": ln, "file": fname}
            if fn not in it["fns"]:
                it["fns"].append(fn)
    # لیبل‌های نام‌دار: {qty} و مانند آن
    items = list(cat.values())
    gorder = [g for g, _ in _GROUPS] + list(_MOD_GROUP.values()) + [_OTHER]
    items.sort(key=lambda i: (gorder.index(i["group"]) if i["group"] in gorder else 99, i["file"], i["line"]))
    for n, it in enumerate(items, 1):
        it["n"] = n
    _cat = {i["key"]: i for i in items}
    _order = [i["key"] for i in items]


def catalog():
    if _cat is None:
        with _lock:
            if _cat is None:
                _build()
    return _cat


def groups():
    catalog()
    g = {}
    for k in _order:
        g.setdefault(_cat[k]["group"], []).append(k)
    return g


def _regex(tpl):
    """قالب -> regex تطبیق روی متن نهایی"""
    parts = []
    pos = 0
    seen = {}
    ms = list(_PH.finditer(tpl))
    for i, m in enumerate(ms):
        parts.append(re.escape(tpl[pos:m.start()]))
        name = m.group(1)
        edge = (m.start() == 0 or m.end() == len(tpl))
        if name in seen:
            parts.append("(?P=g%s)" % seen[name])
        else:
            gid = "%d" % (len(seen) + 1)
            seen[name] = gid
            parts.append("(?P<g%s>%s)" % (gid, "[^\\n]*?" if edge else ".*?"))
        pos = m.end()
    parts.append(re.escape(tpl[pos:]))
    return re.compile("".join(parts), re.S), list(seen)


def _edge_unsafe(tpl):
    lit = _PH.sub("", tpl)
    if (tpl.startswith("{") or tpl.rstrip().endswith("}")) and len(lit.strip()) < 25:
        return True
    return False


def _rebuild_rx():
    global _rx
    rx = []
    cat = catalog()
    for k, h in _ov.items():
        it = cat.get(k)
        if not it or _edge_unsafe(it["tpl"]):
            continue
        try:
            c, names = _regex(it["tpl"])
        except re.error:
            continue
        rx.append((len(_PH.sub("", it["tpl"])), it, c, names, h))
    rx.sort(key=lambda x: -x[0])  # طولانی‌ترین اول
    _rx = rx


# ---------------- ذخیره‌ی ویرایش‌ها ----------------
def init(bot_module):
    global B
    B = bot_module
    reload()


def reload():
    global _ov
    ov = {}
    try:
        with B.get_db() as c:
            for r in c.execute("SELECT key, html FROM text_overrides").fetchall():
                ov[r[0]] = r[1]
    except Exception:
        logging.exception("texts.reload")
    _ov = ov
    _rebuild_rx()


def set_override(key, html):
    with B.get_db() as c:
        c.execute("INSERT INTO text_overrides (key, html, updated_at) VALUES (?,?,?) "
                  "ON CONFLICT (key) DO UPDATE SET html=excluded.html, updated_at=excluded.updated_at",
                  (key, html, int(time.time())))
    reload()


def del_override(key):
    with B.get_db() as c:
        c.execute("DELETE FROM text_overrides WHERE key=?", (key,))
    reload()


def overrides_count():
    return len(_ov)


# ---------------- entity -> HTML ----------------
def _u16(s):
    return s.encode("utf-16-le")


def entities_to_html(text, entities):
    """متن + entityهای تلگرام (offset بر پایه‌ی UTF-16) -> HTML تلگرام؛ همه‌ی قالب‌ها حفظ می‌شود"""
    raw = _u16(text)
    n = len(raw) // 2
    ents = []
    for e in entities or []:
        t = e.get("type")
        if t in ("bold", "italic", "underline", "strikethrough", "spoiler", "code", "pre", "text_link",
                 "blockquote", "expandable_blockquote", "custom_emoji", "text_mention"):
            o, l = int(e["offset"]), int(e["length"])
            if l > 0 and o >= 0 and o + l <= n:
                ents.append((o, o + l, e))
    ents.sort(key=lambda x: (x[0], -x[1]))

    def seg(a, b):
        return raw[a * 2:b * 2].decode("utf-16-le", "replace")

    def tags(e):
        t = e["type"]
        if t == "bold":
            return "<b>", "</b>"
        if t == "italic":
            return "<i>", "</i>"
        if t == "underline":
            return "<u>", "</u>"
        if t == "strikethrough":
            return "<s>", "</s>"
        if t == "spoiler":
            return "<tg-spoiler>", "</tg-spoiler>"
        if t == "code":
            return "<code>", "</code>"
        if t == "pre":
            lang = e.get("language")
            if lang:
                return '<pre><code class="language-%s">' % _h.escape(lang), "</code></pre>"
            return "<pre>", "</pre>"
        if t == "text_link":
            return '<a href="%s">' % _h.escape(e.get("url", ""), quote=True), "</a>"
        if t == "text_mention":
            return '<a href="tg://user?id=%s">' % int(e.get("user", {}).get("id", 0)), "</a>"
        if t == "blockquote":
            return "<blockquote>", "</blockquote>"
        if t == "expandable_blockquote":
            return "<blockquote expandable>", "</blockquote>"
        return "", ""

    def render(a, b, lst):
        out = []
        pos = a
        i = 0
        while i < len(lst):
            s, e_, e = lst[i]
            if s < pos:       # هم‌پوشانیِ ناقص: نادیده
                i += 1
                continue
            out.append(_h.escape(seg(pos, s), quote=False))
            inner = []
            j = i + 1
            while j < len(lst) and lst[j][0] < e_:
                inner.append((lst[j][0], min(lst[j][1], e_), lst[j][2]))
                j += 1
            if e["type"] == "custom_emoji":
                out.append('<tg-emoji emoji-id="%s">%s</tg-emoji>' % (_h.escape(str(e.get("custom_emoji_id", ""))),
                                                                       _h.escape(seg(s, e_), quote=False)))
            else:
                o, c = tags(e)
                out.append(o + render(s, e_, inner) + c)
            pos = e_
            i = j
        out.append(_h.escape(seg(pos, b), quote=False))
        return "".join(out)

    return render(0, n, ents)


def message_to_html(message):
    """پیام ادمین -> HTML. اگر ادمین فرمت‌دهیِ تلگرام نزده و Markdown تایپ کرده باشد (*bold* _italic_ `code` [متن](لینک)) همان تبدیل می‌شود."""
    text = message.get("text") or message.get("caption") or ""
    ents = message.get("entities") or message.get("caption_entities") or []
    if ents:
        return entities_to_html(text, ents)
    return B._md_to_html(text)


# ---------------- اعمال روی ارسال ----------------
_TAG = re.compile(r"<[^>]+>")


def _to_plain(h):
    return _h.unescape(_TAG.sub("", h))


def _fill(html, groups_by_name, pm):
    """{n} در متن ویرایش‌شده را با مقدارهای واقعی جایگزین می‌کند"""
    def conv(v):
        if v is None:
            return ""
        if pm == "HTML":
            return v
        if pm in ("Markdown", "MarkdownV2"):
            return B._md_to_html(v)
        return _h.escape(v, quote=False)

    def sub(m):
        nm = m.group(1)
        if nm in groups_by_name:
            return conv(groups_by_name[nm])
        return m.group(0)
    return _PH.sub(sub, html)


def apply(method, params):
    """اگر متن این ارسال شامل مورد ویرایش‌شده‌ای باشد، params جدید (HTML) برمی‌گرداند؛ وگرنه None"""
    if not _rx:
        return None
    if method == "answerCallbackQuery":
        key = "text"
    elif method in ("sendMessage", "editMessageText"):
        key = "text"
    elif method in ("sendPhoto", "sendDocument", "editMessageCaption", "sendVideo", "sendAnimation"):
        key = "caption"
    else:
        return None
    t = params.get(key)
    if not isinstance(t, str) or not t:
        return None
    spans = []   # (start, end, html_filled)
    for _, it, c, names, h in _rx:
        for m in c.finditer(t):
            if m.end() == m.start():
                continue
            if any(not (m.end() <= s or m.start() >= e) for s, e, _ in spans):
                continue
            gb = {nm: m.group("g%d" % (i + 1)) for i, nm in enumerate(names)}
            spans.append((m.start(), m.end(), (h, gb)))
    if not spans:
        return None
    spans.sort()
    pm = params.get("parse_mode")
    q = dict(params)
    if method == "answerCallbackQuery":
        buf = []
        pos = 0
        for s, e, (h, gb) in spans:
            buf.append(t[pos:s])
            buf.append(_to_plain(_fill(h, gb, pm if pm else None)))
            pos = e
        buf.append(t[pos:])
        q[key] = "".join(buf)[:200]
        return q
    raw = []
    pos = 0
    fills = []
    for n, (s, e, (h, gb)) in enumerate(spans):
        raw.append(t[pos:s])
        raw.append(_TOK % n)
        fills.append(_fill(h, gb, pm))
        pos = e
    raw.append(t[pos:])
    base = "".join(raw)
    if pm == "HTML":
        body = base
    elif pm in ("Markdown", "MarkdownV2"):
        body = B._md_to_html(base)
    else:
        body = _h.escape(base, quote=False)
    body = B._mono_ids(body)
    html = "<b>" + body + "</b>"
    html = _TOK_RE.sub(lambda m: "</b>" + fills[int(m.group(1))] + "<b>", html)
    html = html.replace("<b></b>", "")
    q[key] = html
    q["parse_mode"] = "HTML"
    return q


# ---------------- رابط ادمین (Reply Keyboard) ----------------
BTN = "🖌 تنظیمات متون"
PAGE = 12
_FA_D = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_TO_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(n):
    return str(n).translate(_TO_FA)


def _kbd(rows):
    return {"keyboard": [[B.btn(x) for x in r] for r in rows], "resize_keyboard": True, "is_persistent": False}


def _snip(tpl, n=28):
    s = _PH.sub("…", re.sub(r"[*_`<>\[\]]|</?\w+[^>]*>", "", tpl))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"


def _preview_html(tpl):
    """نمایش قالب پیش‌فرض (با {n} به‌صورت متن ساده) به‌همان قالب‌بندیِ اصلی"""
    if re.search(r"</?(?:b|i|u|s|a|code|pre|tg-spoiler|blockquote|tg-emoji)\b", tpl):
        return tpl
    return B._md_to_html(tpl)


def _hsend(chat_id, html, kb=None):
    p = {"chat_id": chat_id, "text": html, "parse_mode": "HTML", "disable_web_page_preview": True, "_notx": True}
    if kb:
        p["reply_markup"] = kb
    return B.tg("sendMessage", **p)


def open_root(chat_id, admin_id, note=None):
    gs = groups()
    B.set_state(admin_id, "tx", {"v": "root"})
    rows = []
    cur = []
    for g, keys in gs.items():
        cur.append("%s (%s)" % (g, _fa(len(keys))))
        if len(cur) == 2:
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    rows.append(["♻️ بازنشانی همه‌ی ویرایش‌ها", B.BACK_BTN])
    head = ("🖌 <b>تنظیمات متون ربات</b>\n" + B.LINE + "\n"
            "همه‌ی متن‌های ربات (به‌جز متن‌های ادمین) اینجا قابل ویرایش‌اند.\n\n"
            "📂 یک بخش را از منوی پایین انتخاب کن، بعد متن مورد نظر را بزن تا با جزئیات نمایش داده شود.\n"
            "✍️ متن جدید را با <b>بولد، کج‌نویس، لینک، اسپویلر، کد و ایموجی پرمیوم</b> همان‌طور که می‌خواهی بفرست؛ ربات دقیقاً همان را ارسال می‌کند.\n\n"
            "✏️ ویرایش‌شده تا الان: <b>%s</b> مورد" % _fa(overrides_count()))
    if note:
        head = note + "\n\n" + head
    _hsend(chat_id, head, _kbd(rows))


def open_group(chat_id, admin_id, gname, page=0):
    gs = groups()
    keys = gs.get(gname, [])
    tot = max(1, (len(keys) + PAGE - 1) // PAGE)
    page = max(0, min(page, tot - 1))
    B.set_state(admin_id, "tx", {"v": "group", "g": gname, "p": page})
    rows = []
    for k in keys[page * PAGE:(page + 1) * PAGE]:
        it = _cat[k]
        mark = "✏️" if k in _ov else "▫️"
        rows.append(["%s %s ‹ %s" % (mark, _fa(it["n"]), _snip(it["tpl"]))])
    nav = []
    if page > 0:
        nav.append("◀️ صفحه‌ی قبل")
    if page < tot - 1:
        nav.append("صفحه‌ی بعد ▶️")
    if nav:
        rows.append(nav)
    rows.append(["🔙 فهرست بخش‌ها"])
    ed = sum(1 for k in keys if k in _ov)
    _hsend(chat_id, "%s\n%s\n📄 صفحه‌ی <b>%s</b> از <b>%s</b> • %s متن • ✏️ ویرایش‌شده: <b>%s</b>\n\n"
                    "👇 یکی از متن‌ها را انتخاب کن." % (_h.escape(gname), B.LINE, _fa(page + 1), _fa(tot), _fa(len(keys)), _fa(ed)),
           _kbd(rows))


def _where(it):
    fns = it["fns"][:3]
    return "، ".join(fns) + ("…" if len(it["fns"]) > 3 else "")


def open_item(chat_id, admin_id, key, back=None):
    it = catalog().get(key)
    if not it:
        _hsend(chat_id, "❗️ این متن پیدا نشد.")
        return
    st, data = B.get_state(admin_id)
    B.set_state(admin_id, "tx", {"v": "item", "k": key, "g": it["group"], "p": (data or {}).get("p", 0)})
    edited = key in _ov
    ph = ""
    if _PH.search(it["tpl"]):
        names = []
        seen = set()
        for m in _PH.finditer(it["tpl"]):
            nm = m.group(1)
            if nm in seen:
                continue
            seen.add(nm)
            if nm.isdigit() and int(nm) - 1 < len(it["ex"]):
                names.append("<code>{%s}</code> = <code>%s</code>" % (nm, _h.escape(it["ex"][int(nm) - 1][:50])))
            else:
                names.append("<code>{%s}</code>" % nm)
        ph = ("\n\n🔣 <b>جاهای متغیر</b> (مقدار واقعی را ربات خودش می‌گذارد؛ در متن جدید همین‌ها را بنویس تا جایشان بماند):\n"
              + "\n".join("• " + x for x in names))
    head = ("🧾 <b>متن شماره‌ی %s</b>%s\n%s\n📂 بخش: <b>%s</b>\n🧩 محل استفاده: <code>%s</code>%s\n\n"
            "👇 متن %s:" % (_fa(it["n"]), " ✏️ <i>(ویرایش‌شده)</i>" if edited else "", B.LINE, _h.escape(it["group"]),
                          _h.escape(_where(it)), ph, "فعلی (ویرایش‌شده)" if edited else "پیش‌فرض"))
    _hsend(chat_id, head)
    body = _ov[key] if edited else _preview_html(it["tpl"])
    r = B.tg("sendMessage", chat_id=chat_id, text=body, parse_mode="HTML", disable_web_page_preview=True, _notx=True)
    if not r.get("ok"):
        B.tg("sendMessage", chat_id=chat_id, text=it["tpl"], disable_web_page_preview=True, _notx=True)
    rows = [["✏️ ویرایش این متن"]]
    if edited:
        rows.append(["♻️ بازگشت به پیش‌فرض", "👁 دیدن متن پیش‌فرض"])
    rows.append(["🔙 فهرست این بخش"])
    _hsend(chat_id, "💡 <i>برای ویرایش: می‌توانی همین متن بالا را کپی کنی، تغییر بدهی و بفرستی؛ یا از صفر بنویسی.</i>", _kbd(rows))


def _need_edit(chat_id, admin_id, key):
    it = _cat[key]
    st, data = B.get_state(admin_id)
    B.set_state(admin_id, "tx_edit", {"k": key, "g": it["group"], "p": (data or {}).get("p", 0)})
    ph = ""
    if _PH.search(it["tpl"]):
        ph = "\n🔣 جاهای متغیر (مثل <code>{1}</code>) را در متنت نگه دار."
    _hsend(chat_id, "✍️ <b>متن جدید را بفرست</b>\n%s\nهر قالب‌بندی (بولد، کج، لینک، اسپویلر، کد، ایموجی پرمیوم و …) دقیقاً همان‌طور اعمال می‌شود. "
                    "اگر قالب‌بندی تلگرام نزنی و Markdown تایپ کنی (<code>*بولد*</code> یا <code>_کج_</code>) آن هم اعمال می‌شود.%s\n\n"
                    "⚠️ بخش‌هایی که قالب‌بندی ندارند همان‌طور ساده (بدون بولد) ارسال می‌شوند." % (B.LINE, ph),
           _kbd([["❌ انصراف از ویرایش"]]))


def _validate(html, it):
    r = _PH.findall(html)
    return r


def handle(message, state, data):
    """True اگر پیام مربوط به این بخش بوده و مصرف شد"""
    chat_id = message["chat"]["id"]
    admin_id = message["from"]["id"]
    text = (message.get("text") or "").strip()
    cat = catalog()
    if state == "tx_edit":
        key = data.get("k")
        if text == "❌ انصراف از ویرایش":
            open_item(chat_id, admin_id, key)
            return True
        if text == B.BACK_BTN:
            B.start_admin_panel(chat_id, admin_id)
            return True
        if not (message.get("text") or message.get("caption")):
            _hsend(chat_id, "❗️ فقط متن بفرست (می‌تواند فرمت‌دار باشد).")
            return True
        it = cat.get(key)
        if not it:
            open_root(chat_id, admin_id)
            return True
        h = message_to_html(message)
        if not h.strip():
            _hsend(chat_id, "❗️ متن خالی است.")
            return True
        if len(h) > 3800:
            _hsend(chat_id, "❗️ متن خیلی بلند است (حداکثر حدود ۳۸۰۰ نویسه با تگ‌ها).")
            return True
        # آزمایش پذیرفته‌شدن توسط تلگرام (پیش‌نمایش واقعی)
        r = B.tg("sendMessage", chat_id=chat_id, text=h, parse_mode="HTML", disable_web_page_preview=True, _notx=True)
        if not r.get("ok"):
            _hsend(chat_id, "❗️ تلگرام این متن را نپذیرفت؛ (%s)\nدوباره بفرست." % _h.escape(str(r.get("description", ""))[:120]))
            return True
        set_override(key, h)
        open_item(chat_id, admin_id, key)
        _hsend(chat_id, "✅ ذخیره شد؛ از همین لحظه ربات این متن را ارسال می‌کند. (بالا همان پیش‌نمایش واقعی است)")
        return True
    # state == tx
    v = data.get("v", "root")
    if text == B.BACK_BTN:
        B.start_admin_panel(chat_id, admin_id)
        return True
    if text == "🔙 فهرست بخش‌ها":
        open_root(chat_id, admin_id)
        return True
    if text == "🔙 فهرست این بخش":
        open_group(chat_id, admin_id, data.get("g"), data.get("p", 0))
        return True
    if text == "♻️ بازنشانی همه‌ی ویرایش‌ها":
        B.set_state(admin_id, "tx", {"v": "reset_all"})
        _hsend(chat_id, "⚠️ همه‌ی %s ویرایش حذف و متن‌ها به پیش‌فرض برمی‌گردد. مطمئنی؟" % _fa(overrides_count()),
               _kbd([["✅ بله، همه را بازنشانی کن"], ["🔙 فهرست بخش‌ها"]]))
        return True
    if text == "✅ بله، همه را بازنشانی کن" and v == "reset_all":
        for k in list(_ov):
            del_override(k)
        open_root(chat_id, admin_id, "✅ همه‌ی متن‌ها به پیش‌فرض برگشت.")
        return True
    if text in ("◀️ صفحه‌ی قبل", "صفحه‌ی بعد ▶️") and data.get("g"):
        p = data.get("p", 0) + (-1 if text.startswith("◀") else 1)
        open_group(chat_id, admin_id, data["g"], p)
        return True
    m = re.match(r"^(.+?) \(([\d۰-۹]+)\)$", text)
    if m:
        for g in groups():
            if g == m.group(1):
                open_group(chat_id, admin_id, g, 0)
                return True
    m = re.match(r"^[✏️▫️]+\s*([\d۰-۹]+)\s*‹", text)
    if m:
        n = int(m.group(1).translate(_FA_D))
        for k, it in cat.items():
            if it["n"] == n:
                open_item(chat_id, admin_id, k)
                return True
    key = data.get("k")
    if v == "item" and key in cat:
        if text == "✏️ ویرایش این متن":
            _need_edit(chat_id, admin_id, key)
            return True
        if text == "♻️ بازگشت به پیش‌فرض":
            del_override(key)
            open_item(chat_id, admin_id, key)
            _hsend(chat_id, "♻️ به متن پیش‌فرض برگشت.")
            return True
        if text == "👁 دیدن متن پیش‌فرض":
            _hsend(chat_id, "👁 <b>متن پیش‌فرض:</b>")
            B.tg("sendMessage", chat_id=chat_id, text=_preview_html(cat[key]["tpl"]), parse_mode="HTML", _notx=True)
            return True
    open_root(chat_id, admin_id) if v == "root" else _hsend(chat_id, "از دکمه‌های منوی پایین استفاده کن 👇")
    return True
