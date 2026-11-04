import os, sys, io, json
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b
pgtest.fresh("wb")
b.install_schema(); b.migrate_schema(); b.seed_products()
import miniapp as m
m._schema_done=True; b.BOT_ID=999; b.BOT_USERNAME="jfj_bot"
import texts as T, webadmin as W
sent=[]
def fake(method,_timeout=45,**p):
    sent.append((method,p))
    if method=="getChat": return {"ok":True,"result":{"id":-100123456,"title":"T"}}
    return {"ok":True,"result":{"message_id":len(sent)+10}}
b.tg=fake; T.init(b); b.TEXTS=T
try:
    import games; games.init(b); b.GAMES=games
except Exception as e: print("games init:",e)
def ok(c,n): print(("PASS " if c else "FAIL ")+n)
ADM=b.ADMIN_IDS[0]
for u in (ADM,201): b.upsert_user({"id":u,"first_name":"U","username":"u%d"%u})
def call(method,path,body=None,cookie=None):
    raw=json.dumps(body or {}).encode()
    env={"REQUEST_METHOD":method,"PATH_INFO":path.split("?")[0],"QUERY_STRING":path.partition("?")[2],"wsgi.input":io.BytesIO(raw),"CONTENT_LENGTH":str(len(raw)),"REMOTE_ADDR":"1.1.1.1","wsgi.url_scheme":"https"}
    if cookie: env["HTTP_COOKIE"]="jfj_admin="+cookie
    if method=="POST": env["HTTP_X_REQUESTED_WITH"]="jfj"
    out={}
    def sr(st,h): out["st"]=st; out["h"]=dict(h)
    bb=b"".join(m.application(env,sr))
    try: j=json.loads(bb)
    except Exception: j=bb[:200]
    return out["st"],out["h"],j
pw=W.set_password(ADM)
st,h,j=call("POST","/admin/api/login",{"id":ADM,"password":pw}); ck=h["Set-Cookie"].split(";")[0].split("=",1)[1]
def G(p):
    st,_,j=call("GET","/admin/api/"+p,cookie=ck); ok(st.startswith("200"),"GET "+p+" "+(st if not st.startswith("200") else "")+(str(j)[:150] if not st.startswith("200") else "")); return j
def P(p,body,good=True):
    st,_,j=call("POST","/admin/api/"+p,body,cookie=ck); ok(st.startswith("200")==good,"POST "+p+" "+json.dumps(body,ensure_ascii=False)[:60]+(" -> "+st+str(j)[:120] if st.startswith("200")!=good else "")); return j
for p in ("charts?days=7","orders","products","packs","finance","general","blocked","sponsors","games","reports","userorders/201"): G(p)
with b.get_db() as c: c.execute("INSERT INTO service_orders (tracking_code,user_id,service,quantity,token_cost,link) VALUES ('SO1',201,'views',100,5,'x')")
bal=b.get_balance(201); P("order/SO1",{"ok":False}); ok(b.get_balance(201)==bal+5,"لغو سفارش، بازگشت شاهی"); P("order/SO1",{"ok":True},False)
P("product/views",{"field":"min_qty","value":200}); ok(b.get_product("views")["min_qty"]==200,"حداقل محصول")
P("product/views",{"field":"enabled","value":False}); ok(not b.get_product("views")["enabled"],"خاموش شدن محصول")
n=len(b.JTOKEN_PRODUCTS); P("packs",{"kind":"j","op":"add","amount":77,"price":7000}); ok(len(b.JTOKEN_PRODUCTS)==n+1,"افزودن بسته")
pid=[p["id"] for p in b.JTOKEN_PRODUCTS if p["tokens"]==77][0]; P("packs",{"kind":"j","op":"del","id":pid}); ok(len(b.JTOKEN_PRODUCTS)==n,"حذف بسته")
P("packs",{"kind":"p","op":"add","amount":5,"price":9000})
P("finance",{"op":"card","value":"6037 9911 2233 4455"}); ok(b.get_setting("cfg_card")=="6037-9911-2233-4455","کارت")
P("finance",{"op":"paytoggle","method":"zarin"},False); P("finance",{"op":"zp_merchant","value":"a"*36}); P("finance",{"op":"site_url","value":"https://x.ir"}); P("finance",{"op":"paytoggle","method":"zarin"})
P("finance",{"op":"crypto_wallet","value":"T"+"a"*30}); P("finance",{"op":"crypto_rate","value":"60000"}); P("finance",{"op":"paytoggle","method":"crypto"})
P("finance",{"op":"unit_price","value":"1500"}); P("finance",{"op":"bonus_per","value":"100"}); P("finance",{"op":"bonus_amount","value":"5"}); P("finance",{"op":"bonus_toggle"}); ok(b.bonus_state()["active"],"بونوس فعال")
P("finance",{"op":"disc_add","min":50,"pct":10,"hours":0}); ok(len(b.sjson("disc_tiers",[]))==1,"پله‌ی تخفیف"); P("finance",{"op":"disc_del","index":0})
j=P("dcode",{"user":201,"kind":"pct","value":15,"hours":24}); ok(j.get("code"),"کد تخفیف"); G("finance")
bal=b.get_balance(201); P("masscharge",{"mode":"add","amount":3,"confirm":True}); ok(b.get_balance(201)==bal+3,"شارژ همگانی"); P("masscharge",{"mode":"add","amount":3},False)
P("general",{"op":"section","key":b.SECTIONS[0][0]}); ok(b.SECTIONS[0][0] in b.sections_off(),"بخش خاموش")
P("general",{"op":"fj_add","value":"@mychan"}); P("general",{"op":"fj_toggle"}); ok(len(b.sjson("fj_list",[]))==1,"جوین اجباری"); P("general",{"op":"fj_del","index":0})
P("general",{"op":"support_id","value":"@sup_port"}); P("general",{"op":"cron","value":"5"}); P("general",{"op":"vc_mode","value":"public"}); P("general",{"op":"vc_toggle"})
P("blocked",{"value":"@badchan"}); ok(b._block_keys(),"مسدود"); P("blocked",{"op":"del","key":"@badchan"})
P("sponsor",{"op":"new","user":201,"hours":24,"ref":"@mych"}); sid=G("sponsors")["subs"][0]["id"]; P("sponsor",{"op":"add","id":sid,"hours":2}); P("sponsor",{"op":"cancel","id":sid})
P("reports",{"key":b.REPORT_TOPICS[0][0],"off":True}); ok(b.REPORT_TOPICS[0][0] in b.rep_off(),"گزارش خاموش")
g=G("games"); 
if g["games"]: P("games",{"op":"toggle","key":"s"}); 
if g["cfg"]: P("games",{"op":"cfg","name":g["cfg"][0]["name"],"value":g["cfg"][0]["value"]})
P("usercard/201",{}); P("reqdel/NOPE",{},False)
