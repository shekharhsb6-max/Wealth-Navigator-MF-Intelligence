const MFAPI_BASE = 'https://api.mfapi.in';

function doGet() {
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('Wealth Navigator — MF Intelligence')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function setupMFSystem() {
  const ss = SpreadsheetApp.getActive();
  const schemas = {
    MF_MASTER: ['Scheme_Code','Scheme_Name','Fund_House','Scheme_Type','Scheme_Category','ISIN_Growth','ISIN_Dividend','Plan','Option','Active','Updated_At'],
    MF_LATEST: ['Scheme_Code','Scheme_Name','Latest_NAV','NAV_Date','Updated_At'],
    MF_NAV: ['Scheme_Code','Date','NAV'],
    MF_ANALYTICS: ['Scheme_Code','Scheme_Name','Latest_NAV','NAV_Date','Return_1M','Return_3M','Return_6M','Return_1Y','CAGR_3Y','CAGR_5Y','SMA20','SMA50','SMA200','Max_Drawdown','Trend','Updated_At'],
    MF_WATCHLIST: ['Scheme_Code','Scheme_Name','Notes','Added_At'],
    MF_TRANSACTIONS: ['Date','Owner','Scheme_Code','Transaction','Units','NAV','Amount','Folio','Notes'],
    MF_PORTFOLIO: ['Owner','Scheme_Code','Scheme_Name','Units','Average_NAV','Invested_Value','Current_NAV','Current_Value','P_L','P_L_Percent','Updated_At'],
    MF_SETTINGS: ['Key','Value']
  };

  Object.keys(schemas).forEach(name => {
    let sh = ss.getSheetByName(name);
    if (!sh) sh = ss.insertSheet(name);
    sh.getRange(1,1,1,schemas[name].length).setValues([schemas[name]]);
  });
  return 'MF system sheets created.';
}

function mfFetch_(path, params) {
  let url = MFAPI_BASE + path;
  if (params) {
    const q = Object.keys(params)
      .filter(k => params[k] !== '' && params[k] != null)
      .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k]))
      .join('&');
    if (q) url += '?' + q;
  }

  const response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    headers: {'User-Agent': 'WealthNavigatorPro/1.0'}
  });

  const code = response.getResponseCode();
  if (code === 429) throw new Error('MFAPI rate limit reached. Wait and retry.');
  if (code < 200 || code >= 300) throw new Error('MFAPI HTTP ' + code + ': ' + response.getContentText());

  return JSON.parse(response.getContentText());
}

function searchFunds(query) {
  if (!query || query.trim().length < 2) return [];
  const data = mfFetch_('/mf/search', {q: query.trim()});
  if (Array.isArray(data)) return data;
  return data.data || data.results || data.schemes || [];
}

function getScheme(schemeCode) {
  return mfFetch_('/mf/' + encodeURIComponent(schemeCode));
}

function getLatest(schemeCode) {
  return mfFetch_('/mf/' + encodeURIComponent(schemeCode) + '/latest');
}

function syncScheme(schemeCode) {
  const data = getScheme(schemeCode);
  const rows = cleanHistory_(data.data || []);
  if (!rows.length) throw new Error('No NAV history returned.');

  const meta = data.meta || {};
  const now = new Date();

  const master = SpreadsheetApp.getActive().getSheetByName('MF_MASTER');
  upsertRow_(master, 1, String(schemeCode), [
    String(schemeCode),
    meta.scheme_name || '',
    meta.fund_house || '',
    meta.scheme_type || '',
    meta.scheme_category || '',
    meta.isin_growth || '',
    meta.isin_dividend || '',
    '', '', true, now
  ]);

  const latest = rows[rows.length - 1];
  const latestSheet = SpreadsheetApp.getActive().getSheetByName('MF_LATEST');
  upsertRow_(latestSheet, 1, String(schemeCode), [
    String(schemeCode), meta.scheme_name || '', latest.nav, latest.date, now
  ]);

  writeNavRows_(String(schemeCode), rows);

  const metrics = analyze_(rows);
  const analytics = SpreadsheetApp.getActive().getSheetByName('MF_ANALYTICS');
  upsertRow_(analytics, 1, String(schemeCode), [
    String(schemeCode), meta.scheme_name || '', metrics.latest_nav,
    metrics.nav_date, metrics.return_1m, metrics.return_3m,
    metrics.return_6m, metrics.return_1y, metrics.cagr_3y,
    metrics.cagr_5y, metrics.sma20, metrics.sma50, metrics.sma200,
    metrics.max_drawdown, metrics.trend, now
  ]);

  return {meta: meta, metrics: metrics, points: rows.slice(-365)};
}

function cleanHistory_(raw) {
  const map = {};
  (raw || []).forEach(r => {
    const d = parseDate_(r.date);
    const nav = Number(r.nav);
    if (d && isFinite(nav)) map[Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd')] = nav;
  });
  return Object.keys(map).sort().map(k => ({date: k, nav: map[k]}));
}

function parseDate_(s) {
  if (!s) return null;
  const p = String(s).split('-');
  if (p.length === 3 && p[0].length <= 2) return new Date(Number(p[2]), Number(p[1])-1, Number(p[0]));
  return new Date(s);
}

function returnDays_(rows, days) {
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const target = new Date(last.date);
  target.setDate(target.getDate() - days);
  let old = null;
  for (let i = 0; i < rows.length; i++) {
    if (new Date(rows[i].date) <= target) old = rows[i];
    else break;
  }
  return old && old.nav > 0 ? (last.nav / old.nav - 1) * 100 : null;
}

function cagr_(rows, years) {
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const target = new Date(last.date);
  target.setDate(target.getDate() - Math.round(years * 365.25));
  let old = null;
  rows.forEach(r => { if (new Date(r.date) <= target) old = r; });
  if (!old || old.nav <= 0) return null;
  const actualYears = (new Date(last.date) - new Date(old.date)) / (365.25 * 24 * 3600 * 1000);
  return actualYears > 0 ? (Math.pow(last.nav / old.nav, 1 / actualYears) - 1) * 100 : null;
}

function sma_(rows, n) {
  if (rows.length < n) return null;
  return rows.slice(-n).reduce((a,r) => a + r.nav, 0) / n;
}

function maxDrawdown_(rows) {
  let peak = rows[0].nav, worst = 0;
  rows.forEach(r => {
    peak = Math.max(peak, r.nav);
    if (peak > 0) worst = Math.min(worst, (r.nav / peak - 1) * 100);
  });
  return worst;
}

function analyze_(rows) {
  const latest = rows[rows.length - 1].nav;
  const s20 = sma_(rows,20), s50 = sma_(rows,50), s200 = sma_(rows,200);
  let trend = 'Insufficient history';
  if (s200 != null) {
    if (latest > s50 && s50 > s200) trend = 'Above SMA50 & SMA200';
    else if (latest < s50 && s50 < s200) trend = 'Below SMA50 & SMA200';
    else trend = 'Mixed';
  }
  return {
    latest_nav: latest,
    nav_date: rows[rows.length - 1].date,
    return_1m: returnDays_(rows,30),
    return_3m: returnDays_(rows,90),
    return_6m: returnDays_(rows,182),
    return_1y: returnDays_(rows,365),
    cagr_3y: cagr_(rows,3),
    cagr_5y: cagr_(rows,5),
    sma20: s20, sma50: s50, sma200: s200,
    max_drawdown: maxDrawdown_(rows),
    trend: trend
  };
}

function writeNavRows_(schemeCode, rows) {
  const sh = SpreadsheetApp.getActive().getSheetByName('MF_NAV');
  const values = sh.getDataRange().getValues();
  const existing = {};
  for (let i=1;i<values.length;i++) {
    existing[String(values[i][0]) + '|' + String(values[i][1])] = true;
  }
  const out = [];
  rows.forEach(r => {
    const key = schemeCode + '|' + r.date;
    if (!existing[key]) out.push([schemeCode, r.date, r.nav]);
  });
  if (out.length) sh.getRange(sh.getLastRow()+1,1,out.length,3).setValues(out);
}

function upsertRow_(sh, keyCol, key, row) {
  const last = sh.getLastRow();
  if (last > 1) {
    const values = sh.getRange(2,keyCol,last-1,1).getValues();
    for (let i=0;i<values.length;i++) {
      if (String(values[i][0]) === String(key)) {
        sh.getRange(i+2,1,1,row.length).setValues([row]);
        return;
      }
    }
  }
  sh.getRange(sh.getLastRow()+1,1,1,row.length).setValues([row]);
}

function addToWatchlist(schemeCode, schemeName, notes) {
  const sh = SpreadsheetApp.getActive().getSheetByName('MF_WATCHLIST');
  sh.appendRow([schemeCode, schemeName, notes || '', new Date()]);
  return true;
}

function getWatchlist() {
  const sh = SpreadsheetApp.getActive().getSheetByName('MF_WATCHLIST');
  return sh.getDataRange().getDisplayValues().slice(1);
}

function simulateSIP(schemeCode, monthlyAmount) {
  const data = getScheme(schemeCode);
  const rows = cleanHistory_(data.data || []);
  const amount = Number(monthlyAmount);
  if (!rows.length || !amount || amount <= 0) throw new Error('Invalid SIP inputs.');

  const months = [];
  const seen = {};
  rows.forEach(r => {
    const key = r.date.slice(0,7);
    if (!seen[key]) { seen[key] = true; months.push(r); }
  });

  let invested = 0, units = 0;
  months.forEach(r => {
    invested += amount;
    units += amount / r.nav;
  });

  const currentValue = units * rows[rows.length-1].nav;
  const gain = currentValue - invested;

  return {
    months: months.length,
    invested: invested,
    units: units,
    current_value: currentValue,
    gain: gain,
    gain_percent: invested ? gain/invested*100 : null
  };
}

