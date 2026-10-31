exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
import json
ADM=b.ADMIN_IDS[0]
files=[]; MSG=[700]
def fake_files(method,fields,fname,data,timeout=60):
    files.append((method,dict(fields),len(data))); 
    if method=="sendPhoto": MSG[0]+=1; return {"ok":True,"result":{"message_id":MSG[0]}}
    return {"ok":True,"result":{}}
REAL_FILES=g._tg_files
g._tg_files=fake_files
_orig=b.tg
def tg2(method,_timeout=45,**p):
    if method=="getChatMember": return {"ok":True,"result":{"status":"administrator"}} if p["chat_id"]==G else {"ok":False,"description":"Bad Request: chat not found"}
    if method=="getChat": return {"ok":True,"result":{"id":p["chat_id"],"type":"supergroup","title":"گروه تست"}}
    return fake_tg(method,_timeout,**p)
b.tg=tg2
b.upsert_user({"id":ADM,"first_name":"Admin"})
for i in (31,32,33,34): user(i,100)
def admcb(data):
    b.v2_admin_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
def bal(i): return b.get_db().execute("SELECT tokens FROM users WHERE id=?",(i,)).fetchone()[0]
def M(mn): return g._mon(mn)
def last_edit(): return [f for f in files if f[0]=="editMessageMedia"][-1]
def cap(f): return json.loads(f[1]["media"])["caption"]
def attack(u,mn): cb(u,f"g:mat:{mn}",1)
def newmon():
    ok_,msg=g.mon_send(G); assert ok_,msg
    return b.get_db().execute("SELECT MAX(id) FROM g_mon").fetchone()[0]
HIT=lambda: setattr(g.random,"random",lambda:0.1)
MISS=lambda: setattr(g.random,"random",lambda:0.95)
import random as _r; RR=_r.random; RI=_r.randint
# ارسال
mn=newmon(); m=M(mn)
sp=[f for f in files if f[0]=="sendPhoto"][-1]
ok(m["state"]=="live" and 300<=m["maxhp"]<=450 and m["chances"]==3 and m["has_photo"]==1 and sp[2]>20000,"هیولا با عکس ساخته شد")
c0=sp[1]["caption"]; ok(c0.startswith("<b>") and "هیولا درحال حمله به شاهنشاهی است" in c0 and "۳ شانس" in c0 and "۱ شاهی" in c0,"متن و Bold اولیه")
_km=json.loads(sp[1]["reply_markup"])["inline_keyboard"][0][0]; ok(_km["callback_data"]=="g:mat:%d"%mn and "اتک به هیولا" in _km["text"],"دکمه‌ی اتک")
ok(g.mon_send(G)[0] is False,"همزمان فقط یک هیولا")
# بدون موجودی
user(34,0); alerts.clear(); attack(34,mn)
ok(alerts and "موجودی شما کافی نیست" in alerts[-1] and "موجودی فعلی" in alerts[-1] and M(mn)["chances"]==3,"هشدار نبود موجودی؛ شانس نسوخت")
# اتک موفق
g.random.randint=lambda a,b_: a  # دمیج حداقل
with b.get_db() as c: c.execute("UPDATE g_mon SET hp=400, maxhp=400 WHERE id=?",(mn,))
HIT(); n0=len(files); attack(31,mn)
m=M(mn); ok(m["hp"]==290 and m["chances"]==2 and bal(31)==99,"اتک: ۱۱۰ دمیج، ۱ شاهی کسر")
e=last_edit(); c1=cap(e); ok("۲ شانس" in c1 and "بازیکن" in c1 and "tg://user?id=31" in c1 and "۱۱۰" in c1,"متن بعد از اتک (شانس، نام منشن، داستان)")
ok(e[2]>20000 and "reply_markup" in e[1] and "g:mat" in e[1]["reply_markup"],"عکس ویرایش شد و دکمه می‌ماند")
# خطا
MISS(); attack(32,mn); m=M(mn)
ok(m["hp"]==290 and m["chances"]==1 and bal(32)==99,"خطا: جان کم نشد ولی شانس و شاهی رفت")
ok("۱ شانس" in cap(last_edit()),"متن بعد از خطا")
# کشتن
with b.get_db() as c: c.execute("UPDATE g_mon SET hp=50 WHERE id=?",(mn,))
g.random.randint=lambda a,b_: 4 if (a,b_)==(g.MON_RW_MIN,g.MON_RW_MAX) else a
HIT(); attack(33,mn); m=M(mn)
ok(m["state"]=="done" and m["winner"]==33 and m["reward"]==4 and bal(33)==103,"کشتن: جایزه ۴ + هزینه ۱ کسر")
cf=cap(last_edit()); ok("پس از ۳ تلاش با موفقیت شکست خورد" in cf and "ملکوت" in cf and "tg://user?id=33" in cf and "۴ شاهی" in cf and "پاداش" in cf,"متن پیروزی")
ok(json.loads(last_edit()[1]["reply_markup"])["inline_keyboard"]==[],"دکمه حذف شد")
with b.get_db() as c:
    r=c.execute("SELECT stake_total,payout_total FROM g_log WHERE game='m'").fetchone()
ok(r and r[0]==3 and r[1]==4,"دفتر مالی ثبت شد")
alerts.clear(); attack(31,mn); ok("دیگر فعال نیست" in alerts[-1],"اتک روی هیولای تمام‌شده")
# شکست همه‌ی شانس‌ها
mid2=newmon(); MISS()
for u in (31,32,33): attack(u,mid2)
m=M(mid2); cfail=cap(last_edit())
ok(m["state"]=="fail" and m["chances"]==0 and "۰ شانس" in cfail and cfail.count("بازیکن")==3 and "ملکوت" not in cfail,"شکست: بعد از ۳ تلاش بدون کشتن")
ok(json.loads(last_edit()[1]["reply_markup"])["inline_keyboard"]==[],"دکمه حذف شد (شکست)")
# شانس‌ها مشترک است: یک نفر می‌تواند هر سه را بزند و بعدش تمام
mid3=newmon(); MISS()
for _ in range(3): attack(31,mid3)
alerts.clear(); attack(32,mid3)
ok(M(mid3)["state"]=="fail" and M(mid3)["chances"]==0 and "دیگر فعال نیست" in alerts[-1],"کل شانس ۳ تا و مشترک")
# انقضا بدون اتک
mid4=newmon(); with_=b.get_db()
with b.get_db() as c: c.execute("UPDATE g_mon SET expires=? WHERE id=?",(time.time()-1,mid4))
g._tick_mon(time.time()); ce=cap(last_edit())
ok(M(mid4)["state"]=="idle" and "کسی در مقابل هیولا از شاهنشاهی دفاع نکرد" in ce and "۳ شانس" in ce and "۱ شاهی" in ce,"انقضا بدون اتک")
# انقضا با یک اتک
mid5=newmon(); HIT(); attack(31,mid5)
with b.get_db() as c: c.execute("UPDATE g_mon SET expires=? WHERE id=?",(time.time()-1,mid5))
g._tick_mon(time.time()); ce=cap(last_edit())
ok(M(mid5)["state"]=="fail" and "۲ شانس" in ce and ce.count("بازیکن")==1,"انقضا با اتک ناقص")
# محروم‌شده بی‌صدا
mid6=newmon(); b.set_setting("g_banned",json.dumps([32])); alerts.clear(); attack(32,mid6)
ok(not alerts or alerts[-1] is None,"کاربر محروم بی‌صدا"); b.set_setting("g_banned","[]")
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE id=?",(mid6,))
# ثبت گروه و پنل ادمین
g._CHAT_SEEN.clear(); g.note_chat({"id":G,"type":"supergroup","title":"گروه تست"})
ok(b.get_db().execute("SELECT title FROM g_chats WHERE chat_id=?",(G,)).fetchone()[0]=="گروه تست","ثبت گروه")
ok("my_chat_member" in open('../bot_test.py',encoding='utf-8').read(),"my_chat_member فعال")
t,kb=b.render_games(); ok("gx_mon" in str(kb),"دکمه‌ی هیولا در پنل بازی‌ها")
admcb("adm_p:x:gx_mon"); e=[q for m_,q in sent if m_=="editMessageText"][-1]
ok("گروه تست" in str(e["reply_markup"]) and f"gx_mon_s:{G}" in str(e["reply_markup"]),"لیست گروه‌های ادمین")
g._CHAT_SEEN.clear()
for ch_ in (-9999,):
    g.note_chat({"id":ch_,"type":"supergroup","title":"گروه غیرادمین"})
g._CL[0]=None; admcb("adm_p:x:gx_mon"); e=[q for m_,q in sent if m_=="editMessageText"][-1]
ok("غیرادمین" not in str(e["reply_markup"]),"گروه غیرادمین نمایش داده نمی‌شود")
n0=len([f for f in files if f[0]=="sendPhoto"]); admcb(f"adm_p:x:gx_mon_s:{G}")
ok(len([f for f in files if f[0]=="sendPhoto"])==n0+1,"ارسال دستی از پنل")
admcb(f"adm_p:x:gx_mon_s:{G}"); ok("هیولای فعال" in str([q for m_,q in sent if m_=="editMessageText"][-1]),"ارسال دوباره‌ی همزمان رد شد")
admcb(f"adm_p:x:gx_mon_s:-9999"); 
ok("gx_mon_a" not in str(e["reply_markup"]),"دکمه‌ی خودکار هر گروه برداشته شد")
# ---- ارسال خودکار بر اساس تعداد پیام
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
sp_n=lambda: len([f for f in files if f[0]=="sendPhoto"])
with b.get_db() as c: c.execute("UPDATE g_mon SET created=created-5000, expires=expires-5000")
g._MC.clear(); g._new_goal=lambda: 5
def gm(i=31,**k):
    m_={"message_id":900+len(files),"chat":{"id":G,"type":"supergroup","title":"گروه تست"},"from":{"id":i,"first_name":"u"},"text":"hi"}; m_.update(k); return m_
def feed(n,**k):
    for _ in range(n): g.on_chat_message(gm(**k))
def settle():
    time.sleep(0.8)
n0=sp_n(); feed(4); settle(); ok(sp_n()==n0,"قبل از رسیدن به حد، ارسال نمی‌شود")
g.on_chat_message(gm(from_={"id":1})) if False else None
feed(1,**{"from":{"id":999,"first_name":"bot","is_bot":True}}); settle(); ok(sp_n()==n0,"پیام ربات شمرده نمی‌شود")
feed(1,new_chat_members=[{"id":5}],text=None); settle(); ok(sp_n()==n0,"پیام سرویسی شمرده نمی‌شود")
feed(1); settle(); ok(sp_n()==n0+1,"با پیام پنجم هیولا خودکار آمد")
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
feed(20); settle(); ok(sp_n()==n0+1,"در ۲۰ دقیقه‌ی استراحت شمارش نمی‌شود")
g._MC[G]["cool"]=time.time()-1; g._MC[G]["n"]=0
with b.get_db() as c: c.execute("UPDATE g_mon SET created=created-5000")
feed(5); settle(); ok(sp_n()==n0+2,"بعد از استراحت دوباره شمارش و ارسال")
# خاموش
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'"); c.execute("UPDATE g_mon SET created=created-5000")
g._MC[G]["cool"]=None; g._MC[G]["n"]=0
admcb("adm_p:x:gx_mon_tg"); ok(not g.mon_auto_on(),"کلید خودکار خاموش")
feed(10); settle(); ok(sp_n()==n0+2,"خاموش: ارسال خودکار نمی‌شود")
admcb("adm_p:x:gx_mon_tg"); ok(g.mon_auto_on(),"کلید خودکار روشن")
# ترد
g._MC.clear(); g._MC[G]={"n":0,"goal":2,"thread":None,"cool":0}
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'"); c.execute("UPDATE g_mon SET created=created-5000")
feed(2,message_thread_id=77,is_topic_message=True); settle(); ok(sp_n()==n0+3,"ارسال در گروه تاپیک‌دار")
# صفحه‌ها
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
g._MC[G]={"n":3,"goal":9,"thread":None,"cool":None}
admcb("adm_p:x:gx_mon"); e=[q for m_,q in sent if m_=="editMessageText"][-1]
ok("۳ از ۹" in e["text"] and "ارسال خودکار" in e["text"] and "gx_mon_cfg" in str(e["reply_markup"]) and "gx_mon_rep" in str(e["reply_markup"]),"صفحه‌ی هیولا: پیشرفت و دکمه‌ها")
g._MC[G]["cool"]=time.time()+600; admcb("adm_p:x:gx_mon"); ok("استراحت" in [q for m_,q in sent if m_=="editMessageText"][-1]["text"],"نمایش استراحت")
# تنظیمات
admcb("adm_p:x:gx_mon_cfg"); e=[q for m_,q in sent if m_=="editMessageText"][-1]; ok("تنظیمات هیولا" in e["text"] and "gx_set:mmin" in str(e["reply_markup"]),"صفحه‌ی تنظیمات")
def typed(txt):
    b.set_state(ADM,"adm_in:gx_set:mmax") if False else None
admcb("adm_p:x:gx_set:mmin"); b.handle_update({"update_id":9001,"message":{"message_id":1,"chat":{"id":ADM,"type":"private"},"from":{"id":ADM,"first_name":"A"},"text":"30"}})
ok(g.cv("mmin")==30,"حداقل پیام ۳۰ شد")
admcb("adm_p:x:gx_set:mmax"); b.handle_update({"update_id":9002,"message":{"message_id":2,"chat":{"id":ADM,"type":"private"},"from":{"id":ADM,"first_name":"A"},"text":"20"}})
ok(g.cv("mmax")!=20,"حداکثر کمتر از حداقل رد شد")
admcb("adm_p:x:gx_set:mmax"); b.handle_update({"update_id":9003,"message":{"message_id":3,"chat":{"id":ADM,"type":"private"},"from":{"id":ADM,"first_name":"A"},"text":"70"}})
ok(g.cv("mmax")==70,"حداکثر ۷۰ شد")
admcb("adm_p:x:gx_mon_rst"); ok(g.cv("mmin")==25 and g.cv("mmax")==60,"بازگشت به پیش‌فرض")
admcb("adm_p:x:gx_rst") 
# گزارش
for d_ in (1,7,30):
    admcb(f"adm_p:x:gx_mon_rep:{d_}"); e=[q for m_,q in sent if m_=="editMessageText"][-1]; ok("گزارش هیولا" in e["text"],f"گزارش هیولا {d_}")
ok("هیولای فرستاده‌شده" in e["text"],"محتوای گزارش")
# پایان فوری
mnn=newmon() if not b.get_db().execute("SELECT 1 FROM g_mon WHERE state='live'").fetchone() else b.get_db().execute("SELECT id FROM g_mon WHERE state='live'").fetchone()[0]
admcb(f"adm_p:x:gx_mon_e:{mnn}"); ok(M(mnn)["state"] in ("fail","idle","done"),"پایان فوری")
g.on_my_chat_member({"chat":{"id":G,"type":"supergroup","title":"x"},"new_chat_member":{"status":"kicked"}})
ok(b.get_db().execute("SELECT COUNT(*) FROM g_chats WHERE chat_id=?",(G,)).fetchone()[0]==0,"خروج ربات: گروه حذف شد")
# بدون Pillow
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
art=g._art; g._art=None; n0=len(sent); ok_,msg=g.mon_send(G); mid7=b.get_db().execute("SELECT MAX(id) FROM g_mon").fetchone()[0]
ok(ok_ and M(mid7)["has_photo"]==0 and sent[-1][0]=="sendMessage","بدون Pillow: فقط متن")
HIT(); attack(31,mid7); ok([m_ for m_,q in sent][-1]=="editMessageText" and "۲ شانس" in sent[-1][1]["text"],"بدون Pillow: ویرایش متنی")
g._art=art
# گزارش
t=g._rep_page(1)[0]; ok("هیولا" in t,"گزارش بازی‌ها")
random_ok=True

# ---- آزمون با اعتبارسنجی multipart مثل تلگرام واقعی (نام فیلد عکس و attach://)
import email, io, urllib.request
from PIL import Image
tele=[]
class _R:
    def __init__(s,d): s.d=json.dumps(d).encode()
    def read(s,*a): return s.d
    def __enter__(s): return s
    def __exit__(s,*a): return False
def fake_urlopen(req,timeout=None):
    method=req.full_url.rsplit("/",1)[1]
    ct=req.headers.get("Content-type") or req.headers.get("Content-Type")
    msg=email.message_from_bytes(b"Content-Type: "+ct.encode()+b"\r\n\r\n"+req.data)
    parts={}
    for p in msg.get_payload():
        parts[p.get_param("name",header="content-disposition")]=p.get_payload(decode=True)
    tele.append((method,parts))
    if method=="sendPhoto":
        if "photo" not in parts: return _R({"ok":False,"error_code":400,"description":"Bad Request: there is no photo in the request"})
        Image.open(io.BytesIO(parts["photo"])).verify()
        MSG[0]+=1; return _R({"ok":True,"result":{"message_id":MSG[0]}})
    if method=="editMessageMedia":
        media=json.loads(parts["media"].decode()); ref=media["media"].replace("attach://","")
        if not media["media"].startswith("attach://") or ref not in parts: return _R({"ok":False,"error_code":400,"description":"Bad Request: wrong file identifier/HTTP URL specified"})
        Image.open(io.BytesIO(parts[ref])).verify()
        json.loads(parts["reply_markup"].decode()); int(parts["message_id"].decode()); return _R({"ok":True,"result":{}})
    return _R({"ok":True,"result":{}})
urllib.request.urlopen=fake_urlopen
g._tg_files=REAL_FILES
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
okm,msgm=g.mon_send(G); mr=b.get_db().execute("SELECT MAX(id) FROM g_mon").fetchone()[0]
ok(okm and M(mr)["has_photo"]==1 and tele[-1][0]=="sendPhoto" and "photo" in tele[-1][1],"ارسال واقعی عکس (فیلد photo، JPEG معتبر)")
HIT(); attack(31,mr)
ok([t_[0] for t_ in tele][-1]=="editMessageMedia","ویرایش واقعی تصویر پذیرفته شد")
ok("۲ شانس" in json.loads(tele[-1][1]["media"].decode())["caption"],"متن روی تصویر به‌روز شد")
# اگر ویرایش تصویر رد شود، حداقل متن ویرایش شود
def bad_edit(req,timeout=None):
    if req.full_url.endswith("editMessageMedia"): return _R({"ok":False,"error_code":400,"description":"Bad Request: wrong file identifier"})
    return fake_urlopen(req,timeout)
urllib.request.urlopen=bad_edit; n_=len(sent); MISS(); attack(32,mr)
ok(any(m_=="editMessageCaption" and "۱ شانس" in q.get("caption","") for m_,q in sent[n_:]),"خرابی ویرایش تصویر: متن همچنان ویرایش می‌شود")

# ---- نصب خودکار Pillow
import subprocess, importlib
class _P: 
    def __init__(s,rc,err=""): s.returncode=rc; s.stderr=err; s.stdout=""
calls=[]
def fake_run(cmd,**k):
    calls.append(cmd); return _P(1,"error: externally-managed-environment") if len(calls)==1 else _P(0)
real_run=subprocess.run; subprocess.run=fake_run
saved_art=g._art; g._art=None
g._ART_ST.update(busy=False,err="")
real_load=g._load_art; g._load_art=lambda: saved_art
g._art_bootstrap()
ok(g._art is saved_art and len(calls)==2 and "--user" in calls[1] and calls[0][-1]=="Pillow","نصب خودکار: روش اول شکست، روش دوم موفق، تصویر فعال شد")
# شکست همه‌ی روش‌ها: خطا ثبت و ربات سالم
calls.clear(); g._art=None; subprocess.run=lambda cmd,**k:(calls.append(cmd),_P(1,"ERROR: no matching distribution"))[1]
real_imp=importlib.import_module
importlib.import_module=lambda n,*a,**k:(_ for _ in ()).throw(ImportError("no PIL")) if n=="PIL" else real_imp(n,*a,**k)
g._art_bootstrap(); importlib.import_module=real_imp
ok(g._art is None and len(calls)==4 and "no matching distribution" in g._ART_ST["err"] and g._ART_ST["busy"] is False,"نصب ناموفق: ۴ روش، خطا ثبت شد")
pg=g._mon_page()[0]; ok("غیرفعال" in pg and "no matching distribution" in pg,"پنل: دلیل خطا نشان داده می‌شود")
ok("gx_mon_i" in str(g._mon_page()[1]),"دکمه‌ی نصب دوباره")
n0=len(calls); admcb("adm_p:x:gx_mon_i"); time.sleep(.5)
ok(len(calls)>n0,"دکمه‌ی نصب دوباره کار می‌کند")
subprocess.run=real_run; g._load_art=real_load; g._art=saved_art
ok("فعال" in g._mon_page()[0] and "gx_mon_i" not in str(g._mon_page()[1]),"پنل وقتی تصویر فعال است")
