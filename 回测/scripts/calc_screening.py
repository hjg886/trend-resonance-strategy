# -*- coding: utf-8 -*-
"""
v4.7-R10 观察池选股：数据解析 + 层级1硬过滤 + 24因子评分
2026-08-18 盘中数据（westockdata，K线有延迟，标注数据日期）
权重口径：基本面35% / 趋势35% / 情绪10% / 微观10% / 风控10%（用户确认按文档）
"""
import io, json, re, math, statistics

BASE = r'E:/fnOS/文档/证券/中线趋势共振策略/回测/tmp/sectors'
def load_meta():
    with io.open(BASE + '/cand_meta.json', encoding='utf-8') as f:
        return json.load(f)

META = load_meta()
NAMES = META['names']
CODES = META['M'] + META['H']

# ---------- 1. 解析 K 线 ----------
def parse_kline():
    data = {}  # code -> {dates:[...], last, ma60, ma60_prev20, ma5, ma20, rps20, ret60, vol20, adv20, turn, vr5_20}
    for fn in ['kline_m1.txt', 'kline_m2.txt']:
        with io.open(BASE + '/' + fn, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('|'): continue
                cells = [c.strip() for c in line.strip('|').split('|')]
                if cells[0] == 'symbol' or len(cells) < 9: continue
                code, date, opn, last, high, low, vol, amt, exch = cells[0], cells[1], cells[2], cells[3], cells[4], cells[5], cells[6], cells[7], cells[8]
                try:
                    last = float(last); amt = float(amt); exch = float(exch)
                except ValueError:
                    continue
                d = data.setdefault(code, {'dates': [], 'lasts': [], 'amts': [], 'exchs': [], 'vols': []})
                d['dates'].append(date); d['lasts'].append(last); d['amts'].append(amt); d['exchs'].append(exch); d['vols'].append(float(vol))
    out = {}
    for code, d in data.items():
        lasts = d['lasts']  # 最新在前
        n = len(lasts)
        if n < 61: continue
        last = lasts[0]
        ma60 = sum(lasts[:60]) / 60.0
        ma60_prev20 = sum(lasts[20:80]) / 60.0 if n >= 80 else sum(lasts[20:]) / (n - 20)
        ma5 = sum(lasts[:5]) / 5.0
        ma20 = sum(lasts[:20]) / 20.0
        rps20 = (lasts[0] / lasts[20] - 1) * 100 if len(lasts) > 20 else None   # 20日涨幅
        ret60 = (lasts[0] / lasts[min(60, n-1)] - 1) * 100 if n > 60 else None
        # vol20：近21日收盘年化波动率
        closes = lasts[:21]
        rets = [(closes[i] / closes[i+1] - 1) for i in range(len(closes)-1)]
        sd = statistics.stdev(rets) if len(rets) > 2 else 0
        vol20 = sd * math.sqrt(252) * 100
        adv20 = sum(d['amts'][:20]) / min(20, len(d['amts']))  # 近20日日均成交额(元)
        turn = d['exchs'][0] if d['exchs'] else 0
        # 量比：近5日均量 / 近20日均量
        v5 = sum(d['vols'][:5]) / 5.0 if len(d['vols']) >= 5 else None
        v20 = sum(d['vols'][:20]) / 20.0 if len(d['vols']) >= 20 else None
        vr5_20 = (v5 / v20) if v5 and v20 else 1.0
        out[code] = {'date': d['dates'][0], 'last': last, 'ma60': ma60, 'ma60_prev20': ma60_prev20,
                     'ma5': ma5, 'ma20': ma20, 'rps20': rps20, 'ret60': ret60, 'vol20': vol20,
                     'adv20': adv20, 'turn': turn, 'vr5_20': vr5_20}
    return out

# ---------- 2. 解析 finance ----------
def parse_finance():
    rows = {}   # rows[code][sheet][end] = {field: value}
    cur_sheet = None
    headers = None
    with io.open(BASE + '/finance_m5.txt', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('**'):
                cur_sheet = line.strip('*').strip()
                headers = None
                continue
            if line.startswith('|') and cur_sheet:
                cells = [c.strip() for c in line.strip('|').split('|')]
                if cells[0] == 'symbol':
                    headers = cells
                    continue
                if headers and len(cells) == len(headers):
                    # 数据行：| symbol | _date | code | date | ...（code 在第3列）
                    code = cells[2]
                    end = cells[3] if len(cells) > 3 else ''
                    rec = rows.setdefault(code, {}).setdefault(cur_sheet, {})
                    rec[end] = dict(zip(headers, cells))
    return rows

# ---------- 3. 解析 score ----------
def parse_score():
    out = {}
    with io.open(BASE + '/score_m.txt', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('|'): continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if cells[0] == '代码' or len(cells) < 6: continue
            code = cells[0]
            def num(s):
                m = re.match(r'([\d.]+)', s)
                return float(m.group(1)) if m else None
            out[code] = {'composite': num(cells[2]), 'fund': num(cells[3]), 'fundamental': num(cells[4]),
                         'risk': num(cells[5]), 'tech': num(cells[6])}
    return out

# ---------- 4. 解析 consensus ----------
def parse_consensus():
    out = {}
    cur_code = None
    with io.open(BASE + '/consensus_m.txt', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r'####\s+(sh\d{6}|sz\d{6}|bj\d{6})\s+(.+)', line)
        if m:
            cur_code = m.group(1)
            tp = None; rows = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith('####'):
                lj = lines[j].strip()
                tm = re.match(r'目标价[:：]\s*([\d.]+)', lj)
                if tm: tp = float(tm.group(1))
                if lj.startswith('|'):
                    cells = [c.strip() for c in lj.strip('|').split('|')]
                    if cells[0] == 'year': j += 1; continue
                    if len(cells) >= 8 and re.match(r'^\d{4}$', cells[0]):
                        rows.append(cells)
                j += 1
            out[cur_code] = {'target': tp, 'rows': rows}
            i = j
        else:
            i += 1
    return out

# ---------- 工具函数：分档打分 ----------
def band(v, table, default=50.0):
    """table: [(hi_exclusive, score), ...] 按首个满足的区间打分"""
    if v is None: return default
    for hi, s in table:
        if v < hi:
            return s
    return table[-1][1]

# ---------- 主流程 ----------
kline = parse_kline()
finance = parse_finance()
score = parse_score()
consensus = parse_consensus()

# 综合评分百分位（全样本）
comp_rank = {}
comps = [s['composite'] for s in score.values() if s['composite'] is not None]
comps_sorted = sorted(comps)
def pct_rank(v):
    if v is None: return 50.0
    return sum(1 for x in comps_sorted if x <= v) / len(comps_sorted) * 100

results = []
for code in CODES:
    name = NAMES.get(code, code)
    k = kline.get(code)
    sc = score.get(code, {})
    cs = consensus.get(code, {'target': None, 'rows': []})
    fin = finance.get(code, {})
    if not k or not fin:
        results.append({'code': code, 'name': name, 'error': '数据缺失'})
        continue

    # ---- finance 提取 ----
    def finval(sheet, field, end=None):
        sh = fin.get(sheet, {})
        if not sh: return None
        for e in (sorted(sh.keys(), reverse=True) if end is None else [end]):
            if e not in sh: continue
            r = sh[e]
            if field in r and r[field] not in ('-', ''):
                try: return float(r[field])
                except: continue
        return None

    # income：最新期 2026-03-31（TTM）+ 单季同比（2026Q1 vs 2025Q1）
    rev_ttm = finval('income', 'OperatingRevenueTTM')
    np_ttm = finval('income', 'NPParentCompanyOwnersTTM')
    rev_q_now = finval('income', 'OperatingRevenue_Q', '2026-03-31')
    np_q_now = finval('income', 'NPParentCompanyOwners_Q', '2026-03-31')
    rev_q_yoy = finval('income', 'OperatingRevenue_Q', '2025-03-31')
    np_q_yoy = finval('income', 'NPParentCompanyOwners_Q', '2025-03-31')
    gp_ttm = finval('income', 'GrossProfitTTM')
    rev_yoy = (rev_q_now / rev_q_yoy - 1) * 100 if (rev_q_now and rev_q_yoy) else None
    np_yoy = (np_q_now / np_q_yoy - 1) * 100 if (np_q_now and np_q_yoy) else None
    if rev_yoy is None and rev_ttm:
        rev_ttm_prev = finval('income', 'OperatingRevenueTTM', '2025-12-31')
        rev_yoy = (rev_ttm / rev_ttm_prev - 1) * 100 if rev_ttm_prev else None
    if np_yoy is None and np_ttm:
        np_ttm_prev = finval('income', 'NPParentCompanyOwnersTTM', '2025-12-31')
        np_yoy = (np_ttm / np_ttm_prev - 1) * 100 if np_ttm_prev else None
    # balance / cashflow 最新期
    paid_in = finval('balance', 'PaidInCapital')
    equity = finval('balance', 'TotalShareholderEquity')
    total_liab = finval('balance', 'TotalLiab')
    total_assets = finval('balance', 'TotalAssets')
    ocf = finval('cashflow', 'NetOperateCashFlow')
    if ocf is None:
        ocf = finval('cashflow', 'NetOperateCashFlowTTM')
    # 市值 = last × PaidInCapital
    mkt_cap = (k['last'] * paid_in / 1e8) if paid_in else None   # 亿元
    roe = (np_ttm / equity * 100) if (np_ttm and equity) else None
    gross_m = (gp_ttm / rev_ttm * 100) if (gp_ttm and rev_ttm) else None
    ocf_ratio = (ocf / np_ttm) if (ocf and np_ttm) else None
    debt_ratio = (total_liab / total_assets * 100) if (total_liab and total_assets) else None

    # consensus 2026E
    cs_row = None
    for r in cs['rows']:
        if r[0] == '2026':
            cs_row = r; break
    cs_npyoy = float(cs_row[8]) if (cs_row and len(cs_row) > 8 and cs_row[8] not in ('-', '')) else None
    cs_pe = float(cs_row[5]) if (cs_row and len(cs_row) > 5 and cs_row[5] not in ('-', '')) else None
    cs_pb = float(cs_row[6]) if (cs_row and len(cs_row) > 6 and cs_row[6] not in ('-', '')) else None
    cs_inst = int(cs_row[9]) if (cs_row and len(cs_row) > 9 and cs_row[9] not in ('-', '')) else 0

    # ---- 层级1 硬过滤（一票否决）----
    # OCF高增长豁免：营收+净利双正（双增）→ OCF要求降至>0（仅排除负OCF）
    high_growth = (rev_yoy is not None and np_yoy is not None and
                   rev_yoy > 0 and np_yoy > 0)
    filters = {}
    filters['净利同比≥-12%'] = np_yoy is None or np_yoy >= -12
    filters['营收同比≥-15%'] = rev_yoy is None or rev_yoy >= -15
    filters['ROE>5%'] = roe is not None and roe > 5
    if high_growth:
        filters['现金流/净利>0(高增长豁免)'] = ocf_ratio is None or ocf_ratio > 0
    else:
        filters['现金流/净利>0.5'] = ocf_ratio is None or ocf_ratio > 0.5
    filters['市值≥50亿(无上限)'] = mkt_cap is not None and mkt_cap >= 50
    filters['日均成交额>5000万'] = k['adv20'] > 5e7
    filters['非ST'] = 'ST' not in name and 'st' not in name
    passed = all(filters.values())

    # ---- 24因子评分（仅通过者）----
    if not passed:
        results.append({'code': code, 'name': name, 'mkt_cap': mkt_cap, 'filters': filters,
                        'np_yoy': np_yoy, 'rev_yoy': rev_yoy, 'roe': roe, 'adv20': k['adv20'] / 1e8,
                        'error': '硬过滤未通过'})
        continue

    # 基本面35%
    f1 = band(rev_yoy, [(-15, 15), (0, 45), (10, 65), (25, 80), (40, 92), (1e9, 95)])
    f2 = band(np_yoy, [(-12, 30), (0, 55), (15, 70), (30, 85), (50, 93), (1e9, 95)])
    f3 = band(cs_npyoy, [(0, 40), (10, 60), (20, 75), (35, 88), (1e9, 92)], 50)
    f4 = band(cs_pe, [(0, 90), (20, 78), (35, 62), (50, 48), (70, 35), (1e9, 25)], 50)
    f5 = band(cs_pb, [(0, 88), (3, 76), (6, 62), (10, 48), (15, 35), (1e9, 28)], 50)
    peg = (cs_pe / cs_npyoy) if (cs_pe and cs_npyoy and cs_npyoy > 0) else None
    f6 = band(peg, [(0.8, 90), (1.5, 75), (2.5, 55), (1e9, 35)], 45)
    fundamental = 0.25*f1 + 0.25*f2 + 0.15*f3 + 0.15*f4 + 0.10*f5 + 0.10*f6

    # 趋势35%
    ma60_up = k['ma60'] > k['ma60_prev20']
    t7 = 85 if ma60_up else (60 if abs(k['ma60']-k['ma60_prev20'])/k['ma60_prev20'] < 0.005 else 35)
    pos = k['last'] / k['ma60']
    t8 = band(pos, [(0.90, 30), (0.97, 50), (1.02, 68), (1.08, 82), (1.15, 72), (1e9, 65)])
    if k['ma5'] > k['ma20'] > k['ma60']: t9 = 90
    elif k['ma5'] > k['ma20']: t9 = 65
    else: t9 = 35
    t10 = band(k['rps20'], [(-15, 25), (-5, 45), (0, 58), (8, 72), (18, 85), (30, 92), (1e9, 95)])
    t11 = band(k['ret60'], [(-20, 25), (-5, 45), (5, 58), (15, 70), (30, 82), (50, 90), (1e9, 92)])
    trend = 0.20*t7 + 0.20*t8 + 0.20*t9 + 0.20*t10 + 0.20*t11

    # 情绪10%
    fund_s = sc.get('fund', 50) or 50
    inst_s = band(cs_inst, [(0, 45), (5, 60), (12, 72), (20, 82), (1e9, 88)], 45)
    rank_s = pct_rank(sc.get('composite'))
    emotion = 0.4*fund_s + 0.3*inst_s + 0.3*rank_s

    # 微观10%
    adv_yi = k['adv20'] / 1e8
    m17 = band(adv_yi, [(0.3, 35), (0.8, 55), (2, 70), (6, 82), (15, 88), (1e9, 85)])
    m18 = band(k['turn'], [(0.5, 45), (1, 62), (2.5, 82), (6, 75), (12, 55), (1e9, 45)])
    m19 = band(k['vr5_20'], [(0.6, 50), (0.9, 65), (1.4, 80), (2.2, 72), (3.5, 55), (1e9, 45)])
    m20 = 75  # 回踩量比代理（5日均量比20日均量中位），简化中性
    micro = 0.25*m17 + 0.25*m18 + 0.25*m19 + 0.25*m20

    # 风控10%
    r1 = band(ocf_ratio, [(0.2, 30), (0.5, 60), (0.8, 78), (1.2, 90), (1e9, 92)], 50)
    r2 = band(roe, [(5, 45), (10, 62), (15, 75), (20, 85), (1e9, 88)], 45)
    r3 = band(gross_m, [(10, 35), (20, 55), (30, 70), (45, 85), (1e9, 88)])
    r4 = band(debt_ratio, [(30, 85), (45, 72), (60, 58), (75, 42), (1e9, 30)])
    risk = 0.25*r1 + 0.25*r2 + 0.25*r3 + 0.25*r4

    total = 0.35*fundamental + 0.35*trend + 0.10*emotion + 0.10*micro + 0.10*risk
    if risk < 60: total *= 0.85
    if cs_npyoy is None: total *= 0.95   # 无一致预期覆盖降权

    if total >= 90: grade = 'A+'
    elif total >= 80: grade = 'A'
    elif total >= 70: grade = 'B'
    else: grade = 'C'

    results.append({
        'code': code, 'name': name, 'mkt_cap': mkt_cap, 'adv20': adv_yi,
        'np_yoy': np_yoy, 'rev_yoy': rev_yoy, 'roe': roe, 'ocf_ratio': ocf_ratio,
        'gross_m': gross_m, 'debt_ratio': debt_ratio, 'peg': peg,
        'cs_pe': cs_pe, 'cs_pb': cs_pb, 'cs_npyoy': cs_npyoy, 'cs_inst': cs_inst,
        'ma60_up': ma60_up, 'pos_ma60': pos, 'rps20': k['rps20'], 'ret60': k['ret60'],
        'vol20': k['vol20'], 'turn': k['turn'], 'vr5_20': k['vr5_20'],
        'high_growth_exempt': high_growth,
        'f': {'fundamental': round(fundamental,1), 'trend': round(trend,1), 'emotion': round(emotion,1),
              'micro': round(micro,1), 'risk': round(risk,1)},
        'composite_score': sc.get('composite'),
        'total': round(total, 1), 'grade': grade, 'date': k['date']
    })

# 输出
passed_list = [r for r in results if 'total' in r]
passed_list.sort(key=lambda x: -x['total'])
failed_list = [r for r in results if 'total' not in r and 'error' in r]

print('=== 通过硬过滤进入评分:', len(passed_list), '只 ===')
print('=== 硬过滤未通过:', len(failed_list), '只 ===')
print()
hdr = f"{'代码':<9}{'名称':<8}{'市值亿':>7}{'评分':>6}{'级':>3}{'基本面':>7}{'趋势':>6}{'情绪':>6}{'微观':>6}{'风控':>6}"
print(hdr)
print('-' * len(hdr))
for r in passed_list:
    f = r['f']
    print(f"{r['code']:<9}{r['name']:<8}{r['mkt_cap']:>7.0f}{r['total']:>6.1f}{r['grade']:>4}{f['fundamental']:>7.1f}{f['trend']:>6.1f}{f['emotion']:>6.1f}{f['micro']:>6.1f}{f['risk']:>6.1f}")
print()
print('=== 未通过明细（关键指标）===')
for r in failed_list:
    fl = [k for k, v in r.get('filters', {}).items() if not v]
    print(f"{r['code']} {r['name']} 市值{r.get('mkt_cap')}亿 净利YoY{r.get('np_yoy')} 营收YoY{r.get('rev_yoy')} ROE{r.get('roe')} 成交额{r.get('adv20')}亿 未过:{','.join(fl)}")

with io.open(BASE + '/screen_result.json', 'w', encoding='utf-8') as f:
    json.dump({'passed': passed_list, 'failed': failed_list}, f, ensure_ascii=False, indent=1, default=str)
print('\n已保存 screen_result.json')
