import os, sys, time, threading, random
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b, games as g
pgtest.fresh("x")
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


def setupx(u,stake):
    gm(u,"دوز")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]
    cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p)
    return tid,p
def cell(u,tid,p,i): cb(u,f"g:xo:{tid}:{i}",p)
def roles(tid): return {x["user_id"]:x["pick"] for x in g._players(tid)}
def play(tid,p,moves):  # moves: list of (user,cell)
    for u,i in moves: cell(u,tid,p,i)

gm(11,"دوز"); e=last(); print(e["text"]); print(e["reply_markup"])
ok("دوز شاهنشاهی XO" in e["text"] and "سازنده میز" in e["text"] and "تعیین نشده" in e["text"] and "تعیین مبلغ ورودی" in str(e["reply_markup"]),"پنل اول")
tid=g_t=[0]; 
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p=mid[0]
cb(11,f"g:stk:{tid}",p); ok("حداقل مبلغ › ۲" in lastedit()["text"],"حداقل ۲")
n_=len(sent); gm(11,"1",reply=p); ok(len(sent)==n_,"زیر ۲: بی‌صدا")
gm(11,"2",reply=p); e=lastedit(); ok("ساخت بازی دوز XO" in str(e["reply_markup"]) and "تغییر مبلغ" in str(e["reply_markup"]),"بعد از مبلغ")
cb(12,f"g:mk:{tid}",p); ok("مخصوص" in alerts[-1],"فقط سازنده")
b11=bal(11); cb(11,f"g:mk:{tid}",p); e=lastedit(); print(e["text"]); ok(bal(11)==b11-2 and "پیوستن" in str(e["reply_markup"]) and "۶۰ ثانیه" in e["text"],"join phase")
cb(11,f"g:jn:{tid}",p); ok("همین الان" in alerts[-1],"سازنده دوباره نه")
b12=bal(12); cb(12,f"g:jn:{tid}",p); ok(bal(12)==b12-2 and S(tid)=="play","شروع بازی")
e=lastedit(); print(e["text"]); ok("۱۵۰ ثانیه" in e["text"] and len(e["reply_markup"]["inline_keyboard"])==3,"پنل بازی")
R=roles(tid); ok(set(R.values())=={"X","O"} and g._table(tid)["turn"]==11,"نقش رندوم و سازنده اول")
cell(12,tid,p,0); ok("نوبت شما نیست" in alerts[-1],"نوبت اشتباه")
cell(13,tid,p,0); ok("نیستید" in alerts[-1],"غریبه")
cell(11,tid,p,4); cell(12,tid,p,4); ok("پر است" in alerts[-1],"خانه پر")
# 11 wins with row 3,4,5: 11 plays 3,4,5 ; 12 plays 0,1
b11,b12=bal(11),bal(12)
play(tid,p,[(12,0),(11,3),(12,1),(11,5)])
ok(S(tid)=="purged" and bal(11)==b11+4 and bal(12)==b12,"برد: برنده کل جایزه ۴")
e=lastedit(); print(e["text"]); ok("برنده نهایی" in e["text"] and "بازنده" in e["text"] and "🔍 نتیجه میز" in e["text"],"متن نتیجه")
cell(12,tid,p,8); ok("تمام شده" in alerts[-1],"بعد از پایان بازی ممکن نیست")
# draw
tid,p=setupx(11,10); cb(11,f"g:mk:{tid}",p); cb(12,f"g:jn:{tid}",p)
b11,b12=bal(11),bal(12)
# 11 first: board  X O X / X O O / O X X -> draw sequence with alternating moves 11,12,...
seq=[0,1,2,4,3,5,7,6,8]   # player order: 11,12,11,12,... check no early win
us=[11,12]
R=roles(tid)
# construct draw via roles: use moves by turn index
mv=[(us[k%2],c_) for k,c_ in enumerate(seq)]
play(tid,p,mv)
print(S(tid))
ok(S(tid)=="purged" and bal(11)==b11+10 and bal(12)==b12+10,"مساوی → برگشت ورودی هر دو")
print(lastedit()["text"])
# timeout forfeit
tid,p=setupx(11,10); cb(11,f"g:mk:{tid}",p); cb(12,f"g:jn:{tid}",p); cell(11,tid,p,0)
b11,b12=bal(11),bal(12)   # turn: 12
with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tid))
cell(12,tid,p,1); ok("زمان" in alerts[-1],"حرکت بعد از زمان")
g._tick(); ok(S(tid)=="purged" and bal(11)==b11+20 and bal(12)==b12,"تایم‌اوت: نوبت‌دار (12) می‌بازد")
print(lastedit()["text"])
# nobody joins -> refund
tid,p=setupx(11,10); b11=bal(11); cb(11,f"g:mk:{tid}",p); ok(bal(11)==b11-10,"کسر")
with b.get_db() as c: c.execute("UPDATE g_tables SET join_dl=? WHERE id=?",(time.time()-1,tid))
g._tick(); ok(bal(11)==b11 and S(tid)=="purged","بدون حریف → برگشت")
# cancel via back
gm(11,"دوز")
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
cb(11,f"g:cx:{tid}",mid[0]); ok("لغو" in lastedit()["text"],"بازگشت = لغو")
# no cooldown for xo
tid,p=setupx(11,10); cb(11,f"g:mk:{tid}",p); ok(S(tid)=="join","دوز بدون کول‌داون")
with b.get_db() as c: c.execute("UPDATE g_tables SET join_dl=? WHERE id=?",(time.time()-1,tid))
g._tick()

_orig_purge=g._purge; g._purge=lambda tid: None
# --- RACE: same cell double click / both players click at once; money conservation
for trial in range(15):
    tid,p=setupx(11,10); cb(11,f"g:mk:{tid}",p); cb(12,f"g:jn:{tid}",p)
    tot0=total()
    errs=[]
    def click(u,i):
        try: cell(u,tid,p,i)
        except Exception as e: errs.append(e)
    ths=[threading.Thread(target=click,args=(u,i)) for u in (11,12) for i in range(9) for _ in range(2)]
    random.shuffle(ths); [t.start() for t in ths]; [t.join() for t in ths]
    st=g._table(tid); bd=st["board"]
    nx=bd.count("X"); no=bd.count("O")
    valid = abs(nx-no)<=1 and (bd.count("-")<9)
    # creator first: first mark must be by creator -> counts: creator role count >= other
    R=roles(tid); c_,o_=bd.count(R[11]),bd.count(R[12])
    if not (valid and c_-o_ in (0,1) and not errs and total() in (tot0,tot0+20)):
        print("RACE FAIL",bd,R,errs,total(),tot0); ok(False,"race trial"); break
else: ok(True,"۱۵ تکرار کلیک هم‌زمان: نوبت‌ها درست، تعداد ❌/⭕ مجاز، پول ثابت")
g._purge=_orig_purge
# finish all if open
for k in range(30):
    for tt in g._rows("SELECT * FROM g_tables WHERE state='play'"):
        with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tt["id"]))
    g._tick()
# crash during finish
tid,p=setupx(11,10); cb(11,f"g:mk:{tid}",p); cb(12,f"g:jn:{tid}",p)
play(tid,p,[(11,0),(12,3),(11,1),(12,4)])
tot0=total(); orig=g._pay_in
def boom(c,uid,amt): orig(c,uid,amt); raise RuntimeError("x")
g._pay_in=boom
try: cell(11,tid,p,2)
except Exception: pass
g._pay_in=orig
st=g._table(tid); ok(total()==tot0 and st["state"]=="play" and st["board"].count("-")==5,"کرش وسط پایان بازی → rollback (حرکت هم ثبت نشد، پول سالم)")
cell(11,tid,p,2); ok(S(tid)=="purged","بعد از کرش بازی ادامه می‌یابد")
# trigger texts alone in other cases
n=len(sent); gm(13,"سلام دوز خوبه؟ این یک جمله خیلی طولانی است که نباید"); ok(len(sent)==n,"جمله طولانی نادیده")
