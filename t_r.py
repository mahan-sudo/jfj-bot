exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
def setups(u,game,stake,players):
    gm(u,"کازینو")
    with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
    p=mid[0]; cb(u,f"g:sel:{tid}:{game}",p); cb(u,f"g:stk:{tid}",p); gm(u,str(stake),reply=p); cb(u,f"g:n:{tid}:{players}",p); cb(u,f"g:mk:{tid}",p)
    return tid,p
for i in (11,12,13): user(i,1000)
# 2 از 3 نفر → بسته می‌شود و پول همه برمی‌گردد
tid,p=setups(11,"s",10,3); cb(12,f"g:jn:{tid}",p); ok(bal(11)==990 and bal(12)==990 and S(tid)=="join","۲ نفر از ۳ نفر: هنوز join")
with b.get_db() as c: c.execute("UPDATE g_tables SET join_dl=? WHERE id=?",(time.time()-1,tid))
g._tick(); t_=lastedit()["text"]; print(t_)
ok(S(tid)=="purged" and bal(11)==1000 and bal(12)==1000 and "تعداد بازیکنان تکمیل نشد" in t_,"بازی ۲ نفره روی میز ۳ نفره شروع نمی‌شود؛ پول هر دو برگشت")
# پیوستن بدون محدودیت و بدون ثبت کول‌داون برای پیوسته
with b.get_db() as c: c.execute("DELETE FROM g_cool")
tid,p=setups(11,"s",10,2)   # 11 سازنده
cb(12,f"g:jn:{tid}",p); ok(S(tid)=="send","12 پیوست")
gm(11,dice=22,emoji="🎰"); gm(12,dice=43,emoji="🎰"); time.sleep(g.REVEAL_DELAY+.2); g._tick()
with b.get_db() as c: cool={r[0] for r in c.execute("SELECT user_id FROM g_cool")}
ok(cool=={11},f"فقط سازنده محدود شد {cool}")
gm(11,"کازینو"); ok("برو استراحت" in last()["text"],"سازنده محدود است")
# 12 می‌تواند هم میز بسازد و هم به میز دیگران بپیوندد
gm(12,"کازینو"); ok("🃏 کازینو شاهنشاهی" in last()["text"],"پیوسته می‌تواند میز بسازد")
with b.get_db() as c: c.execute("UPDATE g_tables SET state='expired' WHERE state='menu'")
# پیوستن حتی وقتی خودش در کول‌داون باشد: ۱۳ را در کول‌داون بگذار
with b.get_db() as c: c.execute("INSERT OR REPLACE INTO g_cool VALUES (13,?)",(time.time(),))
with b.get_db() as c: c.execute("DELETE FROM g_cool WHERE user_id=11")
tid,p=setups(11,"d",10,2); cb(11,f"g:md:{tid}:max",p); cb(13,f"g:jn:{tid}",p); ok(S(tid)=="send" and bal(13)==990,"پیوستن با کول‌داون فعال مشکلی ندارد")
# متن منقضی
gm(12,"کازینو")
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]; c.execute("UPDATE g_tables SET touched=0 WHERE id=?",(tid,))
g._tick(); _e=lastedit(); ok(_e["text"].rstrip().endswith("🛑 این گردونه دیگر اعتبار ندارد...</b>") and "کازینو شاهنشاهی" in _e["text"] and not _e.get("reply_markup",{}).get("inline_keyboard"),"متن پنل منقضی: ته همان پیام اضافه شد")
os.remove(DB)
