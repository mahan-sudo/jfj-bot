exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
ADM=b.ADMIN_IDS[0]
def admcb(data):
    b.v2_admin_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
def adm_text(text):
    b.handle_update({"update_id":int(time.time()*1000000)%10**12,"message":{"message_id":9,"from":{"id":ADM,"first_name":"A"},"chat":{"id":ADM,"type":"private"},"text":text}})
def setups(u,game,stake,players):
    gm(u,"کازینو")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]; cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p); cb(u,f"g:mk:{tid}",p)
    return tid,p
for i in (11,12,13): user(i,1000)
b.upsert_user({"id":ADM,"first_name":"Admin"})
# صفحه‌ی اصلی
t,kb=b.render_games(); k=str(kb)
ok(all(x in k for x in ("gx_cfg","gx_rep","gx_act","gx_find","gmt:l","gmt:p")),"دکمه‌های پنل جامع")
# تنظیمات
admcb("adm_p:x:gx_cfg"); e=lastedit()["text"] if sent and sent[-1][0]=="editMessageText" else ""
ok("تنظیمات بازی‌ها" in e and "حداکثر مبلغ ورودی" in e and "۱۰۰" in e,"صفحه‌ی تنظیمات")
admcb("adm_p:x:gx_set:max"); ok(b.get_state(ADM)[0]=="adm_in","ورود به حالت ویرایش")
adm_text("250"); ok(g.cv("max")==250 and b.get_setting("casino_max")=="250","حداکثر ورودی ۲۵۰ شد")
# اعمال واقعی: مبلغ ۲۰۰ پذیرفته می‌شود و ۳۰۰ رد
gm(11,"کازینو")
with b.get_db() as c: t1=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p1=mid[0]; cb(11,f"g:sel:{t1}:s",p1); cb(11,f"g:stk:{t1}",p1); gm(11,"300",reply=p1); ok("۲۵۰" in last()["text"] and "حداکثر" in last()["text"],"سقف جدید اعمال شد")
gm(11,"200",reply=p1); ok(g._table(t1)["stake"]==200,"۲۰۰ قبول")
cb(11,f"g:cx:{t1}",p1)
# اعتبارسنجی
admcb("adm_p:x:gx_set:min"); adm_text("999"); ok(g.cv("min")==5,"حداقل بیشتر از حداکثر: رد")
admcb("adm_p:x:gx_set:join"); adm_text("abc"); ok(g.cv("join")==60,"ورودی نامعتبر رد")
admcb("adm_p:x:gx_set:join"); adm_text("5"); ok(g.cv("join")==60,"خارج از بازه رد")
admcb("adm_p:x:gx_set:join"); adm_text("30"); ok(g.cv("join")==30,"مهلت پیوستن ۳۰")
admcb("adm_p:x:gx_set:dp"); adm_text("1.8"); ok(g.cv("dp")==1.8 and g.dice_solo_mult("e",2)==1.8,"ضریب تاس تغییر کرد")
admcb("adm_p:x:gx_rst"); ok(g.cv("max")==100 and g.cv("join")==60 and g.cv("dp")==1.5,"بازگشت به پیش‌فرض")
# میز فعال + بستن
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE users SET tokens=1000")
tid,p=setups(11,"s",10,2); cb(12,f"g:jn:{tid}",p); ok(bal(11)==990 and bal(12)==990,"دو نفر روی میز")
admcb("adm_p:x:gx_act"); e=lastedit()["text"]; ok(f"#{tid}" in e and "بستن" in str(lastedit()["reply_markup"]),"لیست میزهای فعال")
admcb(f"adm_p:x:gx_close:{tid}"); ok(S(tid)=="purged" and bal(11)==1000 and bal(12)==1000,"بستن میز: پول همه برگشت")
ok("توسط مدیریت بسته شد" in [q for m,q in sent if m=="editMessageText" and "مدیریت" in q.get("text","")][-1]["text"],"پیام میز به‌روز شد")
with b.get_db() as c: ok(c.execute("SELECT COUNT(*) FROM g_log WHERE kind='admin'").fetchone()[0]==1,"ثبت در دفتر مالی")
# بستن همه
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
t1_,pp=setups(11,"s",10,2); cb(12,f"g:jn:{t1_}",pp)
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
t2_,pq=setups(13,"d",10,2); cb(13,f"g:mk:{t2_}",pq); cb(13,f"g:md:{t2_}:max",pq)
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
cb(12,f"g:jn:{t2_}",pq) if False else None

admcb("adm_p:x:gx_closeall"); ok(S(t1_)=="purged" and S(t2_)=="purged" and bal(11)==1000 and bal(12)==1000 and bal(13)==1000,"بستن همه با بازگشت پول")
# گزارش
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
tid,p=setups(11,"s",10,2); cb(12,f"g:jn:{tid}",p); gm(11,dice=64,emoji="🎰"); gm(12,dice=1,emoji="🎰"); time.sleep(g.REVEAL_DELAY+.2); g._tick(); g._tick()
for d in (1,7,30):
    admcb(f"adm_p:x:gx_rep:{d}"); e=lastedit()["text"]; ok("گزارش بازی‌های گروهی" in e and "گردونه" in e and "بازیکنان یکتا" in e,f"گزارش {d} روزه")
ok("۱</b> بازی" in e,"آمار گزارش")
# جستجوی بازیکن
admcb("adm_p:x:gx_find"); adm_text("11"); pg=[q for m,q in sent if m=="sendMessage" and q.get("chat_id")==ADM][-1]["text"]
ok("آخرین بازی‌ها" in pg and "<code>11</code>" in pg and "برد ۱" in pg,"صفحه‌ی بازیکن")
admcb("adm_p:x:gx_find"); adm_text("999999"); ok("پیدا نشد" in [q for m,q in sent if m=="sendMessage" and q.get("chat_id")==ADM][-1]["text"],"کاربر ناموجود")
# ریست کول‌داون
with b.get_db() as c: c.execute("INSERT OR REPLACE INTO g_cool VALUES (11,?)",(time.time(),))
admcb("adm_p:x:gx_cdr:11"); ok(g._cool_left(11)==0,"ریست کول‌داون")
# محرومیت از بازی
admcb("adm_p:x:gx_ban:11"); ok(g.gbanned(11),"محروم شد")
n0=len(sent); gm(11,"کازینو"); ok(len(sent)==n0,"محروم: بی‌صدا")
gm(11,"پروفایل"); ok(len(sent)>n0,"پروفایل برای محروم از بازی کار می‌کند")
admcb("adm_p:x:gx_ban:11"); ok(not g.gbanned(11),"رفع محرومیت")
# خاموش/روشن لیدربرد و پروفایل
g._LB_LAST.clear(); g._PROF_LAST.clear()
admcb("adm_p:x:gmt:l"); admcb("adm_p:x:gmt:p"); n0=len(sent); gm(12,"لیدربرد"); gm(12,"پروفایل"); ok(len(sent)==n0,"لیدربرد/پروفایل خاموش: بی‌صدا")
admcb("adm_p:x:gmt:l"); admcb("adm_p:x:gmt:p"); g._LB_LAST.clear(); gm(12,"لیدربرد"); ok("لیدربرد جهانی" in last()["text"],"روشن شد")
# رتبه دقیق با مساوی
for i in range(21,31): user(i,500)
with b.get_db() as c: c.execute("UPDATE users SET tokens=5 WHERE id<21"); c.execute("UPDATE users SET banned=1 WHERE id=25")
g._LB_LAST.clear(); g._PROF_LAST.clear(); rk=g._lb_rank("t",28)
rows=g._rows(g._LB_SQL["t"][0],(100,)); pos=[r["uid"] for r in rows].index(28)+1
ok(rk==pos,f"رتبه = جایگاه واقعی در لیست ({rk}=={pos})")
gm(28,"پروفایل"); ok(f"{g._n(pos)}ام لیدربرد" in last()["text"],"پروفایل همان رتبه")
cb(28,"g:lb:28:t:0",77); e=lastedit()["text"]; ok(f"{g._n(pos)}ام لیدربرد" in e,"لیدربرد همان رتبه (در صفحه‌ی اول یا در هر صفحه)")
# ورود از کیبورد اصلی پنل مدیریت
n0=len(sent); adm_text("🃏 بازی‌های گروهی")
q=[q for m_,q in sent[n0:] if m_=="sendMessage" and q.get("chat_id")==ADM]
ok(q and "بازی‌های گروهی" in q[-1]["text"] and "gx_cfg" in str(q[-1]["reply_markup"]) and "adm_p:g:home" not in str(q[-1]["reply_markup"]),"کیبورد اصلی: باز شدن صفحه‌ی بازی‌ها بدون دکمه‌ی بازگشت قدیمی")
os.remove(DB)
