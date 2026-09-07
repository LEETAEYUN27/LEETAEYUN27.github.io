# -*- coding: utf-8 -*-
"""한국부동산원 R-ONE Open API — 주간 아파트 매매·전세 가격지수.
   인증키는 코드에 넣지 않는다. 다음 순서로 찾는다:
     1) 환경변수 RONE_KEY
     2) 이 폴더의 secrets.local.json  {"RONE_KEY": "..."}   ← .gitignore 처리됨
"""
import json, os, urllib.request

HERE=os.path.dirname(os.path.abspath(__file__)); RAW=os.path.join(HERE,"raw")
os.makedirs(RAW,exist_ok=True)
def key():
    k=os.environ.get("RONE_KEY","").strip()
    if k: return k
    p=os.path.join(HERE,"secrets.local.json")
    if os.path.exists(p): return json.load(open(p,encoding="utf-8"))["RONE_KEY"].strip()
    return ""

API="https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
TABLES={"sale":("T244183132827305","아파트 매매가격지수"),
        "jeonse":("T247713133046872","아파트 전세가격지수")}
REGIONS={50001:"전국",50008:"서울",50002:"수도권",50016:"경기",50124:"인천"}

def fetch(k,statbl,cls_id):
    out=[]; idx=1
    while True:
        u=(f"{API}?KEY={k}&Type=json&pIndex={idx}&pSize=100"
           f"&STATBL_ID={statbl}&DTACYCLE_CD=WK&CLS_ID={cls_id}")
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read())
        b=d["SttsApiTblData"]; total=b[0]["head"][0]["list_total_count"]
        rows=b[1].get("row",[]) if len(b)>1 else []
        out+=[[r["WRTTIME_DESC"],round(float(r["DTA_VAL"]),3)] for r in rows if r.get("DTA_VAL") is not None]
        idx+=1
        if len(out)>=total or not rows: break
    out.sort()
    return out

if __name__=="__main__":
    k=key()
    if not k:
        print("  [skip] RONE_KEY 없음 — 한국 부동산 섹션은 이번 갱신에서 제외"); raise SystemExit(0)
    res={}
    for tag,(statbl,label) in TABLES.items():
        res[tag]={"label":label,"source":"한국부동산원 R-ONE (주간)","regions":{}}
        for cid,nm in REGIONS.items():
            s=fetch(k,statbl,cid)
            if not s: continue
            yoy=round((s[-1][1]/s[-53][1]-1)*100,2) if len(s)>53 else None
            res[tag]["regions"][nm]={"last":s[-1][1],"asof":s[-1][0],"yoy":yoy,"series":s[-320:]}
            print(f"  {label} {nm:4} {s[-1][0]} {s[-1][1]:.2f}  전년비 {yoy}%  ({len(s)}주)")
    json.dump(res,open(os.path.join(RAW,"kr_housing.json"),"w",encoding="utf-8"),ensure_ascii=False)
    print("saved kr_housing.json")
