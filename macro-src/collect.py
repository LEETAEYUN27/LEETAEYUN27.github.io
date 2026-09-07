# -*- coding: utf-8 -*-
"""클라우드 컨테이너용 수집기 — Yahoo chart API · SEC EDGAR · NY연준 · 시카고연준 · BLS · multpl · Zillow."""
import json, os, re, io, time, urllib.request, datetime as dt

HERE=os.path.dirname(os.path.abspath(__file__)); RAW=os.path.join(HERE,"raw"); os.makedirs(RAW,exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (research; a01092796847@gmail.com)"}
SEC={"User-Agent":"taeyun a01092796847@gmail.com"}

def get(u,h=UA,timeout=25,retry=3):
    last=None
    for i in range(retry):
        try:
            return urllib.request.urlopen(urllib.request.Request(u,headers=h),timeout=timeout).read()
        except Exception as e:
            last=e; time.sleep(1.5*(i+1))
    raise last

# ── 1. 시세 (Yahoo chart API) ───────────────────────────────────────
GROUPS={
 "indices":{"^GSPC":"S&P 500","^IXIC":"나스닥 종합","^DJI":"다우존스","^RUT":"러셀 2000",
   "^KS11":"코스피","^KQ11":"코스닥","^N225":"닛케이 225","^HSI":"항셍",
   "^STOXX50E":"유로 STOXX 50","^SOX":"필라델피아 반도체","^VIX":"VIX 변동성"},
 "commodities":{"GC=F":"금","SI=F":"은","CL=F":"WTI 원유","BZ=F":"브렌트유","HG=F":"구리",
   "NG=F":"천연가스","PL=F":"백금","BTC-USD":"비트코인"},
 "fx_rates":{"DX-Y.NYB":"달러지수(DXY)","KRW=X":"원/달러","JPY=X":"엔/달러","EURUSD=X":"유로/달러",
   "CNY=X":"위안/달러","^TNX":"미 10년물","^FVX":"미 5년물","^IRX":"미 13주(3개월)"},
 "sectors_us":{"XLK":"기술","XLF":"금융","XLE":"에너지","XLV":"헬스케어","XLI":"산업재",
   "XLY":"경기소비재","XLP":"필수소비재","XLU":"유틸리티","XLB":"소재","XLRE":"부동산","XLC":"커뮤니케이션"},
 "sectors_kr":{"091160.KS":"KODEX 반도체","091170.KS":"KODEX 은행","117460.KS":"KODEX 에너지화학",
   "266370.KS":"KODEX IT","227540.KS":"TIGER 헬스케어","102960.KS":"KODEX 기계장비",
   "139260.KS":"TIGER 200 IT","228790.KS":"TIGER 화장품"},
 "realestate":{"VNQ":"미 리츠(VNQ)","IYR":"미 부동산(IYR)","REZ":"미 주거리츠","SCHH":"미 리츠(SCHH)",
   "181480.KS":"KINDEX 미국리츠","329200.KS":"TIGER 리츠부동산","088980.KS":"맥쿼리인프라",
   "365550.KS":"ESR켄달스퀘어리츠","330590.KS":"롯데리츠"},
}
Y="https://query1.finance.yahoo.com/v8/finance/chart/{}?range={}&interval={}"

def yahoo(t,rng,iv):
    d=json.loads(get(Y.format(urllib.parse.quote(t),rng,iv)))
    r=d["chart"]["result"][0]
    ts=r["timestamp"]; cl=r["indicators"]["quote"][0]["close"]
    out=[]
    for a,b in zip(ts,cl):
        if b is None: continue
        out.append([dt.datetime.utcfromtimestamp(a).strftime("%Y-%m-%d" if iv=="1d" else "%Y-%m"), round(float(b),4)])
    return out
import urllib.parse

def chg(s,n):
    return None if len(s)<=n else round((s[-1][1]/s[-1-n][1]-1)*100,2)

def collect_prices(gname):
    names=GROUPS[gname]; out={}
    for t,label in names.items():
        try:
            daily=yahoo(t,"1y","1d"); monthly=yahoo(t,"25y","1mo")
            if not daily: print("  skip",t); continue
            yr=daily[-1][0][:4]
            first=[p for p in daily if p[0][:4]==yr]
            out[t]={"name":label,"last":daily[-1][1],"asof":daily[-1][0],
                "chg":{k:chg(daily,n) for k,n in [("d1",1),("w1",5),("m1",21),("m3",63),("m6",126),("y1",251)]},
                "ytd":round((daily[-1][1]/first[0][1]-1)*100,2) if first else None,
                "daily":daily,"monthly":monthly}
            print(f"  ok {t:12} {out[t]['last']:>12,.2f} {out[t]['asof']}")
            time.sleep(0.25)
        except Exception as e: print("  ERR",t,str(e)[:60])
    json.dump(out,open(os.path.join(RAW,f"{gname}.json"),"w",encoding="utf-8"),ensure_ascii=False)
    return out

# ── 2. SEC 13F ──────────────────────────────────────────────────────
FILERS={"berkshire":("0001067983","버크셔 해서웨이"),"blackrock":("0002012383","블랙록"),
        "nps":("0001608046","국민연금공단"),"vanguard":("0000102909","뱅가드")}
def collect_13f(key):
    cik,label=FILERS[key]
    j=json.loads(get(f"https://data.sec.gov/submissions/CIK{cik}.json",SEC))
    r=j["filings"]["recent"]; acc=rdate=None
    for i,f in enumerate(r["form"]):
        if f=="13F-HR": acc=r["accessionNumber"][i].replace("-",""); rdate=r["reportDate"][i]; break
    idx=json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json",SEC))
    xml=[f["name"] for f in idx["directory"]["item"] if f["name"].endswith(".xml") and "primary_doc" not in f["name"]]
    raw=get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{xml[0]}",SEC).decode("utf-8","replace")
    raw=re.sub(r'<(/?)\w+:',r'<\1',raw)
    agg={}
    for blk in re.findall(r'<infoTable>(.*?)</infoTable>',raw,re.S):
        g=lambda t:(re.search(r'<%s>(.*?)</%s>'%(t,t),blk,re.S).group(1).strip()
                    if re.search(r'<%s>(.*?)</%s>'%(t,t),blk,re.S) else "")
        try: v=float(g("value"))
        except ValueError: continue
        n=g("nameOfIssuer").replace("&amp;","&")
        a=agg.setdefault(n,{"name":n,"value":0.0}); a["value"]+=v
    lst=sorted(agg.values(),key=lambda x:-x["value"]); tot=sum(x["value"] for x in lst) or 1
    for x in lst: x["pct"]=round(x["value"]/tot*100,2)
    res={"key":key,"label":label,"report_date":rdate,"total_value_usd":tot,
         "n_positions":len(lst),"top":lst[:15]}
    json.dump(res,open(os.path.join(RAW,f"13f_{key}.json"),"w",encoding="utf-8"),ensure_ascii=False)
    print(f"  {label} {rdate} ${tot/1e9:,.0f}B {len(lst)}종목 1위 {lst[0]['name']} {lst[0]['pct']}%")

# ── 3. 거시 ─────────────────────────────────────────────────────────
def collect_macro():
    m={}
    # NY연준 침체확률 (allmonth.xls)
    try:
        import pandas as pd
        raw=get("https://www.newyorkfed.org/medialibrary/media/research/capital_markets/allmonth.xls")
        df=pd.read_excel(io.BytesIO(raw))
        dc="Date"; pc="Rec_prob"
        s=df[[dc,pc]].dropna()
        ser=[[str(pd.to_datetime(a).date())[:7], round(float(b)*(100 if float(b)<=1 else 1),2)] for a,b in s.values]
        m["RECPROB"]={"label":"뉴욕연준 12개월 침체확률","source":"NY Fed Treasury-spread 모형",
                      "last":ser[-1][1],"asof":ser[-1][0],"series":ser[-240:]}
        print("  침체확률",ser[-1])
    except Exception as e: print("  ERR 침체확률",str(e)[:80])
    # 시카고연준 NFCI
    try:
        t=get("https://www.chicagofed.org/-/media/publications/nfci/nfci-data-series-csv.csv").decode("utf-8","replace")
        rows=[r.split(",") for r in t.strip().splitlines()[1:]]
        ser=[[r[0],float(r[1])] for r in rows if len(r)>1 and r[1] not in ("","NA")]
        ser=[[dt.datetime.strptime(d,"%m/%d/%Y").strftime("%Y-%m-%d") if "/" in d else d, v] for d,v in ser]
        ser.sort()
        m["NFCI"]={"label":"시카고연준 금융여건지수","source":"Chicago Fed",
                   "last":round(ser[-1][1],3),"asof":ser[-1][0],"series":ser[-300:]}
        print("  NFCI",ser[-1])
    except Exception as e: print("  ERR NFCI",str(e)[:80])
    # BLS 근원CPI / 실업률
    for sid,label,key in [("CUSR0000SA0L1E","근원 소비자물가(식품·에너지 제외)","CORECPI"),
                          ("LNS14000000","실업률","UNRATE")]:
        try:
            h=get(f"https://data.bls.gov/timeseries/{sid}").decode("utf-8","replace")
            rows=re.findall(r'<TH scope="row">(\d{4})</TH>((?:<TD>[^<]*</TD>)+)',h,re.I)
            ser=[]
            for yr,tds in rows:
                vals=re.findall(r'<TD>([^<]*)</TD>',tds,re.I)
                for i,v in enumerate(vals[:12]):
                    v=v.strip().replace(",","")
                    if re.match(r'^-?\d+(\.\d+)?$',v): ser.append([f"{yr}-{i+1:02d}",float(v)])
            ser.sort()
            if ser:
                m[key]={"label":label,"source":"BLS","last":ser[-1][1],"asof":ser[-1][0],"series":ser[-180:]}
                if key=="CORECPI" and len(ser)>12:
                    m[key]["yoy"]=round((ser[-1][1]/ser[-13][1]-1)*100,2)
                print(" ",key,ser[-1], m[key].get("yoy",""))
        except Exception as e: print("  ERR",key,str(e)[:80])
    # multpl CAPE
    try:
        h=get("https://www.multpl.com/shiller-pe/table/by-month").decode("utf-8","replace")
        rows=re.findall(r'<td>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td>\s*(?:&#x2002;)?\s*([\d.]+)',h)
        ser=[[dt.datetime.strptime(d,"%b %d, %Y").strftime("%Y-%m"),float(v)] for d,v in rows]
        ser.sort()
        m["CAPE"]={"label":"실러 CAPE (경기조정 PER)","source":"multpl.com",
                   "last":ser[-1][1],"asof":ser[-1][0],"series":ser[-300:]}
        print("  CAPE",ser[-1])
    except Exception as e: print("  ERR CAPE",str(e)[:80])
    # 정책금리 EFFR
    try:
        d=json.loads(get("https://markets.newyorkfed.org/api/rates/unsecured/effr/last/1.json"))["refRates"][0]
        m["EFFR"]={"label":"연방기금 실효금리","source":"NY Fed","last":d["percentRate"],
                   "asof":d["effectiveDate"],"target_from":d["targetRateFrom"],"target_to":d["targetRateTo"]}
        print("  EFFR",d["percentRate"],d["targetRateFrom"],"-",d["targetRateTo"])
    except Exception as e: print("  ERR EFFR",str(e)[:80])
    # 미국 주택가격 (Zillow ZHVI 전국)
    try:
        t=get("https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv").decode("utf-8","replace")
        lines=t.splitlines(); hdr=lines[0].split(",")
        row=next(l for l in lines[1:] if l.startswith("102001,") or ",United States," in l)
        vals=row.split(","); ser=[]
        for i,c in enumerate(hdr):
            if re.match(r'^\d{4}-\d{2}-\d{2}$',c) and i<len(vals) and vals[i]:
                ser.append([c[:7],round(float(vals[i]))])
        m["ZHVI"]={"label":"미국 주택가격 (Zillow ZHVI 전국)","source":"Zillow Research",
                   "last":ser[-1][1],"asof":ser[-1][0],"series":ser[-160:],
                   "yoy":round((ser[-1][1]/ser[-13][1]-1)*100,2)}
        print("  ZHVI",ser[-1],m["ZHVI"]["yoy"])
    except Exception as e: print("  ERR ZHVI",str(e)[:80])
    json.dump(m,open(os.path.join(RAW,"macro.json"),"w",encoding="utf-8"),ensure_ascii=False)
    return m

if __name__=="__main__":
    import sys
    a=sys.argv[1]
    if a in GROUPS: collect_prices(a)
    elif a=="13f":
        for k in FILERS: collect_13f(k)
    elif a=="macro": collect_macro()
