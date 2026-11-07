"""ایموجی پرمیوم برای «متن پیام‌های» ربات (Bot API: <tg-emoji emoji-id="…">😀</tg-emoji>)

طرز کار:
  • پیام‌ها همان متن معمولی با ایموجی معمولی‌اند (نسخه‌ی بدون پرمیوم). درست قبل از ارسال، اگر حالت فعال باشد،
    ایموجی ابتدای هر خط که متن آن خط در فهرست قانون‌ها باشد با نسخه‌ی پرمیوم‌اش عوض می‌شود
    (مثل «💎 شاهی چیه…» ← آیدی 5825623013852192219)؛ ایموجی معمولی داخل <tg-emoji> می‌ماند
    تا اگر پرمیوم نمایش داده نشد، همان ایموجی معمولی دیده شود.
  • قانون‌ها «اسکلت متن خط» ← آیدی هستند. اگر یک متن در چند پیام ایموجی متفاوت دارد، شرط پیام
    با «@@» می‌آید:  «لینک:@@درخواست JFJ پیدا شد».
  • چند ایموجی خاص (⚠️ ❗️ ‼️ 🛑 ✅ ❌ 💎 ◁) در هر جای متن (حتی وسط خط) هم عوض می‌شوند.
  • حالت‌ها: خودکار / روشن / خاموش (تنظیم premium_emoji_msg). اگر تلگرام پیامِ دارای ایموجی پرمیوم را رد کند،
    همان پیام بدون آن ارسال می‌شود؛ در حالت «خودکار» تا ۶ ساعت خاموش می‌ماند و بعد دوباره امتحان می‌کند.
  • داخل <code> و <pre> هرگز تغییری داده نمی‌شود.
"""
import html as _html
import json
import logging
import re
import threading
import time

RETRY_AFTER = 6 * 3600
MAX_EMOJI = 100

WARN = "5893125726353236397"
CHK = "5830144944399981619"
CROSS = "5819154526816444042"
GEM = "5825623013852192219"
CLOCK = "5906896396526560494"
CODE = "5823239319887815835"
USER = "5843973755545590553"
WALLET = "5886285995229323603"
DOC = "5888937012253171131"
WAIT = "5825656411517886523"
N1, N2, N3, N4, N5, N6, N7 = ("5193091523629037038", "5193097682612140985", "5192991596919930332", "5195073127050129140",
                              "5192763753199843285", "5192724424184316515", "5192777969541594503")

# اسکلت متن خط ← آیدی  (کلید «متن@@شرط» یعنی فقط وقتی «شرط» در کل پیام باشد)
DEFAULT_RULES = {
    # --- خوش‌آمدگویی و راهنما ---
    "به جفج شاهنشاهی خوش آمدی": "5461151367559141950",
    "من برات چکار انجام میدم": "5314589624377554054",
    "همین الان شروع JFJ": "5928998611764387949",
    "راهنمای استفاده از ربات": "5819051035284479206",
    "ربات جفج شاهنشاهی چه کاری انجام": "5911319564301376749",
    "جفج و JFJ چی هست": "5884362854903064294",
    "شاهی چیه و چه کاربردی": GEM,
    "چطور JFJ بریم": "5911198059676574025",
    "جمع‌آوری شاهی برای جفج": N1,
    "درخواست کانال-گروه خودت": N2,
    "نکات مهم و قوانین": WARN,
    "ممبر واقعی:": N1,
    "تأیید عضویت:": N2,
    "قانون لفت دادن:": N3,
    "عدم خروج زودهنگام:": N4,
    "ثبت صحیح مقصد:": N5,
    "رعایت قوانین تلگرام:": N6,
    "عدم سوءاستفاده:": N7,
    "با کمک همدیگه رشد می‌کنیم": "5832433801191498078",
    # --- قوانین ---
    "قوانین استفاده از ربات": "5818716826699307883",
    "کاربران می‌توانند خارج از ربات": N1,
    "تا زمان تکمیل شدن سفارش": N2,
    "پس از خرید اشتراک": N3,
    # --- حساب من و زیرمجموعه‌گیری ---
    "نام کاربر:": USER,
    "ایدی عددی:": "5908942862543756657",
    "آیدی عددی:": "5908942862543756657",
    "موجودی:": WALLET,
    "زیرمجموعه‌گیری:": "5816404884458577332",
    "زمان:": CLOCK,
    "لینک زیرمجموعه‌گیری اختصاصی": "5816404884458577332",
    "با ارسال لینک بالا": "5823592920250327036",
    # --- شروع JFJ و درخواست JFJ ---
    "به بخش JFJ رفتن": "5818866927216369505",
    "در این بخش با جوین شدن": GEM,
    "دارم برات درخواست JFJ پیدا": WAIT,
    "تعداد ممبر مورد نیاز": "5819151717907832367",
    "1 member": USER,
    "موجودی شما:": "5859667780793539624",
    "لطفا از منوی زیر": "5820903824046432799",
    "لینک کانال یا گروه مورد نظرتونو": "5832335747088130009",
    "حتما قبل از ارسال لینکتون": WARN,
    "کانال شما اکنون": "5819046718842347822",
    "درخواست JFJ شما #ثبت شد": DOC,
    "کد پیگیری:": CODE,
    "زمان ثبت:": CLOCK,
    "درخواست JFJ پیدا شد": CODE,
    "لینک:@@درخواست JFJ پیدا شد": "5889002570633977838",
    # --- بانک و خرید شاهی ---
    "میخوای چند شاهی انتقال بدی": GEM,
    "خرید شاهی": GEM,
    "فاکتور": DOC,
    "مبلغ قابل پرداخت:": WALLET,
    "مبلغ:": WALLET,
    "کد پیگیری فاکتور:": CODE,
    "زمان صدور فاکتور:": CLOCK,
    "شماره کارت:": "5888625992196431593",
    "به نام:": USER,
    "نکته مهم:": WARN,
    "این مبلغ مخصوص": N1,
    "این تراکنش به مدت": N2,
    "لطفا پس از واریزتون": "5819051035284479206",
    "تأیید خرید": DOC,
    "محصول:@@تأیید خرید": "5909146585727509820",
    "قیمت:": "5859667780793539624",
    "رسید شما برای فاکتور": CROSS,
    "زمان بررسی:": CLOCK,
    "در صورت اشتباه بودن": "5465169893580086142",
    "رسید شما دریافت شد": CHK,
    "کد فاکتور:": CODE,
    "زمان دریافت رسید:": CLOCK,
    "زمان دریافت:": CLOCK,
    "زمان تأیید:": CLOCK,
    "بعد از بررسی ادمین": WAIT,
    "زمان ثبت پرداخت:": CLOCK,
    "رسید واریزی را ارسال کنید": "5854818638162304218",
    # --- سفارش من ---
    "وضعیت درخواست های JFJ اخیر شما": DOC,
    "وضعیت: درحال انجام": WAIT,
    "وضعیت: در حال انجام": WAIT,
    "وضعیت: ربات عزل شد": "5818716826699307883",
    "وضعیت: تکمیل شده": CHK,
    "وضعیت: لغو شده": CROSS,
    "تعداد ممبر درخواستی:": USER,
    "لینک:@@کد پیگیری": "5825460599663894403",
    "سفارش‌های خرید محصولات شما": "5909146585727509820",
    "محصول:@@کد پیگیری": "5927029738626359516",
    "تعداد:": "5911198059676574025",
    # --- جوین اجباری و لفت ---
    "خوش اومدی گلم": "5409109841538994759",
    "به دلیل لفت دادن شما": WARN,
    # --- بازی‌ها ---
    "برای پیوستن به میز": "5857454223368657979",
    # --- پشتیبانی ---
    "پشتیبانی": "5465169893580086142",
    "لطفا موضوع و توضیحات": WARN,
    "وضعیت ››› بازنده": "5872823922751185495",
}

# ایموجی ← آیدی: در هر جای متن (حتی وسط خط) جایگزین می‌شوند
GLOBAL_EMOJI = {
    "⚠": WARN, "❗": WARN, "‼": WARN, "🛑": WARN,
    "💎": GEM, "✅": CHK, "❌": CROSS, "◁": "5823664135103061930",
    "🎯": "5832335747088130009", "🥇": "5832692422647226240", "🥈": "5834620746999012948", "🥉": "5832346686369832003",
    "🏅": "5836866392124563486", "🎖": "5845858434439716957", "🏆": "5818913299978263825", "🎲": "5875483791702630534",
    "🃏": "5875308385238262342", "🏦": WALLET, "📄": "5882230558259420962", "✂": "5881796225396645401",
    "👑": "5837050654811496370", "🔍": CODE, "🏁": "5888594273862950655", "📋": "5911198059676574025",
    "👥": "5816404884458577332", "⤵": "5820903824046432799", "📊": "5298520596945070277", "🕹": "5852627620725792383",
    "🛎": "5883982896326254229", "🪪": "5843911663203392756", "🏰": "5857321629138297224", "🎭": "5879733124971111582",
    "⏰": CLOCK, "🎉": "5461151367559141950", "⁉": "5258344772778619330", "✨": "5818677197036069696",
    "🪨": "5882236803141868717", "🍇": "5337218351066266838", "🍋": "5219705713680463026", "⭕": "5857031396723269245",
}
DOOZ_X = "5857415006022278161"          # ❌ در پیام‌های دوز (خط نقش بازیکن و صفحه‌ی بازی)
KEYCAP7 = "5884468176091094657"         # 7️⃣ در کازینو
# ارقام «رتبه‌ی کاربران در لیدربرد» (رتبه ۶ › …  /  رتبه شما › ۱۲ام): هم ارقام انگلیسی هم فارسی
DIGIT_IDS = {"1": "5845974321247297274", "2": "5843861725618642819", "3": "5843973811380167207",
             "4": "5846158858812136854", "5": "5846159120805141727", "6": "5845716047683921674",
             "7": "5845766741182914502", "8": "5845685686560105154", "9": "5845753611467889699",
             "0": "5845994722341952716"}
_FA_TO_EN = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_RANK_RE = re.compile(r"(رتبه(?: شما)?(?: ›+)? ?)([0-9۰-۹]{1,6})(?![0-9۰-۹])")
_BOARD_ONLY = re.compile(r"^[❌⭕◻\uFE0E\uFE0F\u200c\s]+$")

_ID = re.compile(r"^\d{15,20}$")


def valid_id(x):
    return bool(_ID.match(str(x or "")))


# ---------------------------------------------------------------- ابزار متن
_TAG = re.compile(r"<[^>]*>")
_VS = "︎️"
_EMO1 = (r"(?:[0-9#*]️?⃣|"
         r"(?:[©®‼⁉™ℹ↔-↪⌚-⏿Ⓜ▪-◾☀-➿"
         r"⤴⤵⬅-⭕〰〽㊗㊙\U0001F000-\U0001FAFF][︎️]?"
         r"[\U0001F3FB-\U0001F3FF]?(?:‍[♀♂⚕-⚖✈❤\U0001F000-\U0001FAFF][︎️]?)*))")
_LEAD = re.compile(r"^((?:\s*<[^>/][^>]*>)*[ \t]*)(" + _EMO1 + r")")
_LINE_PLAIN_TRANS = str.maketrans({"ي": "ی", "ك": "ک", "‏": "", "‎": "", " ": " "})


# ایموجی‌های BMP (زیر U+1F000) که تلگرام زیر <tg-emoji> می‌پذیرد؛ نمادهای متنی مثل ◁ ● ★ ✓ مجاز نیستند
# (ENTITY_TEXT_INVALID می‌دهند و کل پیام رد می‌شود)
_BMP_EMOJI = set()
for _a, _b in ((0xA9, 0xA9), (0xAE, 0xAE), (0x203C, 0x203C), (0x2049, 0x2049), (0x2122, 0x2122), (0x2139, 0x2139),
               (0x2194, 0x2199), (0x21A9, 0x21AA), (0x231A, 0x231B), (0x2328, 0x2328), (0x23CF, 0x23CF),
               (0x23E9, 0x23F3), (0x23F8, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25AB), (0x25B6, 0x25B6),
               (0x25C0, 0x25C0), (0x25FB, 0x25FE), (0x2600, 0x2604), (0x260E, 0x260E), (0x2611, 0x2611),
               (0x2614, 0x2615), (0x2618, 0x2618), (0x261D, 0x261D), (0x2620, 0x2620), (0x2622, 0x2623),
               (0x2626, 0x2626), (0x262A, 0x262A), (0x262E, 0x262F), (0x2638, 0x263A), (0x2640, 0x2640),
               (0x2642, 0x2642), (0x2648, 0x2653), (0x265F, 0x2660), (0x2663, 0x2663), (0x2665, 0x2666),
               (0x2668, 0x2668), (0x267B, 0x267B), (0x267E, 0x267F), (0x2692, 0x2697), (0x2699, 0x2699),
               (0x269B, 0x269C), (0x26A0, 0x26A1), (0x26A7, 0x26A7), (0x26AA, 0x26AB), (0x26B0, 0x26B1),
               (0x26BD, 0x26BE), (0x26C4, 0x26C5), (0x26C8, 0x26C8), (0x26CE, 0x26CF), (0x26D1, 0x26D1),
               (0x26D3, 0x26D4), (0x26E9, 0x26EA), (0x26F0, 0x26F5), (0x26F7, 0x26FA), (0x26FD, 0x26FD),
               (0x2702, 0x2702), (0x2705, 0x2705), (0x2708, 0x270D), (0x270F, 0x270F), (0x2712, 0x2712),
               (0x2714, 0x2714), (0x2716, 0x2716), (0x271D, 0x271D), (0x2721, 0x2721), (0x2728, 0x2728),
               (0x2733, 0x2734), (0x2744, 0x2744), (0x2747, 0x2747), (0x274C, 0x274C), (0x274E, 0x274E),
               (0x2753, 0x2755), (0x2757, 0x2757), (0x2763, 0x2764), (0x2795, 0x2797), (0x27A1, 0x27A1),
               (0x27B0, 0x27B0), (0x27BF, 0x27BF), (0x2934, 0x2935), (0x2B05, 0x2B07), (0x2B1B, 0x2B1C),
               (0x2B50, 0x2B50), (0x2B55, 0x2B55), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3297),
               (0x3299, 0x3299)):
    _BMP_EMOJI.update(range(_a, _b + 1))
# نمادهای متنی پرکاربرد ← نزدیک‌ترین ایموجی واقعی (فقط برای متن داخل <tg-emoji>؛ اگر پرمیوم نمایش داده نشد دیده می‌شود)
_FALLBACK_GLYPH = {"◁": "◀\uFE0F", "▷": "▶\uFE0F", "◀": "◀\uFE0F", "▶": "▶\uFE0F"}


def safe_glyph(g):
    """متن مجاز برای داخل <tg-emoji> یا None اگر ایموجی واقعی نیست"""
    if not g:
        return None
    if re.match(r"[0-9#*]\uFE0F?\u20E3$", g):
        return g
    base = g[0]
    if base in _FALLBACK_GLYPH:
        return _FALLBACK_GLYPH[base]
    o = ord(base)
    if o >= 0x1F000:
        return g
    return g if o in _BMP_EMOJI else None


def norm(s):
    """متن بدون تگ/ستاره، یکدست‌شده برای مقایسه"""
    s = _html.unescape(_TAG.sub("", s or "")).translate(_LINE_PLAIN_TRANS)
    s = s.replace("*", "")
    s = re.sub(r"\s*[:：]\s*", ":", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def split_key(k):
    if "@@" in k:
        a, b = k.split("@@", 1)
        return norm(a), norm(b)
    return norm(k), ""


class PremMsg:
    def __init__(self, bot):
        self.bot = bot
        self._cache = (0.0, None)
        self._scache = (0.0, None)
        self._rules = None
        self._rkey = None

    # ---------- تنظیمات ----------
    def settings(self):
        t, v = self._cache
        if v is not None and time.time() - t < 20:
            return v
        mode = self.bot.get_setting("premium_emoji_msg", "auto") or "auto"
        if mode not in ("auto", "on", "off"):
            mode = "auto"
        rules = dict(DEFAULT_RULES)
        raw = self.bot.get_setting("premium_emoji_msg_map", "") or ""
        try:
            ov = json.loads(raw) if raw else {}
        except ValueError:
            ov = {}
        for k, v2 in (ov.items() if isinstance(ov, dict) else []):
            if v2 == "" or v2 is None:
                rules.pop(k, None)
            elif valid_id(v2):
                rules[k] = str(v2)
        self._cache = (time.time(), (mode, rules))
        return mode, rules

    def digits_on(self):
        """رقم رتبه‌ی لیدربرد پرمیوم شود؟ (تنظیم premium_emoji_msg_digits؛ پیش‌فرض روشن)"""
        t, v = getattr(self, "_dcache", (0.0, None))
        if v is not None and time.time() - t < 20:
            return v
        v = (self.bot.get_setting("premium_emoji_msg_digits", "1") or "1") != "0"
        self._dcache = (time.time(), v)
        return v

    def refresh(self):
        self._dcache = (0.0, None)
        self._cache = (0.0, None)
        self._scache = (0.0, None)
        self._rules = None

    def state(self):
        t, v = self._scache
        if v is not None and time.time() - t < 20:
            return v
        s = self.bot.get_setting("premium_emoji_msg_state", "") or ""
        try:
            kind, ts = s.split(":")
            v = (kind, float(ts))
        except Exception:
            v = ("", 0.0)
        self._scache = (time.time(), v)
        return v

    def active(self):
        mode, _ = self.settings()
        if mode == "off":
            return False
        if mode == "on":
            return True
        kind, ts = self.state()
        return not (kind == "fail" and time.time() - ts < RETRY_AFTER)

    def _compiled(self, rules):
        k = id(rules)
        if self._rules is None or self._rkey != k:
            lst = []
            for key, eid in rules.items():
                sk, ctx = split_key(key)
                if sk:
                    lst.append((bool(ctx), len(sk), sk, ctx, str(eid)))
            lst.sort(key=lambda x: (not x[0], -x[1]))
            self._rules, self._rkey = lst, k
        return self._rules

    # ---------- تبدیل ----------
    @staticmethod
    def _tg(eid, glyph):
        return f'<tg-emoji emoji-id="{eid}">{glyph}</tg-emoji>'

    def transform(self, h, rules=None, digits=True):
        """h = متن HTML ؛ خروجی: HTML با <tg-emoji>  (یا همان h اگر چیزی عوض نشد).
        digits=True یعنی رقم رتبه‌ی لیدربرد هم پرمیوم شود"""
        if not h or not isinstance(h, str):
            return h
        if rules is None:
            rules = self.settings()[1]
        comp = self._compiled(rules)
        whole = norm(h)
        lines = h.split("\n")
        depth = 0           # عمق <code>/<pre> در ابتدای هر خط
        out = []
        n = 0
        for line in lines:
            start_depth = depth
            depth += len(re.findall(r"<(?:code|pre)\b", line)) - len(re.findall(r"</(?:code|pre)>", line))
            if start_depth > 0 or "<tg-emoji" in line:
                out.append(line)
                continue
            m = _LEAD.match(line)
            if m and n < MAX_EMOJI:
                core = norm(line[m.end():])
                eid = None
                for has_ctx, _l, sk, ctx, rid in comp:
                    if core.startswith(sk) and (not ctx or ctx in whole):
                        eid = rid
                        break
                glyph = safe_glyph(m.group(2)) if eid else None
                if glyph:
                    line = line[:m.end(1)] + self._tg(eid, glyph) + line[m.end():]
                    n += 1
            line, n = self._globals(line, n)
            if digits and "رتبه" in line and n < MAX_EMOJI:
                line, n = self._rank_digits(line, n)
            out.append(line)
        res = "\n".join(out)
        return res if n else h

    def _rank_digits(self, line, n):
        def sub(mm):
            nonlocal n
            run = mm.group(2)
            if n + len(run) > MAX_EMOJI:
                return mm.group(0)
            outp = []
            for d in run:
                e = d.translate(_FA_TO_EN)
                outp.append(self._tg(DIGIT_IDS[e], e + "\uFE0F\u20E3"))
            n += len(run)
            return mm.group(1) + "".join(outp)
        parts = re.split(r"(<[^>]*>)", line)
        in_te = in_code = in_a = 0
        res = []
        for p in parts:
            if p.startswith("<") and p.endswith(">"):
                low = p.lower()
                in_te += low.startswith("<tg-emoji")
                in_te = max(0, in_te - low.startswith("</tg-emoji"))
                in_code += bool(re.match(r"<(code|pre)\b", low))
                in_code = max(0, in_code - bool(re.match(r"</(code|pre)>", low)))
                in_a += bool(re.match(r"<a\b", low))
                in_a = max(0, in_a - low.startswith("</a"))
                res.append(p)
            elif in_te or in_code or in_a:
                res.append(p)
            else:
                res.append(_RANK_RE.sub(sub, p))
        return "".join(res), n

    def _globals(self, line, n):
        if n >= MAX_EMOJI:
            return line, n
        plain = _html.unescape(_TAG.sub("", line))
        dooz_x = ("⭕" in plain) or ("نقش" in plain) or bool(_BOARD_ONLY.match(plain.strip() or "-"))
        parts = re.split(r"(<[^>]*>)", line)
        res, in_te, in_code, in_a = [], 0, 0, 0
        cls = "([" + "".join(GLOBAL_EMOJI) + "])[\uFE0E\uFE0F]?"
        rx = re.compile(r"(7\uFE0F?\u20E3)|" + cls)
        for p in parts:
            if p.startswith("<") and p.endswith(">"):
                low = p.lower()
                if low.startswith("<tg-emoji"):
                    in_te += 1
                elif low.startswith("</tg-emoji"):
                    in_te = max(0, in_te - 1)
                elif re.match(r"<(code|pre)\b", low):
                    in_code += 1
                elif re.match(r"</(code|pre)>", low):
                    in_code = max(0, in_code - 1)
                elif re.match(r"<a\b", low):
                    in_a += 1
                elif low.startswith("</a"):
                    in_a = max(0, in_a - 1)
                res.append(p)
                continue
            if in_te or in_code or in_a or not p:
                res.append(p)
                continue

            def sub(mm):
                nonlocal n
                if n >= MAX_EMOJI:
                    return mm.group(0)
                whole_m = mm.group(0)
                if mm.group(1):
                    eid, g = KEYCAP7, whole_m if whole_m.endswith("\u20e3") else "7\uFE0F\u20E3"
                    g = safe_glyph(g)
                elif mm.group(2):
                    ch = mm.group(2)
                    eid = GLOBAL_EMOJI[ch]
                    if ch == "❌" and dooz_x:
                        eid = DOOZ_X
                    g = safe_glyph(ch + "\uFE0F" if ord(ch) < 0x1F000 else ch)
                else:
                    return whole_m
                if not g:
                    return whole_m
                n += 1
                return self._tg(eid, g)
            p = rx.sub(sub, p)
            res.append(p)
        return "".join(res), n

    # ---------- ارسال ----------
    _KEYS = {"sendMessage": "text", "editMessageText": "text", "sendPhoto": "caption", "sendVideo": "caption",
             "sendDocument": "caption", "sendAnimation": "caption", "editMessageCaption": "caption"}

    def prepare(self, method, params):
        key = self._KEYS.get(method)
        if not key or params.get("parse_mode") != "HTML" or not isinstance(params.get(key), str):
            return None
        if not self.active():
            return None
        t2 = self.transform(params[key], digits=self.digits_on())
        if t2 is params[key] or t2 == params[key]:
            return None
        p2 = dict(params)
        p2[key] = t2
        return p2

    def note_ok(self):
        mode, _ = self.settings()
        if mode == "auto" and self.state()[0] != "ok":
            old = self.state()[0]
            self._set_state("ok")
            if old == "fail":
                self._notify("💎 <b>ایموجی پرمیوم پیام‌ها دوباره فعال شد</b>")

    def _set_state(self, kind):
        self.bot.set_setting("premium_emoji_msg_state", f"{kind}:{int(time.time())}")
        self._scache = (0.0, None)

    _UNRELATED = re.compile(r"not modified|not found|can't be edited|can't be deleted|blocked|deactivated|kicked|forbidden|too many|"
                            r"retry|chat not|user not|query is too old|message to|need administrator|have no rights|not enough rights|"
                            r"is too long|too long|wrong file|reply markup|button", re.I)
    _EMOJISH = re.compile(r"emoji|document_invalid|entit|custom|premium|tg-emoji", re.I)

    def on_fail(self, send, params, r):
        """send(params) → dict. اگر پیام با ایموجی پرمیوم رد شد، همان پیام بدون آن ارسال می‌شود"""
        desc = str(r.get("description", r.get("error_description", "")))
        if r.get("error_code") not in (400, None) or self._UNRELATED.search(desc):
            return r
        r2 = send(params)
        if r2.get("ok"):
            mode, _ = self.settings()
            logging.warning("premsg: تلگرام ایموجی پرمیوم پیام را نپذیرفت: %s", desc[:200])
            if mode == "auto" and self._EMOJISH.search(desc):
                old = self.state()[0]
                self._set_state("fail")
                if old != "fail":
                    self._notify("⚠️ <b>ایموجی پرمیوم پیام‌ها خاموش شد</b>\n"
                                 "تلگرام آن را نپذیرفت؛ پیام‌ها با ایموجی معمولی ارسال می‌شوند و هر ۶ ساعت دوباره امتحان می‌شود.\n"
                                 f"<code>{_html.escape(desc[:120])}</code>")
        return r2

    def _notify(self, text):
        def run():
            try:
                for a in list(self.bot.ADMIN_IDS)[:3]:
                    self.bot._tg_send("sendMessage", 20, {"chat_id": a, "text": text, "parse_mode": "HTML"})
            except Exception:
                logging.exception("premsg notify")
        threading.Thread(target=run, daemon=True).start()
