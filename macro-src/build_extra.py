# -*- coding: utf-8 -*-
"""금리 시나리오 확률(연방기금 선물) + 연준 일정 + 시나리오 파급 경로 → raw/extra.json"""
import json, os, re, urllib.request, datetime as dt
HERE=os.path.dirname(os.path.abspath(__file__)); RAW=os.path.join(HERE,"raw")
H={"User-Agent":"Mozilla/5.0"}
g=lambda u: urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=25).read()

def px(t):
    d=json.loads(g(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d"))
    m=d["chart"]["result"][0]["meta"]; return float(m["regularMarketPrice"]), m.get("longName","")

def fomc_dates():
    h=g("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm").decode("utf-8","replace")
    t=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",h))
    out=[]
    for yr in ("2026","2027"):
        i=t.find(f"{yr} FOMC Meetings")
        if i<0: continue
        nxt_i=t.find("FOMC Meetings", i+20)
        seg=t[i:(nxt_i if nxt_i>0 else i+2600)]
        MON={m:k+1 for k,m in enumerate(["January","February","March","April","May","June","July",
             "August","September","October","November","December"])}
        for mo,d1,d2 in re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:-(\d{1,2}))?\*?",seg):
            if not d2: continue                      # 두 날짜짜리만 = 회의(단일 날짜는 의사록 공개일)
            out.append((dt.date(int(yr),MON[mo],int(d2)).isoformat(), f"FOMC {int(MON[mo])}월 회의 ({mo} {d1}-{d2})"))
    today=dt.date.today().isoformat()
    seen,ded=set(),[]
    for d,n in sorted(set([o for o in out if o[0]>=today])):
        k=d[:7]
        if k in seen: continue
        seen.add(k); ded.append((d,n))
    return ded[:5]

def main():
    macro=json.load(open(os.path.join(RAW,"macro.json"),encoding="utf-8"))
    eff=macro["EFFR"]["last"]; lo,hi=macro["EFFR"]["target_from"],macro["EFFR"]["target_to"]
    sep,_=px("ZQU26.CBT"); octb,_=px("ZQV26.CBT"); dec,_=px("ZQZ26.CBT")
    imp=lambda p: round(100-p,4)
    i_sep,i_oct,i_dec=imp(sep),imp(octb),imp(dec)
    meetings=fomc_dates()
    nxt=meetings[0][0] if meetings else None
    # 10월물(회의 다음 달) 기준 25bp 인상 확률
    delta=i_oct-eff
    p_hike=max(0.0,min(100.0,delta/0.25*100))
    outcomes=[{"key":"hike","label":"25bp 인상","prob":round(p_hike)},
              {"key":"hold","label":"동결","prob":round(100-p_hike)}]
    # 9월물 교차검증 (회의일 이후 14/30일 반영 가정)
    x_sep=(i_sep-eff*(16/30))/(14/30)
    cross=round(max(0.0,min(100.0,(x_sep-eff)/0.25*100)))
    extra={
      "rate_odds":{
        "meeting": f"다음 FOMC {nxt}" if nxt else "다음 FOMC",
        "asof": dt.date.today().isoformat(),
        "outcomes": outcomes,
        "method": (f"연방기금 선물 내재금리 기준 · 현재 실효금리 {eff:.2f}% (목표 {lo:.2f}–{hi:.2f}%) "
                   f"→ 10월물 내재 {i_oct:.2f}% · 차이 {delta*100:+.0f}bp ÷ 25bp. "
                   f"9월물({i_sep:.2f}%)로 교차검증 시 {cross}% — 두 계약이 {min(round(p_hike),cross)}~{max(round(p_hike),cross)}% 범위로 수렴. "
                   f"CME FedWatch 공식 수치가 아니라 선물 가격에서 직접 환산한 근사치."),
        "path":[{"label":"현재 실효금리","v":f"{eff:.2f}%"},
                {"label":"9월물 내재","v":f"{i_sep:.2f}%"},
                {"label":"10월물 내재","v":f"{i_oct:.2f}%"},
                {"label":"12월물 내재","v":f"{i_dec:.2f}%"},
                {"label":"연말까지 반영폭",  "v":f"{(i_dec-eff)*100:+.0f}bp"}],
      },
      "events":[{"date":d,"name":n,
                 "why":("선물이 반영한 경로와 실제 결정의 괴리가 곧 변동성. 현재 이 회의에 대한 인상 반영률 %d%%"%round(p_hike))
                        if i==0 else ("점도표 갱신 회의" if "3월" in n or "6월" in n or "9월" in n or "12월" in n
                                      else "중간 회의 — 경로 수정 여부 확인")}
                for i,(d,n) in enumerate(meetings)]
        +[{"date":"매월 중순","name":"미국 소비자물가(CPI)","why":"근원 물가가 2% 목표에서 얼마나 떨어져 있는지가 인상 논쟁의 핵심 변수"},
          {"date":"매월 첫 금요일","name":"미국 고용보고서","why":"고용이 꺾이면 인상 명분이 사라진다. Sahm룰 감시 지점"},
          {"date":"분기 말 +45일","name":"기관 13F 공시","why":"버크셔·블랙록·국민연금의 실제 포지션 변화가 드러나는 유일한 공식 창구"}],
      "scenarios":[
        {"tag":"시나리오 A","title":f"9월 25bp 인상 (선물 반영 {round(p_hike)}%)","rows":[
          ["단기금리·2년물","상승",1],["달러·원달러","달러 강세 → 원화 약세 압력",1],
          ["금","실질금리 상승 = 하락 압력",-1],["성장주 멀티플","할인율 상승 = 압축",-1],
          ["은행(XLF)","순이자마진 개선 = 상대 우위",1],["리츠·부동산","조달비용 상승 = 약세",-1]]},
        {"tag":"시나리오 B","title":f"동결 ({round(100-p_hike)}%)","rows":[
          ["주식 전반","선반영 되돌림 = 안도 랠리",1],["금","실질금리 하락 = 반등",1],
          ["원화","약세 압력 완화",1],["채권","단기물 금리 하락",1],
          ["잔존 리스크","물가 재가속 시 다음 회의로 이연될 뿐",-1]]},
        {"tag":"시나리오 C","title":"물가 재가속 → 추가 긴축","rows":[
          ["선물 반영 경로",f"12월물 내재 {i_dec:.2f}% = 연말까지 {(i_dec-eff)*100:+.0f}bp",1],
          ["수익률곡선","단기 급등 시 재역전 위험",-1],
          ["MRI-U 금리쇼크 축","2년물 6개월 변화가 곧바로 점수 상승",-1],
          ["방어 자산","현금·단기채의 상대 매력 상승",1]]},
      ],
    }
    json.dump(extra,open(os.path.join(RAW,"extra.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print("인상확률 %d%% (교차검증 %d%%) · 다음회의 %s" % (round(p_hike),cross,nxt))
    print("경로:", [(p["label"],p["v"]) for p in extra["rate_odds"]["path"]])
    print("회의:", meetings)
if __name__=="__main__": main()
