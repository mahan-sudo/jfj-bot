exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
def setups(u,game,stake,players):
    gm(u,"کازینو")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]; cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p); 
    return tid,p
def cnt_rows():
    with b.get_db() as c: return c.execute("SELECT (SELECT COUNT(*) FROM g_tables),(SELECT COUNT(*) FROM g_players)").fetchone()
# 4) triggers exact
n=len(sent)
for bad in ("کازینول","سلام کازینو","دوزل","کازینو شاهنشاهی","دوز شاهنشاهی","کازینو  شاهی ؟"): gm(13,bad)
ok(len(sent)==n,"فقط متن دقیق؛ شبیه‌ها پاسخ نمی‌گیرند")
gm(13,"  کازینو  "); ok("🃏 کازینو شاهنشاهی 👑" in last()["text"],"متن دقیق (با فاصله‌ی دور) جواب می‌گیرد")
gm(13,"دوز"); ok("دوز شاهنشاهی XO" in last()["text"],"دوز")
# 1) تعیین بی‌رنگ
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
kb=last()["reply_markup"]["inline_keyboard"]
ok("style" not in kb[0][0] and "تعیین" in kb[0][0]["text"] and kb[1][0].get("style")=="danger","تعیین بی‌رنگ، بازگشت قرمز")
cb(13,f"g:cx:{tid}",mid[0])
# 2) ایموجی یکتا + 3) پنل ارسال چندنفره + 7) مساوی
bad=0
for trial in range(20):
    with b.get_db() as c: c.execute("DELETE FROM g_cool")
    for i in (11,12,13): user(i,1000)
    tid,p=setups(11,"s",20,3); cb(11,f"g:mk:{tid}",p); cb(12,f"g:jn:{tid}",p); cb(13,f"g:jn:{tid}",p)
    emos=[x["emo"] for x in g._players(tid)]
    if len(set(emos))!=3: bad+=1
    if trial==0:
        e=lastedit(); print(e["text"])
        ok("⬜️ ⬜️ ⬜️ ..." in e["text"] and "هنوز خالیه" in e["text"] and e["text"].count("👑 بازیکن ››")==3 and "🎰 کازینو گردونه شانس 🃏" in e["text"],"پنل ارسال چندنفره طبق متن جدید")
        gm(11,dice=22,emoji="🎰"); time.sleep(g.REVEAL_DELAY+.2); g._tick(); print(lastedit()["text"])
    # finish quickly: all send same triple → draw
    for u in (11,12,13): gm(u,dice=22,emoji="🎰") if g._players(tid) and not [x for x in g._players(tid) if x["user_id"]==u and x["sent"]] else None
    time.sleep(g.REVEAL_DELAY+.2); g._tick()
    if trial==0: t_=lastedit()["text"]; print(t_)
ok(bad==0,"ایموجی بازیکن‌های یک میز هیچ‌وقت تکراری نیست (۲۰ تکرار)")
ok("🃏 بازی مساوی شد ، مبلغ به کیف پول بازمیگردد." in t_ and "مساوی ›››" not in t_,"متن مساوی جدید")
ok(bal(11)==1000 and bal(12)==1000 and bal(13)==1000,"مساوی: ورودی هر ۳ نفر برگشت")
# 5) purge
ok(cnt_rows()==(0,0),f"بعد از پایان بازی‌ها هیچ ردی در دیتابیس نمی‌ماند {cnt_rows()}")
# 6) شبکه کند نباید قفل دیتابیس را نگه دارد
g._purge=g._purge
orig_ans=b.answer_callback
def slow(cid,text=None,show_alert=False):
    time.sleep(1.5)
b.answer_callback=slow
with b.get_db() as c: c.execute("DELETE FROM g_cool")
gm(11,"کازینو")
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
t0=time.time()
th=threading.Thread(target=cb,args=(12,f"g:sel:{tid}:s",mid[0]))   # غریبه → alert کند
th.start(); time.sleep(0.2)
t1=time.time()
with b.get_db() as c: c.execute("BEGIN IMMEDIATE"); c.execute("UPDATE users SET tokens=tokens WHERE id=11"); c.commit()
dt=time.time()-t1
th.join(); ok(dt<0.5,f"callback کند، قفل نوشتن را نگه نمی‌دارد (انتظار نوشتن دیگر: {dt:.2f}s)")
b.answer_callback=orig_ans
# اگر یک میز خراب شود بقیه کار کنند
with b.get_db() as c:
    c.execute("DELETE FROM g_cool")
    c.execute("INSERT INTO g_tables (chat_id,owner,owner_name,state,stake,maxp,send_dl,touched,created,game) VALUES (1,11,'x','send',10,1,0,0,0,'s')")
g._tick(); ok(True,"میز خراب (بدون بازیکن) کل tick را نمی‌خواباند")
os.remove(DB)
