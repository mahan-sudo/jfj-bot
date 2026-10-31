exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
user(14,0) if False else None
NM[14]="New"
ADM=b.ADMIN_IDS[0]
def rmsg(u,text,to=None,topic=False,**kw):
    cnt[0]+=1
    m={"message_id":cnt[0]+9000,"from":{"id":u,"first_name":NM[u]},"chat":{"id":G,"type":"supergroup"},"text":text}
    if to is not None: m["reply_to_message"]={"message_id":7,"from":{"id":to,"first_name":NM.get(to,"?"),"is_bot":False}}
    if topic: m["reply_to_message"]={"message_id":1,"forum_topic_created":{"name":"t"},"from":{"id":11,"first_name":"Ali"}}
    m.update(kw)
    b.handle_update({"update_id":cnt[0]*7+int(time.time()*1000)%1000000*100,"message":m})
def lastsend(): return [q for m,q in sent if m=="sendMessage"][-1]
def inbot(i): return b.user_exists(i)
# راهنما
for t in ("انتقال","انتقال شاهی","انتقال شاهی 10","انتقال شاهی abc"):
    n=len(sent); rmsg(11,t); ok(len(sent)==n+1 and "آموزش استفاده درست" in lastsend()["text"],f"راهنما برای «{t}»")
n=len(sent); rmsg(11,"انتقال دادم دیشب"); ok(len(sent)==n,"گفتگوی عادی نادیده")
# عضو نیست
n=len(sent); rmsg(11,"انتقال شاهی 10",to=99); ok("کاربر عضو ربات نیست" in lastsend()["text"],"کاربر ناعضو")
rmsg(11,"انتقال شاهی 10 @nobody"); ok("کاربر عضو ربات نیست" in lastsend()["text"],"یوزرنیم ناشناس")
# حداقل / موجودی / خود
rmsg(11,"انتقال شاهی 1",to=12); ok("حداقل" in lastsend()["text"],"زیر حداقل")
rmsg(11,"انتقال شاهی 99999",to=12); ok("موجودی" in lastsend()["text"],"موجودی کم")
rmsg(11,"انتقال شاهی 10",to=11); ok("خودتان" in lastsend()["text"],"به خود")
# جریان موفق (با ارقام فارسی)
b11,b12=bal(11),bal(12)
rmsg(11,"انتقال شاهی ۲۵",to=12); e=lastsend(); print(e["text"]); print(e["reply_markup"])
ok("آیا از انتقال شاهی هاتون اطمینان دارید" in e["text"] and "مبلغ درحال انتقال ›› ۲۵ شاهی" in e["text"] and 'tg://user?id=11' in e["text"] and 'tg://user?id=12' in e["text"],"پنل تایید")
kb=e["reply_markup"]["inline_keyboard"][0]; ok(kb[0]["style"]=="danger" and kb[1]["style"]=="success","❌ قرمز، ✅ سبز")
with b.get_db() as c: xid=c.execute("SELECT MAX(id) FROM g_xfer").fetchone()[0]
cb(12,f"g:tx:{xid}:y",1); ok("فقط انتقال‌دهنده" in alerts[-1] and bal(11)==b11,"غیرفرستنده نمی‌تواند")
cb(11,f"g:tx:{xid}:y",1); ok(bal(11)==b11-25 and bal(12)==b12+25,"انتقال انجام شد")
r=lastedit(); print(r["text"]); ok("رسید انتقال شاهی" in r["text"] and "با موفقیت انتقال یافت. ✅" in r["text"],"رسید")
cb(11,f"g:tx:{xid}:y",1); ok("معتبر نیست" in alerts[-1] and bal(11)==b11-25,"کلیک دوباره: دوباره انتقال نمی‌شود")
with b.get_db() as c: ok(c.execute("SELECT COUNT(*) FROM g_xfer WHERE state='done'").fetchone()[0]==1 and c.execute("SELECT COUNT(*) FROM g_xfer WHERE state='pending'").fetchone()[0]==0 and c.execute("SELECT COUNT(*) FROM transfers WHERE amount=25").fetchone()[0]==1,"رسید done ماندگار است و لاگ transfers ثبت شد")
# لغو
b11=bal(11); rmsg(11,"انتقال شاهی 10",to=12)
with b.get_db() as c: xid=c.execute("SELECT MAX(id) FROM g_xfer").fetchone()[0]
cb(11,f"g:tx:{xid}:n",1); ok("🛑 انتقال شاهی لغو شد." in lastedit()["text"] and bal(11)==b11,"لغو")
# 60 ثانیه
rmsg(11,"انتقال شاهی 10",to=12)
with b.get_db() as c: xid=c.execute("SELECT MAX(id) FROM g_xfer").fetchone()[0]; c.execute("UPDATE g_xfer SET deadline=?",(time.time()-1,))
cb(11,f"g:tx:{xid}:y",1); ok(bal(11)==b11 and "معتبر نیست" in alerts[-1],"بعد از ۶۰ ثانیه تایید رد می‌شود")
g._tick(); ok("🛑 انتقال شاهی خودکار لغو شد." in lastedit()["text"],"لغو خودکار")
# یوزرنیم / آیدی عددی
with b.get_db() as c: c.execute("UPDATE users SET username='sara_x' WHERE id=12")
b11,b12=bal(11),bal(12)
rmsg(11,"انتقال شاهی 5 @Sara_X"); ok("آیا از انتقال" in lastsend()["text"],"با @یوزرنیم")
rmsg(11,"انتقال شاهی 5 12"); ok("آیا از انتقال" in lastsend()["text"],"با آیدی عددی")
with b.get_db() as c: ok(c.execute("SELECT COUNT(*) FROM g_xfer WHERE state='pending'").fetchone()[0]==1,"فقط یک پنل در انتظار برای هر فرستنده")
# تاپیک: ریپلای به پیام ساخت تاپیک = بدون ریپلای
n=len(sent); rmsg(11,"انتقال شاهی 5",topic=True); ok("آموزش" in lastsend()["text"],"ریپلای به سرتاپیک هدف حساب نمی‌شود")
# هم‌زمانی: ۳۰ کلیک ✅ هم‌زمان
rmsg(11,"انتقال شاهی 40",to=12)
with b.get_db() as c: xid=c.execute("SELECT MAX(id) FROM g_xfer").fetchone()[0]
t0=total(); b11,b12=bal(11),bal(12)
ths=[threading.Thread(target=cb,args=(11,f"g:tx:{xid}:y",1)) for _ in range(30)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(bal(11)==b11-40 and bal(12)==b12+40 and total()==t0,"۳۰ تایید هم‌زمان = فقط یک انتقال")
# کرش وسط تایید
rmsg(11,"انتقال شاهی 40",to=12)
with b.get_db() as c: xid=c.execute("SELECT MAX(id) FROM g_xfer").fetchone()[0]
b11,b12=bal(11),bal(12); orig=g._pay_in
def boom(c,u_,a): orig(c,u_,a); raise RuntimeError("x")
g._pay_in=boom
try: cb(11,f"g:tx:{xid}:y",1)
except Exception: pass
g._pay_in=orig
with b.get_db() as c: pend=c.execute("SELECT COUNT(*) FROM g_xfer WHERE state='pending'").fetchone()[0]
ok(bal(11)==b11 and bal(12)==b12 and pend==1,"کرش وسط انتقال → rollback کامل")
# کلید ادمین
b.set_setting("g_t_on","0"); n=len(sent); rmsg(11,"انتقال شاهی 5",to=12); rmsg(11,"انتقال"); ok(len(sent)==n,"خاموش: بی‌صدا")
b.set_setting("g_t_on","1")
t,kb=b.render_games(); ok("gmt:t" in str(kb) and "انتقال شاهی در گروه" in t,"کلید در پنل ادمین")
# حداقل از تنظیم ربات
b.MIN_TRANSFER_AMOUNT=50; rmsg(11,"انتقال شاهی 10",to=12); ok("حداقل مبلغ انتقال ۵۰" in lastsend()["text"],"حداقل همان تنظیم بانک ربات است")
os.remove(DB)
