"""ایموجی پرمیوم برای دکمه‌های ربات (Bot API: icon_custom_emoji_id)

قانون تلگرام: آیدی ایموجی پرمیوم کنار دکمه فقط وقتی کار می‌کند که صاحب ربات اشتراک پرمیوم داشته باشد
(یا ربات یوزرنیم اضافه از Fragment خریده باشد). به همین خاطر:
  • حالت «خودکار»: ربات اول با ایموجی پرمیوم امتحان می‌کند؛ اگر تلگرام نپذیرفت، همان پیام را بدون آن می‌فرستد
    و تا ۶ ساعت خاموش می‌ماند، بعد دوباره امتحان می‌کند (اگر پرمیوم تمدید شده باشد خودش روشن می‌شود).
  • حالت «روشن»: همیشه امتحان می‌کند (فقط فالبک همان پیام).  • حالت «خاموش»: هیچ‌وقت.

فقط «اسکلت متن» دکمه نگه داشته می‌شود؛ ایموجی‌های معمولی و علامت‌های اضافه (مثل ◁) حذف و آیدی پرمیوم جایگزین می‌شود.
"""
import json
import logging
import re
import threading
import time

RETRY_AFTER = 6 * 3600
BLANK = "⠀"            # متن نامرئی برای دکمه‌های فقط‌آیکون (اگر تلگرام نپذیرد، خودکار حذف می‌شود)

# اسکلت متن دکمه → آیدی ایموجی پرمیوم  (اسکلت = متن بدون ایموجی/علامت)
DEFAULT_KEYS = {
    "پشتیبانی": "5465169893580086142",
    "شاهی": "5825623013852192219", "خرید شاهی": "5825623013852192219",
    "زیرمجموعه‌گیری": "5816404884458577332", "تعیین تعداد بازیکن": "5816404884458577332",
    "شروع JFJ": "5888594273862950655", "درخواست JFJ": "5889002570633977838",
    "انصراف": "5819154526816444042",
    "عضو شدم | بررسی": "5830144944399981619", "جوین شدم": "5830144944399981619", "پرداخت کردم": "5830144944399981619",
    "پیوستن به میز": "5819032824623144971",
    "ساخت میز قمار": "5818704981179505821", "ساخت میز دوز": "5818704981179505821",
    "کمترین عدد": "6046541528669626552", "بیشترین عدد": "6046421205160829795",
    "تغییر مبلغ ورودی": "5823445637231814311", "تعیین مبلغ ورودی": "5823445637231814311",
    "لینک درخواستی": "5859527571586161695", "خصوصی": "5856986522904959860",
    "کپی مبلغ": "5823592920250327036", "کپی شماره کارت": "5888625992196431593",
    "دارم کد تخفیف": "5902293707708701317",
    "استارز پست": "5816666216038669347",
    "ری‌اکشن پرمیومی-بوستی پست": "5929398662198206659",
    "ممبر فیک چنل": "5888998808242625656",
    "ری‌اکشن پست": "5830106027701314719", "ویو پست": "5843493805835165294",
    "قبل": "5845874566336880660", "قبلی": "5845874566336880660",
    "بعد": "5843732253829503840", "بعدی": "5843732253829503840",
    "تغییر تعداد بازیکن": "5816404884458577332",
    "کپی لینک زیرمجموعه‌گیری": "5859215993183674044",
    "ارسال شماره‌ی من": "5884362854903064294",
    "قوانین": "5825563515670242868", "سفارش من": "5888937012253171131",
    "خرید ممبر و سین ...": "5909146585727509820", "خرید سین و ممبر ...": "5909146585727509820",
    "Mini app": "5825460599663894403", "بانک انتقال": "5859667780793539624",
    "حساب من": "5843973755545590553", "بازگشت": "5832364184066614283",
}

# وقتی اسکلت متن در جدول بالا نبود: اولین ایموجی شناخته‌شده‌ی داخل متن (به ترتیب نوشتن) جایگزین می‌شود
EMOJI_KEYS = {
    "💎": "5825623013852192219",
    "❌": "5819154526816444042", "✅": "5830144944399981619",
    "🎰": "5875360259853263196", "🎲": "5875483791702630534",
    "🪨": "5882236803141868717", "📄": "5882230558259420962", "✂": "5881796225396645401",
}
DOOZ_X, DOOZ_O = "5857415006022278161", "5857031396723269245"      # ❌ و ⭕ خانه‌های بازی دوز
DIGIT_IDS = {"1": "5845974321247297274", "2": "5843861725618642819", "3": "5843973811380167207",
             "4": "5846158858812136854", "5": "5846159120805141727", "6": "5845716047683921674"}

_EMO_RE = re.compile("[\U0001F000-\U0001FAFF←-⇿⌀-⏿■-◿☀-➿⤀-⥿"
                     "⬀-⯿〰〽㊗㊙︎️‍⃣©®]")
_KEYCAP = re.compile("^([1-6])️?⃣$")
_SOLO = re.compile("^([❌✅⭕])️?$")
_ID_RE = re.compile(r"^\d{15,20}$")


def core(text):
    """اسکلت متن: بدون ایموجی و علامت‌های تزئینی؛ نیم‌فاصله‌ی فارسی حفظ می‌شود"""
    return re.sub(r"\s+", " ", _EMO_RE.sub(" ", text or "")).strip()


def valid_id(v):
    return bool(_ID_RE.match(str(v or "")))


class Premoji:
    def __init__(self, bot):
        self.bot = bot
        self._lock = threading.Lock()
        self._cache = (0.0, None)          # (زمان، (mode, map))
        self._scache = (0.0, None)         # (زمان، (kind, ts)) کش وضعیت
        self._rev = None
        self._rev_key = None
        self.icon_only_ok = True
        self._reg = set()

    # ---------- تنظیمات ----------
    def settings(self):
        t, v = self._cache
        if v is not None and time.time() - t < 20:
            return v
        try:
            mode = self.bot.get_setting("premium_emoji", "auto")
            raw = self.bot.get_setting("premium_emoji_map", "") or ""
            ov = json.loads(raw) if raw else {}
        except Exception:
            mode, ov = "auto", {}
        if mode not in ("auto", "on", "off"):
            mode = "auto"
        mp = dict(DEFAULT_KEYS)
        for k, v2 in (ov.items() if isinstance(ov, dict) else []):
            if v2 == "" or v2 is None:
                mp.pop(k, None)
            elif valid_id(v2):
                mp[k] = str(v2)
        self._cache = (time.time(), (mode, mp))
        return mode, mp

    def refresh(self):
        self._cache = (0.0, None)
        self._scache = (0.0, None)
        self._rev = None

    def state(self):
        t, v = self._scache
        if v is not None and time.time() - t < 20:
            return v
        v = self._read_state()
        self._scache = (time.time(), v)
        return v

    def _read_state(self):
        s = self.bot.get_setting("premium_emoji_state", "") or ""
        try:
            kind, ts = s.split(":")
            return kind, float(ts)
        except Exception:
            return "", 0.0

    def active(self):
        mode, _ = self.settings()
        if mode == "off":
            return False
        if mode == "on":
            return True
        kind, ts = self.state()
        return not (kind == "fail" and time.time() - ts < RETRY_AFTER)

    def register_reply_texts(self, texts):
        self._reg = set(t for t in texts if t)
        self._rev = None

    # ---------- تبدیل یک دکمه ----------
    def resolve(self, text, cb, mp, allow_solo=True):
        """(آیدی، متن جدید) یا None.  متن جدید = BLANK یعنی دکمه‌ی فقط‌آیکون"""
        m = _KEYCAP.match(text or "")
        if m:
            return (DIGIT_IDS[m.group(1)], BLANK) if allow_solo else None
        m = _SOLO.match(text or "")
        if m:
            if not allow_solo:
                return None
            ch = m.group(1)
            if str(cb or "").startswith("g:xo:"):
                return (DOOZ_X if ch == "❌" else DOOZ_O, BLANK)
            if ch in EMOJI_KEYS:
                return EMOJI_KEYS[ch], BLANK
            return None
        c = core(text)
        if not c:
            return self._emoji_only(text or "", cb) if allow_solo else None
        if c in mp:
            return mp[c], c
        for ch in re.sub("[︎️]", "", text or ""):
            if ch in EMOJI_KEYS:
                return EMOJI_KEYS[ch], c
        return None

    @staticmethod
    def _emoji_only(t, cb):
        """دکمه‌ای که متنش فقط ایموجی است (مثل 🎰 یا 🪨📄✂️ یا ❌⭕ منوی کازینو).
        هر دکمه فقط «یک» آیکون می‌گیرد: اولین ایموجی شناخته‌شده آیکون می‌شود و بقیه (اگر بود) به‌صورت متن می‌مانند"""
        sel = str(cb or "").startswith("g:sel:")
        for i, ch in enumerate(t):
            if sel and ch in "❌⭕":
                eid = DOOZ_X if ch == "❌" else DOOZ_O
            elif ch in EMOJI_KEYS:
                eid = EMOJI_KEYS[ch]
            else:
                continue
            rest = t[:i] + re.sub("^[\uFE0E\uFE0F]+", "", t[i + 1:])
            rest = rest.strip()
            return eid, (rest if core(rest) == "" and _EMO_RE.search(rest) else BLANK)
        return None

    def prepare(self, params):
        """params جدید با آیکون‌ها، یا None اگر چیزی عوض نشد / خاموش است"""
        if not self.active():
            return None
        return self._build(params, True)

    def _build(self, params, allow_solo):
        mode, mp = self.settings()
        rm = params.get("reply_markup")
        if isinstance(rm, str):
            try:
                rm = json.loads(rm)
            except Exception:
                return None
        if not isinstance(rm, dict):
            return None
        out, n, solo = {}, 0, 0
        for key in ("inline_keyboard", "keyboard"):
            rows = rm.get(key)
            if not isinstance(rows, list):
                continue
            new_rows = []
            for row in rows:
                nr = []
                for b in (row if isinstance(row, list) else []):
                    if isinstance(b, dict) and b.get("text") and not b.get("icon_custom_emoji_id"):
                        plain = key == "keyboard" and not any(k in b for k in ("request_contact", "web_app", "request_chat", "request_users", "request_poll", "request_location"))
                        if not plain or b["text"] in self._reg:
                            r = self.resolve(b["text"], b.get("callback_data"), mp, allow_solo)
                            if r:
                                b = dict(b)
                                b["icon_custom_emoji_id"] = r[0]
                                b["text"] = r[1]
                                n += 1
                                solo += r[1] == BLANK
                    nr.append(b)
                new_rows.append(nr)
            out[key] = new_rows
        if not n:
            return None
        rm2 = dict(rm)
        rm2.update(out)
        p2 = dict(params)
        p2["reply_markup"] = rm2 if not isinstance(params.get("reply_markup"), str) else json.dumps(rm2, ensure_ascii=False)
        return {"params": p2, "icons": n, "solo": solo}

    # ---------- متن دکمه‌ی ریپلای که کاربر می‌فرستد ----------
    def normalize_incoming(self, text):
        if not text or not self._reg:
            return text
        mode, mp = self.settings()
        key = (id(mp), self.icon_only_ok)
        if self._rev is None or self._rev_key != key:
            rev = {}
            for orig in self._reg:
                r = self.resolve(orig, None, mp, True)
                if r and r[1] != BLANK:
                    rev[r[1]] = orig
            self._rev, self._rev_key = rev, key
        return self._rev.get(text, text)

    # ---------- نتیجه‌ی ارسال ----------
    def _set_state(self, kind):
        old, _ = self.state()
        self.bot.set_setting("premium_emoji_state", f"{kind}:{int(time.time())}")
        self._scache = (0.0, None)
        return old

    def note_ok(self):
        mode, _ = self.settings()
        if mode == "auto":
            old = self._set_state("ok") if self.state()[0] != "ok" else "ok"
            if old == "fail":
                self._notify("💎 <b>ایموجی پرمیوم دکمه‌ها دوباره فعال شد</b>\nتلگرام دوباره ایموجی پرمیوم را پذیرفت.")

    _UNRELATED = re.compile(r"not modified|not found|can't be edited|can't be deleted|blocked|deactivated|kicked|forbidden|too many|retry|"
                            r"chat not|user not|query is too old|message to|need administrator|have no rights|not enough rights", re.I)
    _ICONISH = re.compile(r"icon|emoji|premium|button|document_invalid|entity|custom", re.I)

    def on_fail(self, send, method, timeout, params, alt, r):
        """send(method, timeout, params) → dict.  ابتدا بدون دکمه‌های فقط‌آیکون، بعد بدون هر آیکون"""
        desc = str(r.get("description", r.get("error_description", "")))
        if r.get("error_code") not in (400, None) or self._UNRELATED.search(desc):
            return r
        if alt["solo"]:
            a2 = self._build(params, False)
            if a2:
                r2 = send(method, timeout, a2["params"])
                if r2.get("ok"):
                    self.icon_only_ok = False
                    logging.warning("premoji: دکمه‌ی فقط‌آیکون پذیرفته نشد؛ فقط با متن استفاده می‌شود (%s)", desc[:120])
                    self.note_ok()
                    return r2
            else:
                a2 = None
        r3 = send(method, timeout, params)
        if r3.get("ok"):
            mode, _ = self.settings()
            logging.warning("premoji: تلگرام ایموجی پرمیوم را نپذیرفت: %s", desc[:200])
            if mode == "auto" and self._ICONISH.search(desc):
                old = self._set_state("fail")
                if old != "fail":
                    self._notify("⚠️ <b>ایموجی پرمیوم دکمه‌ها خاموش شد</b>\n"
                                 "تلگرام آن را نپذیرفت (احتمالاً اشتراک پرمیوم صاحب ربات تمام شده).\n"
                                 "ربات به متن ساده برگشت و هر ۶ ساعت دوباره امتحان می‌کند.\n"
                                 f"<code>{desc[:120]}</code>")
        return r3

    def _notify(self, text):
        def run():
            try:
                for a in list(self.bot.ADMIN_IDS)[:3]:
                    self.bot._tg_send("sendMessage", 20, {"chat_id": a, "text": text, "parse_mode": "HTML"})
            except Exception:
                logging.exception("premoji notify")
        threading.Thread(target=run, daemon=True).start()
