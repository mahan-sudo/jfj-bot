import os, sys
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),".."))
import pgtest
import bot_test as b
pgtest.fresh("bt")
b.install_schema(); b.migrate_schema()
def ok(c,n): print(("PASS " if c else "FAIL ")+n)
b.tg=lambda *a,**k:{"ok":True,"result":{"message_id":1}}
for u in (90,91,92): b.upsert_user({"id":u,"first_name":"U","username":"u%d"%u})
def joins(u,n,left):
    with b.get_db() as c:
        for i in range(n):
            c.execute("INSERT INTO joins (user_id,tracking_code,joined_at,left_at) VALUES (?,?,?,?)",(u,"T%d_%d"%(u,i),"2026-11-01 10:00:00","2026-11-02 10:00:00" if left else None))
def req(u):
    with b.get_db() as c: c.execute("INSERT INTO requests (tracking_code,user_id,link,member_count,token_cost,status) VALUES (?,?,?,?,?,?)",("R%d"%u,u,"https://t.me/x",5,1,"in_progress"))
# 90: ordered, left 9, negative balance -> verdict
req(90); joins(90,9,True); b.set_balance(90,-50) if hasattr(b,"set_balance") else None
s=b.betrayal_stats(90); ok(s["verdict"],"leaver with 9 lefts flagged: "+s["reason"])
# 91: no request -> not betrayer
joins(91,9,True); ok(not b.betrayal_stats(91)["verdict"],"no request => safe")
# 92: ordered, only 2 lefts -> safe
req(92); joins(92,2,True); ok(not b.betrayal_stats(92)["verdict"],"too few lefts => safe")
ok(b.betrayal_flag(90) in (True,None,False),"flag runs")
with b.get_db() as c: n=c.execute("SELECT COUNT(*) FROM betrayers WHERE user_id=90").fetchone()[0]
ok(n==1,"flagged stored once"); b.betrayal_flag(90)
with b.get_db() as c: n=c.execute("SELECT COUNT(*) FROM betrayers WHERE user_id=90").fetchone()[0]
ok(n==1,"no duplicate")
