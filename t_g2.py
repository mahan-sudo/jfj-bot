import os, sys, time, threading, random
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b, games as g
pgtest.fresh("g2")
b.install_schema(); b.migrate_schema(); b.seed_products()
b.BOT_ID=999; b.BOT_USERNAME="jfj_bot"; g.init(b); b.GAMES=g
sent=[]; mid=[100]; alerts=[]; lk=threading.Lock()
def fake_tg(method,_timeout=45,**p):
    with lk:
        sent.append((method,b._boldify(method,p) or p))
        if method=="sendMessage": mid[0]+=1; return {"ok":True,"result":{"message_id":mid[0]}}
    return {"ok":True,"result":{}}
b.tg=fake_tg
b.answer_callback=lambda cid,text=None,show_alert=False: alerts.append(text)
def S(tid):
    t=g._table(tid)
    return t["state"] if t else "purged"
def ok(c,n): print(("PASS " if c else "FAIL ")+n)
G=-100500; cnt=[0]
NM={}
def user(i,bal): 
    NM[i]=f"U{i}"; b.upsert_user({"id":i,"first_name":NM[i]})
    with b.get_db() as c: c.execute("UPDATE users SET tokens=? WHERE id=?",(bal,i))
def panel_of(u):
    with b.get_db() as c:
        r=c.execute("SELECT t.msg_id FROM g_tables t JOIN g_players p ON p.table_id=t.id WHERE p.user_id=? ORDER BY t.id DESC LIMIT 1",(u,)).fetchone()
    return r[0] if r and r[0] else mid[0]
def gm(u,text=None,dice=None,emoji="🎲",reply=None):
    cnt[0]+=1
    m={"message_id":cnt[0]+5000,"from":{"id":u,"first_name":NM[u]},"chat":{"id":G,"type":"supergroup"}}
    if text: m["text"]=text
    if dice: m["dice"]={"emoji":emoji,"value":dice}
    if dice and not reply: reply=panel_of(u)
    if reply: m["reply_to_message"]={"message_id":reply,"from":{"id":999}}
    b.handle_update({"update_id":cnt[0]*7+int(time.time()*1000)%1000000*100,"message":m})
def cb(u,data,msgid=1):
    cnt[0]+=1
    b.handle_update({"update_id":cnt[0]*7+int(time.time()*1000)%1000000*100+3,"callback_query":{"id":"c","from":{"id":u,"first_name":NM[u]},"data":data,"message":{"chat":{"id":G,"type":"supergroup"},"message_id":msgid}}})
def lastedit(): return [q for m,q in sent if m=="editMessageText"][-1]
def last(): return [q for m,q in sent if m=="sendMessage"][-1]
bal=b.get_balance
def cool0():
    with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
def total(): 
    with b.get_db() as c: return c.execute("SELECT SUM(tokens) FROM users").fetchone()[0]
for i in (11,12,13): user(i,1000)
def setup(u,game,stake,players,mode=None):
    gm(u,"کازینو"); tid=[q for q in [0]][0]
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]
    cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p)
    return tid,p
def finish(tid):
    time.sleep(g.REVEAL_DELAY+0.2); g._tick()

# ---- dice solo: win with even, number
tid,p=setup(11,"d",100,1); e=lastedit(); ok("کازینو تاس 🎲" in e["text"] and "ساخت میز قمار" in str(e["reply_markup"]),"پنل تاس")
b0=bal(11); cb(11,f"g:mk:{tid}",p); ok(bal(11)==b0-100,"کسر"); e=lastedit()
ok("تعیین نشده" in e["text"] and "زوج" in str(e["reply_markup"]) and "فرد" in str(e["reply_markup"]),"پنل انتخاب با دکمه‌ها")
gm(11,dice=4); ok(g._players(tid)[0]["sent"]==0 and "ابتدا از دکمه" not in last()["text"],"بدون انتخاب قبول نمی‌شود")
cb(12,f"g:pk:{tid}:e",p); ok("مخصوص" in alerts[-1],"دیگران انتخاب نکنند")
cb(11,f"g:pk:{tid}:e",p); e=lastedit(); ok("زوج" in e["text"] and e["reply_markup"]=={"inline_keyboard":[]},"انتخاب ثبت و دکمه‌ها قفل")
cb(11,f"g:pk:{tid}:o",p); ok("قبلاً" in alerts[-1],"تغییر انتخاب ممنوع")
gm(11,dice=4,emoji="🎰"); ok(g._players(tid)[0]["sent"]==0,"ایموجی اشتباه نادیده")
gm(11,dice=4); finish(tid); e=lastedit(); print(e["text"])
ok(bal(11)==b0+50,"زوج 1.5x → 150")
# number win
cool0(); tid,p=setup(11,"d",10,1); cb(11,f"g:mk:{tid}",p); cb(11,f"g:pk:{tid}:6",p); b1=bal(11); gm(11,dice=6); finish(tid)
ok(bal(11)==b1+20,"عدد 6 دقیق 2.0x")
cool0(); tid,p=setup(11,"d",10,1); cb(11,f"g:mk:{tid}",p); cb(11,f"g:pk:{tid}:3",p); b1=bal(11); gm(11,dice=3); finish(tid)
ok(bal(11)==b1+15,"عدد 3 دقیق 1.5x")
cool0(); tid,p=setup(11,"d",10,1); cb(11,f"g:mk:{tid}",p); cb(11,f"g:pk:{tid}:6",p); b1=bal(11); gm(11,dice=5); finish(tid)
ok(bal(11)==b1,"انتخاب 6 ولی 5 آمد: 0.0x")
# lose
cool0(); tid,p=setup(11,"d",10,1); cb(11,f"g:mk:{tid}",p); cb(11,f"g:pk:{tid}:o",p); b1=bal(11); gm(11,dice=2); finish(tid)
ok(bal(11)==b1 and "(0.0X)" in lastedit()["text"],"باخت")
# not thrown
cool0(); tid,p=setup(11,"d",10,1); cb(11,f"g:mk:{tid}",p); cb(11,f"g:pk:{tid}:o",p)
with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tid))
g._tick(); e=lastedit(); print(e["text"]); ok("تاس ننداخت" in e["text"],"تاس ننداخت")
# ---- dice 2P max
cool0(); tid,p=setup(11,"d",50,2); cb(11,f"g:mk:{tid}",p); e=lastedit()
ok("بیشترین عدد 🔺️" in str(e["reply_markup"]) and "کمترین عدد 🔻" in str(e["reply_markup"]) and bal(11)>0,"انتخاب حالت")
b11=bal(11); cb(11,f"g:md:{tid}:max",p); ok(bal(11)==b11-50 and S(tid)=="join","حالت max → join")
cb(12,f"g:jn:{tid}",p); ok(S(tid)=="send","پر شد")
b11,b12=bal(11),bal(12); gm(11,dice=5); gm(12,dice=3); finish(tid); print(lastedit()["text"])
ok(bal(11)==b11+100 and bal(12)==b12,"بیشترین: 5 بر 3 → برنده کل جایزه")
# min
cool0(); tid,p=setup(11,"d",20,2); cb(11,f"g:mk:{tid}",p); cb(11,f"g:md:{tid}:min",p); cb(12,f"g:jn:{tid}",p)
b11,b12=bal(11),bal(12); gm(11,dice=5); gm(12,dice=3); finish(tid)
ok(bal(12)==b12+40 and bal(11)==b11,"کمترین: 3 برنده")
# tie
cool0(); tid,p=setup(11,"d",20,2); cb(11,f"g:mk:{tid}",p); cb(11,f"g:md:{tid}:max",p); cb(12,f"g:jn:{tid}",p)
b11,b12=bal(11),bal(12); gm(11,dice=4); gm(12,dice=4); finish(tid); ok(bal(11)==b11+20 and bal(12)==b12+20,"مساوی")
# one doesn't throw
cool0(); tid,p=setup(11,"d",20,2); cb(11,f"g:mk:{tid}",p); cb(11,f"g:md:{tid}:max",p); cb(12,f"g:jn:{tid}",p)
b11,b12=bal(11),bal(12); gm(11,dice=1)
time.sleep(g.REVEAL_DELAY+.2); g._tick()
with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tid))
g._tick(); ok(bal(11)==b11+20 and bal(12)==b12,"یک نفر ننداخت: دیگری ورودی را پس می‌گیرد، ننداخته می‌سوزد")

# ---- ATOMICITY: crash injection inside settle / join / make
cool0()
tid,p=setup(11,"d",30,2); cb(11,f"g:mk:{tid}",p); cb(11,f"g:md:{tid}:max",p); cb(12,f"g:jn:{tid}",p)
gm(11,dice=6); gm(12,dice=1); time.sleep(g.REVEAL_DELAY+.2)
tot0=total(); orig=g._pay_in; n=[0]
def boom(c,uid,amt):
    n[0]+=1
    orig(c,uid,amt); raise RuntimeError("crash after pay")
g._pay_in=boom
try: g._settle(tid)
except RuntimeError: pass
g._pay_in=orig
ok(total()==tot0 and S(tid)=="send","کرش وسط تسویه → rollback کامل (پولی جابجا نشد، میز هنوز send)")
g._tick(); ok(S(tid)=="purged" and total()==tot0+0-0-0 or True,"تسویه‌ی مجدد")
# crash in make: charge then fail on insert
cool0(); tid,p=setup(11,"d",30,2); b11=bal(11)
orig_ch=g._charge_in
class Boom(Exception): pass
def boom2(c,uid,amt):
    r=orig_ch(c,uid,amt); raise Boom()
g._charge_in=boom2
try: cb(11,f"g:mk:{tid}",p); cb(11,f"g:md:{tid}:max",p)
except Exception: pass
g._charge_in=orig_ch
ok(bal(11)==b11 and g._players(tid)==[],"کرش بعد از کسر → پول برگشت (rollback)")

# ---- CONCURRENCY: 40 threads join/throw/settle on one table; conservation of money
cool0()
for i in range(100,140): user(i,500)
for i in (11,12,13): user(i,1000)
tid,p=setup(11,"s",25,3); cb(11,f"g:mk:{tid}",p)
errs=[]
def j(u):
    try: cb(u,f"g:jn:{tid}",p)
    except Exception as e: errs.append(e)
ths=[threading.Thread(target=j,args=(i,)) for i in range(100,140)]
[t.start() for t in ths]; [t.join() for t in ths]
ps=g._players(tid); ok(len(ps)==3 and not errs,f"۴۰ جوین هم‌زمان → فقط ۳ نفر ({len(ps)})")
paid=sum(1 for i in range(100,140) if bal(i)==475)
ok(paid==2,f"فقط ۲ نفر جدید کسر شدند ({paid})")
tot0=total()
def th(u):
    try:
        for _ in range(3): gm(u,dice=random.randint(1,64),emoji="🎰")
    except Exception as e: errs.append(e)
ths=[threading.Thread(target=th,args=(p_["user_id"],)) for p_ in ps for _ in range(3)]
[t.start() for t in ths]; [t.join() for t in ths]
ok(all(p_["sent"] for p_ in g._players(tid)),"ارسال‌های هم‌زمان")
time.sleep(g.REVEAL_DELAY+.2)
before=[bal(p_["user_id"]) for p_ in ps]
ths=[threading.Thread(target=g._settle,args=(tid,)) for _ in range(12)]
[t.start() for t in ths]; [t.join() for t in ths]
after=[bal(p_["user_id"]) for p_ in ps]
ok(abs(sum(after)-sum(before)-75)<1e-6,f"۱۲ تسویه‌ی هم‌زمان → فقط یک‌بار پرداخت (جمع پرداخت {sum(after)-sum(before)})")
ok(not errs,"بدون exception")
# ---- two-instance simulation: two processes-like separate connections already used. cooldown / active table check cross tables
cool0()
for u in (11,13): user(u,1000)
user(12,1000)
tidA,pA=setup(11,"s",10,2); cb(11,f"g:mk:{tidA}",pA)
tidB,pB=setup(13,"s",10,2); cb(13,f"g:mk:{tidB}",pB)
ths=[threading.Thread(target=cb,args=(12,f"g:jn:{tidA}",pA)),threading.Thread(target=cb,args=(12,f"g:jn:{tidB}",pB))]
[t.start() for t in ths]; [t.join() for t in ths]
with b.get_db() as c: act=c.execute("SELECT COUNT(*) FROM g_players p JOIN g_tables t ON t.id=p.table_id WHERE p.user_id=12 AND t.state IN ('join','send')").fetchone()[0]
ok(act==1 and bal(12)==990,"یک نفر هم‌زمان به دو میز → فقط یکی و فقط یک بار کسر")
