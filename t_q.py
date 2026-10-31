exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
ADM=b.ADMIN_IDS[0]; b.upsert_user({"id":ADM,"first_name":"Admin"})
b.rep_ev_ref_ok=lambda *a,**k: None; b.rep_ev_ref_new=lambda *a,**k: None
def admcb(data):
    b.admin_panel_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
user(401,10); user(402,0); user(403,0)
# پیش‌فرض: روشن، پاداش فوری نیست
ok(b.ref_act_on(),"پیش‌فرض: شرط فعالیت روشن")
with b.get_db() as c: c.execute("UPDATE users SET referred_by=401 WHERE id=402")
b.notify_new_referral(401,{"id":402}); ok(bal(401)==10,"روشن: پاداش فوری داده نشد")
b.maybe_reward_referrer(402); ok(bal(401)==10,"روشن: قبل از فعالیت پاداش ندارد")
b.add_activity_tokens(402,b.REFERRAL_ACTIVITY_THRESHOLD); b.maybe_reward_referrer(402); ok(bal(401)==10+b.REFERRAL_REWARD,"روشن: بعد از فعالیت پاداش")
# پنل: دکمه‌ی خاموش
admcb("adm_p:r:home") if False else None
t,k=b.render_referral(); ok("rtg" in str(k) and "خاموش کردن شرط" in str(k) and "🟢 روشن" in t,"پنل: دکمه‌ی خاموش‌کردن")
admcb("adm_p:r:rtg"); ok(not b.ref_act_on(),"کلید خاموش شد")
t,k=b.render_referral(); ok("روشن کردن شرط" in str(k) and "🔴 خاموش" in t,"پنل: وضعیت خاموش")
# خاموش: پاداش فوری و فقط یک‌بار
with b.get_db() as c: c.execute("UPDATE users SET referred_by=401, ref_need=0 WHERE id=403")
before=bal(401); b.notify_new_referral(401,{"id":403}); ok(bal(401)==before+b.REFERRAL_REWARD,"خاموش: پاداش همان لحظه")
b.notify_new_referral(401,{"id":403}); b.add_activity_tokens(403,50); b.maybe_reward_referrer(403)
ok(bal(401)==before+b.REFERRAL_REWARD,"خاموش: دوبار پرداخت نمی‌شود")
ok([q for m,q in sent if m=="sendMessage" and q.get("chat_id")==401][-1]["text"].count("تایید شد")>=1,"خاموش: پیام تایید برای معرف")
admcb("adm_p:r:rtg"); ok(b.ref_act_on(),"دوباره روشن شد")
# ---- شرط هر زیرمجموعه در زمان ثبت‌نام قفل می‌شود
admcb("adm_p:r:rtg")  # دوباره روشن است؟
if not b.ref_act_on(): admcb("adm_p:r:rtg")
user(410,0); user(411,0); user(412,0); user(413,0)
b.REFERRAL_ACTIVITY_THRESHOLD=3
def signup(uid,ref):
    with b.get_db() as c: c.execute("DELETE FROM users WHERE id=?",(uid,))
    b.upsert_user({"id":uid,"first_name":"N%d"%uid},referred_by=ref)
    if True: b.notify_new_referral(ref,{"id":uid})
need=lambda u: b.get_db().execute("SELECT ref_need FROM users WHERE id=?",(u,)).fetchone()[0]
signup(410,401); ok(need(410)==3,"ثبت‌نام با شرط ۳ → ref_need=3")
b.REFERRAL_ACTIVITY_THRESHOLD=10   # ادمین شرط را به ۱۰ تغییر می‌دهد
signup(411,401); ok(need(411)==10,"بعد از تغییر شرط: جدیدها ۱۰")
b0=bal(401); b.add_activity_tokens(410,3); b.maybe_reward_referrer(410)
ok(bal(401)==b0+b.REFERRAL_REWARD,"زیرمجموعه‌ی قدیمی با همان شرط ۳ پاداش گرفت")
b.add_activity_tokens(411,3); b.maybe_reward_referrer(411); ok(bal(401)==b0+b.REFERRAL_REWARD,"زیرمجموعه‌ی جدید با ۳ هنوز پاداش ندارد")
# قدیمی‌ها بعد از خاموش‌شدن همچنان باید شرطشان را انجام دهند
signup(412,401); ok(need(412)==10,"ثبت‌نام ۴۱۲ با شرط ۱۰")
admcb("adm_p:r:rtg"); ok(not b.ref_act_on(),"شرط خاموش شد")
b1=bal(401); b.add_activity_tokens(412,5); b.maybe_reward_referrer(412)
ok(bal(401)==b1,"خاموش‌شدن شرط روی زیرمجموعه‌ی قبلی اثر ندارد (هنوز ۱۰ لازم)")
b.add_activity_tokens(412,5); b.maybe_reward_referrer(412); ok(bal(401)==b1+b.REFERRAL_REWARD,"با رسیدن به ۱۰ پاداش داده شد")
signup(413,401); ok(need(413)==0 and bal(401)==b1+2*b.REFERRAL_REWARD,"ثبت‌نام بعد از خاموشی: بی‌شرط و فوری")
# ---- متن‌های پویا
b.REFERRAL_REWARD=2
ok("2 شاهی" in b.referral_confirmed_text() and "5 شاهی" not in b.referral_confirmed_text(),"متن تایید با پاداش فعلی ساخته می‌شود")
ok("2 شاهی" in b.referral_signup_text(3) and "3 شاهی" in b.referral_signup_text(3),"متن ثبت‌نام با پاداش و شرط فعلی")
# ---- جوین اجباری: پاداش فقط بعد از عضویت و زدن «عضو شدم»
import json as _j
b.set_setting("fj_enabled","1"); b.set_setting("fj_list",_j.dumps([{"ref":"@chfj","title":"کانال"}]))
STAT={"v":"left"}
b._fj_status=lambda uid,ref: STAT["v"]
b.fj_info=lambda e: {"title":"کانال","link":"https://t.me/chfj"}
user(420,0); user(421,0)
while not b.ref_act_on(): admcb("adm_p:r:rtg")
admcb("adm_p:r:rtg")                      # خاموش: فقط جوین اجباری شرط است
with b.get_db() as c: c.execute("DELETE FROM users WHERE id=421")
b.upsert_user({"id":421,"first_name":"N421"},referred_by=420)
b.notify_new_referral(420,{"id":421}); ok(bal(420)==0,"جوین اجباری فعال و زیرمجموعه عضو نیست: پاداش نیست")
ok(not b.fj_gate(421,421) is False,"قفل جوین اجباری نمایش داده شد")
b.maybe_reward_referrer(421); ok(bal(420)==0,"هنوز عضو نیست: پاداش نیست")
STAT["v"]="member"                       # عضو شد ولی روی «بررسی» نزد
b.maybe_reward_referrer(421); ok(bal(420)==0,"عضو شد ولی بررسی نزد: پاداش نیست")
n0=len(sent); r=b.fj_gate(421,421); ok(r is True and "fj_check" in str(sent[-1][1]),"از او خواسته می‌شود «عضو شدم | بررسی» را بزند")
ok(bal(420)==0,"هنوز پاداش نیست")
b.handle_fj_check({"id":"x","from":{"id":421},"message":{"chat":{"id":421},"message_id":9},"data":"fj_check"})
ok(bal(420)==2,"بعد از «عضو شدم | بررسی» پاداش ۲ شاهی داده شد")
ok("2 شاهی" in [q for m,q in sent if m=="sendMessage" and q.get("chat_id")==420][-1]["text"],"متن تایید برای معرف با ۲ شاهی")
b.handle_fj_check({"id":"x","from":{"id":421},"message":{"chat":{"id":421},"message_id":9},"data":"fj_check"}); ok(bal(420)==2,"دوبار پرداخت نشد")
# کاربری که اصلاً قفل را ندیده (از قبل عضو است) بدون کلیک رد می‌شود
user(430,0); user(431,0)
with b.get_db() as c: c.execute("DELETE FROM users WHERE id=431")
b.upsert_user({"id":431,"first_name":"N431"},referred_by=430); b.notify_new_referral(430,{"id":431})
ok(bal(430)==0,"عضو از قبل: قبل از اولین تعامل پاداش نیست")
ok(b.fj_gate(431,431) is False and bal(430)==2,"عضو از قبل: بدون کلیک رد می‌شود و پاداش می‌گیرد")
b.set_setting("fj_enabled","0")
os.remove(DB)
