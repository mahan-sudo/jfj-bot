exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
g._purge=lambda tid: None
def setups(u,game,stake,players):
    gm(u,"کازینو")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]; cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p); cb(u,f"g:mk:{tid}",p)
    return tid,p
def gmid(u,value,msgid,emoji="🎰"):
    cnt[0]+=1
    m={"message_id":msgid,"from":{"id":u,"first_name":NM[u]},"chat":{"id":G,"type":"supergroup"},"dice":{"emoji":emoji,"value":value},"reply_to_message":{"message_id":panel_of(u),"from":{"id":999}}}
    b.handle_update({"update_id":cnt[0]*7+int(time.time()*1000)%1000000*100,"message":m})
# 1) اولی حساب می‌شود، بقیه نادیده
tid,p=setups(11,"s",10,1)
gmid(11,1,p+1); gmid(11,64,p+2); gmid(11,64,p+3)
ok(g._players(tid)[0]["value"]==1,"اولین 🎰 حساب شد (۷۷۷های بعدی نادیده)")
time.sleep(g.REVEAL_DELAY+.2); g._tick(); ok(g._players(tid)[0]["value"]==1 and bal(11)==1000-10,"BAR BAR BAR همان ماند")
# 2) پردازش وارونه (هم‌زمانی): پیام زودتر دیرتر پردازش شد
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
tid,p=setups(11,"s",10,1)
gmid(11,64,p+5)      # دومی اول پردازش شد
gmid(11,1,p+4)       # اولی (message_id کوچک‌تر) دیرتر رسید
ok(g._players(tid)[0]["value"]==1,"ترتیب واقعی (message_id) ملاک است، نه ترتیب پردازش")
# 3) بعد از نمایش نتیجه تغییر نمی‌کند
time.sleep(g.REVEAL_DELAY+.2); g._tick(); gmid(11,64,p+3); ok(g._players(tid)[0]["value"]==1,"بعد از نمایش، جایگزین نمی‌شود")
# 4) 🎰 قبل از ساخت پنل
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
gm(11,"کازینو")
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p=mid[0]; cb(11,f"g:sel:{tid}:s",p); cb(11,f"g:stk:{tid}",p); gm(11,"10",reply=p); cb(11,f"g:n:{tid}:1",p); cb(11,f"g:mk:{tid}",p)
gmid(11,64,p-50); ok(g._players(tid)[0]["sent"]==0,"🎰 قدیمی‌تر از پنل نادیده")
# 5) تاس: ۶ زودتر با ۱ دیرتر
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0"); c.execute("UPDATE g_tables SET state='expired' WHERE state='send'")
tid,p=setups(11,"d",10,1); cb(11,f"g:pk:{tid}:o",p)
gmid(11,1,p+9,"🎲"); gmid(11,6,p+10,"🎲"); gmid(11,6,p+11,"🎲")
ok(g._players(tid)[0]["value"]==1,"تاس: اولی (۱) حساب شد")
os.remove(DB)
