# -*- coding: utf-8 -*-
"""台股熱門產業監控 — Streamlit 互動式介面

執行方式：python stock_dashboard.py
安裝套件：pip install streamlit plotly yfinance pandas numpy requests
"""

import os, json, re, warnings
import requests as _req
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

try:
    from streamlit_autorefresh import st_autorefresh as _st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False

TODAY = datetime.today()

SECTORS = {
    # 金融業：涵蓋主要金控，台灣50+中型100成份為骨幹
    "金融業": {
        "富邦金": "2881.TW", "國泰金": "2882.TW", "中信金": "2891.TW", "玉山金": "2884.TW",
        "兆豐金": "2886.TW", "第一金": "2892.TW", "合庫金": "5880.TW", "開發金": "2883.TW",
        "永豐金": "2890.TW", "台新金": "2887.TW",
    },
    # 石化/材料：台塑四寶 + 鋼鐵
    "石化/材料": {
        "台塑":   "1301.TW", "南亞":   "1303.TW", "台化":   "1326.TW", "台塑化": "6505.TW",
        "中鋼":   "2002.TW", "東鋼":   "2006.TW", "燁輝":   "2023.TW",
    },
    # 醫療生技：製藥 + 醫材，台灣生技主要上市公司
    "醫療生技": {
        "美時":     "1795.TW", "生達":     "1720.TW", "東洋":     "4105.TW",
        "聯合骨科": "4129.TW", "台灣神隆": "4167.TW", "杏國":     "6546.TW",
    },
    # 消費/零售：便利商店、百貨、餐飲連鎖
    "消費/零售": {
        "統一":     "1216.TW", "統一超": "2912.TW", "遠東百貨": "2903.TW",
        "王品":     "2727.TW", "六角":   "2732.TW", "寶雅":     "5904.TW",
    },
    # 電信/通訊：台灣三大電信寡占，加亞太
    "電信/通訊": {
        "中華電": "2412.TW", "台灣大": "3045.TW", "遠傳": "4904.TW", "亞太電信": "3682.TW",
    },
    # 建設/不動產：上市建商
    "建設/不動產": {
        "國建":   "2501.TW", "冠德":   "2520.TW", "興富發": "2542.TW", "皇翔": "2545.TW",
        "華固":   "2548.TW", "長虹":   "5534.TW", "遠雄":   "5522.TW",
    },
    # 食品飲料：糧食加工、飼料、食用油
    "食品飲料": {
        "味全":   "1201.TW", "卜蜂":   "1215.TW", "泰山":   "1218.TW",
        "福壽":   "1219.TW", "聯華食": "1231.TW", "大統益": "1232.TW",
    },
    # 運輸/物流：貨櫃三雄 + 散裝
    "運輸/物流": {
        "長榮海":  "2603.TW", "裕民":    "2606.TW", "陽明海":  "2609.TW",
        "萬海":    "2615.TW", "台航":    "2617.TW", "慧洋-KY": "2637.TW",
    },
    # 電力/電源設備：電力設備製造 + 台達電（電源供應器、工控、EV充電）
    # 台達電從 EMS 移至此處，主業為電源模組與工業自動化，非組裝代工
    "電力/電源設備": {
        "台達電": "2308.TW", "士電":   "1503.TW", "東元":   "1504.TW",
        "永大":   "1507.TW", "中興電": "1513.TW", "亞力":   "1514.TW", "大同": "2371.TW",
    },
}

TECH_SUBSECTORS = {
    # 晶圓代工/封裝：前段晶圓代工 + 後段封裝測試，同屬半導體製造服務
    # 日月光投控為 OSAT（封裝測試），與晶圓代工同屬製造服務鏈，合併一類
    # 新增京元電子（2449），台灣重要封測廠
    "晶圓代工/封裝": {
        "台積電":   "2330.TW", "聯電":     "2303.TW", "世界先進":  "5347.TW",
        "力積電":   "6770.TW", "日月光投控": "3711.TW", "京元電子": "2449.TW",
    },
    # IC 設計：新增瑞鼎（3592），其主業為面板驅動 IC，屬 IC 設計業
    "IC 設計": {
        "聯發科": "2454.TW", "瑞昱": "2379.TW", "聯詠": "3034.TW", "威盛": "2388.TW",
        "矽統":   "2363.TW", "聯陽": "3014.TW", "智原": "3035.TW", "瑞鼎": "3592.TW",
    },
    # 記憶體晶片：僅保留自製記憶體晶片廠（DRAM + NOR Flash）
    # 移除鈺創（5351）、威剛（3260）——兩者為記憶體模組通路商，非晶片製造
    "記憶體晶片": {
        "南亞科": "2408.TW", "旺宏": "2337.TW", "華邦電": "2344.TW",
    },
    # 伺服器/AI 硬體：AI 伺服器 ODM + AI PC 品牌，均為 AI 需求直接受益族群
    "伺服器/AI 硬體": {
        "廣達": "2382.TW", "緯創": "3231.TW", "英業達": "2356.TW", "緯穎": "6669.TW",
        "技嘉": "2376.TW", "微星": "2377.TW", "華碩":   "2357.TW",
    },
    # 電子組裝 (EMS)：純代工組裝廠，台達電已移至電力/電源設備
    "電子組裝 (EMS)": {
        "鴻海": "2317.TW", "和碩": "4938.TW", "仁寶": "2324.TW", "光寶科": "2301.TW",
    },
    # PCB/電路板：載板 + 多層板，完整涵蓋台灣 PCB 供應鏈
    "PCB/電路板": {
        "臻鼎-KY": "4958.TW", "欣興": "3037.TW", "健鼎": "3044.TW",
        "金像電":  "2368.TW", "華通": "2313.TW", "楠梓電": "2316.TW",
    },
    # 面板/顯示：移除瑞鼎（已改歸 IC 設計），保留純面板製造商
    "面板/顯示": {
        "群創": "3481.TW", "友達": "2409.TW", "彩晶": "6116.TW", "凌巨": "8104.TW",
    },
}

ETF_SECTORS = {
    # 大盤指數型：追蹤台灣50、中型100，最常被當核心持倉的被動型ETF
    "ETF｜大盤指數": {
        "元大台灣50":   "0050.TW",  "富邦台50":     "006208.TW",
        "元大中型100":  "0051.TW",  "富邦公司治理": "00692.TW",
    },
    # 高股息：以殖利率為主軸選股，台灣散戶最熱門的存股標的
    "ETF｜高股息": {
        "元大高股息":       "0056.TW",  "國泰永續高股息": "00878.TW",
        "元大台灣高息低波": "00713.TW", "群益台灣精選高息": "00919.TW",
        "富邦特選高股息30": "00900.TW",
    },
    # 科技/半導體主題：鎖定半導體、5G、電子科技等成長產業
    "ETF｜科技主題": {
        "中信關鍵半導體":   "00891.TW", "國泰台灣5G+":     "00881.TW",
        "富邦科技":         "0052.TW",  "富邦台灣電子科技": "00892.TW",
    },
    # 海外市場：追蹤美股大盤、那斯達克、科技巨頭
    "ETF｜海外市場": {
        "元大S&P500": "00646.TW", "統一FANG+":  "00757.TW",
        "富邦NASDAQ": "00662.TW",
    },
    # 固定收益：追蹤美國長天期公債與投資級企業債
    "ETF｜固定收益": {
        "元大美債20年":     "00679B.TW",
        "元大投資級公司債": "00720B.TW",
    },
}

ALL_SECTORS: dict[str, dict[str, str | None]] = {**SECTORS, **TECH_SUBSECTORS, **ETF_SECTORS}
TICKER_TO_NAME: dict[str, str] = {
    v: k for sec in ALL_SECTORS.values() for k, v in sec.items() if v
}
# 名稱 → ticker（含 .TW），供模糊查詢使用
NAME_TO_TICKER: dict[str, str] = {v: k for k, v in TICKER_TO_NAME.items()}

MARKET_SUFFIX: dict[str, str] = {'上市': '.TW', '上櫃': '.TWO', '興櫃': '.TWO'}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_all_stocks() -> dict[str, tuple[str, str]]:
    """一次抓取上市、上櫃、興櫃完整清單，回傳 {代號: (公司名稱, suffix)}。
    suffix: '.TW'（上市）或 '.TWO'（上櫃/興櫃）。上市優先，避免重複代號被覆蓋。"""
    from io import StringIO
    markets = [('2', '.TW'), ('4', '.TWO'), ('5', '.TWO')]
    result: dict[str, tuple[str, str]] = {}
    for mode, suffix in markets:
        url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
        try:
            resp = _req.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
            resp.encoding = 'big5'
            tables = pd.read_html(StringIO(resp.text))
            for _, row in tables[0].iterrows():
                cell = str(row.iloc[0])
                if '　' in cell:
                    code, _, name = cell.partition('　')
                    code = code.strip(); name = name.strip()
                    if code.isdigit() and 4 <= len(code) <= 5 and name:
                        if code not in result:      # 上市優先
                            result[code] = (name, suffix)
        except Exception:
            continue
    return result


def fuzzy_resolve(raw: str,
                  all_stocks: dict[str, tuple[str, str]] | None = None,
                  ) -> list[tuple[str, str]]:
    """輸入股票代號或名稱，回傳 [(name, full_ticker), ...]。
    all_stocks: fetch_all_stocks() 回傳值 {代號: (名稱, suffix)}。"""
    raw = raw.strip()
    if not raw:
        return []
    code = raw.upper().replace('.TWO', '').replace('.TW', '').strip()

    if code.isdigit():
        # 先查 SECTORS 預定義（上市常用股）
        t = code + '.TW'
        if t in TICKER_TO_NAME:
            return [(TICKER_TO_NAME[t], t)]
        # 查合併市場清單
        if all_stocks and code in all_stocks:
            name, suffix = all_stocks[code]
            return [(name, code + suffix)]
        # 未知代號 → 預設 .TW，讓 yfinance 判斷
        return [(code, code + '.TW')]

    # 名稱模糊比對
    low  = raw.lower()
    seen: set[str] = set()
    hits: list[tuple[str, str]] = []
    for n, t in NAME_TO_TICKER.items():
        if low in n.lower():
            c = t.replace('.TWO', '').replace('.TW', '')
            if c not in seen:
                hits.append((n, t)); seen.add(c)
    if all_stocks:
        for c, (n, suffix) in all_stocks.items():
            if low in n.lower() and c not in seen:
                hits.append((n, c + suffix)); seen.add(c)
    hits.sort(key=lambda x: (not x[0].startswith(raw), x[0]))
    return hits

WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watchlist.json')
SNAPSHOT_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screen_snapshots')


# ── 資料抓取 & 技術指標 ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker: str, days: int = 365) -> pd.DataFrame | None:
    start = (TODAY - timedelta(days=days + 60)).strftime('%Y-%m-%d')
    try:
        df = yf.download(ticker, start=start, end=TODAY.strftime('%Y-%m-%d'),
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

        df['MA5']  = df['Close'].rolling(5).mean()
        df['MA10'] = df['Close'].rolling(10).mean()
        df['MA20'] = df['Close'].rolling(20).mean()

        delta = df['Close'].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        df['RSI'] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD']        = ema12 - ema26
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_hist']   = df['MACD'] - df['MACD_signal']

        df['BB_mid']   = df['Close'].rolling(20).mean()
        std            = df['Close'].rolling(20).std()
        df['BB_upper'] = df['BB_mid'] + 2 * std
        df['BB_lower'] = df['BB_mid'] - 2 * std

        low9  = df['Low'].rolling(9).min()
        high9 = df['High'].rolling(9).max()
        rsv   = ((df['Close'] - low9) / (high9 - low9).replace(0, np.nan) * 100).fillna(50)
        K_vals, D_vals = [50.0], [50.0]
        for r in rsv.values[1:]:
            k = 2/3 * K_vals[-1] + 1/3 * r
            d = 2/3 * D_vals[-1] + 1/3 * k
            K_vals.append(k)
            D_vals.append(d)
        df['KD_K'] = K_vals
        df['KD_D'] = D_vals

        return df.tail(days)
    except Exception:
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_dividend_info(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        result = {}
        dy = info.get('dividendYield')
        if dy and dy > 0:
            result['殖利率'] = round(float(dy) * 100, 2)
        ex = info.get('exDividendDate')
        if ex:
            try:
                result['除息日'] = (datetime.fromtimestamp(int(ex)).strftime('%Y-%m-%d')
                                   if isinstance(ex, (int, float)) else str(ex)[:10])
            except Exception:
                pass
        pe = info.get('trailingPE')
        if pe and 0 < float(pe) < 999:
            result['本益比'] = round(float(pe), 1)
        return result
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        result = {}
        for key, label in [('grossMargins', '毛利率'), ('operatingMargins', '營業利益率')]:
            v = info.get(key)
            if v is not None:
                result[label] = round(float(v) * 100, 1)
        rg = info.get('revenueGrowth')
        if rg is not None:
            result['營收成長率(YoY)'] = round(float(rg) * 100, 1)
        eps = info.get('trailingEps')
        if eps is not None:
            result['EPS(TTM)'] = round(float(eps), 2)
        return result
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_cashflow_roe(ticker: str) -> dict:
    """取得年度 OCF / FCF（億元）及 ROE（%），最多近 4 年。"""
    try:
        tk  = yf.Ticker(ticker)
        out = {'roe': None, 'ocf': {}, 'fcf': {}}

        roe = tk.info.get('returnOnEquity')
        if roe is not None:
            out['roe'] = round(float(roe) * 100, 1)

        cf = tk.cashflow
        if cf is None or cf.empty:
            return out

        def _row(df, *kws):
            for idx in df.index:
                s = str(idx).lower().replace(' ', '').replace('_', '')
                if all(k in s for k in kws):
                    return df.loc[idx]
            return None

        ocf_row = _row(cf, 'operating', 'cashflow')
        if ocf_row is None:
            ocf_row = _row(cf, 'totalcashfromoperatingactivities')
        capex_row = _row(cf, 'capital', 'expenditure')
        if capex_row is None:
            capex_row = _row(cf, 'capitalexpenditures')

        if ocf_row is not None:
            for date in cf.columns[:4]:
                val = ocf_row.get(date)
                if pd.isna(val):
                    continue
                yr = str(date.year)
                out['ocf'][yr] = round(float(val) / 1e8, 1)
                if capex_row is not None:
                    cap = capex_row.get(date)
                    if not pd.isna(cap):
                        out['fcf'][yr] = round((float(val) + float(cap)) / 1e8, 1)

        return out
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ownership_ratio(ticker: str) -> dict:
    """抓取外資持股比率（僑外法人／本國持股）。
    來源：鉅亨網 (cnyes.com) 個股頁面 foreignStockOwnRatio 欄位，每日更新。
    ETF 或無資料個股回傳空 dict。
    本國持股 = 100 - 外資，含自然人＋法人；細項分拆需 TWSE 月報，目前無公開 JSON API。"""
    code = ticker.replace('.TWO', '').replace('.TW', '').strip()
    result: dict[str, float] = {}
    try:
        r = _req.get(
            f"https://www.cnyes.com/twstock/ps4/{code}.htm",
            timeout=15,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.cnyes.com/',
            },
        )
        text = r.content.decode('utf-8', errors='replace')
        m = re.search(r'"foreignStockOwnRatio"\s*:\s*([\d.]+)', text)
        if m:
            fval = float(m.group(1))
            if 0 < fval <= 100:
                result['僑外法人（外資及陸資）'] = fval
                result['本國持股（自然人＋法人）'] = round(100.0 - fval, 2)
    except Exception:
        pass
    return result


def fetch_realtime_quotes(tickers: list[str]) -> list[dict]:
    """TWSE / OTC MIS 即時報價 (mis.twse.com.tw)。
    tickers 格式：['2330.TW', '3481.TWO', 't00.TW'(加權指數), 'o00.TWO'(櫃買指數)]
    市場時間 09:00-13:30 有即時價，盤後顯示最後成交價。"""
    if not tickers:
        return []
    ch_parts = []
    for tk in tickers:
        if tk.endswith('.TWO'):
            code = tk[:-4]
            ch_parts.append(f'otc_{code}.tw')
        else:
            code = tk.replace('.TW', '')
            ch_parts.append(f'tse_{code}.tw')
    url = ("https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
           f"?ex_ch={'|'.join(ch_parts)}&json=1&delay=0")
    try:
        resp = _req.get(url, timeout=8,
                        headers={'User-Agent': 'Mozilla/5.0',
                                 'Referer': 'https://mis.twse.com.tw/'})
        data = resp.json()
        results = []
        for item in data.get('msgArray', []):
            try:
                def _f(key):
                    v = item.get(key, '-')
                    return float(v) if v not in ('-', '', None) else None
                price = _f('z')   # 成交（即時）
                # z 暫無成交（兩筆交易間隔 / 盤前盤後）→ 用最佳買進首價估算
                if price is None:
                    bids = item.get('b', '-')
                    if bids and bids not in ('-', ''):
                        first_bid = bids.split('_')[0].strip()
                        try:
                            price = float(first_bid) if first_bid else None
                        except (ValueError, TypeError):
                            price = None
                prev    = _f('y')   # 昨收
                chg     = round(price - prev, 2)       if price and prev else None
                chg_pct = round(chg / prev * 100, 2)   if chg and prev   else None
                vol_raw = item.get('v', '-')
                results.append({
                    '代號':      item.get('c', ''),
                    '名稱':      item.get('n', ''),
                    '現價':      price,
                    '昨收':      prev,
                    '漲跌':      chg,
                    '漲跌%':     chg_pct,
                    '開盤':      _f('o'),
                    '最高':      _f('h'),
                    '最低':      _f('l'),
                    '成交量(張)': int(float(vol_raw)) if vol_raw not in ('-', '', None) else None,
                })
            except Exception:
                continue
        # 興櫃 fallback：.TWO 股票若 TWSE MIS 無即時成交價，改用 TPEx GETQ20
        twse_priced = {r['代號'] for r in results if r.get('現價') is not None}
        for tk in tickers:
            if not tk.endswith('.TWO'):
                continue
            code = tk[:-4]
            if code in twse_priced:
                continue
            eq = fetch_emerging_quote(code)
            if eq:
                results = [r for r in results if r['代號'] != code]
                results.append(eq)
        return results
    except Exception:
        return []


def fetch_emerging_quote(stock_id: str) -> dict | None:
    """TPEx 興櫃即時報價 (mis.tpex.org.tw/Quote.asmx/GETQ20)。
    stock_id: 純4碼代號，例如 '6892'。無資料時回傳 None。"""
    try:
        import xml.etree.ElementTree as ET
        resp = _req.post(
            'https://mis.tpex.org.tw/Quote.asmx/GETQ20',
            data={'SymbolID': stock_id},
            timeout=8,
            verify=False,           # TPEx 憑證缺 Subject Key Identifier，需停用驗證
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': 'https://mis.tpex.org.tw/',
            },
        )
        root = ET.fromstring(resp.text)

        def _tag(name):
            for el in root.iter():
                if el.tag.split('}')[-1] == name:
                    return el.text.strip() if el.text else None
            return None

        def _f(name):
            v = _tag(name)
            try:
                return float(v) if v else None
            except (ValueError, TypeError):
                return None

        price = _f('TradePrice')
        prev  = _f('PreAverage')   # 前日均價（相當於昨收）
        if not price and not prev:
            return None            # 非交易時間或代號不存在

        chg     = round(price - prev, 2)       if price and prev else None
        chg_pct = round(chg / prev * 100, 2)   if chg and prev   else None

        vol_lots = None
        vol_raw = _tag('TradeStatisticTtlVol')
        if vol_raw:
            try:
                vol_lots = round(int(float(vol_raw)) / 1000)  # 股 → 張
            except (ValueError, TypeError):
                pass

        return {
            '代號':      stock_id,
            '名稱':      '',
            '現價':      price,
            '昨收':      prev,
            '漲跌':      chg,
            '漲跌%':     chg_pct,
            '開盤':      _f('TradeStatisticOpen'),
            '最高':      _f('TradeStatisticHigh'),
            '最低':      _f('TradeStatisticLow'),
            '成交量(張)': vol_lots,
        }
    except Exception:
        return None


def calc_risk_metrics(df: pd.DataFrame,
                      benchmark_df: pd.DataFrame | None = None) -> dict:
    """計算個股風險指標：年化波動率、最大回撤、Beta（需要 benchmark_df）。"""
    if df is None or len(df) < 20:
        return {}
    returns = df['Close'].pct_change().dropna()
    vol    = float(returns.std() * np.sqrt(252) * 100)
    cummax = df['Close'].cummax()
    max_dd = float(((df['Close'] - cummax) / cummax * 100).min())
    result = {'年化波動率': round(vol, 1), '最大回撤': round(max_dd, 1)}
    if benchmark_df is not None and len(benchmark_df) >= 20:
        bmk_r   = benchmark_df['Close'].pct_change().dropna()
        aligned = pd.concat([returns, bmk_r], axis=1, join='inner').dropna()
        aligned.columns = ['s', 'b']
        if len(aligned) >= 20 and aligned['b'].var() > 0:
            result['Beta'] = round(
                float(aligned['s'].cov(aligned['b']) / aligned['b'].var()), 2)
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_monthly_revenue(ticker: str) -> pd.DataFrame | None:
    """FinMind 月營收（近24個月）。
    回傳 DataFrame(月份, 當月(億), MoM%, YoY%) 或 None。"""
    code  = ticker.replace('.TWO', '').replace('.TW', '')
    start = (TODAY - timedelta(days=760)).strftime('%Y-%m-%d')
    try:
        resp = _req.get(
            'https://api.finmindtrade.com/api/v4/data',
            params={'dataset': 'TaiwanStockMonthRevenue',
                    'data_id': code, 'start_date': start},
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        records = resp.json().get('data', [])
    except Exception:
        return None
    if not records:
        return None

    rows = []
    for rec in records:
        try:
            yr  = int(rec['revenue_year'])
            mo  = int(rec['revenue_month'])
            rev = float(rec['revenue'])
            if rev <= 0:
                continue
            rows.append({
                '月份':    f"{yr}/{mo:02d}",
                '_sort':   yr * 100 + mo,
                '_rev':    rev,
                '當月(億)': round(rev / 1e8, 2),
            })
        except Exception:
            continue

    if not rows:
        return None

    df_rev = (pd.DataFrame(rows)
              .drop_duplicates('月份')
              .sort_values('_sort')
              .reset_index(drop=True))

    rev_s = df_rev['_rev']
    df_rev['MoM(%)'] = rev_s.pct_change(1).mul(100).round(1)
    df_rev['YoY(%)'] = rev_s.pct_change(12).mul(100).round(1)

    result = (df_rev
              .drop(columns=['_sort', '_rev'])
              .tail(24)
              .reset_index(drop=True))
    return result if len(result) >= 3 else None


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_margin_day_ok(date_str: str) -> dict:
    """TWSE MI_MARGN 單日快取，失敗拋 ValueError（不被快取）。"""
    url = (f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
           f"?response=json&date={date_str}&selectType=STOCK")
    resp = _req.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
    data = resp.json()
    if data.get('stat') != 'OK':
        raise ValueError('no data')

    # API 回傳 tables 陣列；欄位名稱因 encoding 全為亂碼，固定用位置索引：
    # [0]=代號, [5]=融資今日餘額, [6]=融資前日餘額
    # [11]=融券今日餘額, [12]=融券前日餘額
    tables = data.get('tables', [])
    table  = next((t for t in tables if t.get('data')), None)
    if not table:
        raise ValueError('no table')
    rows = table['data']

    def _p(v):
        try:
            return int(str(v).replace(',', ''))
        except Exception:
            return 0

    result = {}
    for row in rows:
        try:
            sid = str(row[0]).strip()
            if not sid or not sid.isdigit() or len(row) < 14:
                continue
            today_f = _p(row[5])
            prev_f  = _p(row[6])
            today_s = _p(row[11])
            prev_s  = _p(row[12])
            result[sid] = {
                '融資餘額': today_f,
                '融資增減': today_f - prev_f,
                '融券餘額': today_s,
                '融券增減': today_s - prev_s,
            }
        except Exception:
            continue
    if not result:
        raise ValueError('empty')
    return result


def _fetch_margin_day(date_str: str) -> dict | None:
    try:
        return _fetch_margin_day_ok(date_str)
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_margin_history(ticker: str, n_days: int = 60) -> pd.DataFrame | None:
    """個股融資融券歷史（近 n_days 個交易日，上市股票）。v2"""
    stock_id = ticker.replace('.TWO', '').replace('.TW', '')
    rows, checked = [], 0
    for delta in range(1, n_days * 3):
        if len(rows) >= n_days or checked > n_days + 60:
            break
        day = TODAY - timedelta(days=delta)
        if day.weekday() >= 5:
            continue
        checked += 1
        day_data = _fetch_margin_day(day.strftime('%Y%m%d'))
        if not day_data or stock_id not in day_data:
            continue
        rows.append({'日期': day, **day_data[stock_id]})
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values('日期').reset_index(drop=True)


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_t86_day_ok(date_str: str) -> dict:
    """T86 單日快取：單次 HTTP 請求，假日/無資料拋 ValueError（不被快取）。"""
    url = (f"https://www.twse.com.tw/rwd/zh/fund/T86"
           f"?response=json&selectType=ALLBUT0999&date={date_str}")
    resp = _req.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
    data = resp.json()
    if data.get('stat') != 'OK' or not data.get('data'):
        raise ValueError('no data')     # 假日或無資料：拋例外，Streamlit 不快取
    result = {}
    def _p(v):
        s = str(v).replace(',', '').strip()
        return int(s) if s and s not in ('--', '') else 0
    for row in data.get('data', []):
        try:
            sid = row[0].strip()
            if not sid or not sid.isdigit():
                continue
            fii   = _p(row[4])
            trust = _p(row[10])
            total = _p(row[-1])
            result[sid] = {
                '外資':     int(fii   / 1000),
                '投信':     int(trust / 1000),
                '自營商':   int((total - fii - trust) / 1000),
                '三大合計': int(total / 1000),
            }
        except Exception:
            continue
    if not result:
        raise ValueError('empty result')  # 解析全失敗：也不快取
    return result


def _fetch_t86_day(date_str: str) -> dict | None:
    """單次請求取 T86 一日資料；失敗不快取，下次可重試。"""
    try:
        return _fetch_t86_day_ok(date_str)
    except Exception:
        return None


def get_inst_nd(ticker: str, n: int = 5) -> dict:
    """取近 n 個交易日三大法人買賣超合計（張），找不到資料時回空 dict"""
    stock_id = ticker.replace('.TWO', '').replace('.TW', '')
    totals   = {'外資': 0, '投信': 0, '自營商': 0, '三大合計': 0}
    found    = 0
    for delta in range(1, 30):          # 最多往回 30 個日曆日
        if found >= n:
            break
        day = TODAY - timedelta(days=delta)
        if day.weekday() >= 5:          # 跳過週六(5)、週日(6)
            continue
        day_data = _fetch_t86_day(day.strftime('%Y%m%d'))
        if not day_data or stock_id not in day_data:
            continue
        for k in totals:
            totals[k] += day_data[stock_id][k]
        found += 1
    return totals if found > 0 else {}


def get_inst_streak(ticker: str, min_streak: int = 3, max_check: int = 10) -> list[str]:
    """檢查近期法人是否連續同方向買賣超。
    回傳警示字串清單，例如 ['🔥外資連買4日', '🔴投信連賣3日']"""
    stock_id = ticker.replace('.TWO', '').replace('.TW', '')
    daily: dict[str, list[int]] = {'外資': [], '投信': [], '三大合計': []}
    found = 0
    for delta in range(1, 40):
        if found >= max_check:
            break
        day = TODAY - timedelta(days=delta)
        if day.weekday() >= 5:
            continue
        day_data = _fetch_t86_day(day.strftime('%Y%m%d'))
        if not day_data or stock_id not in day_data:
            continue
        d = day_data[stock_id]
        for k in daily:
            daily[k].append(d[k])
        found += 1

    alerts = []
    label_map = {'外資': '外資', '投信': '投信', '三大合計': '三大'}
    for k, label in label_map.items():
        vals = daily[k]
        if len(vals) < min_streak:
            continue
        direction = 1 if vals[0] > 0 else (-1 if vals[0] < 0 else 0)
        if direction == 0:
            continue
        streak = 1
        for v in vals[1:]:
            v_dir = 1 if v > 0 else (-1 if v < 0 else 0)
            if v_dir == direction:
                streak += 1
            else:
                break
        if streak >= min_streak:
            emoji  = "🔥" if direction > 0 else "🔴"
            action = "連買" if direction > 0 else "連賣"
            alerts.append(f"{emoji}{label}{action}{streak}日")
    return alerts


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_institutional(ticker: str, days: int = 60) -> pd.DataFrame | None:
    """三大法人時序（使用 T86 逐日快取彙整，上市股票）"""
    stock_id = ticker.replace('.TWO', '').replace('.TW', '')
    rows, checked = [], 0
    for delta in range(1, days * 3):    # 最多往回找 days×3 個日曆日
        if len(rows) >= days or checked > days + 60:
            break
        day = TODAY - timedelta(days=delta)
        if day.weekday() >= 5:
            continue
        checked += 1
        day_data = _fetch_t86_day(day.strftime('%Y%m%d'))
        if not day_data or stock_id not in day_data:
            continue
        d = day_data[stock_id]
        rows.append({'日期': day, '外資': d['外資'], '投信': d['投信'],
                     '自營商': d['自營商'], '三大合計': d['三大合計']})
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values('日期').reset_index(drop=True)


# ── 訊號分析 ──────────────────────────────────────────────────────
def signal_verdict(df: pd.DataFrame) -> dict:
    if df is None or len(df) < 3:
        return {"KD狀態": "N/A", "MACD": "N/A", "均線": "N/A",
                "訊號": "—", "警示": "—", "評估": "⚪ N/A"}
    last, prev = df.iloc[-1], df.iloc[-2]
    rsi        = float(last['RSI']) if not np.isnan(last['RSI']) else 50.0
    kd_k, kd_d = float(last['KD_K']), float(last['KD_D'])
    pk,   pd_  = float(prev['KD_K']), float(prev['KD_D'])
    macd_bull  = bool(last['MACD'] > last['MACD_signal'] and last['MACD'] > 0)
    macd_cross = bool(last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal'])
    ma_bull    = bool(last['MA5'] > last['MA10'] > last['MA20'])
    kd_golden  = kd_k > kd_d and pk <= pd_
    kd_dead    = kd_k < kd_d and pk >= pd_

    sigs, warns = [], []
    if rsi < 30:    sigs.append("RSI超賣")
    elif rsi < 40:  sigs.append("RSI偏低")
    elif rsi > 75:  warns.append("RSI超買")
    elif rsi > 65:  warns.append("RSI偏熱")
    if kd_k < 20:   sigs.append("KD超賣")
    elif kd_k > 80: warns.append("KD超買")
    if kd_golden:   sigs.append("KD金叉")
    if kd_dead:     warns.append("KD死叉")
    if macd_cross:  sigs.append("MACD金叉")
    elif macd_bull: sigs.append("MACD多頭")
    if ma_bull:     sigs.append("均線多排")

    if len(warns) >= 2:               verdict = "🔴 過熱"
    elif len(warns) == 1 and not sigs: verdict = "🟡 偏熱"
    elif len(sigs) >= 3:              verdict = "🟢 有機會"
    elif len(sigs) >= 1:              verdict = "🟢 中性偏多"
    else:                             verdict = "⚪ 中性"

    kd_status = ("金叉" if kd_golden else "死叉" if kd_dead else
                 "超賣" if kd_k < 20 else "超買" if kd_k > 80 else "正常")
    return {
        "KD狀態": kd_status, "MACD": "多頭" if macd_bull else "空頭",
        "均線":   "多排" if ma_bull else "空排",
        "訊號":   " | ".join(sigs)  if sigs  else "—",
        "警示":   " | ".join(warns) if warns else "—",
        "評估":   verdict,
    }


def backtest_signal(df: pd.DataFrame) -> list[dict]:
    """計算 KD金叉 / MACD金叉 / RSI超賣反彈 在 5/10/20 日後的歷史勝率與平均報酬"""
    if df is None or len(df) < 30:
        return []
    signals = {
        'KD 黃金交叉':    (df['KD_K'] > df['KD_D']) & (df['KD_K'].shift(1) <= df['KD_D'].shift(1)),
        'MACD 黃金交叉':  (df['MACD'] > df['MACD_signal']) & (df['MACD'].shift(1) <= df['MACD_signal'].shift(1)),
        'RSI 超賣反彈':   (df['RSI'] >= 30) & (df['RSI'].shift(1) < 30),
    }
    rows = []
    for sig_name, mask in signals.items():
        positions = [df.index.get_loc(i) for i in df.index[mask]]
        fwd: dict[int, list[float]] = {5: [], 10: [], 20: []}
        for pos in positions:
            base = float(df.iloc[pos]['Close'])
            for n in (5, 10, 20):
                fp = pos + n
                if fp < len(df):
                    fwd[n].append((float(df.iloc[fp]['Close']) / base - 1) * 100)
        row: dict = {'訊號': sig_name, '歷史次數': len(positions)}
        for n in (5, 10, 20):
            vals = fwd[n]
            if vals:
                row[f'{n}日勝率'] = f"{sum(v > 0 for v in vals) / len(vals) * 100:.0f}%"
                row[f'{n}日均報'] = f"{np.mean(vals):+.2f}%"
            else:
                row[f'{n}日勝率'] = row[f'{n}日均報'] = "—"
        rows.append(row)
    return rows


def _scan_alerts() -> list[dict]:
    """掃描自選清單，回傳今日觸發的警示（每 session 只算一次）"""
    alerts = []
    for ticker, wl_entry in st.session_state.watchlist.items():
        if not isinstance(wl_entry, dict):
            continue
        name   = wl_entry.get('name', ticker)
        cost   = wl_entry.get('cost')
        target = wl_entry.get('target')
        df = fetch(ticker, 90)
        if df is None or len(df) < 2:
            continue
        last, prev = df.iloc[-1], df.iloc[-2]
        price  = float(last['Close'])
        kd_k, kd_d = float(last['KD_K']), float(last['KD_D'])
        pk,   pd_  = float(prev['KD_K']), float(prev['KD_D'])
        raw = ticker.replace('.TW', '')

        if kd_k > kd_d and pk <= pd_:
            alerts.append({'type': 'buy',  'icon': '🟢', 'name': name, 'raw': raw,
                           'msg': f'KD 黃金交叉 (K={kd_k:.1f} / D={kd_d:.1f})'})
        if kd_k < kd_d and pk >= pd_:
            alerts.append({'type': 'sell', 'icon': '🔴', 'name': name, 'raw': raw,
                           'msg': f'KD 死亡交叉 (K={kd_k:.1f} / D={kd_d:.1f})'})
        if last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal']:
            alerts.append({'type': 'buy',  'icon': '🟢', 'name': name, 'raw': raw,
                           'msg': 'MACD 黃金交叉'})
        if target and price >= target:
            alerts.append({'type': 'target', 'icon': '🎯', 'name': name, 'raw': raw,
                           'msg': f'股價 {price:.1f} 已達目標價 {target:.1f}'})
        if cost and price < cost:
            alerts.append({'type': 'warn', 'icon': '⚠️', 'name': name, 'raw': raw,
                           'msg': f'股價 {price:.1f} 跌破成本 {cost:.1f}（{(price/cost-1)*100:+.1f}%）'})
    return alerts


def _heat_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 20:
        return -999.0
    last      = df.iloc[-1]
    price_now = float(last['Close'])
    ret_1m    = (price_now / float(df['Close'].iloc[-20]) - 1) * 100
    rsi       = float(last['RSI']) if not np.isnan(last['RSI']) else 50.0
    macd_bull = float(bool(last['MACD'] > last['MACD_signal'] and last['MACD'] > 0))
    ma_bull   = float(bool(last['MA5'] > last['MA10'] > last['MA20']))
    return ret_1m * 0.4 + (rsi - 50) * 0.2 + macd_bull * 10 * 0.2 + ma_bull * 10 * 0.2


def rank_sectors(days: int) -> list[dict]:
    results, items = [], list(ALL_SECTORS.items())
    prog = st.progress(0, text="計算產業熱度中…")
    for i, (sec_name, stocks) in enumerate(items):
        scores, rets = [], []
        for ticker in stocks.values():
            if not ticker:
                continue
            df = fetch(ticker, days)
            if df is None or len(df) < 20:
                continue
            s = _heat_score(df)
            if s > -999:
                scores.append(s)
                rets.append((float(df['Close'].iloc[-1]) / float(df['Close'].iloc[-20]) - 1) * 100)
        if scores:
            results.append({"產業": sec_name,
                            "熱度分數": round(float(np.mean(scores)), 2),
                            "平均近1月%": f"{float(np.mean(rets)):+.1f}%",
                            "有效股票數": len(scores)})
        prog.progress((i + 1) / len(items), text=f"已完成：{sec_name}")
    prog.empty()
    return sorted(results, key=lambda x: x["熱度分數"], reverse=True)


def rank_stocks(sec_name: str, days: int) -> list[dict]:
    results = []
    for name, ticker in ALL_SECTORS[sec_name].items():
        if not ticker:
            continue
        df = fetch(ticker, days)
        if df is None or len(df) < 20:
            continue
        last  = df.iloc[-1]
        price = float(last['Close'])
        ret_1m = (price / float(df['Close'].iloc[-20]) - 1) * 100
        ret_6m = (price / float(df['Close'].iloc[max(0, len(df) - 120)]) - 1) * 100
        rsi    = float(last['RSI']) if not np.isnan(last['RSI']) else 0.0
        results.append({
            "公司": name, "代號": ticker.replace('.TW', ''),
            "股價": round(price, 1),
            "近1月%": f"{ret_1m:+.1f}%", "近6月%": f"{ret_6m:+.1f}%",
            "RSI": round(rsi, 1),
            "KD_K": round(float(last['KD_K']), 1), "KD_D": round(float(last['KD_D']), 1),
            "MACD多":  "✅" if last['MACD'] > last['MACD_signal'] and last['MACD'] > 0 else "❌",
            "均線多排": "✅" if last['MA5'] > last['MA10'] > last['MA20'] else "❌",
            "熱度分數": round(_heat_score(df), 2), "_df": df,
        })
    return sorted(results, key=lambda x: x["熱度分數"], reverse=True)


def screen_stocks(cond: dict, days: int) -> list[dict]:
    seen: dict[str, tuple[str, str]] = {}
    for sec_name, stocks in ALL_SECTORS.items():
        for name, ticker in stocks.items():
            if ticker and ticker not in seen:
                seen[ticker] = (name, sec_name)

    results, items = [], list(seen.items())
    prog = st.progress(0, text="掃描全市場中…")

    for i, (ticker, (name, sec_name)) in enumerate(items):
        prog.progress((i + 1) / len(items), text=f"掃描：{name}")
        df = fetch(ticker, days)
        if df is None or len(df) < 3:
            continue

        last, prev = df.iloc[-1], df.iloc[-2]
        rsi    = float(last['RSI']) if not np.isnan(last['RSI']) else 50.0
        kd_k   = float(last['KD_K'])
        kd_d   = float(last['KD_D'])
        pk, pd_ = float(prev['KD_K']), float(prev['KD_D'])
        price  = float(last['Close'])
        ret_1m = (price / float(df['Close'].iloc[-20]) - 1) * 100 if len(df) >= 20 else 0
        macd_bull  = bool(last['MACD'] > last['MACD_signal'] and last['MACD'] > 0)
        macd_cross = bool(last['MACD'] > last['MACD_signal'] and prev['MACD'] <= prev['MACD_signal'])
        ma_bull    = bool(last['MA5'] > last['MA10'] > last['MA20'])
        kd_golden  = kd_k > kd_d and pk <= pd_
        kd_dead    = kd_k < kd_d and pk >= pd_

        passed = True
        preset_map = {
            "RSI 超賣（< 30）":    lambda: rsi < 30,
            "RSI 偏低（30-40）":   lambda: 30 <= rsi < 40,
            "RSI 偏熱（> 65）":    lambda: rsi > 65,
            "RSI 超買（> 75）":    lambda: rsi > 75,
            "KD 超賣（K < 20）":   lambda: kd_k < 20,
            "KD 超買（K > 80）":   lambda: kd_k > 80,
            "KD 黃金交叉":         lambda: kd_golden,
            "KD 死亡交叉":         lambda: kd_dead,
            "MACD 多頭":           lambda: macd_bull,
            "MACD 黃金交叉":       lambda: macd_cross,
            "均線多頭排列":         lambda: ma_bull,
            "近1月上漲（> 0%）":   lambda: ret_1m > 0,
            "近1月下跌（< 0%）":   lambda: ret_1m < 0,
        }
        for c in cond.get('presets', []):
            if c in preset_map and not preset_map[c]():
                passed = False
                break

        if passed and cond.get('use_rsi_range'):
            lo, hi = cond['rsi_range']
            if not (lo <= rsi <= hi):
                passed = False
        if passed and cond.get('use_ret_range'):
            lo, hi = cond['ret_range']
            if not (lo <= ret_1m <= hi):
                passed = False

        if passed:
            v = signal_verdict(df)
            results.append({
                "產業": sec_name, "公司": name, "代號": ticker.replace('.TW', ''),
                "股價": round(price, 1), "近1月%": f"{ret_1m:+.1f}%",
                "RSI": round(rsi, 1), "KD_K": round(kd_k, 1), "KD_D": round(kd_d, 1),
                "MACD": v['MACD'], "均線": v['均線'], "評估": v['評估'],
                "訊號": v['訊號'], "熱度分數": round(_heat_score(df), 2), "_df": df,
            })

    prog.empty()
    return sorted(results, key=lambda x: x['熱度分數'], reverse=True)


def save_screen_snapshot(cond_label: str, results: list[dict]) -> str:
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(SNAPSHOT_DIR, f"screen_{ts}.json")
    payload  = {
        "date": datetime.now().strftime('%Y-%m-%d %H:%M'), "conditions": cond_label,
        "count": len(results),
        "stocks": [{"ticker": r['代號'], "company": r['公司'], "sector": r['產業'],
                    "price": r['股價'], "ret_1m": r['近1月%'], "rsi": r['RSI'],
                    "verdict": r['評估'], "signals": r['訊號']} for r in results],
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return filepath


# ── 圖表 ─────────────────────────────────────────────────────────
def make_chart(df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.38, 0.12, 0.14, 0.18, 0.18],
        subplot_titles=("K線 + MA + 布林帶", "成交量", "RSI (14)", "MACD", "KD (9)"),
    )

    fig.add_trace(go.Scatter(x=df.index, y=df['BB_upper'], name='BB上軌',
                             line=dict(color='rgba(100,100,220,0.35)', width=1),
                             showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BB_lower'], name='BB下軌',
                             fill='tonexty', fillcolor='rgba(100,100,220,0.07)',
                             line=dict(color='rgba(100,100,220,0.35)', width=1),
                             showlegend=False), row=1, col=1)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='K線', showlegend=False,
        increasing_line_color='#e74c3c', increasing_fillcolor='#e74c3c',
        decreasing_line_color='#27ae60', decreasing_fillcolor='#27ae60',
    ), row=1, col=1)
    for ma, color, dash in [('MA5','#f39c12','dash'), ('MA10','#2ecc71','dashdot'), ('MA20','#e74c3c','dot')]:
        fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma,
                                 line=dict(color=color, width=1, dash=dash)), row=1, col=1)

    # 買賣訊號標記（偏移量 = 整段可見價格區間的固定比例，避免壓到 K 棒）
    _price_range  = float(df['High'].max() - df['Low'].min()) or float(df['Close'].mean()) * 0.1
    _off1 = _price_range * 0.045   # 第一層（KD 金叉／死叉）
    _off2 = _price_range * 0.085   # 第二層（MACD 金叉，與 KD 金叉錯開避免疊加）
    kd_gold   = df[(df['KD_K'] > df['KD_D']) & (df['KD_K'].shift(1) <= df['KD_D'].shift(1))]
    kd_dead   = df[(df['KD_K'] < df['KD_D']) & (df['KD_K'].shift(1) >= df['KD_D'].shift(1))]
    macd_gold = df[(df['MACD'] > df['MACD_signal']) & (df['MACD'].shift(1) <= df['MACD_signal'].shift(1))]
    if not kd_gold.empty:
        fig.add_trace(go.Scatter(x=kd_gold.index, y=kd_gold['Low'] - _off1, mode='markers',
                                 marker=dict(symbol='triangle-up', size=11, color='#2980b9'),
                                 name='KD金叉'), row=1, col=1)
    if not kd_dead.empty:
        fig.add_trace(go.Scatter(x=kd_dead.index, y=kd_dead['High'] + _off1, mode='markers',
                                 marker=dict(symbol='triangle-down', size=11, color='#e67e22'),
                                 name='KD死叉'), row=1, col=1)
    if not macd_gold.empty:
        fig.add_trace(go.Scatter(x=macd_gold.index, y=macd_gold['Low'] - _off2, mode='markers',
                                 marker=dict(symbol='star', size=13, color='#27ae60'),
                                 name='MACD金叉'), row=1, col=1)

    vol_colors = ['#e74c3c' if float(c) >= float(o) else '#27ae60'
                  for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='成交量',
                         marker_color=vol_colors, opacity=0.75, showlegend=False), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'],
                             line=dict(color='#8e44ad', width=1.5), showlegend=False), row=3, col=1)
    for y, c, d in [(70,'red','dash'), (50,'gray','dot'), (30,'green','dash')]:
        fig.add_hline(y=y, line_dash=d, line_color=c, opacity=0.4, row=3, col=1)

    bar_colors = ['#e74c3c' if v >= 0 else '#27ae60' for v in df['MACD_hist']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_hist'], marker_color=bar_colors,
                         opacity=0.65, showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'],
                             line=dict(color='#2980b9', width=1.5), showlegend=False), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_signal'],
                             line=dict(color='#e67e22', width=1.5), showlegend=False), row=4, col=1)
    fig.add_hline(y=0, line_color='black', opacity=0.2, row=4, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['KD_K'],
                             line=dict(color='#2980b9', width=1.5), showlegend=False), row=5, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['KD_D'],
                             line=dict(color='#e67e22', width=1.5), showlegend=False), row=5, col=1)
    for y, c, d in [(80,'red','dash'), (50,'gray','dot'), (20,'green','dash')]:
        fig.add_hline(y=y, line_dash=d, line_color=c, opacity=0.4, row=5, col=1)

    fig.update_layout(
        title=dict(text=title, font=dict(size=14)), height=900,
        margin=dict(l=5, r=5, t=60, b=5),
        legend=dict(orientation='h', y=1.03, x=0, font=dict(size=11)),
        hovermode='x unified', xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    fig.update_yaxes(range=[0, 100], row=5, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=['sat', 'mon'])])
    return fig


def make_institutional_chart(df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=['外資買賣超（張）', '投信買賣超（張）', '自營商買賣超（張）'])
    for row_i, col_name in enumerate(['外資', '投信', '自營商'], 1):
        vals   = df[col_name]
        colors = ['#e74c3c' if v > 0 else '#27ae60' for v in vals]
        fig.add_trace(go.Bar(x=df['日期'], y=vals, marker_color=colors,
                             opacity=0.8, showlegend=False), row=row_i, col=1)
        fig.add_hline(y=0, line_color='black', opacity=0.2, row=row_i, col=1)
    fig.update_layout(title=title, height=560,
                      margin=dict(l=5, r=5, t=50, b=5), hovermode='x unified')
    return fig


# ── 自選清單 I/O ──────────────────────────────────────────────────
def load_watchlist() -> dict[str, dict]:
    """回傳格式：{ticker: {name, target, cost, lots}}；自動相容舊字串格式"""
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        migrated = {}
        for k, v in data.items():
            if isinstance(v, str):
                migrated[k] = {"name": v, "target": None, "cost": None, "lots": None}
            else:
                if 'lots' not in v:
                    v['lots'] = None
                migrated[k] = v
        return migrated
    return {}


def save_watchlist(wl: dict[str, dict]) -> None:
    with open(WATCHLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)


# ── Streamlit UI ──────────────────────────────────────────────────
def _run_app():
    st.set_page_config(page_title="台股監控", page_icon="📈", layout="wide")

    if 'watchlist' not in st.session_state:
        st.session_state.watchlist = load_watchlist()

    with st.sidebar:
        st.header("⚙️ 全域設定")
        days = st.selectbox("分析區間", [90, 180, 365], index=2,
                            format_func=lambda x: f"{x} 天")
        if st.button("🔄 清除快取", use_container_width=True):
            st.cache_data.clear()
            # 重置警示快取，讓下次重新掃描
            for key in ('active_alerts', 'alerts_dismissed'):
                st.session_state.pop(key, None)
            st.rerun()
        st.caption(f"資料日期：{TODAY.strftime('%Y-%m-%d')}\n資料來源：Yahoo Finance / TWSE")

    st.title("📈 台股熱門產業監控")
    with st.spinner("載入股票清單…"):
        all_stocks = fetch_all_stocks()   # {代號: (名稱, suffix)}

    # ── 啟動警示面板 ──────────────────────────────────────────────
    if st.session_state.watchlist and not st.session_state.get('alerts_dismissed'):
        if 'active_alerts' not in st.session_state:
            with st.spinner("掃描自選清單警示中…"):
                st.session_state.active_alerts = _scan_alerts()
        alerts = st.session_state.active_alerts
        if alerts:
            col_hdr, col_dis = st.columns([9, 1])
            col_hdr.subheader("🔔 今日自選股警示")
            if col_dis.button("✕ 關閉"):
                st.session_state.alerts_dismissed = True
                st.rerun()
            for a in alerts:
                msg = f"**{a['name']}（{a['raw']}）** — {a['msg']}"
                if a['type'] == 'buy':
                    st.success(f"{a['icon']} {msg}")
                elif a['type'] == 'sell':
                    st.error(f"{a['icon']} {msg}")
                elif a['type'] == 'target':
                    st.info(f"{a['icon']} {msg}")
                else:
                    st.warning(f"{a['icon']} {msg}")
            st.divider()

    tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["🌐 大盤概覽", "🏭 產業熱度", "🔍 個股查詢",
         "⭐ 自選清單", "🏦 籌碼面板", "🎯 條件選股", "⚡ 即時行情"]
    )

    # ── Tab 0：大盤概覽 ───────────────────────────────────────────
    with tab0:
        if not st.button("📊 載入大盤資料", type="primary", key="t0_run"):
            st.info("點「載入大盤資料」取得加權指數最新狀況", icon="📊")
        else:
            with st.spinner("載入加權指數（^TWII）…"):
                df_twii = fetch('^TWII', days)
            if df_twii is None:
                st.error("無法載入加權指數，請確認網路連線")
            else:
                last_tw = df_twii.iloc[-1]
                prev_tw = df_twii.iloc[-2]
                idx_now = float(last_tw['Close'])
                idx_chg = (idx_now / float(prev_tw['Close']) - 1) * 100
                idx_1m  = (idx_now / float(df_twii['Close'].iloc[-20]) - 1) * 100
                rsi_tw  = float(last_tw['RSI']) if not np.isnan(last_tw['RSI']) else 50.0
                ma_bull = bool(last_tw['MA5'] > last_tw['MA10'] > last_tw['MA20'])

                if   rsi_tw < 30: temp_label = "極度低迷"
                elif rsi_tw < 45: temp_label = "偏冷"
                elif rsi_tw < 60: temp_label = "中性"
                elif rsi_tw < 70: temp_label = "偏熱"
                else:             temp_label = "過熱"

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("加權指數",  f"{idx_now:,.0f}",  f"{idx_chg:+.2f}%")
                m2.metric("近1月漲跌", f"{idx_1m:+.1f}%")
                m3.metric("RSI (14)",  f"{rsi_tw:.1f}")
                m4.metric("均線排列",  "多頭 ✅" if ma_bull else "空頭 ❌")
                m5.metric("市場溫度",  temp_label)
                st.caption("市場溫度依加權指數 RSI：< 30 極低迷 / 30-45 偏冷 / 45-60 中性 / 60-70 偏熱 / > 70 過熱")
                st.plotly_chart(make_chart(df_twii, "加權指數 (^TWII)"), width='stretch', key='twii_chart')

    # ── Tab 1：產業熱度 ───────────────────────────────────────────
    with tab1:
        st.caption("產業熱度分析以預設上市股票清單（台灣50＋中型100為骨幹）為基礎。")
        if True:
            col_a, col_b = st.columns(2)
            top_n = col_a.slider("顯示熱門產業數", 1, 5, 3)
            top_m = col_b.slider("每產業顯示股票數", 1, 5, 3)
            if not st.button("🔍 開始分析", type="primary", key="t1_run"):
                st.info("設定完成後點「開始分析」", icon="👈")
            else:
                st.subheader("產業熱度排名")
                sector_ranking = rank_sectors(days)

                def _hi(row):
                    return (['background-color: #8b1a1a; color: #ffffff'] * len(row)
                            if row.name < 5 else [''] * len(row))

                st.dataframe(pd.DataFrame(sector_ranking).style.apply(_hi, axis=1),
                             width='stretch', hide_index=True)

                DCOLS = ["公司","代號","股價","近1月%","近6月%","RSI","KD_K","KD_D","MACD多","均線多排","熱度分數"]
                for rank_i, sec_info in enumerate(sector_ranking[:top_n], 1):
                    sn = sec_info["產業"]
                    st.divider()
                    st.subheader(f"#{rank_i}  {sn}　熱度：{sec_info['熱度分數']}　近1月均漲：{sec_info['平均近1月%']}")
                    with st.spinner(f"分析 {sn}…"):
                        results = rank_stocks(sn, days)
                    st.dataframe(
                        pd.DataFrame([{k: v for k, v in r.items() if k in DCOLS} for r in results], columns=DCOLS),
                        width='stretch', hide_index=True,
                    )
                    for stock in results[:top_m]:
                        label = (f"{stock['公司']}（{stock['代號']}）　近1月 {stock['近1月%']}　"
                                 f"RSI {stock['RSI']}　KD_K {stock['KD_K']} / KD_D {stock['KD_D']}")
                        with st.expander(label, expanded=True):
                            st.plotly_chart(make_chart(stock["_df"], f"{stock['公司']} ({stock['代號']})"),
                                            width='stretch', key=f"sector_{stock['代號']}")

    # ── Tab 2：個股查詢 ───────────────────────────────────────────
    with tab2:
        c1, c2, c3 = st.columns([3, 1, 1])
        code_input = c1.text_input(
            "股票代號或名稱",
            placeholder="例如：2330 或 台積電、6892 或 台寶生醫",
            label_visibility='collapsed', key="t2_code",
        )
        search_btn = c2.button("🔍 查詢",    type="primary", key="t2_search")
        add_btn    = c3.button("⭐ 加入自選", key="t2_add")

        # 模糊比對（傳入合併市場清單，自動判斷 suffix）
        ticker = name = None
        if code_input.strip():
            candidates = fuzzy_resolve(code_input.strip(), all_stocks=all_stocks)
            if len(candidates) == 0:
                raw_in = code_input.strip()
                ticker = raw_in if '.' in raw_in else raw_in + '.TW'
                name   = TICKER_TO_NAME.get(ticker, raw_in)
            elif len(candidates) == 1:
                name, ticker = candidates[0]
            else:
                options = [f"{n}（{t.replace('.TW','').replace('.TWO','')}）" for n, t in candidates]
                chosen  = st.selectbox("找到多個符合股票，請選擇：", options, key="t2_select")
                idx     = options.index(chosen)
                name, ticker = candidates[idx]

        # 按查詢/加入 → 存進 session_state，radio 切換時結果仍保留
        if (search_btn or add_btn) and ticker:
            st.session_state['t2_ticker'] = ticker
            st.session_state['t2_name']   = name
            if add_btn:
                if ticker not in st.session_state.watchlist:
                    st.session_state.watchlist[ticker] = {"name": name, "target": None, "cost": None, "lots": None}
                    save_watchlist(st.session_state.watchlist)
                    st.success(f"✅ 已將 {name}（{ticker.replace('.TW','').replace('.TWO','')}）加入自選清單")
                else:
                    st.info(f"{name} 已在自選清單中")

        # 結果區塊
        active_ticker = st.session_state.get('t2_ticker')
        active_name   = st.session_state.get('t2_name', active_ticker)

        if active_ticker:
            with st.spinner(f"載入 {active_name}…"):
                df       = fetch(active_ticker, days)
                df_bench = fetch('^TWII', days)
                div_info = fetch_dividend_info(active_ticker)
                fund     = fetch_fundamentals(active_ticker)

            if df is None:
                st.error(f"找不到股票 {active_name}（{active_ticker}），請確認代號是否正確")
            else:
                last   = df.iloc[-1]
                price  = float(last['Close'])
                ret_1m = (price / float(df['Close'].iloc[-20]) - 1) * 100
                v      = signal_verdict(df)

                code_disp = active_ticker.replace('.TWO', '').replace('.TW', '')
                st.subheader(f"{active_name}（{code_disp}）　{v['評估']}")
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                m1.metric("股價",  f"{price:.1f}")
                m2.metric("近1月", f"{ret_1m:+.1f}%")
                m3.metric("RSI",   f"{float(last['RSI']):.1f}")
                m4.metric("KD_K",  f"{float(last['KD_K']):.1f}")
                m5.metric("KD_D",  f"{float(last['KD_D']):.1f}")
                m6.metric("殖利率", f"{div_info['殖利率']:.1f}%" if div_info.get('殖利率') else "—")
                m7.metric("本益比", f"{div_info['本益比']}"       if div_info.get('本益比') else "—")

                if div_info.get('除息日'):
                    st.caption(f"最近除息日：{div_info['除息日']}")
                if v['訊號'] != "—":
                    st.success(f"訊號：{v['訊號']}")
                if v['警示'] != "—":
                    st.warning(f"警示：{v['警示']}")

                # 三大法人：上市（.TW）才支援
                st.divider()
                if active_ticker.endswith('.TW'):
                    inst_n = st.radio("法人觀察天數", [3, 5, 10], index=1,
                                      horizontal=True, key="t2_inst_n")
                    with st.spinner("載入法人資料…"):
                        inst = get_inst_nd(active_ticker, inst_n)
                    if inst:
                        st.caption(f"三大法人近 {inst_n} 個交易日買賣超（張，正值＝買超）")
                        i1, i2, i3, i4 = st.columns(4)
                        def _ifmt(v): return f"{v:+,}"
                        i1.metric("外資",     _ifmt(inst['外資']),     delta_color="normal")
                        i2.metric("投信",     _ifmt(inst['投信']),     delta_color="normal")
                        i3.metric("自營商",   _ifmt(inst['自營商']),   delta_color="normal")
                        i4.metric("三大合計", _ifmt(inst['三大合計']), delta_color="normal")
                    else:
                        st.caption("暫無法人資料（可能為假日或非交易日）")
                else:
                    st.caption("⚠️ 三大法人資料僅支援上市（TWSE）股票，此股為上櫃／興櫃，不提供法人資訊。")

                # 持股結構（外資 vs 本國）
                st.divider()
                st.caption("👥 持股比例（來源：鉅亨網，每日更新）")
                with st.spinner("載入持股比例…"):
                    own = fetch_ownership_ratio(active_ticker)
                if own:
                    ocols = st.columns(len(own))
                    for col, (k, v) in zip(ocols, own.items()):
                        col.metric(k, f"{v:.1f}%")
                    fig_own = go.Figure(go.Pie(
                        labels=list(own.keys()), values=list(own.values()),
                        hole=0.45, textinfo='label+percent',
                        marker=dict(colors=['#3498db', '#2ecc71']),
                        direction='clockwise',
                    ))
                    fig_own.update_layout(
                        title="持股比例分布",
                        height=280, margin=dict(t=40, b=5, l=5, r=5),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_own, width='stretch', key='own_pie_t2')
                    st.caption("⚠️ 本國持股含自然人＋法人，細項分拆需 TWSE 月報（目前無公開 JSON API）")
                else:
                    st.caption("持股比例資料暫不可用（ETF 或無資料個股）")

                if fund:
                    st.divider()
                    st.caption("📊 財務基本面（TTM / 最近年報）")
                    fcols = st.columns(len(fund))
                    for col, (key, val) in zip(fcols, fund.items()):
                        fsuffix = "%" if "率" in key else ""
                        col.metric(key, f"{val}{fsuffix}")

                # ── 現金流量 & ROE ─────────────────────────────────
                with st.spinner("載入現金流量資料…"):
                    cf_data = fetch_cashflow_roe(active_ticker)

                has_roe = cf_data.get('roe') is not None
                has_cf  = bool(cf_data.get('ocf'))
                if has_roe or has_cf:
                    st.divider()
                    st.caption("💰 現金流量 & 股東權益報酬率（年度）")

                    roe_col, chart_col = st.columns([1, 3])
                    with roe_col:
                        roe_val = cf_data.get('roe')
                        if roe_val is not None:
                            roe_delta = "優異 ✅" if roe_val >= 15 else ("正常" if roe_val >= 8 else "偏低 ⚠️")
                            st.metric("ROE（TTM）", f"{roe_val:.1f}%", delta=roe_delta,
                                      delta_color="off")
                        else:
                            st.metric("ROE（TTM）", "—")
                        st.caption("≥15% 優異｜8–15% 正常｜<8% 偏低")

                    with chart_col:
                        if has_cf:
                            ocf_d = cf_data['ocf']
                            fcf_d = cf_data.get('fcf', {})
                            years = sorted(ocf_d.keys())
                            ocf_v = [ocf_d[y] for y in years]
                            fcf_v = [fcf_d.get(y) for y in years]
                            has_fcf_data = any(v is not None for v in fcf_v)
                            fcf_plot = [v if v is not None else 0 for v in fcf_v]

                            def _yoy(vals):
                                result = [None]
                                for i in range(1, len(vals)):
                                    p, c = vals[i - 1], vals[i]
                                    if p is not None and c is not None and p != 0:
                                        result.append(round((c - p) / abs(p) * 100, 1))
                                    else:
                                        result.append(None)
                                return result

                            yoy_ocf = _yoy(ocf_v)
                            yoy_fcf = _yoy(fcf_plot) if has_fcf_data else []

                            # 主軸（億元）範圍：最大值 * 1.3 留空間給文字標籤
                            all_bar = [v for v in ocf_v + fcf_plot if v is not None]
                            bar_max = max(all_bar) if all_bar else 1
                            bar_min = min(all_bar) if all_bar else 0
                            y1_max = bar_max * 1.3 if bar_max > 0 else bar_max * 0.7
                            y1_min = bar_min * 1.3 if bar_min < 0 else 0

                            # 次軸（YoY%）範圍：上下各加 45% + 10 留空間給文字
                            all_yoy = [v for v in yoy_ocf + yoy_fcf if v is not None]
                            if all_yoy:
                                yoy_max = max(all_yoy)
                                yoy_min = min(all_yoy)
                                # 讓 YoY 折線浮在圖表上方 ~20% 區域：
                                # 頂端貼近資料最高點，底端拉低使總範圍 = 資料跨度的 5 倍
                                yoy_span = max(abs(yoy_max - yoy_min), 30)
                                y2_max = yoy_max + yoy_span * 0.6
                                y2_min = y2_max - yoy_span * 5
                            else:
                                y2_max, y2_min = 200, -600

                            fig_cf = make_subplots(specs=[[{"secondary_y": True}]])

                            fig_cf.add_trace(go.Bar(
                                name='OCF 營業現金流',
                                x=years, y=ocf_v,
                                marker_color=['#1a3a6b' if v >= 0 else '#e74c3c' for v in ocf_v],
                                text=[f"{v:.1f}" for v in ocf_v],
                                textposition='outside',
                                cliponaxis=False,
                            ), secondary_y=False)

                            if has_fcf_data:
                                fig_cf.add_trace(go.Bar(
                                    name='FCF 自由現金流',
                                    x=years, y=fcf_plot,
                                    marker_color=['#3498db' if v >= 0 else '#e67e22' for v in fcf_plot],
                                    text=[f"{v:.1f}" for v in fcf_plot],
                                    textposition='outside',
                                    cliponaxis=False,
                                ), secondary_y=False)

                            # OCF YoY：黃色，文字在上方
                            fig_cf.add_trace(go.Scatter(
                                name='OCF YoY%',
                                x=years, y=yoy_ocf,
                                mode='lines+markers+text',
                                line=dict(color='#f1c40f', width=2, dash='dot'),
                                marker=dict(size=7, color='#f1c40f'),
                                text=[f"{v:.1f}%" if v is not None else "" for v in yoy_ocf],
                                textposition='top center',
                                textfont=dict(color='#f1c40f', size=11),
                            ), secondary_y=True)

                            # FCF YoY：紅色，文字在下方（避免與 OCF YoY 重疊）
                            if has_fcf_data and yoy_fcf:
                                fig_cf.add_trace(go.Scatter(
                                    name='FCF YoY%',
                                    x=years, y=yoy_fcf,
                                    mode='lines+markers+text',
                                    line=dict(color='#e74c3c', width=2, dash='dot'),
                                    marker=dict(size=7, color='#e74c3c'),
                                    text=[f"{v:.1f}%" if v is not None else "" for v in yoy_fcf],
                                    textposition='bottom center',
                                    textfont=dict(color='#e74c3c', size=11),
                                ), secondary_y=True)

                            fig_cf.update_yaxes(title_text="億元",
                                                range=[y1_min, y1_max], secondary_y=False)
                            fig_cf.update_yaxes(title_text="年增率 %", ticksuffix="%",
                                                range=[y2_min, y2_max], secondary_y=True)
                            fig_cf.update_layout(
                                title=dict(text="年度現金流量（億元）｜右軸：年增率%",
                                           x=0, y=0.97, xanchor='left'),
                                barmode='group', height=360,
                                margin=dict(t=50, b=70, l=5, r=5),
                                legend=dict(orientation='h', yanchor='top', y=-0.18, x=0),
                            )
                            st.plotly_chart(fig_cf, width='stretch', key='cf_bar_t2')
                        else:
                            st.caption("現金流量資料不足（ETF 或 yfinance 無此股資料）")

                # ── 風險指標 ──────────────────────────────────────────
                risk = calc_risk_metrics(df, df_bench)
                if risk:
                    st.divider()
                    st.caption("⚠️ 風險指標（基於近期歷史資料）")
                    r1, r2, r3 = st.columns(3)
                    r1.metric("年化波動率", f"{risk['年化波動率']:.1f}%")
                    r2.metric("最大回撤",   f"{risk['最大回撤']:.1f}%")
                    if 'Beta' in risk:
                        b      = risk['Beta']
                        blabel = "高波動" if b > 1.2 else ("低波動" if b < 0.8 else "同步大盤")
                        r3.metric("Beta（對大盤）", f"{b:.2f}",
                                  delta=blabel, delta_color="off")

                # ── 月營收趨勢 ─────────────────────────────────────────
                with st.expander("📅 月營收趨勢（公開資訊觀測站）", expanded=False):
                    with st.spinner("載入月營收資料…"):
                        rev_df = fetch_monthly_revenue(active_ticker)
                    if rev_df is not None:
                        fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
                        fig_rev.add_trace(go.Bar(
                            x=rev_df['月份'], y=rev_df['當月(億)'],
                            name='當月營收(億)',
                            marker_color='#2980b9',
                            text=[f"{v:.1f}" for v in rev_df['當月(億)']],
                            textposition='outside', cliponaxis=False,
                        ), secondary_y=False)
                        yoy_vals = rev_df['YoY(%)'].tolist()
                        if any(v is not None for v in yoy_vals):
                            fig_rev.add_trace(go.Scatter(
                                x=rev_df['月份'], y=rev_df['YoY(%)'],
                                name='YoY(%)',
                                mode='lines+markers+text',
                                line=dict(color='#e74c3c', width=2, dash='dot'),
                                marker=dict(size=7, color='#e74c3c'),
                                text=[f"{v:.1f}%" if v is not None else ""
                                      for v in yoy_vals],
                                textposition='top center',
                                textfont=dict(color='#e74c3c', size=10),
                            ), secondary_y=True)
                        rev_max  = max(rev_df['當月(億)']) * 1.3
                        all_yoy  = [v for v in yoy_vals if v is not None]
                        if all_yoy:
                            yoy_span = max(abs(max(all_yoy) - min(all_yoy)), 20)
                            y2_max   = max(all_yoy) + yoy_span * 0.5
                            y2_min   = y2_max - yoy_span * 5
                        else:
                            y2_max, y2_min = 50, -150
                        fig_rev.update_yaxes(title_text="億元",
                                             range=[0, rev_max], secondary_y=False)
                        fig_rev.update_yaxes(title_text="YoY %",
                                             range=[y2_min, y2_max], secondary_y=True)
                        fig_rev.update_layout(
                            title=dict(text="月營收（億元）｜右軸：YoY%",
                                       x=0, y=0.97),
                            barmode='group', height=320,
                            margin=dict(t=50, b=60, l=5, r=5),
                            legend=dict(orientation='h', yanchor='top', y=-0.2, x=0),
                        )
                        st.plotly_chart(fig_rev, width='stretch', key='rev_chart_t2')
                    else:
                        st.caption("月營收資料無法取得（ETF、興櫃或 MOPS 暫時無資料）")

                st.plotly_chart(make_chart(df, f"{active_name} ({code_disp}) — 技術分析"), width='stretch', key='tech_chart_t2')

                # 訊號歷史勝率回測
                with st.expander("📊 訊號歷史勝率回測", expanded=False):
                    bt = backtest_signal(df)
                    if bt:
                        st.caption(f"基於近 {days} 天歷史資料，統計各訊號發出後的實際績效")
                        st.dataframe(pd.DataFrame(bt), width='stretch', hide_index=True)
                        st.caption("勝率 = 訊號後該天數內收盤價高於訊號當天的比例；樣本數少時參考價值有限")
                    else:
                        st.info("資料不足，無法計算回測結果")

    # ── Tab 3：自選清單 ───────────────────────────────────────────
    with tab3:
        if not st.session_state.watchlist:
            st.info("自選清單為空，請在「個股查詢」頁面點「加入自選」", icon="⭐")
        else:
            # ── 持倉總覽（需設定成本 + 張數才顯示）────────────────
            portfolio_data = []
            for ticker, wl_entry in st.session_state.watchlist.items():
                if not isinstance(wl_entry, dict):
                    continue
                cost = wl_entry.get('cost')
                lots = wl_entry.get('lots')
                if not cost or not lots:
                    continue
                df_p = fetch(ticker, 90)
                if df_p is None:
                    continue
                price    = float(df_p.iloc[-1]['Close'])
                invested = cost * lots * 1000
                current  = price * lots * 1000
                sec_name = next((s for s, stks in ALL_SECTORS.items()
                                 if ticker in stks.values()), '其他')
                portfolio_data.append({
                    '公司': wl_entry['name'], 'ticker': ticker,
                    '產業': sec_name, '張數': int(lots),
                    '成本': cost, '現價': round(price, 1),
                    '投入(元)': invested, '市值(元)': current,
                    '浮盈虧(元)': current - invested,
                    '浮盈虧%': (price / cost - 1) * 100,
                })

            if portfolio_data:
                st.subheader("💼 持倉總覽")
                total_inv = sum(d['投入(元)'] for d in portfolio_data)
                total_cur = sum(d['市值(元)'] for d in portfolio_data)
                total_pnl = total_cur - total_inv
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("總投入",   f"{total_inv/10000:.1f} 萬")
                m2.metric("目前市值", f"{total_cur/10000:.1f} 萬",
                          f"{(total_cur/total_inv-1)*100:+.1f}%" if total_inv else None)
                m3.metric("總浮盈/虧", f"{total_pnl/10000:+.1f} 萬")
                m4.metric("持倉檔數", f"{len(portfolio_data)} 支")

                # 浮盈/虧 Bar chart
                pf_df = pd.DataFrame(portfolio_data)
                fig_pnl = go.Figure(go.Bar(
                    x=pf_df['公司'], y=pf_df['浮盈虧%'],
                    marker_color=['#e74c3c' if v >= 0 else '#27ae60' for v in pf_df['浮盈虧%']],
                    text=[f"{v:+.1f}%" for v in pf_df['浮盈虧%']], textposition='auto',
                ))
                fig_pnl.update_layout(title="各持倉浮盈/虧（%）", height=280,
                                      margin=dict(t=40, b=5, l=5, r=5))
                st.plotly_chart(fig_pnl, width='stretch', key='pnl_bar_t3')

                # 產業佔比 Pie chart
                sec_alloc = pf_df.groupby('產業')['市值(元)'].sum()
                fig_pie = go.Figure(go.Pie(
                    labels=sec_alloc.index, values=sec_alloc.values, hole=0.4,
                ))
                fig_pie.update_layout(title="持倉產業分布（市值）", height=320,
                                      margin=dict(t=40, b=5, l=5, r=5))
                st.plotly_chart(fig_pie, width='stretch', key='alloc_pie_t3')
                st.divider()

            # ── 多股走勢比較 ────────────────────────────────────────
            st.subheader("📈 多股走勢比較")
            wl_tickers = list(st.session_state.watchlist.keys())
            wl_names   = [v['name'] if isinstance(v, dict) else v
                          for v in st.session_state.watchlist.values()]
            ticker_labels = [f"{nm}（{tk.replace('.TW','').replace('.TWO','')}）"
                             for nm, tk in zip(wl_names, wl_tickers)]
            sel_labels = st.multiselect(
                "選擇要比較的股票（2～4 支）", ticker_labels,
                max_selections=4, placeholder="點此選擇…", key="t3_cmp_sel"
            )
            if len(sel_labels) >= 2:
                cmp_period = st.radio("比較區間", ["1個月", "3個月", "6個月", "1年"],
                                      index=1, horizontal=True, key="t3_cmp_period")
                period_days = {"1個月": 30, "3個月": 90, "6個月": 180, "1年": 365}[cmp_period]
                fig_cmp = go.Figure()
                for lb in sel_labels:
                    idx  = ticker_labels.index(lb)
                    tk   = wl_tickers[idx]
                    nm   = wl_names[idx]
                    df_c = fetch(tk, period_days + 30)
                    if df_c is None or len(df_c) < 2:
                        continue
                    df_c = df_c.tail(period_days)
                    base = float(df_c['Close'].iloc[0])
                    norm = (df_c['Close'] / base * 100).round(2)
                    fig_cmp.add_trace(go.Scatter(
                        x=df_c.index, y=norm,
                        name=f"{nm}（{tk.replace('.TW','').replace('.TWO','')}）",
                        mode='lines', line=dict(width=2),
                    ))
                fig_cmp.update_layout(
                    title=f"近 {cmp_period} 標準化走勢（起始日 = 100）",
                    yaxis_title="相對表現（起始=100）",
                    height=380, margin=dict(t=40, b=5, l=5, r=5),
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                )
                st.plotly_chart(fig_cmp, width='stretch', key='cmp_chart_t3')
            elif len(sel_labels) == 1:
                st.info("請再多選一支以上的股票才能比較")

            # ── 持倉相關係數矩陣 ─────────────────────────────────────
            if len(wl_tickers) >= 2:
                st.markdown("##### 📊 持倉相關係數矩陣（近90日）")
                price_dict: dict[str, pd.Series] = {}
                for tk, nm in zip(wl_tickers, wl_names):
                    df_c = fetch(tk, 90)
                    if df_c is not None:
                        price_dict[nm] = df_c['Close']
                if len(price_dict) >= 2:
                    corr_df = pd.DataFrame(price_dict).corr().round(2)
                    n = len(corr_df)
                    fig_corr = go.Figure(go.Heatmap(
                        z=corr_df.values,
                        x=list(corr_df.columns),
                        y=list(corr_df.index),
                        colorscale='RdBu_r', zmid=0, zmin=-1, zmax=1,
                        text=corr_df.values,
                        texttemplate='%{text:.2f}',
                        textfont=dict(size=12),
                        hoverongaps=False,
                    ))
                    fig_corr.update_layout(
                        height=max(280, n * 80 + 100),
                        margin=dict(l=5, r=5, t=30, b=5),
                    )
                    st.plotly_chart(fig_corr, width='stretch', key='corr_heatmap_t3')
                    st.caption("1.0 = 完全同向；0 = 無相關；-1.0 = 完全反向。"
                               "理想分散持倉應避免相關係數 > 0.8。")
            st.divider()

            # 快速訊號總覽
            st.subheader("📊 快速訊號總覽")
            summary_rows  = []
            streak_alerts = []   # [(name, ticker, alerts_list)]
            for ticker, wl_entry in st.session_state.watchlist.items():
                name = wl_entry['name'] if isinstance(wl_entry, dict) else wl_entry
                df = fetch(ticker, days)
                if df is None or len(df) < 3:
                    continue
                last   = df.iloc[-1]
                price  = float(last['Close'])
                ret_1m = (price / float(df['Close'].iloc[-20]) - 1) * 100
                v      = signal_verdict(df)
                div    = fetch_dividend_info(ticker)
                cost   = wl_entry.get('cost')   if isinstance(wl_entry, dict) else None
                target = wl_entry.get('target') if isinstance(wl_entry, dict) else None
                pnl    = f"{(price/cost-1)*100:+.1f}%" if cost else "—"
                to_tgt = f"{(target-price)/price*100:+.1f}%" if target else "—"
                inst5  = get_inst_nd(ticker, 5)
                streaks = get_inst_streak(ticker, min_streak=3)
                if streaks:
                    streak_alerts.append((name, ticker.replace('.TW',''), streaks))
                summary_rows.append({
                    "公司": name, "代號": ticker.replace('.TW',''),
                    "股價": round(price, 1), "近1月%": f"{ret_1m:+.1f}%",
                    "RSI": round(float(last['RSI']), 1),
                    "KD_K": round(float(last['KD_K']), 1), "KD狀態": v['KD狀態'],
                    "MACD": v['MACD'], "均線": v['均線'],
                    "殖利率": f"{div['殖利率']:.1f}%" if div.get('殖利率') else "—",
                    "評估": v['評估'], "訊號": v['訊號'],
                    "外資(5日)": f"{inst5['外資']:+,}"     if inst5 else "—",
                    "投信(5日)": f"{inst5['投信']:+,}"     if inst5 else "—",
                    "三大(5日)": f"{inst5['三大合計']:+,}" if inst5 else "—",
                    "籌碼警示": "  ".join(streaks) if streaks else "—",
                    "浮盈/虧": pnl, "離目標%": to_tgt,
                })
            if summary_rows:
                st.dataframe(pd.DataFrame(summary_rows), width='stretch', hide_index=True)

            # 籌碼異動警示摘要
            if streak_alerts:
                st.subheader("🔔 籌碼異動警示")
                st.caption("法人連續 3 日以上同向操作，可能有大戶積極佈局或撤退跡象")
                for nm, code, alerts in streak_alerts:
                    badge = "  ".join(alerts)
                    st.markdown(f"**{nm}（{code}）** &nbsp; {badge}")
            st.divider()

            # 個別圖表 + 持倉設定
            for ticker, wl_entry in list(st.session_state.watchlist.items()):
                name = wl_entry['name'] if isinstance(wl_entry, dict) else wl_entry
                raw  = ticker.replace('.TW', '')
                col1, col2 = st.columns([9, 1])
                col1.subheader(f"{name}（{raw}）")
                if col2.button("移除", key=f"del_{ticker}"):
                    del st.session_state.watchlist[ticker]
                    save_watchlist(st.session_state.watchlist)
                    st.rerun()

                with st.expander("💰 設定成本 / 目標價 / 張數", expanded=False):
                    entry = wl_entry if isinstance(wl_entry, dict) else \
                            {"name": wl_entry, "target": None, "cost": None, "lots": None}
                    st.session_state.watchlist[ticker] = entry
                    ec1, ec2, ec3, ec4 = st.columns([2, 2, 2, 1])
                    new_cost   = ec1.number_input("成本價", value=float(entry.get('cost') or 0),
                                                  min_value=0.0, step=1.0, key=f"cost_{ticker}")
                    new_target = ec2.number_input("目標價", value=float(entry.get('target') or 0),
                                                  min_value=0.0, step=1.0, key=f"tgt_{ticker}")
                    new_lots   = ec3.number_input("持有張數", value=int(entry.get('lots') or 0),
                                                  min_value=0, step=1, key=f"lots_{ticker}")
                    ec4.write("")
                    ec4.write("")
                    if ec4.button("儲存", key=f"save_{ticker}"):
                        entry['cost']   = new_cost   if new_cost   > 0 else None
                        entry['target'] = new_target if new_target > 0 else None
                        entry['lots']   = new_lots   if new_lots   > 0 else None
                        save_watchlist(st.session_state.watchlist)
                        st.success("已儲存")

                with st.spinner(f"載入 {name}…"):
                    df = fetch(ticker, days)
                if df is not None:
                    st.plotly_chart(make_chart(df, f"{name} — 技術分析"), width='stretch', key=f"tech_wl_{ticker}")
                else:
                    st.warning(f"無法取得 {name} 資料")

    # ── Tab 4：籌碼面板 ───────────────────────────────────────────
    with tab4:
        st.caption("資料來源：TWSE T86（三大法人資料僅涵蓋上市股票；上櫃／興櫃自選股無法人資料）")

        # 自選股法人速覽
        if st.session_state.watchlist:
            wl_n = st.radio("觀察天數", [3, 5, 10], index=1, horizontal=True, key="t4_wl_n")
            if st.button("📋 掃描自選股法人動向", key="t4_wl_scan"):
                inst_rows  = []
                t4_streaks = []
                prog = st.progress(0, text="掃描中…")
                wl_items = list(st.session_state.watchlist.items())
                for i, (ticker, wl_entry) in enumerate(wl_items):
                    name = wl_entry['name'] if isinstance(wl_entry, dict) else wl_entry
                    prog.progress((i + 1) / len(wl_items), text=f"載入：{name}")
                    inst    = get_inst_nd(ticker, wl_n)
                    streaks = get_inst_streak(ticker, min_streak=3)
                    if streaks:
                        t4_streaks.append((name, ticker.replace('.TW',''), streaks))
                    inst_rows.append({
                        "公司":   name,
                        "代號":   ticker.replace('.TW', ''),
                        f"外資({wl_n}日)":     f"{inst['外資']:+,}"     if inst else "—",
                        f"投信({wl_n}日)":     f"{inst['投信']:+,}"     if inst else "—",
                        f"自營商({wl_n}日)":   f"{inst['自營商']:+,}"   if inst else "—",
                        f"三大合計({wl_n}日)": f"{inst['三大合計']:+,}" if inst else "—",
                        "籌碼警示": "  ".join(streaks) if streaks else "—",
                    })
                prog.empty()
                st.subheader(f"自選股法人近 {wl_n} 日買賣超（張）")
                st.dataframe(pd.DataFrame(inst_rows), width='stretch', hide_index=True)
                if t4_streaks:
                    st.subheader("🔔 連續買賣超警示")
                    for nm, code, alerts in t4_streaks:
                        st.markdown(f"**{nm}（{code}）** &nbsp; {'  '.join(alerts)}")
            st.divider()

        # 單股籌碼查詢
        c1, c2 = st.columns([4, 1])
        inst_code = c1.text_input("股票代號", placeholder="例如：2330",
                                  label_visibility='collapsed', key="t4_code")
        inst_btn  = c2.button("🏦 查詢籌碼", type="primary", key="t4_btn")

        if inst_btn and inst_code.strip():
            raw    = inst_code.strip()
            ticker = raw if '.' in raw else raw + '.TW'
            name   = TICKER_TO_NAME.get(ticker, raw)
            with st.spinner(f"載入 {name} 三大法人資料（近60日）…"):
                df_inst = fetch_institutional(ticker, 60)
            if df_inst is None:
                st.error(f"無法取得 {raw} 的法人資料（OTC 上櫃股票暫不支援）")
            else:
                st.subheader(f"{name}（{raw}）— 三大法人近60日買賣超")
                m1, m2, m3, m4 = st.columns(4)
                def _s10(col): return int(df_inst[col].tail(10).sum())
                m1.metric("外資近10日",    f"{_s10('外資'):+,} 張")
                m2.metric("投信近10日",    f"{_s10('投信'):+,} 張")
                m3.metric("自營商近10日",  f"{_s10('自營商'):+,} 張")
                m4.metric("三大合計近10日", f"{_s10('三大合計'):+,} 張")
                st.plotly_chart(  # TODO: add key='own_pie_t4'
                    make_institutional_chart(df_inst, f"{name} ({raw}) 三大法人買賣超"),
                    width='stretch',
                )
                with st.expander("📋 完整資料表", expanded=False):
                    df_show = df_inst.copy()
                    df_show['日期'] = df_show['日期'].dt.strftime('%Y-%m-%d')
                    st.dataframe(df_show, width='stretch', hide_index=True)

                # 持股比例（外資 vs 本國）
                st.divider()
                st.caption("👥 持股比例（來源：鉅亨網，每日更新）")
                with st.spinner("載入持股比例…"):
                    own_t4 = fetch_ownership_ratio(ticker)
                if own_t4:
                    ocols_t4 = st.columns(len(own_t4))
                    for col, (k, v) in zip(ocols_t4, own_t4.items()):
                        col.metric(k, f"{v:.1f}%")
                    fig_own_t4 = go.Figure(go.Pie(
                        labels=list(own_t4.keys()), values=list(own_t4.values()),
                        hole=0.45, textinfo='label+percent',
                        marker=dict(colors=['#3498db', '#2ecc71']),
                        direction='clockwise',
                    ))
                    fig_own_t4.update_layout(
                        title="持股比例分布",
                        height=280, margin=dict(t=40, b=5, l=5, r=5),
                        showlegend=False,
                    )
                    st.plotly_chart(fig_own_t4, width='stretch', key='own_pie_t4b')
                    st.caption("⚠️ 本國持股含自然人＋法人，細項分拆需 TWSE 月報（目前無公開 JSON API）")
                else:
                    st.caption("持股比例資料暫不可用（ETF 或無資料個股）")

                # ── 融資融券 ──────────────────────────────────────────
                st.divider()
                st.caption("💸 融資融券餘額（來源：TWSE，近60交易日，僅支援上市股票）")
                with st.spinner("載入融資融券資料…"):
                    mg_df = fetch_margin_history(ticker, 60)
                if mg_df is not None:
                    mg_last = mg_df.iloc[-1]
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("融資餘額(張)", f"{int(mg_last['融資餘額']):,}")
                    mc2.metric("融資增減(張)", f"{int(mg_last['融資增減']):+,}")
                    mc3.metric("融券餘額(張)", f"{int(mg_last['融券餘額']):,}")
                    mc4.metric("融券增減(張)", f"{int(mg_last['融券增減']):+,}")
                    fig_mg = make_subplots(
                        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=['融資餘額（張）', '融券餘額（張）'],
                    )
                    fig_mg.add_trace(go.Scatter(
                        x=mg_df['日期'], y=mg_df['融資餘額'],
                        mode='lines', line=dict(color='#e74c3c', width=2),
                        showlegend=False,
                    ), row=1, col=1)
                    fig_mg.add_trace(go.Scatter(
                        x=mg_df['日期'], y=mg_df['融券餘額'],
                        mode='lines', line=dict(color='#2980b9', width=2),
                        showlegend=False,
                    ), row=2, col=1)
                    fig_mg.update_layout(
                        height=400, hovermode='x unified',
                        margin=dict(l=5, r=5, t=50, b=5),
                    )
                    st.plotly_chart(fig_mg, width='stretch', key='margin_chart_t4')
                    with st.expander("📋 融資融券完整資料", expanded=False):
                        df_mg_show = mg_df.copy()
                        df_mg_show['日期'] = df_mg_show['日期'].dt.strftime('%Y-%m-%d')
                        st.dataframe(df_mg_show, width='stretch', hide_index=True)
                else:
                    st.caption("融資融券資料暫不可用（假日、非交易日或上櫃股票）")

    # ── Tab 5：條件選股 ───────────────────────────────────────────
    with tab5:
        st.subheader("設定篩選條件（所有選取條件同時成立才列出）")

        presets = st.multiselect(
            "預設條件",
            options=[
                "RSI 超賣（< 30）", "RSI 偏低（30-40）",
                "RSI 偏熱（> 65）", "RSI 超買（> 75）",
                "KD 超賣（K < 20）", "KD 超買（K > 80）",
                "KD 黃金交叉", "KD 死亡交叉",
                "MACD 多頭", "MACD 黃金交叉",
                "均線多頭排列",
                "近1月上漲（> 0%）", "近1月下跌（< 0%）",
            ],
            placeholder="點此選擇條件…",
        )

        col1, col2 = st.columns(2)
        with col1:
            use_rsi_range = st.checkbox("自訂 RSI 範圍")
            rsi_range = st.slider("RSI 範圍", 0, 100, (20, 50)) if use_rsi_range else None
        with col2:
            use_ret_range = st.checkbox("自訂近1月漲跌幅範圍 (%)")
            ret_range = st.slider("漲跌幅 (%)", -50, 100, (-10, 5)) if use_ret_range else None

        if not st.button("🎯 開始篩選", type="primary", key="t5_run"):
            st.info("選擇條件後點「開始篩選」掃描全市場股票", icon="🔍")
        elif not presets and not use_rsi_range and not use_ret_range:
            st.warning("請至少選擇一個篩選條件")
        else:
            cond = {"presets": presets,
                    "use_rsi_range": use_rsi_range, "rsi_range": rsi_range,
                    "use_ret_range": use_ret_range, "ret_range": ret_range}
            results = screen_stocks(cond, days)

            if not results:
                st.info("沒有符合條件的股票", icon="🔍")
            else:
                st.success(f"找到 {len(results)} 支符合條件的股票")
                snap_path = save_screen_snapshot(" | ".join(presets) or "自訂範圍", results)
                st.caption(f"📁 結果已存檔：{snap_path}")

                SCOLS = ["產業","公司","代號","股價","近1月%","RSI","KD_K","KD_D",
                         "MACD","均線","評估","訊號","熱度分數"]
                st.dataframe(
                    pd.DataFrame([{k: v for k, v in r.items() if k in SCOLS} for r in results],
                                 columns=SCOLS),
                    width='stretch', hide_index=True,
                )
                for r in results:
                    label = f"{r['公司']}（{r['代號']}）　RSI {r['RSI']}　{r['評估']}　{r['訊號']}"
                    with st.expander(label, expanded=False):
                        col1, col2 = st.columns([9, 1])
                        col1.write("")
                        if col2.button("⭐ 加入自選", key=f"screen_add_{r['代號']}"):
                            t = r['代號'] + '.TW'
                            st.session_state.watchlist[t] = {"name": r['公司'], "target": None,
                                                              "cost": None, "lots": None}
                            save_watchlist(st.session_state.watchlist)
                            st.success(f"已加入：{r['公司']}")
                        st.plotly_chart(make_chart(r["_df"], f"{r['公司']} ({r['代號']})"),
                                        width='stretch', key=f"screener_{r['代號']}")

        st.divider()
        st.subheader("📂 歷史篩選快照")
        if not os.path.exists(SNAPSHOT_DIR):
            st.caption("尚無歷史快照")
        else:
            snap_files = sorted(
                [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith('.json')], reverse=True)
            if not snap_files:
                st.caption("尚無歷史快照")
            else:
                selected = st.selectbox("選擇快照", snap_files,
                                        format_func=lambda f: f.replace('screen_','').replace('.json',''))
                if selected:
                    with open(os.path.join(SNAPSHOT_DIR, selected), 'r', encoding='utf-8') as f:
                        snap = json.load(f)
                    st.caption(f"篩選時間：{snap['date']}　條件：{snap['conditions']}　共 {snap['count']} 支")
                    st.dataframe(pd.DataFrame(snap['stocks']), width='stretch', hide_index=True)


    # ── Tab 6：即時行情 ───────────────────────────────────────────
    with tab6:
        # ── 自動更新控制（fragment 外；改完後整頁更新套用新間隔）──────────
        rc1, rc2, rc3 = st.columns([2, 2, 6])
        auto_on = rc1.toggle("自動更新", value=False, key="rt_auto_on")
        rt_sec  = rc2.select_slider("更新間隔", [10, 15, 20, 30, 60], value=15,
                                     format_func=lambda x: f"{x} 秒", key="rt_sec")
        _rt_interval = rt_sec if auto_on else None
        if auto_on:
            rc3.success(f"✅ 每 {rt_sec} 秒自動刷新（僅此頁籤，不影響其他頁面）")

        @st.fragment(run_every=_rt_interval)
        def _rt_body():
            st.caption(
                f"即時價：TWSE MIS API　技術指標：前一日收盤計算　"
                f"最後更新：{datetime.now().strftime('%H:%M:%S')}　"
                f"交易時間：09:00–13:30"
            )
    
            # ── 大盤指數 ──────────────────────────────────────────────
            st.markdown("##### 大盤概況")
            with st.spinner("載入指數…"):
                idx_rt = fetch_realtime_quotes(['t00.TW', 'o00.TWO'])
            idx_label = {'t00': '加權指數', 'o00': '櫃買指數'}
            if idx_rt:
                icols = st.columns(min(len(idx_rt), 4))
                for col, item in zip(icols, idx_rt):
                    code    = item['代號']
                    label   = idx_label.get(code, item['名稱'] or code)
                    price   = item['現價']
                    chg     = item['漲跌']
                    chg_pct = item['漲跌%']
                    if price:
                        delta_str = f"{chg:+.2f} ({chg_pct:+.2f}%)" if chg and chg_pct else None
                        col.metric(label, f"{price:,.2f}", delta_str)
                    else:
                        col.metric(label, "—")
            else:
                st.caption("指數資料暫時無法取得")
    
            st.divider()
    
            # ── 自選股資料建構（即時 + EOD 技術面合併）──────────────
            if not st.session_state.watchlist:
                st.info("自選清單為空，請先在「個股查詢」頁面加入股票", icon="⭐")
            else:
                wl_tickers_rt = list(st.session_state.watchlist.keys())
                wl_names_map  = {tk: (v['name'] if isinstance(v, dict) else v)
                                 for tk, v in st.session_state.watchlist.items()}
    
                with st.spinner("載入即時報價 & 技術面…"):
                    rt_data = fetch_realtime_quotes(wl_tickers_rt)
                rt_map = {item['代號']: item for item in rt_data}
    
                table_rows = []
                card_data  = []
    
                for ticker in wl_tickers_rt:
                    name = wl_names_map.get(ticker, ticker)
                    code = ticker.replace('.TWO', '').replace('.TW', '')
                    rt   = rt_map.get(code, {})
    
                    rt_price   = rt.get('現價')
                    rt_chg_pct = rt.get('漲跌%')
                    rt_chg     = rt.get('漲跌')
                    rt_vol     = rt.get('成交量(張)')
                    prev_close = rt.get('昨收')
    
                    df_eod = fetch(ticker, 90)
                    v_dict = signal_verdict(df_eod) if df_eod is not None else {}
    
                    rsi_val = kd_k_val = kd_d_val = None
                    bb_pos = dist_ma5 = dist_ma20 = vol_ratio = amplitude = None
                    bb_upper_v = bb_lower_v = bb_mid_v = None
                    bb_pos_label = "—"
    
                    if df_eod is not None and len(df_eod) > 0:
                        last_eod  = df_eod.iloc[-1]
                        eod_close = float(last_eod['Close'])
                        price_ref = rt_price if rt_price else eod_close
    
                        rsi_val  = round(float(last_eod['RSI']),  1) if not np.isnan(last_eod['RSI'])  else None
                        kd_k_val = round(float(last_eod['KD_K']), 1)
                        kd_d_val = round(float(last_eod['KD_D']), 1)
                        ma5      = float(last_eod['MA5'])  if not np.isnan(last_eod['MA5'])  else None
                        ma20     = float(last_eod['MA20']) if not np.isnan(last_eod['MA20']) else None
                        bb_upper_v = float(last_eod['BB_upper']) if not np.isnan(last_eod['BB_upper']) else None
                        bb_lower_v = float(last_eod['BB_lower']) if not np.isnan(last_eod['BB_lower']) else None
                        bb_mid_v   = float(last_eod['BB_mid'])   if not np.isnan(last_eod['BB_mid'])   else None
    
                        if ma5:
                            dist_ma5  = round((price_ref / ma5  - 1) * 100, 2)
                        if ma20:
                            dist_ma20 = round((price_ref / ma20 - 1) * 100, 2)
                        if bb_upper_v and bb_lower_v:
                            bb_range = bb_upper_v - bb_lower_v
                            if bb_range > 0:
                                bb_pos = round((price_ref - bb_lower_v) / bb_range * 100, 1)
                                if   bb_pos > 100: bb_pos_label = "⬆ 突破上軌"
                                elif bb_pos > 66:  bb_pos_label = "上段"
                                elif bb_pos > 33:  bb_pos_label = "中段"
                                elif bb_pos > 0:   bb_pos_label = "下段"
                                else:              bb_pos_label = "⬇ 跌破下軌"
    
                        avg_vol_5d = df_eod['Volume'].tail(5).mean()
                        if rt_vol and avg_vol_5d and avg_vol_5d > 0:
                            vol_ratio = round((rt_vol * 1000) / avg_vol_5d, 2)
    
                    if rt.get('最高') and rt.get('最低') and prev_close and prev_close > 0:
                        amplitude = round((rt['最高'] - rt['最低']) / prev_close * 100, 2)
    
                    # RSI / KD 帶狀態的標籤
                    def _rsi_label(v):
                        if v is None: return "—"
                        if v < 30:   return f"{v} ⬇超賣"
                        if v < 40:   return f"{v} 偏低"
                        if v > 75:   return f"{v} ⬆超買"
                        if v > 65:   return f"{v} 偏熱"
                        return str(v)
    
                    def _kd_label(k, d):
                        if k is None: return "—"
                        tag = "⬆超買" if k > 80 else "⬇超賣" if k < 20 else ""
                        return f"K{k}/D{d} {tag}".strip()
    
                    table_rows.append({
                        '代號':    code,
                        '名稱':    name,
                        '現價':    rt_price if rt_price else "—",
                        '漲跌%':   f"{rt_chg_pct:+.2f}%" if rt_chg_pct is not None else "—",
                        '振幅%':   f"{amplitude:.2f}%" if amplitude else "—",
                        '量比':    f"{vol_ratio:.1f}×" if vol_ratio else "—",
                        'RSI':     _rsi_label(rsi_val),
                        'KD':      _kd_label(kd_k_val, kd_d_val),
                        '均線':    v_dict.get('均線', '—'),
                        'MACD':    v_dict.get('MACD', '—'),
                        'BB位置':  bb_pos_label,
                        '距MA20%': f"{dist_ma20:+.2f}%" if dist_ma20 is not None else "—",
                        '評估':    v_dict.get('評估', '—'),
                    })
                    card_data.append({
                        'ticker': ticker, 'name': name, 'code': code,
                        'rt': rt, 'df_eod': df_eod, 'v_dict': v_dict,
                        'rsi_val': rsi_val, 'kd_k_val': kd_k_val, 'kd_d_val': kd_d_val,
                        'bb_pos': bb_pos, 'bb_pos_label': bb_pos_label,
                        'bb_upper': bb_upper_v, 'bb_lower': bb_lower_v, 'bb_mid': bb_mid_v,
                        'dist_ma5': dist_ma5 if 'dist_ma5' in dir() else None,
                        'dist_ma20': dist_ma20, 'vol_ratio': vol_ratio,
                        'amplitude': amplitude, 'rt_chg_pct': rt_chg_pct,
                        '_rsi_label': _rsi_label, '_kd_label': _kd_label,
                    })
    
                # ── 總覽表格 ──────────────────────────────────────────
                st.markdown("##### 自選股即時技術面總覽")
                if table_rows:
                    overview_df = pd.DataFrame(table_rows)
    
                    def _ov_style(val):
                        s = str(val)
                        if s.startswith('+') and ('%' in s or s[1:].replace('.','').isdigit()):
                            return 'color: #e74c3c; font-weight: bold'
                        if s.startswith('-') and ('%' in s or s[1:].replace('.','').isdigit()):
                            return 'color: #27ae60; font-weight: bold'
                        if '突破上軌' in s or '超買' in s:
                            return 'color: #e74c3c'
                        if '跌破下軌' in s or '超賣' in s:
                            return 'color: #27ae60; font-weight: bold'
                        if '🟢' in s:
                            return 'color: #27ae60'
                        if '🔴' in s:
                            return 'color: #e74c3c'
                        return ''
    
                    st.dataframe(
                        overview_df.style.map(
                            _ov_style,
                            subset=['漲跌%', '振幅%', 'RSI', 'KD', 'BB位置', '距MA20%', '評估'],
                        ),
                        width='stretch', hide_index=True,
                    )
                st.divider()
    
                # ── 個股詳細卡片 ──────────────────────────────────────
                st.markdown("##### 個股詳細卡片")
                for card in card_data:
                    ticker   = card['ticker']
                    name     = card['name']
                    code     = card['code']
                    rt       = card['rt']
                    df_eod   = card['df_eod']
                    v_dict   = card['v_dict']
                    rt_price = rt.get('現價')
                    rt_chg   = rt.get('漲跌')
                    chg_pct  = card['rt_chg_pct']
    
                    chg_icon  = "🔴" if (chg_pct or 0) >= 0 else "🟢"
                    price_str = f"{rt_price:.2f}" if rt_price else "非交易時間"
                    chg_str   = f" {chg_pct:+.2f}%" if chg_pct is not None else ""
                    verdict   = v_dict.get('評估', '')
                    exp_label = f"{name}（{code}）　{chg_icon} {price_str}{chg_str}　{verdict}"
    
                    with st.expander(exp_label, expanded=False):
                        # ── 報價區 ────────────────────────────────────
                        st.markdown("**📌 即時報價**")
                        q1, q2, q3, q4, q5, q6 = st.columns(6)
                        q1.metric("現價",       f"{rt_price:.2f}"      if rt_price           else "—",
                                  f"{rt_chg:+.2f}" if rt_chg else None)
                        q2.metric("漲跌%",      f"{chg_pct:+.2f}%"     if chg_pct is not None else "—")
                        q3.metric("開盤",       f"{rt['開盤']:.2f}"    if rt.get('開盤')     else "—")
                        q4.metric("最高 / 最低",
                                  (f"{rt['最高']:.2f} / {rt['最低']:.2f}"
                                   if rt.get('最高') and rt.get('最低') else "—"))
                        q5.metric("成交量(張)", f"{rt['成交量(張)']:,}" if rt.get('成交量(張)') else "—")
                        q6.metric("量比(5日均)", f"{card['vol_ratio']:.1f}×" if card['vol_ratio'] else "—")
    
                        if df_eod is not None:
                            # ── 技術指標區 ────────────────────────────
                            st.divider()
                            st.markdown("**📊 技術指標（基於前一日收盤）**")
                            t1, t2, t3, t4, t5, t6 = st.columns(6)
                            rsi_v  = card['rsi_val']
                            kd_k   = card['kd_k_val']
                            kd_d   = card['kd_d_val']
                            t1.metric("RSI(14)",   card['_rsi_label'](rsi_v))
                            t2.metric("KD_K / D",  f"{kd_k} / {kd_d}" if kd_k else "—")
                            t3.metric("KD狀態",    v_dict.get('KD狀態', '—'))
                            t4.metric("均線排列",  v_dict.get('均線', '—'))
                            t5.metric("MACD方向",  v_dict.get('MACD', '—'))
                            t6.metric("綜合評估",  v_dict.get('評估', '—'))
    
                            # ── 位置感知區 ────────────────────────────
                            st.divider()
                            st.markdown("**📍 價格位置感知**")
                            p1, p2, p3, p4 = st.columns(4)
                            p1.metric("距MA5",    f"{card['dist_ma5']:+.2f}%"  if card.get('dist_ma5')  is not None else "—")
                            p2.metric("距MA20",   f"{card['dist_ma20']:+.2f}%" if card['dist_ma20'] is not None else "—")
                            p3.metric("BB帶位置", card['bb_pos_label'])
                            p4.metric("今日振幅", f"{card['amplitude']:.2f}%"  if card['amplitude']     else "—")
    
                            bp = card['bb_pos']
                            if bp is not None and card['bb_upper'] and card['bb_lower']:
                                bp_clamped = max(0, min(100, bp))
                                st.caption(
                                    f"布林帶（0%=下軌 → 100%=上軌）：**{bp:.1f}%**　"
                                    f"下軌 {card['bb_lower']:.2f} ／ 中軌 {card['bb_mid']:.2f} ／ 上軌 {card['bb_upper']:.2f}"
                                )
                                st.progress(bp_clamped / 100)
    
                            # 訊號 & 警示橫幅
                            sig  = v_dict.get('訊號', '—')
                            warn = v_dict.get('警示', '—')
                            if sig  != '—': st.success(f"📈 訊號：{sig}")
                            if warn != '—': st.warning(f"⚠️ 警示：{warn}")
    
                            # ── 迷你走勢圖（近20日 + BB + 即時價橫線）──
                            df_mini     = df_eod.tail(20).copy()
                            up_color    = '#e74c3c' if (chg_pct or 0) >= 0 else '#27ae60'
                            fill_color  = ('rgba(231,76,60,0.08)' if (chg_pct or 0) >= 0
                                           else 'rgba(39,174,96,0.08)')
    
                            fig_spark = go.Figure()
                            # BB 帶底色
                            fig_spark.add_trace(go.Scatter(
                                x=df_mini.index, y=df_mini['BB_upper'],
                                mode='lines', line=dict(color='rgba(100,100,220,0.35)', width=1),
                                showlegend=False, hoverinfo='skip',
                            ))
                            fig_spark.add_trace(go.Scatter(
                                x=df_mini.index, y=df_mini['BB_lower'],
                                mode='lines', line=dict(color='rgba(100,100,220,0.35)', width=1),
                                fill='tonexty', fillcolor='rgba(100,100,220,0.06)',
                                showlegend=False, hoverinfo='skip',
                            ))
                            # MA20
                            fig_spark.add_trace(go.Scatter(
                                x=df_mini.index, y=df_mini['MA20'],
                                mode='lines', line=dict(color='#e67e22', width=1.5, dash='dot'),
                                name='MA20',
                                hovertemplate='MA20 %{y:.2f}<extra></extra>',
                            ))
                            # MA5
                            fig_spark.add_trace(go.Scatter(
                                x=df_mini.index, y=df_mini['MA5'],
                                mode='lines', line=dict(color='#3498db', width=1.5, dash='dash'),
                                name='MA5',
                                hovertemplate='MA5 %{y:.2f}<extra></extra>',
                            ))
                            # 收盤走勢（主線）
                            fig_spark.add_trace(go.Scatter(
                                x=df_mini.index, y=df_mini['Close'],
                                mode='lines+markers',
                                line=dict(color=up_color, width=2.5),
                                marker=dict(size=4, color=up_color),
                                fill='tozeroy', fillcolor=fill_color,
                                name='收盤',
                                hovertemplate='%{x|%m/%d}<br>收盤 %{y:.2f}<extra></extra>',
                            ))
                            # 即時價橫線
                            if rt_price:
                                fig_spark.add_hline(
                                    y=rt_price, line_dash='dash',
                                    line_color='#f39c12', line_width=1.5, opacity=0.9,
                                    annotation_text=f"  即時 {rt_price:.2f}",
                                    annotation_position="right",
                                    annotation_font=dict(size=11, color='#f39c12'),
                                )
                            fig_spark.update_layout(
                                title=dict(text=f"{name} — 近20日走勢（含布林帶 & MA）",
                                           font=dict(size=13)),
                                height=230,
                                margin=dict(l=5, r=90, t=35, b=5),
                                xaxis=dict(showgrid=False, tickformat='%m/%d',
                                           tickfont=dict(size=10)),
                                yaxis=dict(showgrid=True, gridcolor='rgba(0,0,0,0.06)'),
                                showlegend=True,
                                legend=dict(orientation='h', y=1.12, x=0, font=dict(size=10)),
                                plot_bgcolor='rgba(0,0,0,0)',
                                hovermode='x unified',
                            )
                            st.plotly_chart(fig_spark, width='stretch', key=f"spark_{card['code']}")
    

        _rt_body()
        # ── 自訂即時查詢 ──────────────────────────────────────────
        st.divider()
        st.markdown("##### 快速查詢其他股票即時價")
        qc1, qc2 = st.columns([4, 1])
        rt_input = qc1.text_input(
            "代號", label_visibility='collapsed',
            placeholder="輸入代號，例如：2330,2317,0050（逗號分隔）",
            key="rt_custom_input",
        )
        rt_query_btn = qc2.button("查詢", type="primary", key="rt_custom_btn")
        if rt_query_btn and rt_input.strip():
            raw_codes = [c.strip() for c in rt_input.replace('，', ',').split(',') if c.strip()]
            custom_tickers = []
            for c in raw_codes:
                if '.' in c:
                    custom_tickers.append(c)
                elif c in all_stocks:
                    custom_tickers.append(c + all_stocks[c][1])
                else:
                    custom_tickers.append(c + '.TW')
            with st.spinner("查詢中…"):
                custom_rt = fetch_realtime_quotes(custom_tickers)
            if custom_rt:
                for i in range(0, len(custom_rt), 4):
                    chunk = custom_rt[i:i + 4]
                    cols  = st.columns(4)
                    for col, item in zip(cols, chunk):
                        price   = item['現價']
                        chg_pct = item['漲跌%']
                        chg     = item['漲跌']
                        iname   = item['名稱'] or item['代號']
                        if price:
                            delta_str = (f"{chg:+.2f} ({chg_pct:+.2f}%)"
                                         if chg is not None and chg_pct is not None else None)
                            col.metric(f"{iname}（{item['代號']}）", f"{price:.2f}", delta_str)
                        else:
                            col.metric(f"{iname}（{item['代號']}）", "無資料")
            else:
                st.warning("查無資料，請確認代號是否正確")


# ── 執行入口 ──────────────────────────────────────────────────────
def _is_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if _is_streamlit():
    _run_app()
elif __name__ == '__main__':
    import subprocess, sys, webbrowser, threading, time
    threading.Thread(
        target=lambda: (time.sleep(4), webbrowser.open('http://localhost:8501')),
        daemon=True,
    ).start()
    subprocess.run([
        sys.executable, '-m', 'streamlit', 'run', __file__,
        '--server.headless', 'true',
        '--browser.gatherUsageStats', 'false',
    ])
