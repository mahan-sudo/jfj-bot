import os, sys, time, json, re
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b
pgtest.fresh("cap")
b.install_schema(); b.migrate_schema()
P=F=0
def ok(c,n):
    global P,F
    if c: P+=1; print('PASS '+n)
    else: F+=1; print("FAIL "+n)
calls=[]; mid=[1000]
def fake_send(method, timeout, params):
    calls.append((method,dict(params)))
    if method=="getCustomEmojiStickers":
        return {"ok":True,"result":[{"custom_emoji_id":i,"emoji":"🔥"} for i in params["custom_emoji_ids"]]}
    if method in ("copyMessage","sendMessage"):
        mid[0]+=1; return {"ok":True,"result":{"message_id":mid[0]}}
    return {"ok":True,"result":True}
b._tg_send=fake_send
b.init_premoji()
ADM=b.ADMIN_IDS[0]
b.upsert_user({"id":ADM,"first_name":"Admin"}); b.upsert_user({"id":55,"first_name":"U"})
def cbk(data):
    calls.clear()
    b.v2_admin_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
n=[200]
def msg(**kw):
    n[0]+=1
    m={"message_id":n[0],"from":{"id":ADM,"first_name":"A"},"chat":{"id":ADM,"type":"private"}}; m.update(kw)
    calls.clear()
    b.handle_update({"update_id":n[0]*11,"message":m}); return m
def sends(method): return [p for mt,p in calls if mt==method]
def texts(): return " ".join(str(p.get("text","")) for mt,p in calls if mt in ("sendMessage","editMessageText"))
def btns():
    out=[]
    for mt,p in calls:
        if mt in ("sendMessage","editMessageText"):
            rm=p.get("reply_markup")
            if rm:
                rm=json.loads(rm) if isinstance(rm,str) else rm
                for r in rm["inline_keyboard"]:
                    for x in r: out.append(x.get("callback_data"))
    return out
def st(): return b.get_state(ADM)[1] or {}
def start(kind, purpose="bc"):
    b.set_state(ADM,"admin_panel")
    if purpose=="bc": b.rich_start(ADM,ADM,"bc","g",aud="all",then="gen")
    else: b.rich_start(ADM,ADM,"dm","s",uid=55)
    cbk("adm_p:x:rk:"+kind)

# ۱) عکس بدون کپشن ← پرسش کپشن، تأیید نهایی هنوز نه
start("photo")
msg(photo=[{"file_id":"x","file_size":1}])
ok("adm_p:x:rcap" in btns() and "adm_p:x:rcok" in btns(),"عکس بدون کپشن: پیشنهاد افزودن کپشن / ادامه")
ok("adm_p:x:rgo" not in btns() and "adm_p:x:rgop" not in btns(),"عکس بدون کپشن: هنوز مرحله‌ی تأیید نهایی نیست")
ok("ندارد" in texts(),"متن پرسش: کپشن ندارد")
ok(len(sends("copyMessage"))==1 and "caption" not in sends("copyMessage")[0],"پیش‌نمایش بدون کپشن")
d=st(); ok(d.get("media_mid") and d.get("src_mid") and d.get("cap_text")=="","state: media_mid/src_mid")
# ادامه بدون کپشن
cbk("adm_p:x:rcok")
ok("adm_p:x:rgop" in btns() and "adm_p:x:rgo" in btns(),"ادامه بدون کپشن → تأیید نهایی اطلاعیه")
# ۲) افزودن کپشن
start("photo")
m=msg(photo=[{"file_id":"x"}])
orig=m["message_id"]
cbk("adm_p:x:rcap")
ok(st().get("await")=="cap" and "متن کپشن" in texts(),"درخواست متن کپشن")
msg(text="سلام دنیا",entities=[{"type":"bold","offset":0,"length":4}])
cm=sends("copyMessage")
ok(len(cm)==1 and cm[0]["message_id"]==orig and cm[0]["caption"]=="سلام دنیا" and cm[0]["caption_entities"]==[{"type":"bold","offset":0,"length":4}],"کپشن جدید روی رسانه‌ی اصلی کپی شد")
d=st(); ok(d["cap_text"]=="سلام دنیا" and not d.get("await") and d["src_mid"]==d["cap_prev"],"state بعد از کپشن")
ok("adm_p:x:rcap" in btns() and "adm_p:x:rcok" in btns() and "افزودن به کپشن" in str([p for mt,p in calls]),"حالا «افزودن به کپشن» پیشنهاد می‌شود")
first_prev=d["src_mid"]
# ۳) افزودن دوم: متن به انتهای کپشن با جابه‌جایی entity
cbk("adm_p:x:rcap")
msg(text="ادامه 😀 مهم",entities=[{"type":"italic","offset":5,"length":2}])
cm=sends("copyMessage")[0]
ok(cm["caption"]=="سلام دنیا\nادامه 😀 مهم","کپشن اضافه شد با خط جدید")
shift=len("سلام دنیا\n")
ok(cm["caption_entities"]==[{"type":"bold","offset":0,"length":4},{"type":"italic","offset":shift+5,"length":2}],"offset موجودیت‌ها جابه‌جا شد")
ok(any(mt=="deleteMessage" and p["message_id"]==first_prev for mt,p in calls),"پیش‌نمایش قبلیِ ربات پاک شد")
ok(not any(mt=="deleteMessage" and p["message_id"]==orig for mt,p in calls),"پیام اصلی ادمین پاک نشد")
# ادامه ← ارسال برای همه با src_mid کپشن‌دار
cbk("adm_p:x:rcok")
d=st(); src=d["src_mid"]
ok("adm_p:x:rgop" in btns(),"تأیید نهایی پس از کپشن")
jobs=[]
orig_bc=b.bc_create
b.bc_create=lambda *a,**k:(jobs.append((a,k)),1)[1]
cbk("adm_p:x:rgo")
ok(jobs and jobs[0][0][3]==src and jobs[0][0][3]!=orig,"ارسال همگانی از نسخه‌ی کپشن‌دار انجام می‌شود")
b.bc_create=orig_bc
# ۴) عکس با کپشن ← «افزودن به کپشن» نشان داده شود، پیش‌نمایش اصلی
start("photo")
m=msg(photo=[{"file_id":"x"}],caption="کپشن اولیه",caption_entities=[{"type":"bold","offset":0,"length":5}])
ok("افزودن به کپشن" in str(calls) and "adm_p:x:rcap" in btns() and "adm_p:x:rcok" in btns(),"عکس با کپشن: پیشنهاد افزودن به کپشن")
ok(len(sends("copyMessage"))==1 and "caption" not in sends("copyMessage")[0],"کپشن بدون تغییر: همان پیام اصلی کپی می‌شود")
cbk("adm_p:x:rcap"); msg(text="بیشتر",entities=[])
cm=sends("copyMessage")[0]
ok(cm["caption"]=="کپشن اولیه\nبیشتر" and cm["caption_entities"]==[{"type":"bold","offset":0,"length":5}],"افزودن به کپشنِ اولیه")
# ۵) حد ۱۰۲۴
cbk("adm_p:x:rcap"); before=st()["cap_text"]
msg(text="ا"*1100)
ok(not sends("copyMessage") and "بیشتر می‌شود" in texts() and st()["cap_text"]==before and st().get("await")=="cap","بیش از ۱۰۲۴ نویسه: رد شد و کپشن قبلی می‌ماند")
msg(photo=[{"file_id":"y"}])
ok("فقط" in texts() and "متن" in texts() and st().get("await")=="cap","غیرمتن در حالت کپشن رد می‌شود")
# «بدون تغییر ادامه»
cbk("adm_p:x:rcok"); ok(not st().get("await") and "adm_p:x:rgo" in btns(),"ادامه بدون تغییر")
# ۶) کد ایموجی پرمیوم در کپشن
start("voice")
msg(voice={"file_id":"v"},caption="درود {5825623013852192219}")
cm=sends("copyMessage")
ok(len(cm)==1 and "caption" in cm[0] and "{" not in cm[0]["caption"] and any(e["type"]=="custom_emoji" for e in cm[0]["caption_entities"]),"ویس: کد پرمیوم در کپشن تبدیل شد")
cbk("adm_p:x:rcap"); msg(text="و {💎:5825623013852192219}")
cm=sends("copyMessage")[0]
ok(sum(e["type"]=="custom_emoji" for e in cm["caption_entities"])==2 and "{" not in cm["caption"],"افزودن متن با کد پرمیوم: هر دو تبدیل شد")
# ۷) گیف
start("gif")
msg(animation={"file_id":"g"})
ok("adm_p:x:rcap" in btns(),"گیف: پرسش کپشن")
# ۸) استیکر / متن / فوروارد: بدون پرسش کپشن
for k,kw in (("sticker",{"sticker":{"file_id":"s"}}),("text",{"text":"سلام"})):
    start(k); msg(**kw)
    ok("adm_p:x:rcap" not in btns() and "adm_p:x:rgop" in btns(),f"{k}: مستقیم تأیید نهایی (بدون کپشن)")
start("forward"); msg(text="fwd",forward_origin={"type":"hidden_user"})
ok("adm_p:x:rcap" not in btns() and "adm_p:x:rgop" in btns(),"فوروارد: مستقیم تأیید نهایی")
# ۹) پیام خصوصی به کاربر
start("photo","dm"); msg(photo=[{"file_id":"x"}])
ok("adm_p:x:rcap" in btns(),"پیام به کاربر: عکس → پرسش کپشن")
cbk("adm_p:x:rcap"); msg(text="سلام کاربر")
cbk("adm_p:x:rcok")
ok("adm_p:x:rgo" in btns() and "adm_p:x:rgop" not in btns() and "ارسال شود" in texts(),"پیام به کاربر: تأیید نهایی dm")
sent_to=[]
cbk("adm_p:x:rgo")
cm=[p for p in sends("copyMessage") if p["chat_id"]==55]
ok(len(cm)==1 and cm[0]["message_id"]==st().get("src_mid", cm[0]["message_id"]),"dm: copyMessage به کاربر")
# ۱۰) نوع اشتباه
start("photo"); msg(text="متن به‌جای عکس")
ok("نمی‌خواند" in texts(),"نوع اشتباه رد می‌شود")
# ۱۱) رد شدن کپشن توسط تلگرام: کپشن قبلی دست‌نخورده
start("photo"); msg(photo=[{"file_id":"x"}]); cbk("adm_p:x:rcap")
def bad(method,timeout,params):
    if method=="copyMessage" and "caption" in params: return {"ok":False,"description":"Bad Request: bad entities"}
    return fake_send(method,timeout,params)
b._tg_send=bad
msg(text="x")
ok("کپشن ساخته نشد" in texts() and st()["cap_text"]=="","رد شدن توسط تلگرام: کپشن قبلی دست‌نخورده")
b._tg_send=fake_send
# ۱۲) انقضا
b.set_state(ADM,"admin_panel"); cbk("adm_p:x:rcap")
ok(True,"callback منقضی بدون خطا")
print(f"== {P} PASS / {F} FAIL"); sys.exit(1 if F else 0)
