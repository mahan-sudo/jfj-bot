import os, sys, time, json, re
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b
import premium_msg as pm_
pgtest.fresh("pm")
b.install_schema(); b.migrate_schema()
P=F=0
def ok(c,n):
    global P,F
    if c: P+=1; print('PASS '+n)
    else: F+=1; print("FAIL "+n)
calls=[]; fail={"v":None}
def fake_send(method, timeout, params):
    calls.append((method,params))
    t=params.get("text") or params.get("caption") or ""
    if fail["v"]=="emoji" and "<tg-emoji" in t:
        return {"ok":False,"error_code":400,"description":"Bad Request: DOCUMENT_INVALID"}
    if fail["v"]=="chat" and "<tg-emoji" in t:
        return {"ok":False,"error_code":400,"description":"Bad Request: chat not found"}
    return {"ok":True,"result":{"message_id":1}}
b._tg_send=fake_send
b.init_premoji(); me=b.MSGEMO
ok(me is not None,"loaded")
T=lambda h: me.transform(h)
def ids(h): return re.findall(r'emoji-id="(\d+)"',h)
# خط‌به‌خط
h=T("<b>🌸 به جفج شاهنشاهی خوش آمدی!\n\n🤔 من برات چکار انجام میدم؟\n- متن\n\n/help ◁ [کلیک کن] چطور جفج برم؟! راهنما\n\n🎯 همین الان شروع JFJ رو بزن جفج برو.</b>")
ok(ids(h)==["5461151367559141950","5314589624377554054","5823664135103061930","5928998611764387949"],"welcome ids")
ok(h.startswith('<b><tg-emoji emoji-id="5461151367559141950">🌸</tg-emoji> به جفج'),"first line inside bold")
ok("- متن" in h,"plain bullet untouched")
# سراسری
h=T("<b>🛑 موجودی کافی نیست!\n❗️ فقط عدد\n⚠️ x ‼️ y</b>")
ok(ids(h)==[pm_.WARN]*4,"global warnings")
h=T("<b>💎 شاهی\n✅ ok و ❌ no</b>")
ok(pm_.GEM in ids(h) and pm_.CHK in ids(h) and pm_.CROSS in ids(h),"global gem/check/cross")
# زمینه
f=T("<b>🔍 درخواست JFJ پیدا شد!\n\n💎لینک: https://t.me/x</b>")
ok("5889002570633977838" in ids(f) and "5825460599663894403" not in ids(f),"link ctx found")
o=T("<b>🔐 کد پیگیری: A1\n📦 محصول: p\n🔗 لینک: l</b>")
ok("5825460599663894403" in ids(o) and "5927029738626359516" in ids(o) and "5889002570633977838" not in ids(o),"link/product ctx orders")
c=T("<b>🧾 تأیید خرید\n\n📦 محصول: p\n💰 قیمت: 1 تومان</b>")
ok("5909146585727509820" in ids(c) and "5859667780793539624" in ids(c),"confirm ctx")
# موجودی
a=T("<b>🏦 موجودی : 5 شاهی\n🛑 موجودی کافی نیست</b>")
ok(ids(a)==[pm_.WALLET,pm_.WARN],"balance vs insufficient")
a=T("<b>💎 موجودی شما: 5 شاهی\n👤 1 member = 💎 1 شاهی</b>")
ok(ids(a)==["5859667780793539624",pm_.USER,pm_.GEM],"balance you + 1 member")
# شماره‌ها
a=T("<b>1️⃣ ممبر واقعی: x\n2️⃣ تأیید عضویت: x\n7️⃣ عدم سوءاستفاده: x\n3️⃣ بی‌ربط</b>")
ok(ids(a)==[pm_.N1,pm_.N2,pm_.N7],"numbered rules")
# code/pre
a=T("<b>شماره\n<pre>⚠️ x\n💎 y</pre>\n<code>✅ z</code> ✅</b>")
ok(a.count("<tg-emoji")==1 and "<pre>⚠️ x\n💎 y</pre>" in a,"pre/code untouched")
# بدون ایموجی ابتدای خط → دست‌نخورده
ok(T("<b>موجودی: 5</b>")=="<b>موجودی: 5</b>","no leading emoji no change")
ok(T("")=="" and T("abc")=="abc","empty/plain")
# وضعیت
s=T("<b>⏳️ وضعیت: درحال انجام\n✅️ وضعیت: تکمیل شده\n🚫 وضعیت: ربات عزل شد\n❌ وضعیت: لغو شده (موجودی برگشت)</b>")
ok(ids(s)==[pm_.WAIT,pm_.CHK,"5818716826699307883",pm_.CROSS],"status lines")
# دوز
ok("<tg-emoji" not in T("<b>❌⭕◻️ ✅</b>"),"xo board untouched")
# سقف ۱۰۰
ok(len(ids(T("\n".join(["✅ x"]*150))))<=100,"cap 100")
# ارسال: فعال
b.set_setting("premium_emoji_msg","auto"); b.set_setting("premium_emoji_msg_state",""); me.refresh(); calls.clear()
r=b.tg("sendMessage",chat_id=1,text="💎 *شاهی چیه و چه کاربردی داره؟*",parse_mode="Markdown")
ok(r["ok"] and "<tg-emoji" in calls[0][1]["text"] and len(calls)==1,"send with premium")
ok(me.state()[0]=="ok","state ok after send")
# ارسال: پیام معمولی بدون قانون
calls.clear(); b.tg("sendMessage",chat_id=1,text="سلام",parse_mode="Markdown")
ok("<tg-emoji" not in calls[0][1]["text"],"unmatched untouched")
# کپشن
calls.clear(); b.tg("sendPhoto",chat_id=1,photo="x",caption="💎 *شاهی*",parse_mode="Markdown")
ok("<tg-emoji" in calls[0][1]["caption"],"caption")
# خاموش
b.set_setting("premium_emoji_msg","off"); me.refresh(); calls.clear()
b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
ok("<tg-emoji" not in calls[0][1]["text"],"off")
# رد شدن → فالبک + خاموشی خودکار
b.set_setting("premium_emoji_msg","auto"); b.set_setting("premium_emoji_msg_state",""); me.refresh(); calls.clear(); fail["v"]="emoji"
r=b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
time.sleep(0.3); cc=[c for c in calls if c[1].get("chat_id")==1]
ok(r["ok"] and len(cc)==2 and "<tg-emoji" not in cc[-1][1]["text"],"fallback plain")
ok(me.state()[0]=="fail" and not me.active(),"auto goes off after fail")
calls.clear(); b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
ok(len(calls)==1 and "<tg-emoji" not in calls[0][1]["text"],"stays plain")
# بعد از ۶ ساعت دوباره امتحان
b.set_setting("premium_emoji_msg_state","fail:%d"%(time.time()-7*3600)); me.refresh(); fail["v"]=None; calls.clear()
b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
ok("<tg-emoji" in calls[0][1]["text"] and me.state()[0]=="ok","re-probe re-enables")
# on: بعد از خطا state تغییر نمی‌کند
b.set_setting("premium_emoji_msg","on"); b.set_setting("premium_emoji_msg_state",""); me.refresh(); fail["v"]="emoji"; calls.clear()
b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
ok(me.state()[0]=="" and me.active(),"on mode never flips state")
# خطای نامرتبط: بدون تلاش مجدد
b.set_setting("premium_emoji_msg","auto"); me.refresh(); fail["v"]="chat"; calls.clear()
r=b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown")
ok(not r["ok"] and len(calls)==1 and me.state()[0]=="","unrelated error no retry")
fail["v"]=None
# override
b.set_setting("premium_emoji_msg_map",json.dumps({"موجودی:":"","سلام":"5000000000000000001","bad":"12"},ensure_ascii=False)); me.refresh()
mode,rules=me.settings()
ok("موجودی:" not in rules and rules.get("سلام")=="5000000000000000001" and "bad" not in rules,"override merge")
ok(ids(T("<b>🏦 موجودی : 5</b>"))==[],"disabled rule")
ok(ids(T("<b>👋 سلام دوست</b>"))==["5000000000000000001"],"custom rule")
# با دکمه‌ها هم‌زمان
b.set_setting("premium_emoji_msg_map",""); b.set_setting("premium_emoji_msg","auto"); b.set_setting("premium_emoji","auto"); me.refresh(); b.PREMOJI.refresh(); calls.clear()
b.tg("sendMessage",chat_id=1,text="💎 *شاهی*",parse_mode="Markdown",reply_markup={"inline_keyboard":[[b.btn_inline("پشتیبانی","x")]]})
ok("<tg-emoji" in calls[0][1]["text"] and "icon_custom_emoji_id" in json.dumps(calls[0][1]["reply_markup"],ensure_ascii=False),"text+buttons together")
# متن‌های جدید واقعی ربات
for name in ("MAIN_MENU_TEXT","HELP_TEXT","RULES_TEXT"):
    t=getattr(b,name)
    h=b._boldify("sendMessage",{"text":t,"parse_mode":"Markdown" if name!="MAIN_MENU_TEXT" else None})["text"]
    n=len(ids(T(h)))
    ok(n>=3,f"{name} premium count {n}")
hh=b._boldify("sendMessage",{"text":b.HELP_TEXT,"parse_mode":"Markdown"})["text"]
ok(len(ids(T(hh)))==16 and len(T(hh))<4096+3000,"help has many ids")
inv=b.invoice_text("p",1000,"C1")
iv=b._boldify("sendMessage",{"text":inv,"parse_mode":"Markdown"})["text"]
ok(pm_.N1 in ids(T(iv)) and "5888625992196431593" in ids(T(iv)) and "5819051035284479206" in ids(T(iv)),"invoice ids")
ok(len(b.HELP_TEXT)<3800,"help under limit")
# صفحه تنظیمات
t,k=b.render_general(); ok("ایموجی پرمیوم پیام‌ها" in t,"render_general msg line")

# ---- v11.1: متن داخل tg-emoji باید ایموجی واقعی باشد (ENTITY_TEXT_INVALID) ----
print("--- glyph safety ---")
ok(pm_.safe_glyph("◁")=="◀️" and pm_.safe_glyph("●") is None and pm_.safe_glyph("★") is None and pm_.safe_glyph("🌸")=="🌸","safe_glyph")
ok(pm_.safe_glyph("1️⃣")=="1️⃣" and pm_.safe_glyph("⚠️")=="⚠️" and pm_.safe_glyph("✅️")=="✅️","safe_glyph keycap/bmp")
h=T("<b>● شاهی چیه و چه کاربردی داره؟\n/help ◁ x</b>")
ok('>●<' not in h and '>◁<' not in h and "◀️" in h,"non-emoji glyph never inside tg-emoji")
allt=[]
for name in ("MAIN_MENU_TEXT","HELP_TEXT","RULES_TEXT"):
    allt.append(b._boldify("sendMessage",{"text":getattr(b,name),"parse_mode":"Markdown" if name!="MAIN_MENU_TEXT" else None})["text"])
allt.append(b._boldify("sendMessage",{"text":b.invoice_text("p",1000,"C1"),"parse_mode":"Markdown"})["text"])
bad=[g for t in allt for g in re.findall(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>',T(t)) if pm_.safe_glyph(g)!=g]
ok(not bad,"all real texts: tg-emoji content valid "+str(bad))
print(f"t_pm: PASS={P} FAIL={F}")
