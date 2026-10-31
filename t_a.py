exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
def clr():
    with b.get_db() as c: c.execute("DELETE FROM g_cool")
def last_menu(): return [q for m,q in sent if m=="sendMessage"][-1]
# --- صفحه ادمین
t,kb=b.render_games(); ok("بازی‌های گروهی" in t and "adm_p:x:gmt:all" in str(kb) and "adm_p:x:gmt:x" in str(kb),"صفحه‌ی بازی‌ها")
t,kb=b.render_general(); ok("adm_p:x:gm" not in str(kb),"دکمه‌ی بازی‌ها دیگر در تنظیمات عمومی نیست")
ADM=b.ADMIN_IDS[0]
def admcb(data):
    b.v2_admin_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
n=len(sent)
admcb("adm_p:x:gmt:d"); ok(b.get_setting("g_d_on")=="0","تاس خاموش")
# منو بدون تاس
gm(11,"کازینو"); m_=last_menu(); ok("🎰" in str(m_["reply_markup"]) and "🎲" not in str(m_["reply_markup"]) and "تاس" not in m_["text"],"فقط دکمه و متن تاس از منو برداشته شد")
tid=g._table(1) and 1
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
n=len(sent); al=len(alerts); cb(11,f"g:sel:{tid}:d",mid[0]); ok(len(sent)==n and alerts[-1] is None,"کلیک روی تاس خاموش: بی‌صدا")
admcb("adm_p:x:gmt:d"); ok(b.get_setting("g_d_on")=="1","تاس روشن")
# دوز خاموش: بی‌پاسخ
admcb("adm_p:x:gmt:x"); n=len(sent); gm(12,"دوز"); ok(len(sent)==n,"دوز خاموش: اصلاً پاسخ نمی‌دهد")
admcb("adm_p:x:gmt:x"); gm(12,"دوز"); ok("دوز شاهنشاهی XO" in last_menu()["text"],"دوز روشن")
with b.get_db() as c: tx_=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
cb(12,f"g:cx:{tx_}",mid[0])
# خاموش کلی
admcb("adm_p:x:gmt:all"); n=len(sent); gm(11,"کازینو"); gm(12,"دوز"); ok(len(sent)==n,"خاموش کلی: هیچ پاسخی")
# میز در جریان وقتی خاموش کلی شد کامل می‌شود
admcb("adm_p:x:gmt:all"); clr()
for u in (11,12): user(u,1000)
gm(11,"دوز")
with b.get_db() as c: tid=c.execute("SELECT MAX(id) FROM g_tables").fetchone()[0]
p=mid[0]; cb(11,f"g:stk:{tid}",p); gm(11,"10",reply=p); cb(11,f"g:mk:{tid}",p)
admcb("adm_p:x:gmt:all")            # وسط بازی خاموش می‌شود
cb(12,f"g:jn:{tid}",p); ok(S(tid)=="play","میز در جریان با خاموش کلی هم ادامه دارد")
b11=bal(11); play(tid,p,[(11,0),(12,3),(11,1),(12,4),(11,2)]) if False else None
def cell(u,tid,p,i): cb(u,f"g:xo:{tid}:{i}",p)
for u,i in [(11,0),(12,3),(11,1),(12,4),(11,2)]: cell(u,tid,p,i)
ok(S(tid)=="purged" and bal(11)==b11+20,"بازی تمام شد و پول درست پرداخت شد (با خاموش کلی)")
admcb("adm_p:x:gmt:all")
# --- بخش‌ها
t,kb=b.render_sections(); ok(all(x in str(kb) for x in ("sect:sp","sect:rf","sect:sv","sect:mi")),"بخش‌های جدید: اسپانسری/زیرمجموعه/ممبر و سین/مینی‌اپ")
sentm=[]
b.send=lambda chat_id,text,rm=None,markdown=True,effect_id=None: sentm.append(text) or {"ok":True}
b.set_setting("sec_off",'["sp","rf","sv"]')
b.handle_message({"from":{"id":11,"first_name":"x"},"chat":{"id":11,"type":"private"},"message_id":1,"text":"/sponser"})
b.handle_message({"from":{"id":11,"first_name":"x"},"chat":{"id":11,"type":"private"},"message_id":2,"text":b.BTN_BUY_SERVICES})
ok(sum("فعلا غیرفعال" in x for x in sentm)==2 and "اسپانسری" in sentm[0],"/sponser و خرید ممبر و سین مسدود شد")
for d in ("acc_ref","sp_pick:x","sps:t:public","svc_views"):
    alerts.clear(); b.handle_callback({"id":"c","from":{"id":11,"first_name":"x"},"data":d,"message":{"chat":{"id":11,"type":"private"},"message_id":3}})
    ok(alerts and "غیرفعال" in str(alerts[-1]),f"callback {d} مسدود")
alerts.clear(); b.handle_callback({"id":"c","from":{"id":ADM,"first_name":"x"},"data":"acc_ref","message":{"chat":{"id":ADM,"type":"private"},"message_id":3}}); ok(not any("غیرفعال" in str(a) for a in alerts),"ادمین مسدود نمی‌شود")
b.set_setting("sec_off",'[]')
os.remove(DB)
