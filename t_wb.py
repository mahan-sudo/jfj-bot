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

for p in ("userx/201","referral","generalx","monster","gamerep?days=7","sponsors?user=201"): G(p)
P("userx/201",{"op":"zero"}); ok(b.get_balance(201)==0,"صفر کردن موجودی")
P("userx/201",{"op":"phone"}); P("userx/201",{"op":"refreset"})
k=list(b.PRODUCT_DEFS)[0]; P("userx/201",{"op":"product","key":k}); ok(b.user_has_product(201,k),"افزودن محصول به کاربر"); P("userx/201",{"op":"product","key":k}); ok(not b.user_has_product(201,k),"برداشتن محصول")
P("referral",{"op":"act_toggle"}); P("generalx",{"op":"phone_verify"}); P("generalx",{"op":"rules_reset"}); P("generalx",{"op":"support_reset"})
P("monster",{"op":"toggle"}); P("monster",{"op":"reset"})

# ===== v7: ناحیه‌ی جدید =====
print("--- v7 ---")
j=G("orders?status=all"); ok(any(o["code"]=="SO1" and "name" in o and "extra" in o for o in j["orders"]),"orders enriched")
j=G("userfull/201"); ok(j["id"]==201 and "betray" in j and isinstance(j["requests"],list),"userfull")
G("userfull/201?x=1")
st,_,_=call("GET","/admin/api/userfull/99999999",cookie=ck); ok(st.startswith("404"),"userfull 404")
with b.get_db() as c:
    c.execute("INSERT INTO requests (tracking_code,user_id,link,member_count,initial_member_count,token_cost,status) VALUES ('RQ7',201,'https://t.me/abc',5,10,2,'in_progress')")
    c.execute("INSERT INTO joins (user_id,tracking_code) VALUES (%s,'RQ7')"%ADM)
j=G("reqinfo/RQ7"); ok(j["code"]=="RQ7" and j["done"]==1 and len(j["joiners"])==1,"reqinfo")
G("reqinfo/RQ7?live=1")
P("reqblock/RQ7",{"block":True}); j=G("reqinfo/RQ7"); ok(j["blocked"],"reqblock on")
P("reqblock/RQ7",{"block":False}); j=G("reqinfo/RQ7"); ok(not j["blocked"],"reqblock off")
j=G("requests?status=in_progress&q=RQ7"); ok(len(j.get("requests",[]))>=1,"requests search")
j=G("gamerep?days=7"); ok("games" in j and "mon" in j and "active" in j,"gamerep new")
P("gametable",{"all":True})
P("broadcastmedia",{"aud":"all","mid":5}); P("broadcastmedia",{"aud":"zzz","mid":5},False); P("broadcastmedia",{"aud":"all"},False)
# upload
def up(kind,data,name="a.jpg"):
    env={"REQUEST_METHOD":"POST","PATH_INFO":"/admin/api/upload","QUERY_STRING":"kind=%s&name=%s"%(kind,name),"wsgi.input":io.BytesIO(data),"CONTENT_LENGTH":str(len(data)),"REMOTE_ADDR":"1.1.1.1","wsgi.url_scheme":"https","HTTP_COOKIE":"jfj_admin="+ck,"HTTP_X_REQUESTED_WITH":"jfj"}
    o={}
    def sr(s,h): o["st"]=s
    bb=b"".join(m.application(env,sr)); return o["st"],bb[:150]
st,bb=up("bad",b"x"); ok(st.startswith("400") or st.startswith("4"),"upload bad kind "+st)
st,bb=up("photo",b""); ok(st.startswith("4"),"upload empty "+st)
st,bb=up("photo",b"x"*(11*1024*1024)); ok(st.startswith("4"),"upload too big "+st)
print("--- v7b ---")
j=G("audit"); ok(len(j["items"])>5 and "action" in j["items"][0],"audit has entries")
ok(not any("password" in (i["detail"] or "") and "…" not in i["detail"] for i in j["items"]),"audit no secrets")
j=G("search?q=SO1"); ok(len(j["orders"])==1,"search order")
j=G("search?q=RQ7"); ok(len(j["requests"])==1,"search req")
j=G("search?q=201"); ok(len(j["users"])>=1,"search user")
j=G("search?q=a"); ok(j["users"]==[],"search short")
j=G("users?sort=neg"); ok("total" in j and "more" in j,"users neg")
G("users?sort=banned&q=u"); G("users?sort=betray"); G("users?sort=phone&page=1")
j=G("admins"); ok(j["can_manage"] and j["admins"][0]["main"],"admins list")
P("admins",{"id":999999},False); P("admins",{"id":"x"},False)
with b.get_db() as c: c.execute("INSERT INTO betrayers (user_id) VALUES (201)") if False else None
P("betrayer/201/unflag",{},False)
if len(b.ADMIN_IDS)>1:
    r=P("admins",{"id":b.ADMIN_IDS[1]}); ok(len(r.get("password",""))>=16,"admin pw reset by main")
j=G("dashx"); ok("today" in j and isinstance(j["new_users"],list) and "refs" in j and "audit" in j,"dashx")
print("--- premoji ---")
b.init_premoji()
j=G("premoji"); ok(j["mode"]=="auto" and len(j["items"])>30 and any(i["key"]=="بازگشت" for i in j["items"]),"premoji get")
P("premoji/mode",{"mode":"off"}); ok(G("premoji")["mode"]=="off","mode off")
P("premoji/mode",{"mode":"zzz"},False)
P("premoji/mode",{"mode":"auto"})
P("premoji/map",{"key":"🎁 پاداش","id":"5843732253829503840"}); j=G("premoji"); ok(any(i["key"]=="پاداش" and i["custom"] for i in j["items"]),"add map (key cored)")
P("premoji/map",{"key":"پاداش","id":"12"},False); P("premoji/map",{"key":"","id":"5843732253829503840"},False); P("premoji/map",{"key":"x","id":""},False)
P("premoji/map",{"key":"قوانین","id":""}); j=G("premoji"); ok([i for i in j["items"] if i["key"]=="قوانین"][0]["disabled"],"disable default")
P("premoji/map",{"key":"قوانین","reset":True}); j=G("premoji"); ok(not [i for i in j["items"] if i["key"]=="قوانین"][0]["custom"],"reset default")
P("premoji/map",{"key":"پاداش","reset":True})
r=P("premoji/test",{}); ok(r.get("ok"),"premoji test send")
P("premoji/nope",{},False)
print("--- premsg ---")
j=G("premsg"); ok(j["mode"]=="auto" and len(j["items"])>80 and any(i["key"]=="موجودی شما:" for i in j["items"]) and len(j["emoji"])>=8,"premsg get")
P("premsg/mode",{"mode":"off"}); ok(G("premsg")["mode"]=="off","premsg off")
P("premsg/mode",{"mode":"zzz"},False)
P("premsg/mode",{"mode":"auto"})
P("premsg/map",{"key":"سلام دوست","id":"5843732253829503840"}); j=G("premsg"); ok(any(i["key"]=="سلام دوست" and i["custom"] for i in j["items"]),"premsg add")
P("premsg/map",{"key":"سلام دوست","id":"12"},False); P("premsg/map",{"key":"","id":"5843732253829503840"},False); P("premsg/map",{"key":"x","id":""},False)
P("premsg/map",{"key":"موجودی:","id":""}); ok([i for i in G("premsg")["items"] if i["key"]=="موجودی:"][0]["disabled"],"premsg disable default")
P("premsg/map",{"key":"موجودی:","reset":True}); ok(not [i for i in G("premsg")["items"] if i["key"]=="موجودی:"][0]["custom"],"premsg reset")
P("premsg/map",{"key":"سلام دوست","reset":True})
r=P("premsg/test",{}); ok(r.get("ok"),"premsg test send")
P("premsg/nope",{},False)
print("--- broadcast codes ---")
sent.clear()
P("broadcast",{"aud":"all","text":"سلام {💎:5825623013852192219} دوستان"})
sm=[p for m,p in sent if m=="sendMessage" and "tg-emoji" in str(p.get("text",""))]
ok(len(sm)==1 and '<tg-emoji emoji-id="5825623013852192219">💎</tg-emoji>' in sm[0]["text"],"web broadcast: code → tg-emoji")
sent.clear(); P("broadcast",{"aud":"all","text":"بدون کد {123}"}); sm=[p for m,p in sent if m=="sendMessage"]
ok(sm and "tg-emoji" not in sm[0]["text"] and "{123}" in sm[0]["text"],"web broadcast: plain text untouched")
