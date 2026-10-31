exec(open('t_x.py',encoding='utf-8').read().split("def setupx")[0])
import gzip, zipfile, io, os
ADM=b.ADMIN_IDS[0]
def admcb(data):
    b.v2_admin_callback({"id":"c","from":{"id":ADM,"first_name":"A"},"data":data,"message":{"chat":{"id":ADM},"message_id":5}})
def admdoc(raw,name):
    b._rs_download=lambda m:(raw,name)
    b.handle_update({"update_id":int(time.time()*1000000)%10**12,"message":{"message_id":9,"from":{"id":ADM,"first_name":"A"},"chat":{"id":ADM,"type":"private"},"document":{"file_id":"f","file_name":name,"file_size":len(raw)}}})
def lasttext(): 
    return [q.get("text","") for m,q in sent if m in("sendMessage","editMessageText") and q.get("chat_id")==ADM][-1]
docs=[]
b._send_doc=lambda *a,**k:(docs.append(a),{"ok":True})[1]
b.upsert_user({"id":ADM,"first_name":"Admin"})
for i in (21,22): user(i,500)
# بکاپ مرجع: دو کاربر با ۵۰۰
name,data,_=b.rep_make_backup(); sql=data
ok(name.endswith(".json") and b'"jfj-pg-backup"' in sql,"بکاپ JSON ساخته شد")
# وضعیت فعلی را تغییر بده
user(21,7); user(22,8)
# صفحه
t,k=b.render_restore(); ok("بازیابی بکاپ" in t and "rs_arm" in str(k) and "PostgreSQL" in t,"صفحه‌ی بازیابی")
ok("rs" in b.XPAGES and "adm_p:x:rs" in str(b.render_general()[1]),"دکمه در تنظیمات عمومی")
def tokens(i): return b.get_db().execute("SELECT tokens FROM users WHERE id=?",(i,)).fetchone()[0]
def run(raw,fname,label):
    admcb("adm_p:x:rs_arm"); ok(b.get_state(ADM)[1].get("name")=="rs_wait",label+": منتظر فایل")
    admdoc(raw,fname); t=lasttext()
    return t
for label,raw,fn in (("json",sql,"a.json"),("gz",gzip.compress(sql),"a.json.gz"),
                     ("zip",(lambda: (lambda bio:(zipfile.ZipFile(bio,"w").writestr("x/a.json",sql) or bio.getvalue()))(io.BytesIO()))(),"a.zip")):
    user(21,7); user(22,8)
    t=run(raw,fn,label); ok("تأیید بازیابی" in t and "rs_ok" in str([q for m,q in sent if q.get("chat_id")==ADM][-1].get("reply_markup")),label+": خلاصه و تأیید")
    ok(tokens(21)==7,label+": قبل از تأیید چیزی عوض نشده")
    admcb("adm_p:x:rs_ok"); ok(tokens(21)==500 and tokens(22)==500,label+": بازیابی شد"); ok("بازیابی کامل شد" in lasttext(),label+": پیام موفقیت")
# بکاپ قدیمی (بدون جدول‌های بازی) → ساختار جدید خودکار ساخته می‌شود و داده‌ها می‌مانند
import json as _j
d_=_j.loads(sql)
for n_ in [n for n in d_["tables"] if n.startswith("g_")]: del d_["tables"][n_]
old_s=_j.dumps(d_).encode()
user(21,7); t=run(old_s,"old.json","قدیمی"); admcb("adm_p:x:rs_ok")
with b.get_db() as c: ok(b._db.table_exists(c,"g_tables") and tokens(21)==500,"بکاپ قدیمی: ساختار جدید ساخته شد")
# ترتیب rid و شمارنده‌ها بعد از بازیابی
with b.get_db() as c:
    c.execute("INSERT INTO transfers (sender_id, recipient_id, amount) VALUES (21,22,5)")
    ok(c.execute("SELECT MAX(id) FROM transfers").fetchone()[0]>=1,"شمارنده‌ی id بعد از بازیابی کار می‌کند")
# فایل‌های بد
bad=(("متن",b"hello world"),("sql",b"CREATE TABLE z(a);"),("json خراب",b'{"format":"jfj-pg-backup","tables":'),
     ("json بیگانه",b'{"a":1}'),("sqlite",b"SQLite format 3\x00"+b"0"*100),
     ("جدول ناقص",b'{"format":"jfj-pg-backup","tables":{"users":{"columns":["id"],"rows":[[1]]}}}'),
     ("نام جدول تزریقی",b'{"format":"jfj-pg-backup","tables":{"users":{"columns":["id"],"rows":[]},"settings":{"columns":["key"],"rows":[]},"x; DROP TABLE users":{"columns":[],"rows":[]}}}'))
for label,raw in bad:
    user(21,7); t=run(raw,"bad.json","بد-"+label); ok("❌" in t and tokens(21)==7,"رد شد: "+label)
    b.set_state(ADM,"admin_panel")
# بازیابی ناموفق وسط کار = هیچ تغییری (تراکنش)
bad_d=_j.loads(sql); bad_d["tables"]["users"]["rows"][0][bad_d["tables"]["users"]["columns"].index("id")]=None   # نقض NOT NULL/PK
user(21,7)
t=run(_j.dumps(bad_d).encode(),"tx.json","تراکنش"); admcb("adm_p:x:rs_ok")
ok(tokens(21)==7 and "❌" in lasttext(),"بازیابی خراب → rollback کامل، داده‌ی فعلی سالم")
b.set_state(ADM,"admin_panel")
# انصراف
t=run(sql,"a.json","لغو"); admcb("adm_p:x:rs_no"); ok(tokens(21)==7 and b.get_state(ADM)[0]=="admin_panel","انصراف")
ok(not any(f.startswith("restore_tmp_") for f in os.listdir(b.BACKUP_DIR)),"فایل موقت پاک شد")
# تأیید منقضی
admcb("adm_p:x:rs_ok"); ok(tokens(21)==7,"تأیید بدون فایل بی‌اثر")
# فایل روی سرور
d=b.BACKUP_DIR; sp=os.path.join(d,"restore.json.gz"); open(sp,"wb").write(gzip.compress(sql))
ok(sp in b.rs_server_files(),"فایل سرور پیدا شد")
admcb("adm_p:x:rs_f:0"); ok("تأیید بازیابی" in lasttext(),"فایل سرور: خلاصه"); admcb("adm_p:x:rs_ok")
ok(tokens(21)==500 and not os.path.exists(sp) and any(f.startswith("restore.json.gz.done_") for f in os.listdir(d)),"فایل سرور مصرف شد")
for f in os.listdir(d):
    if f.startswith(("restore.json","pre_restore_")): os.remove(os.path.join(d,f))
ok(len(docs)>=1,"بکاپ ایمنی ارسال شد")
# غیر ادمین
b.set_state(21,"none") if False else None
# فایل بزرگ
b._rs_download=b.__dict__["_rs_download"]
