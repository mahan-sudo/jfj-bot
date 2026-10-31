import os, sys, time, itertools
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b, games as g
pgtest.fresh("g")
b.install_schema(); b.migrate_schema(); b.seed_products()
b.BOT_ID=999; b.BOT_USERNAME="jfj_bot"
g.init(b); b.GAMES=g
sent=[]; mid=[100]; alerts=[]
def fake_tg(method,_timeout=45,**p):
    q=b._boldify(method,p) or p
    sent.append((method,q))
    if method=="sendMessage": mid[0]+=1; return {"ok":True,"result":{"message_id":mid[0]}}
    return {"ok":True,"result":{}}
b.tg=fake_tg
b.answer_callback=lambda cid,text=None,show_alert=False: alerts.append(text)
def S(tid):
    t=g._table(tid)
    return t["state"] if t else "purged"
def ok(c,n): print(("PASS " if c else "FAIL ")+n)
G=-100500
def user(i,name,bal):
    b.upsert_user({"id":i,"first_name":name}); 
    with b.get_db() as c: c.execute("UPDATE users SET tokens=? WHERE id=?",(bal,i))
for i,n in ((11,"Ali"),(12,"Sara"),(13,"Reza")): user(i,n,100)
uid=[0]
def panel_of(u):
    with b.get_db() as c:
        r=c.execute("SELECT t.msg_id FROM g_tables t JOIN g_players p ON p.table_id=t.id WHERE p.user_id=? ORDER BY t.id DESC LIMIT 1",(u,)).fetchone()
    return r[0] if r and r[0] else mid[0]
def gm(u,text=None,dice=None,reply=None,**kw):
    uid[0]+=1
    m={"message_id":mid[0]+500+uid[0],"from":{"id":u,"first_name":{11:"Ali",12:"Sara",13:"Reza",14:"New"}[u]},"chat":{"id":G,"type":"supergroup"}}
    if text: m["text"]=text
    if dice: m["dice"]={"emoji":"🎰","value":dice}
    if dice and not reply: reply=panel_of(u)
    if reply: m["reply_to_message"]={"message_id":reply,"from":{"id":999}}
    m.update(kw)
    b.handle_update({"update_id":10000+uid[0]+int(time.time()*1000)%100000*1000,"message":m})
def cb(u,data,msgid=1):
    uid[0]+=1
    b.handle_update({"update_id":900000+uid[0]+int(time.time()*1000)%100000*1000,"callback_query":{"id":"c","from":{"id":u,"first_name":{11:"Ali",12:"Sara",13:"Reza",14:"New"}[u]},"data":data,"message":{"chat":{"id":G,"type":"supergroup"},"message_id":msgid}}})
def last(method="sendMessage"): return [q for m,q in sent if m==method][-1]
def lastedit(): return [q for m,q in sent if m=="editMessageText"][-1]
def bal(u): return b.get_balance(u)

# --- evaluate rules
E=lambda *r: g.evaluate(list(r))[0]
B_,G_,L_,S_=0,1,2,3
ok(E(L_,G_,G_)==1.0,"🍋🍇🍇→1.0")
ok(E(G_,L_,L_)==1.5,"2 لیمو→1.5")
ok(E(B_,L_,G_)==0.0,"BAR🍋🍇→0")
ok(E(G_,B_,G_)==1.0,"🍇BAR🍇→1.0")
ok(E(S_,S_,B_)==1.0,"77BAR→1.0")
ok(E(B_,B_,S_)==0.0,"BARBAR7→0")
ok({E(B_,G_,S_) for _ in range(200)}=={1.0,1.5},"BAR🍇7 رندوم")
ok({E(S_,L_,B_) for _ in range(200)}=={1.0,1.5},"7🍋BAR رندوم")
ok(E(S_,S_,S_)==2.0 and E(B_,B_,B_)==0.0 and E(G_,G_,G_)==1.0 and E(L_,L_,L_)==1.5,"سه‌تایی‌ها")
ok(g.decode_dice(1)==[0,0,0] and g.decode_dice(64)==[3,3,3] and g.decode_dice(22)==[1,1,1] and g.decode_dice(43)==[2,2,2],"decode dice")

# --- solo: trigger
gm(11,"کازینو")
menu=last(); ok("کازینو شاهنشاهی" in menu["text"] and menu["text"].startswith("<b>"),"منو + bold")
tid=1; panel=mid[0]
cb(12,f"g:sel:{tid}:s",panel); ok("مخصوص" in (alerts[-1] or ""),"دیگران نمی‌توانند")
cb(11,f"g:sel:{tid}:m",panel); ok(alerts[-1] is None and "💎 معدن" not in menu["text"],"معدن حذف شد")
cb(11,f"g:sel:{tid}:s",panel); e=lastedit(); ok("تعیین نشده" in e["text"] and "تعیین مبلغ ورودی" in str(e["reply_markup"]),"پنل چیدن")
cb(11,f"g:stk:{tid}",panel); ok("حداقل مبلغ › 5" in lastedit()["text"] or "حداقل مبلغ › ۵" in lastedit()["text"],"پنل مبلغ")
n_=len(sent); gm(11,"abc",reply=panel); ok(len(sent)==n_,"ورودی نامعتبر: بی‌صدا")
n_=len(sent); gm(11,"2",reply=panel); ok(len(sent)==n_,"زیر حداقل: بی‌صدا")
gm(11,"5000",reply=panel); ok("حداکثر" in last()["text"],"بالای سقف")
gm(11,"۵۰",reply=panel); e=lastedit(); ok("۵۰ شاهی" in e["text"] and "تعیین تعداد بازیکن" in str(e["reply_markup"]),"مبلغ ثبت شد")
cb(11,f"g:np:{tid}",panel); ok("1️⃣" in str(lastedit()["reply_markup"]),"انتخاب تعداد")
cb(11,f"g:n:{tid}:1",panel); e=lastedit(); ok("ساخت میز قمار" in str(e["reply_markup"]) and "تغییر تعداد" in str(e["reply_markup"]),"آماده ساخت")
cb(11,f"g:mk:{tid}",panel); ok(bal(11)==50,"کسر ورودی"); e=lastedit(); ok("لطفا ایموجی '🎰'" in e["text"] and "⬜ ⬜ ⬜" in e["text"],"پنل ارسال")
# dice forwarded ignored
gm(11,dice=64,forward_origin={"type":"user"}); g._tick(); ok(g._players(tid)[0]["sent"]==0,"فوروارد نادیده")
gm(11,dice=64); gm(11,dice=1)
ok(g._players(tid)[0]["value"]==64,"فقط اولین")
g._tick(); ok(S(tid)=="send","هنوز انیمیشن")
time.sleep(g.REVEAL_DELAY+0.2); g._tick()
e=lastedit(); print(e["text"])
ok(S(tid)=="purged" and bal(11)==50+100,"7️⃣7️⃣7️⃣ → 2x = 100 → موجودی 150")
# cooldown
gm(11,"کازینو"); l=last(); ok("برو استراحت" in l["text"] and "دقیقه" in l["text"],"کول‌داون"); print(l["text"])
# --- burn solo
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
gm(11,"کازینو"); tid2=2; p2=mid[0]
cb(11,f"g:sel:{tid2}:s",p2); cb(11,f"g:stk:{tid2}",p2); gm(11,"20",reply=p2); cb(11,f"g:n:{tid2}:1",p2); cb(11,f"g:mk:{tid2}",p2)
ok(bal(11)==130,"کسر ۲۰")
with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tid2))
g._tick(); e=lastedit(); print(e["text"]); ok(bal(11)==130 and "(0.0x)" in e["text"] and "ʙᴀʀ" in e["text"],"سوختن")
# --- multi: 3 players, one burns, two compete
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
gm(11,"کازینو"); tid3=3; p3=mid[0]
cb(11,f"g:sel:{tid3}:s",p3); cb(11,f"g:stk:{tid3}",p3); gm(11,"30",reply=p3); cb(11,f"g:n:{tid3}:3",p3); cb(11,f"g:mk:{tid3}",p3)
e=lastedit(); ok("پیوستن به میز" in str(e["reply_markup"]) and S(tid3)=="join","فاز پیوستن")
cb(11,f"g:jn:{tid3}",p3); ok("همین الان" in alerts[-1],"دوبار نه")
cb(12,f"g:jn:{tid3}",p3); ok(bal(12)==70,"Sara پیوست")
cb(13,f"g:jn:{tid3}",p3); ok(S(tid3)=="send","پر شد → ارسال")
gm(11,dice=22); gm(12,dice=43)   # 111 → 1.0 ; 222 → 1.5
time.sleep(g.REVEAL_DELAY+0.2); g._tick()
with b.get_db() as c: c.execute("UPDATE g_tables SET send_dl=? WHERE id=?",(time.time()-1,tid3))
b0=(bal(11),bal(12),bal(13)); g._tick(); e=lastedit(); print(e["text"])
ok(S(tid3)=="purged","پایان")
ok(bal(12)==b0[1]+60 and bal(11)==b0[0] and bal(13)==b0[2],"Sara برنده جایزه 60 (سهم Reza سوخت)")
# --- join timeout -> refund
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
gm(12,"کازینو"); tid4=4; p4=mid[0]; b4=bal(12)
cb(12,f"g:sel:{tid4}:s",p4); cb(12,f"g:stk:{tid4}",p4); gm(12,"10",reply=p4); cb(12,f"g:n:{tid4}:2",p4); cb(12,f"g:mk:{tid4}",p4)
ok(bal(12)==b4-10,"کسر")
with b.get_db() as c: c.execute("UPDATE g_tables SET join_dl=? WHERE id=?",(time.time()-1,tid4))
g._tick(); ok(bal(12)==b4 and S(tid4)=="purged","بازگشت پول بدون بازیکن")
# --- unregistered user, balance insufficient
gm(14,"کازینو"); ok("استارت" in last()["text"],"کاربر ثبت‌نشده")
# --- kill switch
b.set_setting("casino_on","0"); n=len(sent); gm(13,"کازینو"); ok(len(sent)==n,"کلید خاموش"); b.set_setting("casino_on","1")
# --- ties
with b.get_db() as c: c.execute("UPDATE g_cool SET ts=0")
gm(11,"کازینو"); tid5=5; p5=mid[0]
cb(11,f"g:sel:{tid5}:s",p5); cb(11,f"g:stk:{tid5}",p5); gm(11,"10",reply=p5); cb(11,f"g:n:{tid5}:2",p5); cb(11,f"g:mk:{tid5}",p5); cb(13,f"g:jn:{tid5}",p5)
b5=(bal(11),bal(13)); gm(11,dice=22); gm(13,dice=22); time.sleep(g.REVEAL_DELAY+0.2); g._tick()
ok(S(tid5)=="purged" and bal(11)==b5[0]+10 and bal(13)==b5[1]+10,"مساوی تقسیم")
# --- admin button
t,kb=b.render_general(); ok("بازی‌های گروهی" not in t and "adm_p:x:gm" not in str(kb),"دکمه‌ی بازی‌ها از تنظیمات عمومی برداشته شد")
ok(any("🃏 بازی‌های گروهی" in x["text"] for row in b.admin_panel_menu()["keyboard"] for x in row),"دکمه‌ی بازی‌ها در کیبورد اصلی پنل")
# --- group other messages ignored; private unaffected
n=len(sent); gm(11,"سلام بچه ها"); ok(len(sent)==n,"پیام عادی گروه نادیده")
# EV
import collections
ev=0
for v in range(1,65):
    ms=[g.evaluate(g.decode_dice(v))[0] for _ in range(400)]
    ev+=sum(ms)/len(ms)/64
print("EV",round(ev,4))
