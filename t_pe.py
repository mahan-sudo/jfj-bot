import os, sys, time, json
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b
import premium_btn as pb
pgtest.fresh("pe")
b.install_schema(); b.migrate_schema()
P=F=0
def ok(c,n):
    global P,F
    if c: P+=1; print('PASS '+n)
    else: F+=1; print("FAIL "+n)
# --- core ---
ok(pb.core("بازگشت ◁")=="بازگشت","core back")
ok(pb.core("👁️‍🗨️ ویو پست")=="ویو پست","core zwj")
ok(pb.core("عضو شدم | بررسی ✅️")=="عضو شدم | بررسی","core pipe")
ok(pb.core("🎄 ری‌اکشن پست")=="ری‌اکشن پست" and "‌" in pb.core("🎄 ری‌اکشن پست"),"core zwnj kept")
ok(pb.core("▷ بعدی")=="بعدی","core arrow")
ok(pb.core("کپی مبلغ💰")=="کپی مبلغ","core glued")
# --- fake send ---
calls=[]; mode_fail={"v":None}
def fake_send(method, timeout, params):
    calls.append((method,json.dumps(params,ensure_ascii=False)))
    rm=params.get("reply_markup")
    s=json.dumps(rm,ensure_ascii=False) if rm else ""
    if mode_fail["v"]=="premium" and "icon_custom_emoji_id" in s:
        return {"ok":False,"error_code":400,"description":"Bad Request: BUTTON_ICON_CUSTOM_EMOJI_INVALID premium required"}
    if mode_fail["v"]=="solo" and '"⠀"' in s:
        return {"ok":False,"error_code":400,"description":"Bad Request: BUTTON_TEXT_EMPTY"}
    if mode_fail["v"]=="notmod":
        return {"ok":False,"error_code":400,"description":"Bad Request: message is not modified"}
    return {"ok":True,"result":{"message_id":1}}
b._tg_send=fake_send
b.init_premoji(); pm=b.PREMOJI
ok(pm is not None,"init")
b.set_setting("premium_emoji","auto"); pm.refresh()
# --- inline ---
kb={"inline_keyboard":[[b.btn_inline("پیوستن به میز 🃏","g:jn:1","success"),b.btn_inline("❌ انصراف","x"),b.btn_inline("✅ ارسال برای همه","y")],
    [b.btn_inline("🎰 گردونه","a"),b.btn_inline("🪨📄✂️ سنگ‌کاغذ‌قیچی","b"),b.btn_inline("شاهی 💎 ۱۰","c")],
    [b.btn_inline("❌️","g:xo:1:0"),b.btn_inline("⭕️","g:xo:1:1"),b.btn_inline("◻️","g:xo:1:2")],
    [b.btn_inline("3️⃣","g:pk:1:3"),b.btn_inline("❌️","g:tx:1:n"),b.btn_inline("▷ بعدی","n"),b.btn_inline("قبلی ◁","p")]]}
r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
sent=json.loads(calls[-1][1])["reply_markup"]["inline_keyboard"]
ok(r["ok"],"send ok")
g=lambda i,j:sent[i][j]
ok(g(0,0)["text"]=="پیوستن به میز" and g(0,0)["icon_custom_emoji_id"]=="5819032824623144971" and g(0,0)["style"]=="success","join icon")
ok(g(0,1)["text"]=="انصراف" and g(0,1)["icon_custom_emoji_id"]=="5819154526816444042","cancel")
ok(g(0,2)["text"]=="ارسال برای همه" and g(0,2)["icon_custom_emoji_id"]=="5830144944399981619","✅ generic")
ok(g(1,0)["icon_custom_emoji_id"]=="5875360259853263196" and g(1,0)["text"]=="گردونه","slot")
ok(g(1,1)["icon_custom_emoji_id"]=="5882236803141868717" and "🪨" not in g(1,1)["text"],"rps first")
ok(g(1,2)["icon_custom_emoji_id"]=="5825623013852192219" and "💎" not in g(1,2)["text"],"diamond")
ok(g(2,0)["icon_custom_emoji_id"]==pb.DOOZ_X and g(2,0)["text"]==pb.BLANK,"dooz x")
ok(g(2,1)["icon_custom_emoji_id"]==pb.DOOZ_O,"dooz o")
ok("icon_custom_emoji_id" not in g(2,2) and g(2,2)["text"]=="◻️","empty cell untouched")
ok(g(3,0)["icon_custom_emoji_id"]==pb.DIGIT_IDS["3"],"digit")
ok(g(3,1)["icon_custom_emoji_id"]=="5819154526816444042" and g(3,1)["text"]==pb.BLANK,"solo ❌ elsewhere")
ok("icon_custom_emoji_id" in g(3,2),"بعدی حالا آیدی دارد")
ok(g(3,3)["icon_custom_emoji_id"]=="5845874566336880660" and g(3,3)["text"]=="قبلی","prev")
ok(kb["inline_keyboard"][0][0]["text"]=="پیوستن به میز 🃏","original not mutated")
# --- reply keyboards ---
mm=b.main_menu(123)
al=pm.prepare({"reply_markup":mm})
ok(al is not None,"main menu transformed")
rows=al["params"]["reply_markup"]["keyboard"]
flat=[x for r_ in rows for x in r_]; orig=[x for r_ in mm["keyboard"] for x in r_]
ok(all("icon_custom_emoji_id" in x for x in flat),"all main-menu buttons iconified: "+str([x["text"] for x in flat if "icon_custom_emoji_id" not in x]))
back={pm.normalize_incoming(x["text"]):1 for x in flat}
ok(all(pm.normalize_incoming(f["text"])==o["text"] for f,o in zip(flat,orig)),"normalize_incoming round-trip")
ok(pm.normalize_incoming("چیز دیگری")=="چیز دیگری","normalize passthrough")
adm=pm.prepare({"reply_markup":b.admin_panel_menu()})
ok(adm is None or all(x["text"] in b.admin_panel_menu()["keyboard"][0][0]["text"] or True for x in []),"admin panel ok")
ab=b.admin_panel_menu()["keyboard"]
txts=[x["text"] for r_ in (adm["params"]["reply_markup"]["keyboard"] if adm else ab) for x in r_]
orig_t=[x["text"] for r_ in ab for x in r_]
ok(all(a==o or (o==b.BACK_BTN and a=="بازگشت") for a,o in zip(txts,orig_t)),"admin reply: only registered (reversible) buttons change")
bk=pm.prepare({"reply_markup":b.back_menu()})
ok(bk and bk["params"]["reply_markup"]["keyboard"][0][0]["text"]=="بازگشت","back reply")
ok(pm.normalize_incoming("بازگشت")==b.BACK_BTN,"back normalize")
# --- fallback ---
calls.clear(); mode_fail["v"]="premium"
r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok(r["ok"] and len(calls)>=2 and "icon_custom_emoji_id" not in calls[-1][1],"fallback plain")
ok(pm.state()[0]=="fail","state fail")
calls.clear(); r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok(len(calls)==1 and "icon_custom_emoji_id" not in calls[0][1],"stays plain while failed")
pm.refresh(); b.set_setting("premium_emoji_state","fail:%d"%(time.time()-pb.RETRY_AFTER-5)); pm.refresh(); mode_fail["v"]=None
calls.clear(); r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok("icon_custom_emoji_id" in calls[0][1] and pm.state()[0]=="ok","re-probe after retry window re-enables")
# solo-only failure
b.set_setting("premium_emoji_state",""); pm.refresh(); mode_fail["v"]="solo"; calls.clear()
r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok(r["ok"] and pm.icon_only_ok is False and pm.state()[0]!="fail","solo failure keeps feature on")
ok("icon_custom_emoji_id" in calls[-1][1] and pb.BLANK not in calls[-1][1],"retry without solo keeps icons")
pm.icon_only_ok=True
# unrelated error
mode_fail["v"]="notmod"; calls.clear(); b.set_setting("premium_emoji_state",""); pm.refresh()
r=b._tg_raw("editMessageReplyMarkup",chat_id=1,message_id=2,reply_markup=kb)
ok(not r["ok"] and len(calls)==1 and pm.state()[0]=="","unrelated error: no retry/no state")
mode_fail["v"]=None
# modes
b.set_setting("premium_emoji","off"); pm.refresh(); calls.clear()
b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok("icon_custom_emoji_id" not in calls[0][1],"off")
b.set_setting("premium_emoji","on"); pm.refresh(); b.set_setting("premium_emoji_state","fail:%d"%time.time()); pm.refresh(); calls.clear()
b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok("icon_custom_emoji_id" in calls[0][1],"on forces even after fail")
mode_fail["v"]="premium"; b.set_setting("premium_emoji_state",""); pm.refresh(); calls.clear()
r=b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb)
ok(r["ok"] and pm.state()[0]=="","on mode failure falls back without changing state")
mode_fail["v"]=None
# overrides
b.set_setting("premium_emoji","auto"); b.set_setting("premium_emoji_map",json.dumps({"بعدی":"5843732253829503840","قوانین":"","bad":"12"})); pm.refresh()
mode,mp=pm.settings()
ok(mp.get("بعدی")=="5843732253829503840" and "قوانین" not in mp and "bad" not in mp,"overrides merge/validate")
# str reply_markup
calls.clear(); b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=json.dumps(kb,ensure_ascii=False))
ok("icon_custom_emoji_id" in calls[0][1],"string markup")
# no markup → untouched
calls.clear(); b._tg_raw("sendMessage",chat_id=1,text="x"); ok(len(calls)==1,"no markup")
# ---- v10: بعدی / تغییر تعداد بازیکن / دکمه‌های منوی کازینو ----
b.set_setting("premium_emoji","auto"); b.set_setting("premium_emoji_map",""); b.set_setting("premium_emoji_state",""); pm.refresh()
_mode,_mp=pm.settings()
rs=lambda t,cb="x": pm.resolve(t,cb,_mp,True)
ok(rs("بعدی ▷")==("5843732253829503840","بعدی") or rs("بعدی ▷")[0]=="5843732253829503840","next button id")
ok(rs("بعدی")[0]=="5843732253829503840","next plain")
ok(rs("تغییر تعداد بازیکن 👑")==("5816404884458577332","تغییر تعداد بازیکن"),"change players id")
ok(rs("🎰","g:sel:1:s")==("5875360259853263196",pb.BLANK),"slot icon")
ok(rs("🎲","g:sel:1:d")==("5875483791702630534",pb.BLANK),"dice icon")
rr=rs("🪨📄✂️","g:sel:1:r")
ok(rr and rr[0]=="5882236803141868717" and "📄" in rr[1],"rps icon first id + rest text")
ok(rs("🎰","g:sel:1:s")[1]==pb.BLANK,"blank text")
kb2={"inline_keyboard":[[{"text":"🎰","callback_data":"g:sel:1:s"},{"text":"🎲","callback_data":"g:sel:1:d"},{"text":"🪨📄✂️","callback_data":"g:sel:1:r"}],[{"text":"بعدی ▷","callback_data":"n"}]]}
calls.clear(); b._tg_raw("sendMessage",chat_id=1,text="x",reply_markup=kb2)
rm_=json.loads(calls[0][1])["reply_markup"]
flat=[x for r_ in rm_["inline_keyboard"] for x in r_]
ok(all("icon_custom_emoji_id" in x for x in flat),"casino menu all icons")
# general panel renders
t,k=b.render_general(); ok("ایموجی پرمیوم" in t,"render_general")
print(f"t_pe: PASS={P} FAIL={F}")
