# -*- coding: utf-8 -*-
"""raw/*.json → data/dashboard.json + standalone.html (단일 파일 버전)"""
import json, os, math, datetime as dt

HERE=os.path.dirname(os.path.abspath(__file__))          # macro-src/
ROOT=os.path.dirname(HERE)                                # 저장소 루트
RAW=os.path.join(HERE,"raw")
OUT=os.path.join(ROOT,os.environ.get("OUT_DIR","macro"))  # 배포 폴더
os.makedirs(OUT,exist_ok=True)

def load(n):
    p=os.path.join(RAW,n)
    return json.load(open(p,encoding="utf-8")) if os.path.exists(p) else None
def group(name):
    d=load(f"{name}.json") or {}
    out=[]
    for tk,v in d.items():
        v=dict(v); v["ticker"]=tk
        dl=[p[1] for p in v.get("daily",[])]
        if dl: v["hi52"],v["lo52"]=max(dl),min(dl)
        out.append(v)
    return out
def clamp(v,lo=0.0,hi=100.0): return max(lo,min(hi,v))
def lin(x,x0,x1):
    if x is None: return None
    return clamp((x1-x)/(x1-x0)*100.0)

# ── 안정성 ──────────────────────────────────────────────────────────
def stability(macro,groups):
    m=macro or {}; g=lambda k:(m.get(k) or {}).get("last")
    comps,metrics=[],[]
    tn=next((x for x in groups["fx_rates"] if x["ticker"]=="^TNX"),None)
    ir=next((x for x in groups["fx_rates"] if x["ticker"]=="^IRX"),None)
    yc=round(tn["last"]-ir["last"],2) if (tn and ir) else None
    rec=g("RECPROB"); core=(m.get("CORECPI") or {}).get("yoy"); nfci=g("NFCI")
    unr=g("UNRATE"); cape=g("CAPE")
    vx=next((x for x in groups["indices"] if x["ticker"]=="^VIX"),None); vix=vx["last"] if vx else None
    def add(n,s,d):
        if s is not None: comps.append({"name":n,"score":round(s,1),"detail":d})
    add("침체 확률 (뉴욕연준 모형)",lin(rec,5,45),
        f"{m['RECPROB']['asof']} 시점 확률 {rec:.1f}% · 현재 수익률곡선으로 12개월 뒤를 예측한 값")
    add("물가 (근원 CPI)",None if core is None else lin(abs(core-2.0),0.3,3.5),
        f"근원 전년비 {core:.2f}% · 목표 2%와 {abs(core-2.0):.2f}%p 이격")
    add("금융여건 (시카고연준 NFCI)",lin(nfci,-0.5,0.8),
        f"NFCI {nfci:+.3f} (0 미만 = 평균보다 완화) · {m['NFCI']['asof']} 기준")
    add("수익률곡선 (10Y−3M)",None if yc is None else lin(-yc,-1.5,0.6),
        f"10년 {tn['last']:.2f}% − 3개월 {ir['last']:.2f}% = {yc:+.2f}%p" + (" · 역전" if yc and yc<0 else " · 정상"))
    add("시장 스트레스 (VIX)",lin(vix,13,38), f"VIX {vix:.1f}")
    add("고용 (실업률)",lin(unr,3.8,7.0), f"실업률 {unr:.1f}% · {m['UNRATE']['asof']} 기준")
    add("시장 밸류에이션 (CAPE)",lin(cape,22,42),
        f"실러 CAPE {cape:.1f} — 역사적 최상단. 경기 지표가 아니라 시장이 감당 중인 위험의 크기")
    score=round(sum(c["score"] for c in comps)/len(comps),1) if comps else 50.0
    label=("안정" if score>=70 else "보통" if score>=55 else "주의" if score>=45 else "취약" if score>=30 else "위험")
    eff=m.get("EFFR") or {}
    if eff: metrics.append({"name":"연방기금 실효금리","value":f"{eff['last']:.2f}% (목표 {eff['target_from']:.2f}–{eff['target_to']:.2f}%)"})
    for nm,v in [("미 10년물",f"{tn['last']:.2f}%" if tn else None),("미 3개월물",f"{ir['last']:.2f}%" if ir else None),
                 ("장단기 금리차 10Y−3M",f"{yc:+.2f}%p" if yc is not None else None),
                 ("근원 CPI 전년비",f"{core:.2f}%" if core is not None else None),
                 ("실업률",f"{unr:.1f}%" if unr is not None else None),
                 ("시카고연준 NFCI",f"{nfci:+.3f}" if nfci is not None else None),
                 ("실러 CAPE",f"{cape:.1f}" if cape is not None else None),
                 ("VIX",f"{vix:.1f}" if vix is not None else None)]:
        if v: metrics.append({"name":nm,"value":v})
    comment=("경기 지표는 견조한데 시장 밸류에이션만 홀로 위험 구간에 있다. "
             "침체가 임박했다는 신호는 없고, 문제는 '얼마나 비싼 가격에 그 안정을 사고 있느냐'다. "
             "이 구도에서 무너지는 방식은 경기 악화가 아니라 멀티플 수축이다.")
    rs=(m.get("RECPROB") or {}).get("series")
    return {"score":score,"label":label,"components":comps,"metrics":metrics,"comment":comment,
            "recession_series":rs[-120:] if rs else None,
            "method":"7개 축을 각 0~100점(100=안정)으로 환산해 단순 평균. 각 축의 원지표와 환산 구간을 그대로 적었다."}

# ── 상관행렬 ────────────────────────────────────────────────────────
def correlation(groups,tickers,window=120):
    pool={x["ticker"]:x for x in sum(groups.values(),[])}
    sel=[t for t in tickers if t in pool]
    seq={}
    for t in sel:
        d=pool[t]["daily"][-(window+1):]
        seq[t]={a:b for a,b in d}
    dates=sorted(set.intersection(*[set(seq[t]) for t in sel])) if sel else []
    dates=dates[-(window+1):]
    if len(dates)<30: return None
    rets={t:[seq[t][dates[i]]/seq[t][dates[i-1]]-1 for i in range(1,len(dates))] for t in sel}
    def corr(a,b):
        n=len(a); ma=sum(a)/n; mb=sum(b)/n
        cov=sum((x-ma)*(y-mb) for x,y in zip(a,b))
        va=math.sqrt(sum((x-ma)**2 for x in a)); vb=math.sqrt(sum((y-mb)**2 for y in b))
        return 0.0 if va*vb==0 else cov/(va*vb)
    return {"labels":[pool[t]["name"] for t in sel],"window":len(dates)-1,
            "matrix":[[round(corr(rets[a],rets[b]),2) for b in sel] for a in sel]}

# ── 기관 교집합 ─────────────────────────────────────────────────────
def overlap(insts):
    agg={}
    for it in insts:
        for h in it["top"][:15]:
            a=agg.setdefault(h["name"],{"name":h["name"],"count":0,"value":0.0})
            a["count"]+=1; a["value"]+=h["value"]
    lst=[x for x in agg.values() if x["count"]>=2]
    return sorted(lst,key=lambda x:(-x["count"],-x["value"]))

def build():
    macro=load("macro.json") or {}
    groups={k:group(k) for k in ["indices","commodities","fx_rates","sectors_us","sectors_kr","realestate"]}
    insts=[x for x in (load(f"13f_{k}.json") for k in ["berkshire","blackrock","nps","vanguard"]) if x]
    extra=load("extra.json") or {}
    housing=[]
    z=macro.get("ZHVI")
    if z: housing.append({"name":"미국 주택가격 (Zillow ZHVI 전국)","source":"Zillow Research",
                          "last":z["last"],"asof":z["asof"],"yoy":z.get("yoy"),"series":z["series"][-140:]})
    krh=load("kr_housing.json")
    macro_series=[]
    for k,unit in [("CORECPI",""),("UNRATE","%"),("NFCI",""),("CAPE","")]:
        d=macro.get(k)
        if d: macro_series.append({"label":d["label"],"source":d["source"],"unit":unit,
                                   "last":d["last"],"asof":d["asof"],"series":d["series"][-120:]})
    today=dt.date.today()
    fresh=[]
    for name,asof,maxdays in [("시세",max(x["asof"] for x in groups["indices"]),4),
                              ("근원CPI",(macro.get("CORECPI") or {}).get("asof","–")+"-01",70),
                              ("실업률",(macro.get("UNRATE") or {}).get("asof","–")+"-01",70),
                              ("NFCI",(macro.get("NFCI") or {}).get("asof","–"),30),
                              ("CAPE",(macro.get("CAPE") or {}).get("asof","–")+"-01",45),
                              ("13F",max(i["report_date"] for i in insts) if insts else "–",120)]:
        try:
            d=dt.date.fromisoformat(asof[:10]); stale=(today-d).days>maxdays
            fresh.append({"name":name,"asof":asof[:10],"stale":stale})
        except Exception: fresh.append({"name":name,"asof":str(asof),"stale":False})
    payload={
      "asof":dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
      "groups":groups,"institutions":insts,"inst_overlap":overlap(insts),
      "stability":stability(macro,groups),"macro_series":macro_series,
      "correlation":correlation(groups,["^GSPC","^IXIC","^KS11","GC=F","CL=F","DX-Y.NYB","^TNX","BTC-USD","VNQ","^VIX"]),
      "housing":housing,"kr_housing":krh,
      "rate_odds":extra.get("rate_odds",{"meeting":"–","asof":"–","method":"미수집","outcomes":[],"path":[]}),
      "events":extra.get("events",[]),"scenarios":extra.get("scenarios",[]),
      "sources":{"prices":"Yahoo Finance","macro":"NY연준·시카고연준·BLS·Zillow·multpl","inst":"SEC EDGAR 13F"},
      "disclaimer":("본 페이지는 공개 데이터를 모아 보여주는 정보 도구이며 투자 자문이 아니다. "
        "시세는 종가 기준 스냅샷으로 실시간이 아니고, 13F는 분기 말 신고 자료라 최대 45일 지연된다. "
        "금리 확률은 연방기금 선물 가격에서 직접 환산한 근사치이며 CME FedWatch 공식 수치가 아니다. "
        "안정성 점수와 시나리오 파급 경로는 공개 지표를 정해진 규칙으로 환산·정리한 해석이고 미래를 예측하지 않는다. "
        "최종 판단과 책임은 이용자 본인에게 있다."),
    }
    tpl=open(os.path.join(HERE,"template.html"),encoding="utf-8").read()
    html=tpl.replace("/*__DATA__*/",json.dumps(payload,ensure_ascii=False))
    target=os.path.join(OUT,"index.html")
    open(target,"w",encoding="utf-8").write(html)
    print("%s  %.0f KB" % (target,os.path.getsize(target)/1024))
    print("안정성 %.1f %s · 상관 %s · 교집합 %d종목" % (payload["stability"]["score"],payload["stability"]["label"],
          "OK" if payload["correlation"] else "없음", len(payload["inst_overlap"])))
    return payload

if __name__=="__main__": build()
