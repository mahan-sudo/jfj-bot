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
    if method=="getCustomEmojiStickers":
        return {"ok":True,"result":[{"custom_emoji_id":i,"emoji":"🔥"} for i in params["custom_emoji_ids"] if i!="1"*19]}
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
ok(ids(T("<b>❌⭕◻️</b>"))==[pm_.DOOZ_X,"5857031396723269245"],"xo board premium")
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
ok(ids(T("<b>💰 موجودی : 5</b>"))==[],"disabled rule")
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

# ---- v12: ایموجی‌های خام، ارقام گروه، دوز ----
print("--- v12 ---")
ok(ids(T("<b>🎗 به بخش JFJ رفتن خوش آمدید.</b>"))==["5818866927216369505"],"jfj welcome id")
ok("رفتن" in b.JFJ_WELCOME_TEXT,"jfj welcome text has رفتن")
gl={"🎯":"5832335747088130009","🥇":"5832692422647226240","🥈":"5834620746999012948","🥉":"5832346686369832003","🏅":"5836866392124563486",
"🎖":"5845858434439716957","🏆":"5818913299978263825","🎲":"5875483791702630534","🃏":"5875308385238262342","🏦":"5886285995229323603",
"📄":"5882230558259420962","✂️":"5881796225396645401","👑":"5837050654811496370","🔍":"5823239319887815835","🏁":"5888594273862950655",
"📋":"5911198059676574025","👥️":"5816404884458577332","⤵":"5820903824046432799","📊":"5298520596945070277","🕹":"5852627620725792383",
"🛎":"5883982896326254229","🪪":"5843911663203392756","🏰":"5857321629138297224","🎭":"5879733124971111582","⏰️":"5906896396526560494",
"🎉":"5461151367559141950","⁉️":"5258344772778619330","✨️":"5818677197036069696","🍇":"5337218351066266838","🍋":"5219705713680463026",
"⭕️":"5857031396723269245"}
bad=[k for k,v in gl.items() if ids(T("<b>x "+k+" y</b>"))!=[v]]
ok(not bad,"raw emoji map "+str(bad))
ok(ids(T("<b>7️⃣ x</b>"))==["5884468176091094657"],"keycap 7")
# دوز
x=T("<b>🎭 نقش › ❌️\n❌️⭕️◻️\n◻️❌️◻️\nتعیین نشده ❌</b>")
ok(ids(x)==[pm_.GLOBAL_EMOJI["🎭"],pm_.DOOZ_X,pm_.DOOZ_X,"5857031396723269245",pm_.DOOZ_X,pm_.CROSS],"dooz x/o contexts")
# بازنده
l=T("<b>📊 وضعیت ››› بازنده ⛔️</b>"); ok(ids(l)==["5872823922751185495"],"loser line")
w=T("<b>📊 وضعیت ››› برنده 🏆</b>"); ok(ids(w)==["5298520596945070277","5818913299978263825"],"winner line")
ok(ids(T("<b>🔻 برای پیوستن به میز دکمه‌ی زیر را بزنید.</b>"))==["5857454223368657979"],"join table line")
# رقم رتبه ساده می‌ماند (اعداد کیبورد، نه ایموجی پرمیوم)
r1=T("<b>رتبه 12 › <a href=\"tg://user?id=5\">علی 77</a> 🍟\n🎖️ رتبه شما › 15ام لیدربرد\n🎖️ رتبه › 3ام لیدربرد</b>")
ok(ids(r1)==[pm_.GLOBAL_EMOJI["🎖"]]*2 and "رتبه 12 ›" in r1 and "15ام" in r1 and "3ام" in r1,"rank digits stay plain")
# 🪨 و پشتیبانی
ok(ids(T("<b>🪨 سنگ</b>"))==["5882236803141868717"],"rock emoji")
sp=T("<b>☎️ پشتیبانی\n\n🔭 لطفا موضوع و توضیحات خود را در یک قالب مسیج ارسال کرده تا بمانید!\n\n@x</b>")
ok(ids(sp)==["5465169893580086142","5893125726353236397"],"support ids")
import games as gm
# همه‌ی tg-emoji ها متن مجاز دارند (متن‌های بازی)
import games as gm
samples=[b._boldify("sendMessage",{"text":t,"parse_mode":"Markdown"})["text"] for t in (b.JFJ_WELCOME_TEXT,gm._lb_menu_text(),"🥇 اول › x\n🏅 چهارم\n🎖 پنجم\n🍇🍋7️⃣ 🃏 🪪 🏰 🛎 🕹 ⁉️ ✨️ ⏰️ ⤵ 📋 👥️ 📄 ✂️ 🎭")]
bad=[g for t in samples for g in re.findall(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>',me.transform(t)) if pm_.safe_glyph(g)!=g]
ok(not bad,"v12 glyphs valid "+str(bad))
ok("🔻" not in gm._lb_menu_text(),"no 🔻 in leaderboard menu")

# ---- v14 ----
print("--- v14 ---")
ok(ids(T("<b>🎰 گردونه</b>"))==["5875360259853263196"],"slot emoji")
ok(ids(T("<b>x 🔺️ y 🔻 z</b>"))==["6046421205160829795","6046541528669626552"],"triangles")
ok(ids(T("<b>🆔️ شناسه</b>"))==["5908942862543756657"],"id emoji")
ok(ids(T("<b>🚀 درخواست JFJ شما #ثبت شد.\n\n🔍 کد پیگیری: 5</b>"))[0]==pm_.CHK,"jfj order submitted rocket")
ok(ids(T("<b>🚀 سفارش افزایش ممبر شما #ثبت شد.\n\n🔍 کد پیگیری: 5</b>"))[0]==pm_.CHK,"service order submitted rocket")
ok(ids(T("<b>🛍 سفارش‌های خرید محصولات شما\n\n🔍 کد پیگیری: 5</b>"))[0]=="5909146585727509820","orders list unaffected")
ok(ids(T("<b>🔻 لطفا مبلغ ورودی را در جواب همین پنل وارد کنید.\nحداقل مبلغ › ۵ شاهی</b>"))==[pm_.GEM],"stake prompt gem")
ok(ids(T("<b>🔻 برای پیوستن به میز دکمه‌ی زیر را بزنید.</b>"))==["5857454223368657979"],"join table line")
ok("🔻 لطفا مبلغ ورودی" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","games.py"),encoding="utf-8").read(),"plain stake prompt unchanged")

# ---- v16: کد ایموجی پرمیوم در اطلاعیه‌ها ----
print("--- codes ---")
CODE="5825623013852192219"
x=pm_.expand_html("سلام {💎:%s} و {%s} و {😀:123}"%(CODE,"5830144944399981619"),lambda ids:{i:"✅" for i in ids})
ok(x.count("<tg-emoji")==2 and '>💎</tg-emoji>' in x and '>✅</tg-emoji>' in x and "{😀:123}" in x,"expand_html both formats, short id untouched")
ok(pm_.expand_html("بدون کد")=="بدون کد","expand_html no code")
x=pm_.expand_html("{x:%s}"%CODE,lambda ids:{CODE:"🔥"}); ok('>🔥</tg-emoji>' in x,"invalid glyph falls back to lookup")
x=pm_.expand_html("{%s}"%CODE); ok('>⭐</tg-emoji>' in x,"no lookup → default star")
x=pm_.expand_html("{●:%s}"%CODE,lambda ids:{CODE:"🔥"}); ok('>🔥</tg-emoji>' in x,"non-emoji glyph rejected")
t0="سلام {💎:%s} علی {%s} 😀 x"%(CODE,"5830144944399981619")
L=pm_.u16len(t0)
nt,ne,n=pm_.expand_entities(t0,[{"type":"bold","offset":0,"length":4},{"type":"italic","offset":5,"length":L-5}],lambda ids:{i:"✅" for i in ids})
ce=[e for e in ne if e["type"]=="custom_emoji"]
ok(n==2 and nt=="سلام 💎 علی ✅ 😀 x" and [(e["offset"],e["length"],e["custom_emoji_id"]) for e in ce]==[(5,2,CODE),(12,1,"5830144944399981619")],"entities: replaced + offsets")
it=[e for e in ne if e["type"]=="italic"][0]; ok(it["offset"]==5 and it["offset"]+it["length"]==pm_.u16len(nt),"entities: italic span adjusted")
ok([e for e in ne if e["type"]=="bold"][0]=={"type":"bold","offset":0,"length":4},"entities: bold before untouched")
nt,ne,n=pm_.expand_entities("a {%s} b"%CODE,[{"type":"code","offset":0,"length":9}]); ok(n==0 and nt=="a {%s} b"%CODE,"codes inside code entity untouched")
nt,ne,n=pm_.expand_entities("😀 {%s}"%CODE,[],None); ok(ne==[{"type":"custom_emoji","offset":3,"length":1,"custom_emoji_id":CODE}] and nt.endswith("⭐"),"utf16 offset after astral emoji")
# جریان تلگرامی: متن
b.set_setting("premium_emoji_msg","auto"); me.refresh(); calls.clear()
msg={"message_id":50,"chat":{"id":7},"from":{"id":7},"text":"سلام {%s} {💎:%s}"%("5830144944399981619",CODE),"entities":[{"type":"bold","offset":0,"length":4}]}
mid,err=b.rich_convert_codes(msg)
sm=[c for c in calls if c[0]=="sendMessage"]
ok(mid==1 and err is None and len(sm)==1 and sm[0][1]["chat_id"]==7 and "parse_mode" not in sm[0][1] and len([e for e in sm[0][1]["entities"] if e["type"]=="custom_emoji"])==2,"telegram flow text: sendMessage with entities")
ok(any(c[0]=="getCustomEmojiStickers" for c in calls) and sm[0][1]["text"].startswith("سلام 🔥"),"bare code looked up via getCustomEmojiStickers")
calls.clear(); b.rich_convert_codes(msg)
ok(not any(c[0]=="getCustomEmojiStickers" for c in calls),"glyph lookup cached")
# کپشن
calls.clear()
cm={"message_id":51,"chat":{"id":7},"from":{"id":7},"photo":[{}],"caption":"عکس {💎:%s}"%CODE,"caption_entities":[]}
mid,err=b.rich_convert_codes(cm); cp=[c for c in calls if c[0]=="copyMessage"]
ok(mid==1 and len(cp)==1 and cp[0][1]["message_id"]==51 and cp[0][1]["caption_entities"][0]["custom_emoji_id"]==CODE,"telegram flow caption: copyMessage with caption_entities")
ok(b.rich_convert_codes({"message_id":52,"chat":{"id":7},"text":"بدون کد"})==(None,None),"no code → None")
# رد شدن توسط تلگرام
def bad_send(method, timeout, params):
    calls.append((method,params))
    if method=="sendMessage": return {"ok":False,"error_code":400,"description":"Bad Request: DOCUMENT_INVALID"}
    return fake_send(method,timeout,params)
b._tg_send=bad_send
mid,err=b.rich_convert_codes(msg); ok(mid is None and "DOCUMENT_INVALID" in err,"telegram rejects → error text")
b._tg_send=fake_send
# rich_receive: پیام تبدیل‌شده جای اصلی را می‌گیرد و پیش‌نمایش دوباره فرستاده نمی‌شود
calls.clear()
b.set_state(7,"adm_in",{"name":"rich","purpose":"bc","back":"s","kind":"text","aud":"all"})
b.rich_receive(msg,{"name":"rich","purpose":"bc","back":"s","kind":"text","aud":"all"})
_,d=b.get_state(7)
ok(d.get("src_mid")==1 and d.get("src_chat")==7 and not any(c[0]=="copyMessage" for c in calls),"rich_receive uses converted message, no duplicate preview")
calls.clear()
b.rich_receive({"message_id":60,"chat":{"id":7},"from":{"id":7},"text":"بدون کد"},{"name":"rich","purpose":"bc","back":"s","kind":"text","aud":"all"})
_,d=b.get_state(7); ok(d.get("src_mid")==60 and any(c[0]=="copyMessage" for c in calls),"rich_receive without code: normal preview")
b._tg_send=bad_send; calls.clear()
b.set_state(7,"adm_in",{"name":"rich","purpose":"bc","back":"s","kind":"text","aud":"all"})
b.rich_receive(msg,{"name":"rich","purpose":"bc","back":"s","kind":"text","aud":"all"})
_,d=b.get_state(7); ok(not d.get("src_mid") and any("DOCUMENT_INVALID" in str(c[1].get("text","")) for c in calls),"rich_receive: rejected code → error to admin, nothing queued")
b._tg_send=fake_send
# راهنما در متن‌های ادمین
ok("{💎:5825623013852192219}" in b._PREM_CODE_HELP and "{5825623013852192219}" in b._PREM_CODE_HELP,"help text mentions both formats")
# وب
ok("tg-emoji" in b.expand_premium_codes_html("x {💎:%s}"%CODE),"web html expansion")
print(f"t_pm: PASS={P} FAIL={F}")
