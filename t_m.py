import os,sys,tempfile
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
import pgtest
import bot_test as b, miniapp as m
pgtest.fresh('m')
m._schema_done=False; m.ensure_ready = m.ensure_ready; b.install_schema(); b.migrate_schema(); b.seed_products()
with b.get_db() as c: c.execute("CREATE TABLE IF NOT EXISTS mini_seen (user_id INTEGER NOT NULL, code TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, code))")
b.upsert_user({"id":5,"first_name":"A"}); b.upsert_user({"id":6,"first_name":"B"})
with b.get_db() as c: c.execute("UPDATE users SET tokens=1000")
b.set_product_field("views","enabled",0)
try: m.api_service(5,{"service":"seen","qty":1000,"link":"https://t.me/x/1"}); print("FAIL disabled buy allowed")
except m.ApiError as e: print("PASS",e)
print("PASS" if not m.products_info(5)["views"]["enabled"] else "FAIL info")
# JFJ
with b.get_db() as c:
    cols=[r[1] for r in c.execute("PRAGMA table_info(requests)")]
    print(cols)
m.reconcile_leaves=lambda *a,**k:[]; m.member_status=lambda *a,**k:"left"; m.chat_title=lambda *a,**k:"T"
b.resolve_chat_ident=lambda cid,link:"@chanx"; b.bot_admin_state=lambda i:True
with b.get_db() as c:
    c.execute("INSERT INTO requests (tracking_code,user_id,member_count,token_cost,link,chat_id,status) VALUES ('C1',6,10,10,'https://t.me/chanx',-100123,'in_progress')")
r=m.api_join_list(5,{}); print("PASS" if len(r["items"])==1 else "FAIL listed",len(r["items"]))
b.block_chan(["@chanx"])
r=m.api_join_list(5,{}); print("PASS" if len(r["items"])==0 else "FAIL blocked still listed")
# confirm برای کد قدیمی در لیست
with b.get_db() as c: c.execute("INSERT OR REPLACE INTO mini_seen (user_id,code,verified) VALUES (5,'C1',1)")
r=m.api_join_confirm(5,{"code":"C1"}); print("PASS" if r.get("gone") else "FAIL confirm",r)
b.unblock_chan("@chanx")
r=m.api_join_list(5,{}); print("PASS" if len(r["items"])==1 else "FAIL unblocked")
b.delete_request_admin("C1",False)
r=m.api_join_list(5,{}); print("PASS" if len(r["items"])==0 else "FAIL deleted still listed")
# بخش‌های خاموش در پنل «فعال/غیرفعال کردن بخش‌ها»
import json as _j
b.set_setting("sec_off",_j.dumps(["bt","sv","sp","bk","sj","rj"]))
ok_=lambda c,n: print("PASS" if c else "FAIL",n)
ok_(set(m.sec_off_list(5))=={"bt","sv","sp","bk","sj","rj"},"secOff برای کاربر عادی")
adm=b.ADMIN_IDS[0]; b.upsert_user({"id":adm,"first_name":"Ad"})
ok_(m.sec_off_list(adm)==[] and "bt" in m.sec_off_list(adm,True),"ادمین در API مستثنی ولی در نمایش می‌بیند")
for fn,body,n in ((m.api_invoice,{"pack":"x"},"خرید شاهی"),(m.api_invoice,{"kind":"sponsor","pack":"x"},"اسپانسری"),(m.api_service,{"service":"member","qty":1},"خدمات"),(m.api_transfer,{"amount":1,"to":6},"انتقال"),(m.api_join_list,{},"شروع JFJ"),(m.api_join_confirm,{"code":"1"},"تایید جوین"),(m.api_request,{"link":"x","count":1},"درخواست JFJ")):
    try: fn(5,body); ok_(False,"باز است: "+n)
    except m.ApiError as e: ok_("غیرفعال" in str(e),"مسدود: "+n)
b.set_setting("sec_off","[]")
ok_(m.sec_off_list(5)==[],"بخش‌ها دوباره فعال")
# ---- webp
import io as _io
from PIL import Image as _Im
_buf=_io.BytesIO(); _Im.effect_noise((320,320),60).convert("RGB").save(_buf,"JPEG",quality=95); _jpg=_buf.getvalue()
_mime,_data=m.webp_pair("image/jpeg",_jpg)
ok_(_mime=="image/webp" and _data[:4]==b"RIFF" and _data[8:12]==b"WEBP" and len(_data)<len(_jpg),"عکس پروفایل/کانال به webp تبدیل می‌شود")
ok_(max(_Im.open(_io.BytesIO(_data)).size)<=128,"حداکثر ۱۲۸ پیکسل")
ok_(m.webp_pair("image/jpeg",b"not an image")==("image/jpeg",b"not an image"),"فایل خراب: همان اصلی برمی‌گردد")
_pb=_io.BytesIO(); _Im.new("RGBA",(64,64),(255,0,0,255)).save(_pb,"PNG"); _png=_pb.getvalue()
import urllib.request as _ur
_orig=_ur.urlopen
class _R:
    def __init__(s,d): s.d=d
    def read(s,n=-1): return s.d
    def __enter__(s): return s
    def __exit__(s,*a): return False
m._EMOJI_MEM.clear(); m._EMOJI_DIR=os.path.join(tempfile.gettempdir(),"jfj_emoji_t"); 
import shutil; shutil.rmtree(m._EMOJI_DIR,ignore_errors=True)
_ur.urlopen=lambda *a,**k: _R(_png)
e1=m.emoji_webp("1f44d.webp"); ok_(e1 and e1[0]=="image/webp" and e1[1][:4]==b"RIFF" and len(e1[1])<len(_png)*2,"ایموجی webp ساخته شد")
_ur.urlopen=lambda *a,**k: (_ for _ in ()).throw(OSError("offline"))
m._EMOJI_MEM.clear(); e2=m.emoji_webp("1f44d.webp"); ok_(e2 and e2[1]==e1[1],"دفعه‌ی بعد از کش دیسک (بدون CDN)")
ok_(m.emoji_webp("../../etc/passwd.webp") is None and m.emoji_webp("zz.webp") is None and m.emoji_webp("1f44d.png") is None,"نام نامعتبر رد می‌شود")
_ur.urlopen=_orig
# انتخاب جدیدترین index.html
import tempfile as _tf, time
_d=_tf.mkdtemp(); _s=os.path.join(_d,"static"); os.makedirs(_s)
open(os.path.join(_s,"index.html"),"w").write("old"); time.sleep(.05); open(os.path.join(_d,"index.html"),"w").write("new")
_h,_sd=m.HERE,m.STATIC_DIR; m.HERE=_d; m.STATIC_DIR=_s
print("PASS" if open(m._index_path()).read()=="new" else "FAIL","جدیدترین index.html انتخاب می‌شود")
m.HERE,m.STATIC_DIR=_h,_sd
