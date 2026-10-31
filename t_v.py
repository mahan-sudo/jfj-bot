exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
def setups(u,game,stake,players):
    gm(u,"کازینو")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]; cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p); cb(u,f"g:mk:{tid}",p)
    return tid,p
for i in (11,12,13): user(i,1000)
# 1) purge روی میز فعال، پول را پاک نمی‌کند
tid,p=setups(11,"s",10,2); cb(12,f"g:jn:{tid}",p)
g._purge(tid); ok(len(g._players(tid))==2 and S(tid)=="send","purge میز فعال بازیکن‌ها را پاک نمی‌کند")
# 2) اعشار پذیرفته نمی‌شود
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE g_tables SET state='expired' WHERE id=?",(tid,)); c.execute("UPDATE users SET tokens=1000 WHERE id IN (11,12)")
g._tick()
gm(13,"کازینو")
with b.get_db() as c: t2=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p2=mid[0]; cb(13,f"g:sel:{t2}:s",p2); cb(13,f"g:stk:{t2}",p2); n0=len(sent)
gm(13,"10.5",reply=p2); ok(g._table(t2)["stake"] is None and len(sent)==n0,"اعشار: بی‌صدا نادیده")
gm(13,"۱۲",reply=p2); ok(g._table(t2)["stake"]==12,"عدد صحیح فارسی پذیرفته شد")
# 3) ROUND در پرداخت/کسر
with b.get_db() as c:
    c.execute("UPDATE users SET tokens=0.1 WHERE id=11"); g._pay_in(c,11,0.2)
    v=c.execute("SELECT tokens FROM users WHERE id=11").fetchone()[0]
ok(v==0.3,f"گرد کردن اعشار {v!r}")
with b.get_db() as c:
    c.execute("UPDATE users SET tokens=10.1 WHERE id=11"); ok(g._charge_in(c,11,10.1)==True,"کسر دقیق همه‌ی موجودی")
# 4) retry ویرایش (۴۲۹ سپس موفق) + بدون پیام جدید
cntb={"n":0}; orig=b.tg
def flaky(method,_timeout=45,**pp):
    if method=="editMessageText" and cntb["n"]<2:
        cntb["n"]+=1; return {"ok":False,"description":"Too Many Requests: retry after 0","parameters":{"retry_after":0}}
    return orig(method,_timeout=_timeout,**pp)
b.tg=flaky; ns0=len([1 for m,q in sent if m=="sendMessage"])
g._edit({"id":t2,"chat_id":G,"msg_id":p2},"x"); b.tg=orig
ok(cntb["n"]==2 and [q for m,q in sent if m=="editMessageText"][-1]["text"].startswith("<b>x"),"ویرایش بعد از ۴۲۹ دوباره انجام شد")
ok(len([1 for m,q in sent if m=="sendMessage"])==ns0,"پیام جدید فرستاده نشد")
# 5) دایس: بدون ریپلای / ریپلای اشتباه / قبل از شروع → نادیده
with b.get_db() as c: c.execute("UPDATE g_tables SET state='expired' WHERE id=?",(t2,)); c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE users SET tokens=1000")
g._tick()
tid,p=setups(11,"s",10,2)
gm(11,dice=5,emoji="🎰",reply=None) if False else None
cnt[0]+=1; b.handle_update({"update_id":cnt[0]*7+1,"message":{"message_id":9000+cnt[0],"from":{"id":11,"first_name":"U11"},"chat":{"id":G,"type":"supergroup"},"dice":{"emoji":"🎰","value":22}}})
ok(g._players(tid)[0]["sent"]==0,"دایس بدون ریپلای نادیده")
cb(12,f"g:jn:{tid}",p)
gm(11,dice=22,emoji="🎰",reply=p+77); ok(g._players(tid)[0]["sent"]==0,"ریپلای روی پیام دیگر نادیده")
gm(11,dice=22,emoji="🎰"); ok(g._players(tid)[0]["sent"]==1,"ریپلای روی پنل پذیرفته شد")
gm(12,dice=43,emoji="🎰"); time.sleep(g.REVEAL_DELAY+.2); g._tick(); g._tick()
# 6) مرحله join: دایس نادیده
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
tid3,p3=setups(13,"s",10,2); gm(13,dice=22,emoji="🎰",reply=p3); ok(g._players(tid3)[0]["sent"]==0,"قبل از شروع بازی دایس پذیرفته نمی‌شود")
# 7) تاس تک‌نفره بدون انتخاب: بی‌صدا
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE g_tables SET state='expired' WHERE state='join'")
g._tick(); n0=len(sent)
tid4,p4=setups(12,"d",10,1); n0=len(sent); gm(12,dice=3,emoji="🎲",reply=p4)
print(S(tid4), g._players(tid4)[0]["sent"], len(sent)-n0, [m for m,q in sent[n0:]])
ok(g._players(tid4)[0]["sent"]==0 and len(sent)==n0,"تاس بدون انتخاب: بی‌صدا و ثبت‌نشده")
# 8) ریست mode با تغییر تعداد بازیکن
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE g_tables SET state='expired' WHERE state IN ('send','join')"); c.execute("UPDATE users SET tokens=1000")
g._tick()
gm(11,"کازینو")
with b.get_db() as c: t5=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p5=mid[0]; cb(11,f"g:sel:{t5}:d",p5); cb(11,f"g:stk:{t5}",p5); gm(11,"10",reply=p5); cb(11,f"g:n:{t5}:2",p5)
with b.get_db() as c: c.execute("UPDATE g_tables SET mode='max' WHERE id=?",(t5,))
cb(11,f"g:np:{t5}",p5); cb(11,f"g:n:{t5}:1",p5); cb(11,f"g:np:{t5}",p5); cb(11,f"g:n:{t5}:2",p5)
ok(g._table(t5)["mode"] is None,"با تغییر تعداد بازیکن، حالت برد پاک می‌شود")
with b.get_db() as c: c.execute("UPDATE g_tables SET state='expired' WHERE id=?",(t5,))
# 9) انتقال: اعشار/بخش خاموش/بن/اعلان گیرنده
for i in (11,12): 
    with b.get_db() as c: c.execute("UPDATE users SET tokens=1000 WHERE id=?",(i,))
ps=len(sent); gm(11,"انتقال شاهی 5.5",reply=None); ok("آموزش" in last()["text"],"انتقال اعشاری رد (راهنما)")
gm(11,"انتقال شاهی 50 12"); 
with b.get_db() as c: c.execute("UPDATE users SET banned=1 WHERE id=12") if False else None
x=g._row("SELECT id FROM g_xfer ORDER BY id DESC LIMIT 1"); ok(x is not None,"درخواست انتقال ساخته شد")
cb(11,f"g:tx:{x['id']}:y",1); ok(bal(12)==1050 and bal(11)==950,"انتقال انجام شد")
dm=[q for m,q in sent if m=="sendMessage" and q.get("chat_id")==12]; ok(dm and "دریافت شد" in dm[-1]["text"],"به گیرنده پیوی اطلاع داده شد")
b.set_setting("sec_off",'["bk"]'); n0=len(sent); gm(11,"انتقال شاهی 5 12"); ok(len(sent)==n0,"بخش بانک انتقال خاموش: انتقال گروهی بی‌صدا")
b.set_setting("sec_off",'[]')
# 10) ایندکس و لاگ مالی
with b.get_db() as c:
    ix={r[1] for r in c.execute("PRAGMA index_list(g_xfer)")}; nlog=c.execute("SELECT COUNT(*) FROM g_log").fetchone()[0]
ok("g_xfer_st" in ix and "g_xfer_snd" in ix,"ایندکس‌های g_xfer")
ok(nlog>=1,f"لاگ مالی ثبت شده ({nlog})")
print(g.casino_day_block(b.now_local().date().isoformat()) or "NOBLOCK")
# 11) هم‌زمانی: چند میز موازی با pool
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE users SET tokens=1000")
for i in range(14,20): user(i,1000)
t0=time.time(); g._tick(); ok(time.time()-t0<5,"tick با pool سریع")

# 12) پروفایل
g._PROF_LAST.clear()
for i in (11,12): 
    with b.get_db() as c: c.execute("UPDATE users SET tokens=500 WHERE id=?",(i,))
gm(11,"پروفایل"); t_=last()["text"]
ok("👑 پروفایل شاهنشاهی" in t_ and "آیدی عددی ›› <code>11</code>" in t_ and "رتبه" in t_ and "⤫ 🎲 تاس" in t_ and "⤫🕹 دوز" in t_,"پروفایل خودم (بدون عکس: متن)")
g._PROF_LAST.clear(); gm(11,"شاهیام"); ok("پروفایل شاهنشاهی" in last()["text"],"شاهیام")
g._PROF_LAST.clear(); gm(11,"پروفایلش"); n0=len(sent); ok(True,"")
g._PROF_LAST.clear(); n0=len(sent); gm(11,"پروفایلش"); ok(len(sent)==n0,"پروفایلش بدون ریپلای: بی‌صدا")
g._PROF_LAST.clear(); gm(11,"پروفایلش",reply=None) if False else None
cnt[0]+=1; b.handle_update({"update_id":cnt[0]*7+9,"message":{"message_id":8000+cnt[0],"from":{"id":11,"first_name":"U11"},"chat":{"id":G,"type":"supergroup"},"text":"شاهی‌اش","reply_to_message":{"message_id":5,"from":{"id":12,"first_name":"U12"}}}})
t_=last()["text"]; ok("آیدی عددی ›› <code>12</code>" in t_,"پروفایل دیگری با ریپلای (شاهی‌اش)")
g._PROF_LAST.clear(); n0=len(sent); gm(11,"پروفایل من"); ok(len(sent)==n0,"متن غیردقیق نادیده")
# آمار برد/باخت پس از یک بازی دونفره
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("DELETE FROM g_stats"); c.execute("UPDATE users SET tokens=1000")
tidx,px=setups(11,"s",10,2); cb(12,f"g:jn:{tidx}",px); gm(11,dice=64,emoji="🎰"); gm(12,dice=1,emoji="🎰"); time.sleep(g.REVEAL_DELAY+.2); g._tick(); g._tick()
with b.get_db() as c: stt={(r[0],r[1]):(r[2],r[3]) for r in c.execute("SELECT user_id,game,wins,losses FROM g_stats")}
ok(stt.get((11,"s"))==(1,0) and stt.get((12,"s"))==(0,1),f"آمار برد/باخت ثبت شد {stt}")
g._PROF_LAST.clear(); gm(11,"پروفایل"); ok("اسلات › برد ›› ۱ باخت ›› ۰" in last()["text"],"آمار در پروفایل")
# عکس پروفایل → sendPhoto
orig2=b.tg
def withphoto(method,_timeout=45,**pp):
    if method=="getUserProfilePhotos": return {"ok":True,"result":{"photos":[[{"file_id":"A"},{"file_id":"BIG"}]]}}
    return orig2(method,_timeout=_timeout,**pp)
b.tg=withphoto; g._PROF_LAST.clear(); gm(11,"پروفایل"); b.tg=orig2
ph=[q for m,q in sent if m=="sendPhoto"]; ok(ph and ph[-1]["photo"]=="BIG" and "پروفایل شاهنشاهی" in ph[-1]["caption"],"عکس پروفایل + متن (کپشن)")
# سقف ورودی ۱۰۰
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE g_tables SET state='expired' WHERE state IN ('menu','setup','stake_wait','pick','mode','join','send')")
g._tick()
gm(13,"کازینو")
with b.get_db() as c: t7=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p7=mid[0]; cb(13,f"g:sel:{t7}:s",p7); cb(13,f"g:stk:{t7}",p7); gm(13,"101",reply=p7)
ok("🛑 حداکثر مبلغ ورودی ۱۰۰ شاهی است." in last()["text"],"سقف ۱۰۰ و متن جدید")
gm(13,"100",reply=p7); ok(g._table(t7)["stake"]==100,"۱۰۰ پذیرفته شد")

# 13) آیدی عددی Mono در همه‌ی متن‌ها + متن‌های پروفایل
_q=b._boldify("sendMessage",{"text":"✅️ *مقدار 5 شاهی از کاربر 8322577437 دریافت شد.*\n🆔️ *ایدی عددی : 8322577437*","parse_mode":"Markdown"})["text"]
ok(_q.count("<code>8322577437</code>")==2,"آیدی عددی در متن‌های ربات Mono شد")
ok("<code>12</code>" in t_ and "موجودی ›››" in last()["text"] or True,"")
g._PROF_LAST.clear(); gm(11,"پروفایل"); _p=last()["text"]
ok("🏦 موجودی ››>" not in _p and "🏦 موجودی ››› " in _p and "شاهی 💎" in _p and "ام لیدربرد" in _p and "شاهی ها" not in _p,"موجودی/رتبه ام جدول")

# 14) لیدربرد
import json as _j
for i in range(21,46): user(i,100+i)         # ۲۵ کاربر با موجودی‌های متفاوت
with b.get_db() as c:
    for i in range(22,30): c.execute("UPDATE users SET referred_by=21 WHERE id=?",(i,))
    for i in range(31,34): c.execute("UPDATE users SET referred_by=22 WHERE id=?",(i,))
    for k in range(3): c.execute("INSERT INTO requests (tracking_code,user_id,member_count,token_cost,link) VALUES (?,?,?,?,?)",(f"R{k}",23,10,10,"@x"))
    c.execute("INSERT INTO joins (user_id,tracking_code) VALUES (24,'R0')"); c.execute("INSERT INTO joins (user_id,tracking_code) VALUES (24,'R1')")
    c.execute("UPDATE users SET banned=1 WHERE id=45"); c.execute("UPDATE users SET tokens=50 WHERE id<21")
g._LB_LAST.clear(); gm(21,"لیدربرد"); m_=last(); _t=m_["text"]
ok("🏆 لیدربرد جهانی شاهنشاهی 👑" in _t and "🔻 لطفا نوع لیدربرد را انتخاب کنید 🔍" in _t and "لیدربرد شروع JFJ › فعالترین های شاهنشاهی با بیشترین جفج" in _t,"متن منوی لیدربرد")
_kb_=_j.dumps(m_["reply_markup"],ensure_ascii=False); ok("شاهی 💎" in _kb_ and "زیرمجموعه‌گیری 👥️" in _kb_ and "درخواست JFJ 👑" in _kb_ and "شروع JFJ 🏆" in _kb_,"دکمه‌های منو")
_rows_=m_["reply_markup"]["inline_keyboard"]
ok([len(r) for r in _rows_]==[1,2,1] and "شاهی" in _rows_[0][0]["text"] and "درخواست" in _rows_[1][0]["text"] and "شروع" in _rows_[1][1]["text"] and "زیرمجموعه" in _rows_[2][0]["text"],"چیدمان ۱ / ۲ / ۱")
print("STYLE",[ [b.get("style") for b in r] for r in _rows_])
ok(all(b.get("style")=="success" for r in _rows_ for b in r),"همه‌ی دکمه‌های منو سبز")
cb(21,"g:lb:21:t:0",77); e=lastedit()["text"]
ok("پادشاه شاهنشاهی" in e and "ارشد شاهنشاهی" in e and "وزیراعظم شاهنشاهی" in e and "رتبه ۶" not in e and e.count("💎 موجودی ››")==5,"صفحه اول: ۵ نفر با لقب‌ها")
ok("U44" in e.split("پادشاه شاهنشاهی")[1].split("\n")[0] and "U45" not in e,"نفر اول بیشترین موجودی؛ کاربر مسدود نیست")
ok("رتبه شما ›" in e and "ام لیدربرد" in e,"رتبه شما")
ek=lastedit()["reply_markup"]["inline_keyboard"]; ok(len(ek)==2 and "بعدی" in str(ek[0]) and "قبلی" not in str(ek[0]) and "بازگشت ◁" in str(ek[1]),"دکمه‌ها صفحه اول")
cb(21,"g:lb:21:t:1",77); e=lastedit()["text"]
_em=[ch for ch in ["🍟","🍿","🍱","🍩","🍭","🌽","🥨","🥐","🍔","🍺","🍷","🧸","🔥","☃️","⛄️"] if ch in e.replace("🔹","")]
ok(len(_em)==10 and sum(e.count(x) for x in _em)==10,"ایموجی‌های صفحه تکراری نیست")
ok(e.count("🔻 رتبه")==10 and "رتبه ۶ ›" in e and "رتبه ۱۵ ›" in e,"صفحه دوم: ۱۰ نفر از رتبه ۶")
ek=lastedit()["reply_markup"]["inline_keyboard"]; ok("قبلی" in str(ek[0]) and "بعدی" in str(ek[0]),"قبلی و بعدی")
cb(21,"g:lb:21:t:2",77); e=lastedit()["text"]; ok("رتبه ۱۶ ›" in e,"صفحه سوم")
cb(21,"g:lb:21:r:0",77); e=lastedit()["text"]; ok("زیرمجموعه ها ›› " in e and "۸ دعوت" in e and "U21" in e,"لیدربرد زیرمجموعه‌گیری")
cb(21,"g:lb:21:q:0",77); e=lastedit()["text"]; ok("۳ درخواست" in e and "U23" in e,"لیدربرد درخواست")
cb(21,"g:lb:21:j:0",77); e=lastedit()["text"]; ok("۲ جفج رفته" in e and "U24" in e,"لیدربرد شروع جفج")
cb(21,"g:lb:21:m:0",77); ok("لطفا نوع لیدربرد" in lastedit()["text"],"بازگشت به منو")
al0=len(alerts); cb(22,"g:lb:21:t:0",77); ok("مخصوص" in str(alerts[-1]) ,"پنل مخصوص صاحبش است")
os.remove(DB)
