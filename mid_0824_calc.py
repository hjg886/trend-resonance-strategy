#!/usr/bin/env python3
"""2026-08-24 午盘小结计算脚本（数据截至午间11:30）"""
import json, math
from datetime import date

SRC = r'E:\fnOS\文档\证券\中线趋势共振策略\kline_mid_0824.txt'
with open(SRC, 'r', encoding='utf-8') as f:
    lines = f.readlines()

data_by_symbol = {}
for line in lines:
    parts = line.strip().split('|')
    if len(parts) < 8 or parts[1].strip() in ('', 'symbol', '---'):
        continue
    try:
        sym = parts[1].strip(); d = parts[2].strip()
        o = float(parts[3]); c = float(parts[4]); h = float(parts[5]); l = float(parts[6])
        v = float(parts[7]) if parts[7] else 0
        data_by_symbol.setdefault(sym, []).append(
            {'date': d, 'open': o, 'close': c, 'high': h, 'low': l, 'volume': v})
    except (ValueError, IndexError):
        continue
for sym in data_by_symbol:
    data_by_symbol[sym].reverse()

def vol20(data):
    if len(data) < 21: return None
    rets = [(data[-i]['close']-data[-(i+1)]['close'])/data[-(i+1)]['close'] for i in range(1,21)]
    m = sum(rets)/len(rets); var = sum((r-m)**2 for r in rets)/(len(rets)-1)
    return math.sqrt(var)*math.sqrt(252)*100

def ma(data, p):
    return sum(d['close'] for d in data[-p:])/p if len(data) >= p else None

def adx(data, p=14):
    if len(data) < p*2: return None
    tr=[]; pdm=[]; mdm=[]
    for i in range(1,len(data)):
        hi,lo,pc = data[i]['high'],data[i]['low'],data[i-1]['close']
        TR = max(hi-lo, abs(hi-pc), abs(lo-pc))
        up = data[i]['high']-data[i-1]['high']; dn = data[i-1]['low']-data[i]['low']
        PD = up if (up>dn and up>0) else 0; MD = dn if (dn>up and dn>0) else 0
        tr.append(TR); pdm.append(PD); mdm.append(MD)
    ATR=sum(tr[:p])/p; PS=sum(pdm[:p])/p; MS=sum(mdm[:p])/p; dx=[]
    for i in range(p,len(tr)):
        ATR=(ATR*(p-1)+tr[i])/p; PS=(PS*(p-1)+pdm[i])/p; MS=(MS*(p-1)+mdm[i])/p
        pdi=(PS/ATR)*100 if ATR>0 else 0; mdi=(MS/ATR)*100 if ATR>0 else 0
        dx.append(abs(pdi-mdi)/(pdi+mdi)*100 if (pdi+mdi)>0 else 0)
    return sum(dx[-p:])/p if len(dx)>=p else None

def atr(data, p=14):
    if len(data) < p+1: return None
    tr=[]
    for i in range(1,len(data)):
        hi,lo,pc=data[i]['high'],data[i]['low'],data[i-1]['close']
        tr.append(max(hi-lo,abs(hi-pc),abs(lo-pc)))
    return sum(tr[-p:])/p

def crossings(data, ma60v):
    n=min(20,len(data)-1); cnt=0
    for i in range(-n,0):
        if ma60v[i-1] is not None and ma60v[i] is not None:
            if (data[i-1]['close']>ma60v[i-1])!=(data[i]['close']>ma60v[i]): cnt+=1
    return cnt

def determine_tre(vol20v, adxv, above, cr):
    if vol20v and vol20v>25: return 'S4(风暴市)'
    if adxv and adxv>=20 and above: return 'S1(强趋势)'
    if adxv and adxv<15 and cr>=5: return 'S4近似(弱震荡)'
    if adxv and adxv<15 and cr>=3: return 'S3(震荡)'
    if adxv and adxv<20 and not above: return 'S2(趋弱)'
    if adxv and adxv<15: return 'S3近似(弱震荡)'
    return 'S2/S3过渡'

results={}
idx_spec=[('sh000300','沪深300'),('sh000905','中证500'),('sz399006','创业板指')]
for sym,name in idx_spec:
    d=data_by_symbol[sym]; last=d[-1]; prev=d[-2]
    v20=vol20(d); m60=ma(d,60); adv=adx(d,14)
    ma60v=[ma(d[:i+1],60) if i>=59 else None for i in range(len(d))]
    cr=crossings(d,ma60v); above=last['close']>m60 if m60 else False
    dev=(last['close']-m60)/m60*100 if m60 else 0
    chg=(last['close']-prev['close'])/prev['close']*100
    tre=determine_tre(v20,adv,above,cr)
    results[sym]={'name':name,'last':last['close'],'open':last['open'],'prev':prev['close'],
                  'high':last['high'],'low':last['low'],'chg':chg,'vol20':v20,'ma60':m60,
                  'adx':adv,'above':above,'dev':dev,'cross':cr,'tre':tre}
    print(f"{name}: 现价{last['close']} 今开{last['open']} 昨收{prev['close']} 涨跌{chg:+.2f}% "
          f"vol20={v20:.2f}% MA60={m60:.2f}(dev={dev:+.2f}%) ADX={adv:.1f} 穿越={cr} TRE={tre}")

hs=results['sh000300']['vol20']
gate = 'A(禁一切新建仓)' if hs<15 else ('B(禁S1/S2常规)' if hs>=20 else '正常区(15-20%)')
print(f"\nR-04闸门: vol20={hs:.2f}% → {gate}")
s4=sum(1 for s,n in idx_spec if results[s]['tre'].startswith('S4'))
gTRE='S4(风暴市)' if s4>=2 else '非S4'
print(f"全局TRE: {gTRE} (S4指数={s4}/3)")

# 持仓 / 观察
print("\n=== 持仓监控 ===")
# 510300：竞价清仓指令已挂(09:15)，待成交回报；现价作市场参考
h510={'sym':'sh510300','name':'沪深300ETF','cost':4.8224,'shares':20400,'buy':'2026-07-08'}
d510=data_by_symbol['sh510300']; l510=d510[-1]; p510=d510[-2]
atr510=atr(d510,14); m60510=ma(d510,60); v20510=vol20(d510)
hd=((date(2026,8,24)-date(2026,7,8)).days)
band=0.07 if hd<=11 else 0.04
e_p1=h510['cost']*(1-band)  # P2口径: ETF E-P1 = 成本×(1-带宽%)
bididx=next((i for i,d in enumerate(d510) if d['date']>=h510['buy']),None)
peak=max(d['high'] for d in d510[bididx:])
dd=(l510['close']-peak)/peak*100
mkt=l510['close']*h510['shares']; pnl=(l510['close']-h510['cost'])*h510['shares']
print(f"510300: 现价{l510['close']} 昨收{p510['close']} 涨跌{(l510['close']-p510['close'])/p510['close']*100:+.2f}% "
      f"成本{h510['cost']} 持有{hd}日 E-P1={e_p1:.4f} 峰值{peak} 回撤{dd:.2f}% "
      f"市值(剩余)¥{mkt:,.0f} 浮亏¥{pnl:,.0f}({pnl/(h510['cost']*h510['shares'])*100:+.2f}%)")

# 159650 稳定器
h159={'sym':'sz159650','name':'国开债ETF','cost':107.587,'shares':1800,'buy':'2026-06-04'}
d159=data_by_symbol['sz159650']; l159=d159[-1]; p159=d159[-2]
m60159=ma(d159,60); above159=l159['close']>m60159
mkt159=l159['close']*h159['shares']; pnl159=(l159['close']-h159['cost'])*h159['shares']
print(f"159650: 现价{l159['close']} 昨收{p159['close']} 涨跌{(l159['close']-p159['close'])/p159['close']*100:+.2f}% "
      f"MA60={m60159:.3f} 上方={above159} 市值¥{mkt159:,.0f} 浮盈¥{pnl159:,.0f}({pnl159/(h159['cost']*h159['shares'])*100:+.2f}%)")

# 药明康德 观察池
dym=data_by_symbol['sh603259']; lym=dym[-1]; pym=dym[-2]
m60ym=ma(dym,60); advym=adx(dym,14); v20ym=vol20(dym)
abv=lym['close']>m60ym; devym=(lym['close']-m60ym)/m60ym*100
print(f"药明康德: 现价{lym['close']} 昨收{pym['close']} 涨跌{(lym['close']-pym['close'])/pym['close']*100:+.2f}% "
      f"MA60={m60ym:.2f}(偏离{devym:+.2f}%) ADX={advym:.1f} vol20={v20ym:.2f}% 上方={abv}")

# 账户估算（假设510300竞价清仓已成交@~4.68）
cash_base=366896.62+44534+95004  # F4可用+恒瑞T+1+510300部分T+1
proceeds_remain=h510['shares']*4.68  # 假设竞价@4.68
cash_total=cash_base+proceeds_remain
total=cash_total+mkt159
print(f"\n=== 账户估算（清仓后）===")
print(f"现金(含T+1): ¥{cash_total:,.0f} ({cash_total/total*100:.1f}%)")
print(f"159650市值: ¥{mkt159:,.0f} ({mkt159/total*100:.1f}%) 总资产≈¥{total:,.0f}")
print(f"510300全程: 成本40700×4.8224=¥{40700*4.8224:,.0f} 回收(20300+20400)×4.68=¥{40700*4.68:,.0f} "
      f"亏损¥{40700*4.68-40700*4.8224:,.0f}({(40700*4.68-40700*4.8224)/(40700*4.8224)*100:.2f}%)")

out={'indices':results,'gate':gate,'global_tre':gTRE,'s4_count':s4,
     'hs300_vol20':hs,'m510':{'last':l510['close'],'prev':p510['close'],'e_p1':e_p1,'peak':peak,'dd':dd,
                              'mkt':mkt,'pnl':pnl,'chg':(l510['close']-p510['close'])/p510['close']*100},
     'm159':{'last':l159['close'],'prev':p159['close'],'mkt':mkt159,'pnl':pnl159,'above':above159,'ma60':m60159},
     'ymkd':{'last':lym['close'],'prev':pym['close'],'m60':m60ym,'dev':devym,'adx':advym,'v20':v20ym,'above':abv},
     'cash_total':cash_total,'total':total,'m159_mkt':mkt159}
with open(r'E:\fnOS\文档\证券\中线趋势共振策略\mid_0824_result.json','w',encoding='utf-8') as f:
    json.dump(out,f,ensure_ascii=False,indent=2,default=str)
print("\n结果保存: mid_0824_result.json")
