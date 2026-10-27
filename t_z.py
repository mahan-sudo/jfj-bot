exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
import json
ADM=b.ADMIN_IDS[0]
files=[]; MSG=[700]
def fake_files(method,fields,fname,data,timeout=60):
    files.append((method,dict(fields),len(data))); 
    if method=="sendPhoto": MSG[0]+=1; return {"ok":True,"result":{"message_id":MSG[0]}}
    return {"ok":True,"result":{}}
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
g.random.randint=lambda a,b_: 4 if (a,b_)==g.MON_REWARD else a
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
ok("گروه تست" in str(e["reply_markup"]) and f"gx_mon_s:{G}" in str(e["reply_markup"]) and "خودکار" in str(e["reply_markup"]),"لیست گروه‌های ادمین")
g._CHAT_SEEN.clear()
for ch_ in (-9999,):
    g.note_chat({"id":ch_,"type":"supergroup","title":"گروه غیرادمین"})
g._CL[0]=None; admcb("adm_p:x:gx_mon"); e=[q for m_,q in sent if m_=="editMessageText"][-1]
ok("غیرادمین" not in str(e["reply_markup"]),"گروه غیرادمین نمایش داده نمی‌شود")
n0=len([f for f in files if f[0]=="sendPhoto"]); admcb(f"adm_p:x:gx_mon_s:{G}")
ok(len([f for f in files if f[0]=="sendPhoto"])==n0+1,"ارسال دستی از پنل")
admcb(f"adm_p:x:gx_mon_s:{G}"); ok("هیولای فعال" in str([q for m_,q in sent if m_=="editMessageText"][-1]),"ارسال دوباره‌ی همزمان رد شد")
admcb(f"adm_p:x:gx_mon_s:-9999"); 
admcb(f"adm_p:x:gx_mon_a:{G}"); ok(G in g._mon_auto(),"خودکار روشن")
with b.get_db() as c: c.execute("UPDATE g_mon SET state='idle' WHERE state='live'")
n0=len([f for f in files if f[0]=="sendPhoto"]); g._tick_mon(time.time()); ok(len([f for f in files if f[0]=="sendPhoto"])==n0+1,"ارسال خودکار")
g._tick_mon(time.time()); ok(len([f for f in files if f[0]=="sendPhoto"])==n0+1,"خودکار قبل از ۱۵ دقیقه تکرار نمی‌شود")
admcb(f"adm_p:x:gx_mon_a:{G}"); ok(G not in g._mon_auto(),"خودکار خاموش")
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
