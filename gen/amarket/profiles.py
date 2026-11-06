"""profiles.py — 香港／日本／韓國大盤報告：每個市場嘅標的、截圖、時區、收市時間（2026-11-06 用戶要求三個市場各出一份）。
截圖由 screencapture `config/charts_asia.json` 截（Drive 大盤根資料夾 HK／JP／KR 子資料夾＋DD mon YYYY），兩邊改要同步。
- core：報告主角（等同美股 SPY／QQQ／IWM）＝追蹤主要指數嘅 ETF（有真實成交量，均線、量比、派發日用佢計）；idx＝對應指數截圖名。
- index：Yahoo 有日線嘅指數（只用嚟核對收市同升跌，指數成交量唔用）。
- sectors：板塊／權重股（等同美股 11 個 SPDR 板塊），用嚟睇相對強弱同輪動。
- t＝jlaw-report /api/ohlcv 代號（港股 5 位數字、日股 4 位、韓股 6 位）；shot＝截圖檔名入面嘅名（NN_<shot>_Daily.png）。
- chart_only：Yahoo 冇（或唔用）嘅項目，只可以讀截圖，報告標「圖表讀數」。"""

PROFILES = {
    'hk': dict(
        key='hk', name='香港', title='香港大盤分析', calendar='XHKG', tz='Asia/Hong_Kong', tzname='HKT', close='16:10', unit='港元',
        drive_sub='HK', lb=True,
        core=[dict(t='02800', shot='2800', name='盈富基金', idx='HSI', idx_name='恒生指數'),
              dict(t='03033', shot='3033', name='南方恒生科技 ETF', idx='HSTECH', idx_name='恒生科技指數'),
              dict(t='02828', shot='2828', name='恒生中國企業 ETF', idx='HSCEI', idx_name='恒生中國企業指數')],
        index=[dict(y='^HSI', shot='HSI', name='恒生指數'), dict(y='^HSCE', shot='HSCEI', name='恒生中國企業指數')],
        sectors=[dict(t='00700', shot='0700', name='騰訊（互聯網）'), dict(t='09988', shot='9988', name='阿里巴巴（電商／雲）'),
                 dict(t='03690', shot='3690', name='美團（消費平台）'), dict(t='00005', shot='0005', name='匯豐（銀行）'),
                 dict(t='01299', shot='1299', name='友邦（保險）'), dict(t='00883', shot='0883', name='中海油（能源）')],
        vol=dict(shot='VHSI', name='恒指波幅指數 VHSI'),
        macro=[dict(shot='USDCNH', name='美元兌離岸人民幣 USDCNH')],
        chart_only=['HSTECH', 'VHSI', 'USDCNH'],
        shots=['HSI', '2800', 'HSTECH', '3033', 'HSCEI', '2828', 'VHSI', '0700', '9988', '3690', '0005', '1299', '0883', 'USDCNH'],
        breadth_note='港股升跌家數、高於 50／200 日線比例、新高新低：截圖冇，Yahoo 冇；要上網核實（例如港交所／財經網站收市統計），搵唔到就標缺。南向資金（港股通）同理。',
    ),
    'jp': dict(
        key='jp', name='日本', title='日本大盤分析', calendar='XTKS', tz='Asia/Tokyo', tzname='JST', close='15:30', unit='日圓',
        drive_sub='JP', lb=False,
        core=[dict(t='1321', shot='1321', name='日經 225 ETF（Nomura）', idx='NI225', idx_name='日經 225'),
              dict(t='1306', shot='1306', name='TOPIX ETF（Nomura）', idx='TOPIX', idx_name='東證股價指數 TOPIX')],
        index=[dict(y='^N225', shot='NI225', name='日經 225')],
        sectors=[dict(t='2644', shot='2644', name='Global X 日本半導體 ETF'), dict(t='1615', shot='1615', name='TOPIX 銀行 ETF'),
                 dict(t='1622', shot='1622', name='TOPIX-17 汽車運輸 ETF'), dict(t='1625', shot='1625', name='TOPIX-17 電機精密 ETF'),
                 dict(t='7203', shot='7203', name='豐田汽車'), dict(t='8035', shot='8035', name='東京電子'),
                 dict(t='9984', shot='9984', name='軟銀集團'), dict(t='8306', shot='8306', name='三菱日聯金融')],
        vol=None,
        macro=[dict(shot='USDJPY', name='美元兌日圓 USDJPY'), dict(shot='JP10Y', name='日本 10 年國債孳息 JP10Y'),
               dict(shot='NK225F', name='日經 225 期貨（OSE，含夜盤）')],
        chart_only=['TOPIX', 'NK225F', 'USDJPY', 'JP10Y'],
        shots=['NI225', '1321', 'TOPIX', '1306', 'NK225F', 'USDJPY', 'JP10Y', '2644', '1615', '1622', '1625', '7203', '8035', '9984', '8306'],
        breadth_note='東證升跌家數、騰落比率、新高新低：截圖冇，Yahoo 冇；日經平均波動指數（Nikkei VI）TradingView 冇。要上網核實，搵唔到就標缺。外資買賣（每週公佈）同理。',
    ),
    'kr': dict(
        key='kr', name='韓國', title='韓國大盤分析', calendar='XKRX', tz='Asia/Seoul', tzname='KST', close='15:30', unit='韓圜',
        drive_sub='KR', lb=False,
        core=[dict(t='069500', shot='069500', name='KODEX 200 ETF', idx='KOSPI', idx_name='KOSPI 綜合指數'),
              dict(t='229200', shot='229200', name='KODEX KOSDAQ150 ETF', idx='KOSDAQ', idx_name='KOSDAQ 綜合指數')],
        index=[dict(y='^KS11', shot='KOSPI', name='KOSPI 綜合指數'), dict(y='^KQ11', shot='KOSDAQ', name='KOSDAQ 綜合指數')],
        sectors=[dict(t='091160', shot='091160', name='KODEX 半導體 ETF'), dict(t='091170', shot='091170', name='KODEX 銀行 ETF'),
                 dict(t='091180', shot='091180', name='KODEX 汽車 ETF'), dict(t='005930', shot='005930', name='三星電子'),
                 dict(t='000660', shot='000660', name='SK 海力士')],
        vol=None,
        macro=[dict(shot='USDKRW', name='美元兌韓圜 USDKRW'), dict(shot='KR10Y', name='韓國 10 年國債孳息 KR10Y')],
        chart_only=['USDKRW', 'KR10Y'],
        shots=['KOSPI', '069500', 'KOSDAQ', '229200', 'USDKRW', 'KR10Y', '091160', '091170', '091180', '005930', '000660'],
        breadth_note='KOSPI／KOSDAQ 升跌家數、新高新低、VKOSPI：截圖冇，Yahoo 冇，TradingView 搵唔到 VKOSPI。要上網核實，搵唔到就標缺。外資淨買賣同理。',
    ),
}
