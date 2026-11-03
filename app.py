"""SportLab 3.1: independent match analysis, not a bookmaker."""
import difflib, io, math, re, unicodedata, html
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='SportLab 4.6 | Analiza sportowa', page_icon='📈', layout='wide')
st.markdown('''<style>
:root{color-scheme:dark} .stApp{background:radial-gradient(circle at 80% 0%,#182a46 0,#0a101d 46%,#090e19 100%);color:#eef3fb}
.block-container{max-width:1160px;padding-top:1.7rem;padding-bottom:4rem}
h1,h2,h3{letter-spacing:-.025em} h1{font-size:2.65rem!important}
[data-testid="stMetric"]{background:#17243a;border:1px solid #2b3c56;border-radius:15px;padding:17px}
[data-testid="stMetricValue"]{color:#f3f7ff} [data-testid="stMetricLabel"]{color:#a7bad5}
div.stButton>button[kind="primary"]{background:#20bf88;border:0;border-radius:12px;padding:.65rem 1.2rem}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
.sl-hero{border:1px solid #30435d;border-radius:22px;padding:22px 25px;background:linear-gradient(115deg,#162742,#111b2e);margin:8px 0 22px}
.sl-kicker{font-size:12px;letter-spacing:2px;color:#69e5b7;font-weight:700}
.sl-sub{color:#a8b8cf;font-size:14px;margin-top:7px}
.sl-card{background:#142338;border:1px solid #30425b;border-radius:17px;padding:19px;margin:10px 0}
.sl-main{background:linear-gradient(125deg,#103e34,#122e32);border-color:#276c59}
.sl-tag{font-size:12px;letter-spacing:1.4px;font-weight:700;color:#76e3b4}
.sl-name{font-size:24px;font-weight:750;line-height:1.3;margin:8px 0 13px}
.sl-explain{font-size:14px;color:#d2e0ed;line-height:1.7;margin-top:10px}
.sl-note{color:#9fb0c8;font-size:12px}
.sl-grid{display:flex;gap:16px;flex-wrap:wrap}.sl-stat{min-width:120px;flex:1}
.sl-value{font-size:27px;font-weight:800}.sl-label{font-size:12px;color:#b3c8d9}
.stChatMessage{background:#142338;border:1px solid #2a4059;border-radius:16px;margin:10px 0} [data-testid='stChatInput']{border:1px solid #2c6c60;border-radius:12px} .sl-pill{display:inline-block;border:1px solid #47627b;border-radius:30px;padding:5px 12px;color:#bed0e4;font-size:12px}
</style>''',unsafe_allow_html=True)

st.markdown('''
<style>
.block-container{max-width:1250px;padding-top:2.1rem}
.stApp{background:radial-gradient(ellipse at 90% 5%,rgba(18,104,98,.22),transparent 37%),linear-gradient(145deg,#070d18 0%,#0b1422 55%,#090e19 100%)}
.sl-newhero{position:relative;overflow:hidden;min-height:280px;padding:40px 46px;border:1px solid #2c5359;background:radial-gradient(circle at 92% 24%,rgba(44,208,163,.19),transparent 36%),linear-gradient(115deg,#122c32,#0e1b30 70%);box-shadow:0 24px 70px #0004}
.sl-newhero:after{content:'◉';position:absolute;right:5%;top:-95px;font-size:340px;color:#43e0b3;opacity:.07;pointer-events:none}
.sl-newhero h1{font-size:clamp(2rem,4vw,3.7rem)!important;line-height:1.07;letter-spacing:-.055em;margin:18px 0!important}
.sl-newhero h1 span{color:#58e6bb}
.sl-newhero p{color:#c3d4df;font-size:1rem;max-width:620px}
.sl-hero-tags{display:flex;flex-wrap:wrap;gap:9px;margin-top:26px}
.sl-hero-tags span{font-size:11px;font-weight:800;letter-spacing:1px;color:#9ff3d9;border:1px solid #37776b;background:#163a3a;border-radius:30px;padding:9px 12px}
.sl-feature-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0 30px}
.sl-feature-row>div{border:1px solid #263d50;background:#101e2e;border-radius:15px;padding:16px 20px}
.sl-feature-row b{display:block;font-size:12px;letter-spacing:1.2px;color:#55e5b8}
.sl-feature-row small{display:block;color:#b9cbd8;margin-top:6px}
[data-testid="stSelectbox"], [data-testid="stDateInput"]{border-radius:14px}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:18px}
.stChatMessage{box-shadow:0 6px 24px #0002}
@media(max-width:700px){.sl-newhero{padding:26px 22px;min-height:0}.sl-feature-row{grid-template-columns:1fr}.sl-feature-row>div{padding:12px 16px}}
</style>
''',unsafe_allow_html=True)
st.markdown("""<style>
/* SportLab 4.6 — actual dashboard layout, not a static mockup */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#071524,#091321)!important;border-right:1px solid #21354d}
[data-testid="stSidebar"] .stMarkdown p{color:#cad9ed}
.block-container{max-width:1600px!important;padding-top:1rem!important}
.stApp{background:radial-gradient(ellipse at 90% 0%,#103448 0%,transparent 45%),linear-gradient(155deg,#050d19,#0a1527 68%,#081322)!important}
.sl-topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border:1px solid #263e56;border-radius:17px;background:#0c1a2b;margin:4px 0 22px;gap:10px}
.sl-brand{font-size:25px;font-weight:900;color:#25e69b}.sl-brand span,.sl-side-brand span{color:#fff}.sl-brand small{font-size:11px;color:#8da9c2}
.sl-topnote{font-size:12px;letter-spacing:1px;color:#9db3ca}.sl-live{border:1px solid #1f8e6c;border-radius:50px;padding:8px 12px;color:#38e3a2;font-size:11px;font-weight:800}
.sl-side-brand{font-size:28px;font-weight:900;color:#20e79c;margin:12px 0 26px}.sl-side-label{font-size:10px;letter-spacing:2px;color:#6486a8}
.sl-page-title{display:flex;align-items:center;justify-content:space-between;gap:15px;margin:12px 0 22px}.sl-page-title h1{font-size:clamp(2rem,3vw,3rem)!important;margin:7px 0!important;color:#fff}.sl-page-title h1 em{font-style:normal;color:#29e8a6}.sl-page-title p{color:#a2b9d1;margin:0}
.sl-eyebrow{font-size:11px;letter-spacing:2px;color:#31e5a9;font-weight:800}.sl-version{font-size:11px;text-align:right;color:#789bb8}.sl-version strong{color:#3ce3b1}
.sl-match-label{font-size:12px;font-weight:800;letter-spacing:1px;color:#b6cde2;text-align:center;background:#10243a;border:1px solid #2d4a65;border-radius:13px;padding:13px;margin:10px 0 15px}
.sl-vs{text-align:center;font-size:31px;font-weight:900;color:#29e7ab;text-shadow:0 0 20px #25e6a777}
[data-testid="stVerticalBlockBorderWrapper"]{border:1px solid #284460!important;background:linear-gradient(145deg,#0c1b2f,#0e2235)!important;border-radius:20px!important;padding:10px!important}
[data-testid="stMetric"]{background:linear-gradient(145deg,#152942,#102037)!important;border-color:#2d4765!important}
[data-testid="stMetricValue"]{color:#39e8af!important}
[data-testid="stChatInput"]{border:1px solid #3b9e83!important}
[data-testid="stSidebarNav"]{display:none}
.sl-card{box-shadow:0 8px 26px #0003}.sl-main{background:linear-gradient(130deg,#0c3b36,#102e3e)!important;border-color:#26ae82!important;box-shadow:0 0 28px #18d99b17}
@media(max-width:850px){.sl-topnote,.sl-version{display:none}.sl-page-title{display:block}.sl-topbar{padding:12px}.sl-brand{font-size:22px}}
</style>""",unsafe_allow_html=True)
HEAD={'User-Agent':'SportLab/3.2 personal statistical analysis'}
def normalize(x):
    return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def fetch(url,params=None):
    r=requests.get(url,params=params,headers=HEAD,timeout=13);r.raise_for_status();return r
@st.cache_data(ttl=21600,show_spinner=False)
def csv(url):return pd.read_csv(io.BytesIO(fetch(url).content),low_memory=False,on_bad_lines='skip')
@st.cache_data(ttl=86400,show_spinner=False)
def excel(url):return pd.read_excel(io.BytesIO(fetch(url).content))
def clean_match_data(d):
    d=d.copy()
    # The extra-league feeds use Home/Away/HG/AG, unlike E0/SP1 etc.
    d=d.rename(columns={'Home':'HomeTeam','Away':'AwayTeam','HG':'FTHG','AG':'FTAG','home':'HomeTeam','away':'AwayTeam','hg':'FTHG','ag':'FTAG','date':'Date'})
    if not {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(d):raise ValueError('Niepoprawny format wyników')
    # All historical football dates use UTC-aware timestamps consistently.
    # ESPN provides ISO timestamps with Z; Football-Data usually provides naive dates.
    d['MatchDate']=pd.to_datetime(d.Date,dayfirst=True,errors='coerce',utc=True)
    for col in ['FTHG','FTAG','HS','AS','HC','AC','HST','AST']:
        if col in d:d[col]=pd.to_numeric(d[col],errors='coerce')
    return d.dropna(subset=['MatchDate','HomeTeam','AwayTeam','FTHG','FTAG'])

# P1 is PORTUGAL's second tier, not Polish Ekstraklasa. Poland uses separate league feed.
LEAGUES={'🇵🇱 Ekstraklasa':('new','POL'),'🏴 Premier League':('classic','E0'),
'🇮🇹 Serie A':('classic','I1'),'🇪🇸 La Liga':('classic','SP1'),
'🇩🇪 Bundesliga':('classic','D1'),'🇫🇷 Ligue 1':('classic','F1'),
'🇳🇱 Eredivisie':('classic','N1'),'🇵🇹 Primeira Liga':('classic','P0'),
'🏴 Championship':('classic','E1'),'🏆 Liga Mistrzów UEFA':('espn','uefa.champions')}
# Real, date-specific fixtures. A league appears only if the source returns a match.
# ESPN competition identifiers are checked independently; unavailable competitions
# are not represented with invented games or historic matchups.
ESPN_LEAGUES={
    '🇵🇱 Ekstraklasa':'pol.1',
    '🏴 Premier League':'eng.1',
    '🇮🇹 Serie A':'ita.1',
    '🇪🇸 La Liga':'esp.1',
    '🇩🇪 Bundesliga':'ger.1',
    '🇫🇷 Ligue 1':'fra.1',
    '🇳🇱 Eredivisie':'ned.1',
    '🇵🇹 Primeira Liga':'por.1',
    '🏴 Championship':'eng.2',
    '🏆 Liga Mistrzów UEFA':'uefa.champions',
}

@st.cache_data(ttl=1800,show_spinner=False)
def day_fixtures(day_iso):
    """Return verified ESPN events on selected Europe/Warsaw calendar date.

    ESPN dates can be UTC, so query adjacent dates and filter locally.
    Missing feeds produce no fake events and are reported to the UI.
    """
    chosen=date.fromisoformat(day_iso)
    rows={};errors={}
    def query_one(league,code,delta):
        d=chosen+timedelta(days=delta)
        payload=fetch(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard',
                      {'dates':f'{d:%Y%m%d}','limit':100}).json()
        if not isinstance(payload.get('events',[]),list):
            raise ValueError('Niepoprawna odpowiedź terminarza')
        return league,payload.get('events',[])
    grouped={league:[] for league in ESPN_LEAGUES}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(query_one,league,code,delta):league
                 for league,code in ESPN_LEAGUES.items() for delta in (-1,0,1)}
        for future in as_completed(futures):
            league=futures[future]
            try:
                _,events=future.result()
                grouped[league].extend(events)
            except Exception as exc:
                errors.setdefault(league,str(exc)[:90])
    for league,games in grouped.items():
        unique={}
        for event in games:
            try:
                dt=datetime.fromisoformat(event['date'].replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Warsaw'))
                if dt.date()!=chosen:continue
                comp=event['competitions'][0]
                teams_raw={c['homeAway']:c for c in comp['competitors']}
                teams={k:c['team']['displayName'] for k,c in teams_raw.items()}
                h,v=teams['home'],teams['away']
                event_id=str(event['id'])
                unique[event_id]={'id':event_id,'home':h,'away':v,'time':dt.strftime('%H:%M'),
                                  'label':f'{dt:%H:%M}  |  {h} – {v}',
                                  'completed':bool(comp.get('status',{}).get('type',{}).get('completed',False)), 'home_id':str(teams_raw['home']['team'].get('id','')), 'away_id':str(teams_raw['away']['team'].get('id','')), 'home_logo':teams_raw['home']['team'].get('logo',''), 'away_logo':teams_raw['away']['team'].get('logo','')}
            except (KeyError,IndexError,TypeError,ValueError):continue
        if unique:rows[league]=sorted(unique.values(),key=lambda x:(x['time'],x['home']))
    return rows,errors

@st.cache_data(ttl=21600,show_spinner=False)
def league_data(league,year):
    mode,code=LEAGUES[league];frames=[];errors=[]
    if mode=='espn':
        return ucl_data(year)
    if mode=='new':
        for url in [f'https://www.football-data.co.uk/new/{code}.csv']:
            try:frames.append(clean_match_data(csv(url)))
            except Exception as e:errors.append(str(e)[:110])
    else:
        for y in (year,year-1):
            season=f'{y%100:02d}{(y+1)%100:02d}'
            try:frames.append(clean_match_data(csv(f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv')))
            except Exception as e:errors.append(str(e)[:110])
    if not frames:raise ValueError('Nie udało się pobrać danych tej ligi. '+(' / '.join(errors[:1])))
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam']).sort_values('MatchDate')

@st.cache_data(ttl=7200,show_spinner=False)
def ucl_data(year):
    """Retrieve finished UCL fixtures in short windows; ESPN rejects multi-year ranges."""
    url='https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard'
    today=date.today()
    # Fetch recent months first; ESPN may cap events in large date queries.
    end=min(today,date(year+1,6,30))
    start=max(date(year-1,8,1),end-timedelta(days=310))
    rows=[];errors=[]
    cursor=start
    while cursor<=end:
        finish=min(cursor+timedelta(days=6),end)
        try:
            payload=fetch(url,{'dates':f'{cursor:%Y%m%d}-{finish:%Y%m%d}','limit':100}).json()
            events=payload.get('events',[])
        except Exception as exc:
            errors.append(str(exc)[:110]);events=[]
            # A single-day query is a documented ESPN scoreboard pattern.
            for offset in range((finish-cursor).days+1):
                try:events+=fetch(url,{'dates':f'{cursor+timedelta(days=offset):%Y%m%d}','limit':100}).json().get('events',[])
                except Exception:pass
        for ev in events:
            try:
                comp=ev['competitions'][0]
                if not comp['status']['type']['completed']:continue
                teams={t['homeAway']:t for t in comp['competitors']}
                h,v=teams['home'],teams['away']
                rows.append({'Date':ev['date'],'HomeTeam':h['team']['displayName'],'AwayTeam':v['team']['displayName'],'FTHG':float(h['score']),'FTAG':float(v['score'])})
            except (KeyError,IndexError,TypeError,ValueError):continue
        cursor=finish+timedelta(days=1)
    if not rows:raise ValueError('Nie udało się pobrać zakończonych meczów Ligi Mistrzów. '+str(errors[:1]))
    return clean_match_data(pd.DataFrame(rows)).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])

CLUB_ALIASES={
    'vfb stuttgart':('stuttgart','vfb stuttgart'),
    'galatasaray':('galatasaray','galatasaray istanbul','galatasaray sk'),
    'bayern munich':('bayern munich','bayern munchen','fc bayern munchen','bayern'),
    'atletico madrid':('atletico madrid','atletico de madrid'),
    'fc barcelona':('barcelona','fc barcelona','barcelona fc'),
    'inter milan':('inter','inter milan','internazionale'),
    'manchester united':('manchester united','man united','man utd','manchester utd','man united fc','manchester united fc','manchester utd fc','man utd fc'),
    'as roma':('as roma','roma','roma fc','as roma fc','roma as'),
    'feyenoord rotterdam':('feyenoord rotterdam','feyenoord','feyenoord rotterdam fc'),
    'shakhtar donetsk':('shakhtar donetsk','shakhtar','shakhtar donets k','fc shakhtar donetsk'),
    'sporting cp':('sporting cp','sporting','sporting lisbon','sporting clube de portugal','sporting portugal'),
    'lask linz':('lask linz','lask','linzer ask','lask linz fc'),
    'slovan bratislava':('slovan bratislava','slovan','sk slovan bratislava','slovan bratislava sk'),
    'borussia dortmund':('borussia dortmund','dortmund'),
    'paris saint germain':('paris saint germain','psg','paris sg'),
}
def club_keys(team):
    key=normalize(team)
    for canonical,aliases in CLUB_ALIASES.items():
        if key in aliases:return set(aliases)
    return {key}
def same_club(a,b):return bool(club_keys(a)&club_keys(b))

def align_club_names(df,reference):
    df=df.copy()
    for col in ('HomeTeam','AwayTeam'):
        df.loc[df[col].apply(lambda name:same_club(name,reference)),col]=reference
    return df

@st.cache_data(ttl=7200,show_spinner=False)
def domestic_history(team,day_iso):
    """Retrieve independent club history from current/previous domestic seasons.
    Report download errors separately from genuine missing club matches."""
    chosen=date.fromisoformat(day_iso)
    key=normalize(team)
    preferred=[]
    for code,terms in [
        ('E0',('manchester','arsenal','chelsea','liverpool','tottenham','newcastle','aston villa')),
        ('I1',('roma','juventus','napoli','inter milan','internazionale','atalanta','lazio','ac milan')),
        ('D1',('stuttgart','bayern','dortmund','leipzig','leverkusen','frankfurt')),
        ('SP1',('madrid','barcelona','sevilla','betis','villarreal')),
        ('F1',('paris','marseille','monaco','lyon','lille')),
        ('N1',('ajax','psv','feyenoord')),
        ('P0',('benfica','porto','sporting','braga')),
    ]:
        if any(t in key for t in terms):preferred.append(code)
    if not preferred:preferred=[]  # Nie pytaj o ligi angielską/włoską dla klubów ukraińskich, austriackich i słowackich
    start_year=chosen.year if chosen.month>=7 else chosen.year-1
    frames=[];notes=[]
    for code in preferred:
        for year in (start_year,start_year-1,start_year-2):
            season=f'{year%100:02d}{(year+1)%100:02d}'
            url=f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
            try:
                raw=csv(url)
                d=clean_match_data(raw)
                d=d[d.MatchDate<pd.Timestamp(chosen,tz='UTC')]
                matches=d.HomeTeam.apply(lambda x:same_club(x,team))|d.AwayTeam.apply(lambda x:same_club(x,team))
                sub=d[matches]
                if len(sub):
                    frames.append(sub)
                    notes.append(f'{code} {season}: {len(sub)} meczów')
                else:
                    notes.append(f'{code} {season}: pobrano {len(d)} meczów, brak dopasowania nazwy klubu; przykładowe nazwy: {", ".join(sorted(set(d.HomeTeam.astype(str)))[:5])}')
            except Exception as exc:
                notes.append(f'{code} {season}: błąd pobierania/formatu: {type(exc).__name__}: {str(exc)[:115]}')
        if frames:break
    if not frames:return pd.DataFrame(),notes or ['Liga krajowa poza bazą Football-Data; sprawdzam alternatywne źródła']
    merged=pd.concat(frames,ignore_index=True)
    merged=merged.drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam']).sort_values('MatchDate')
    return merged,notes

@st.cache_data(ttl=3600,show_spinner=False)
def espn_team_history(team_id, competition, day_iso):
    """Club's official ESPN schedule; try current and previous season identifiers.

    Competition-specific team schedule is different from Champions League team schedule.
    """
    if not team_id:return pd.DataFrame()
    chosen=date.fromisoformat(day_iso)
    rows=[]
    url=f'https://site.api.espn.com/apis/site/v2/sports/soccer/{competition}/teams/{team_id}/schedule'
    for season in (None,chosen.year,chosen.year-1,chosen.year+1):
        params={'limit':500}
        if season is not None:params['season']=season
        try:payload=fetch(url,params).json()
        except Exception:continue
        for ev in payload.get('events',[]):
            try:
                comp=ev['competitions'][0]
                if not comp.get('status',{}).get('type',{}).get('completed',False):continue
                dt=local_event_time(ev.get('date') or comp.get('date'))
                if not dt or dt.date()>=chosen:continue
                pair={c['homeAway']:c for c in comp['competitors']}
                h,a=pair['home'],pair['away']
                rows.append({'Date':ev.get('date') or comp.get('date'),
                             'HomeTeam':h['team']['displayName'],'AwayTeam':a['team']['displayName'],
                             'FTHG':float(h['score']),'FTAG':float(a['score'])})
            except (KeyError,IndexError,TypeError,ValueError):continue
        if len(rows)>=15:break
    if not rows:return pd.DataFrame()
    return clean_match_data(pd.DataFrame(rows)).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])

@st.cache_data(ttl=3600,show_spinner=False)
def espn_team_id_for_league(team,league_code):
    """Find an ESPN league-specific club ID without guessing IDs across competitions."""
    url=f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/teams'
    payload=fetch(url,{'limit':300}).json()
    teams=[]
    for sport in payload.get('sports',[]):
        for lg in sport.get('leagues',[]):
            for item in lg.get('teams',[]):
                t=item.get('team',item)
                teams.append(t)
    for t in teams:
        if any(same_club(team,t.get(k,'')) for k in ('displayName','name','shortDisplayName','abbreviation')):
            return str(t.get('id',''))
    return ''

@st.cache_data(ttl=7200,show_spinner=False)
def domestic_espn_history(team,day_iso):
    """Domestic league fallback, including countries absent from Football-Data."""
    chosen=date.fromisoformat(day_iso)
    key=normalize(team)
    aliases={'eng.1':('manchester','arsenal','chelsea','liverpool','tottenham','newcastle','aston villa'),
             'ita.1':('roma','inter','milan','juventus','napoli','atalanta','lazio'),
             'ger.1':('bayern','stuttgart','dortmund','leipzig','leverkusen','frankfurt'),
             'esp.1':('madrid','barcelona','sevilla','betis','villarreal'),
             'fra.1':('paris','marseille','monaco','lyon','lille'),
             'tur.1':('galatasaray','fenerbahce','besiktas','trabzon'),
             'por.1':('benfica','porto','sporting','braga'),
             'ned.1':('ajax','psv','feyenoord'),
             'aut.1':('lask','linz','salzburg','sturm graz','rapid vienna'),
             'svk.1':('slovan','bratislava','zilina','trnava'),
             'ukr.1':('shakhtar','donetsk','dynamo kyiv','dynamo kiev'),
             'ukr.premier':('shakhtar','donetsk','dynamo kyiv','dynamo kiev'),
             'aut.bundesliga':('lask','linz','salzburg','sturm graz'),
             'svk.superliga':('slovan','bratislava','zilina'),
             'pol.1':('legia','lech','rakow','jagiellonia','wisla')}
    codes=[code for code,words in aliases.items() if any(word in key for word in words)]
    if not codes:return pd.DataFrame()
    results=[]
    # Search scoreboard in month-sized ranges, stopping when enough completed games found.
    for code in codes:
        found=[]
        for offset in range(0,8):
            end=chosen-timedelta(days=offset*30+1)
            start=end-timedelta(days=29)
            try: events=fetch(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard',
                              {'dates':f'{start:%Y%m%d}-{end:%Y%m%d}','limit':200}).json().get('events',[])
            except Exception:continue
            for ev in events:
                try:
                    comp=ev['competitions'][0]
                    if not comp['status']['type']['completed']:continue
                    pair={c['homeAway']:c for c in comp['competitors']}
                    h,a=pair['home'],pair['away']
                    hn=h['team']['displayName'];an=a['team']['displayName']
                    if not (same_club(team,hn) or same_club(team,an)):continue
                    found.append({'Date':ev['date'],'HomeTeam':hn,'AwayTeam':an,
                                  'FTHG':float(h['score']),'FTAG':float(a['score'])})
                except (KeyError,IndexError,TypeError,ValueError):continue
            if len(found)>=15:break
        if found:
            results.extend(found)
            break
    if not results:return pd.DataFrame()
    return clean_match_data(pd.DataFrame(results)).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])

@st.cache_data(ttl=7200,show_spinner=False)
def sportsdb_history(team,day_iso):
    """Free TheSportsDB public v1 endpoint; no subscription or secret required.
    A team is matched by canonical/alias names, not arbitrary fuzzy substring.
    """
    base='https://www.thesportsdb.com/api/v1/json/3'
    chosen=pd.Timestamp(date.fromisoformat(day_iso),tz='UTC')
    aliases=sorted(club_keys(team),key=len,reverse=True)
    lookup=[]
    for candidate in [team]+aliases[:4]:
        try:
            payload=fetch(base+'/searchteams.php',{'t':candidate}).json()
            lookup.extend(payload.get('teams') or [])
        except Exception:continue
    ids=[]
    for entry in lookup:
        if same_club(team,entry.get('strTeam','')):
            tid=entry.get('idTeam')
            if tid and tid not in ids:ids.append(tid)
    if not ids:return pd.DataFrame(),'TheSportsDB: nie znaleziono identyfikatora klubu'
    rows=[];errors=[]
    for tid in ids[:2]:
        for endpoint in ('eventslast.php','eventsnext.php'):
            # last events can include current year; next events are ignored unless finished.
            try:
                payload=fetch(base+'/'+endpoint,{'id':tid}).json()
                events=payload.get('results') or payload.get('events') or []
            except Exception as exc:
                errors.append(type(exc).__name__+': '+str(exc)[:70]);continue
            for ev in events:
                try:
                    h,a=ev.get('strHomeTeam',''),ev.get('strAwayTeam','')
                    if not (same_club(h,team) or same_club(a,team)):continue
                    hg,ag=ev.get('intHomeScore'),ev.get('intAwayScore')
                    if hg is None or ag is None:continue
                    dt=ev.get('dateEvent')
                    if not dt:continue
                    rows.append({'Date':dt,'HomeTeam':h,'AwayTeam':a,'FTHG':int(hg),'FTAG':int(ag)})
                except (TypeError,ValueError):continue
    if not rows:return pd.DataFrame(),'TheSportsDB: brak zakończonych wyników; '+('; '.join(errors[:2]))
    df=clean_match_data(pd.DataFrame(rows))
    df=df[df.MatchDate<chosen].drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])
    return df,f'TheSportsDB: {len(df)} zweryfikowanych meczów'

def combine_football_history(league,season,game,day_iso):
    """Independent history of BOTH clubs, with transparent diagnostics per source."""
    h,v=game['home'],game['away']
    frames=[];diagnostics=[]
    try:
        d=league_data(league,season)
        frames.append(d)
        diagnostics.append(f'{league}: pobrano {len(d)} meczów całych rozgrywek')
    except Exception as exc:
        diagnostics.append(f'{league}: błąd — {str(exc)[:130]}')
    for club,team_id in ((h,game.get('home_id','')),(v,game.get('away_id',''))):
        try:
            domestic,sources=domestic_history(club,day_iso)
            if not domestic.empty:
                frames.append(domestic)
                diagnostics.append(f'{club}: Football-Data — {len(domestic)} spotkań ({", ".join(sources)})')
            else:diagnostics.append(f'{club}: Football-Data — brak wyników; diagnostyka: '+ ' | '.join(sources[:6]))
        except Exception as exc:diagnostics.append(f'{club}: Football-Data — błąd {str(exc)[:110]}')
        def current_count():
            return sum(int((f.HomeTeam.apply(lambda x:same_club(x,club)) | f.AwayTeam.apply(lambda x:same_club(x,club))).sum()) for f in frames)
        if current_count()<15:
            try:
                extra,note=sportsdb_history(club,day_iso)
                diagnostics.append(f'{club}: {note}')
                if not extra.empty:frames.append(extra)
            except Exception as exc:diagnostics.append(f'{club}: TheSportsDB — {type(exc).__name__}: {str(exc)[:100]}')
        if current_count()<15:
            try:
                extra=domestic_espn_history(club,day_iso)
                if not extra.empty:
                    frames.append(extra)
                    diagnostics.append(f'{club}: ESPN liga krajowa (terminarz) — {len(extra)} spotkań')
                else:diagnostics.append(f'{club}: ESPN liga krajowa (terminarz) — brak wyników')
            except Exception as exc:diagnostics.append(f'{club}: ESPN liga krajowa — błąd {str(exc)[:110]}')
        if current_count()<15:
            # A UCL team ID is not necessarily valid in the domestic competition.
            candidates=[]
            key=normalize(club)
            for code,words in {
                'eng.1':('manchester','arsenal','chelsea','liverpool','tottenham','newcastle'),
                'ita.1':('roma','inter','milan','juventus','napoli','lazio','atalanta'),
                'ger.1':('bayern','stuttgart','dortmund','leipzig','leverkusen'),
                'esp.1':('madrid','barcelona','sevilla','betis'),
                'fra.1':('paris','marseille','monaco','lyon'),
                'tur.1':('galatasaray','fenerbahce','besiktas'),
                'por.1':('benfica','porto','sporting'),
                'ned.1':('ajax','psv','feyenoord'),
             'aut.1':('lask','linz','salzburg','sturm graz','rapid vienna'),
             'svk.1':('slovan','bratislava','zilina','trnava'),
             'ukr.1':('shakhtar','donetsk','dynamo kyiv','dynamo kiev'),
             'ukr.premier':('shakhtar','donetsk','dynamo kyiv','dynamo kiev'),
             'aut.bundesliga':('lask','linz','salzburg','sturm graz'),
             'svk.superliga':('slovan','bratislava','zilina'),
                'pol.1':('legia','lech','rakow','jagiellonia'),
            }.items():
                if any(word in key for word in words):candidates.append(code)
            current_code=ESPN_LEAGUES.get(league)
            if current_code and current_code not in candidates:candidates.append(current_code)
            for code in candidates:
                try:
                    domestic_id=espn_team_id_for_league(club,code)
                    if not domestic_id:
                        diagnostics.append(f'{club}: ESPN {code} — nie znaleziono ID drużyny')
                        continue
                    extra=espn_team_history(domestic_id,code,day_iso)
                    if not extra.empty:
                        frames.append(extra)
                        diagnostics.append(f'{club}: ESPN {code} (historia klubu) — {len(extra)} spotkań')
                    else:diagnostics.append(f'{club}: ESPN {code} (historia klubu) — brak wyników')
                except Exception as exc:diagnostics.append(f'{club}: ESPN {code} — błąd {str(exc)[:110]}')
                if current_count()>=15:break
        if current_count()<15 and team_id:
            try:
                extra=espn_team_history(team_id,ESPN_LEAGUES[league],day_iso)
                if not extra.empty:frames.append(extra)
                diagnostics.append(f'{club}: ESPN rozgrywki wybranego meczu — {len(extra)} spotkań')
            except Exception as exc:diagnostics.append(f'{club}: ESPN puchary — błąd {str(exc)[:110]}')
    if not frames:raise ValueError('Brak historii. '+('; '.join(diagnostics[:3])))
    data=pd.concat(frames,ignore_index=True)
    data=align_club_names(align_club_names(data,h),v)
    data['_match_key']=data.apply(lambda r:(str(r.MatchDate.date()),normalize(r.HomeTeam),normalize(r.AwayTeam)),axis=1)
    data=data.sort_values('MatchDate').drop_duplicates('_match_key',keep='last').drop(columns=['_match_key'])
    data.attrs['diagnostics']=diagnostics
    return data

def form(df,team,cutoff,n=15):
    d=df[((df.HomeTeam==team)|(df.AwayTeam==team))&(df.MatchDate<cutoff)].sort_values('MatchDate',ascending=False).head(n)
    rows=[]
    for _,r in d.iterrows():
        home=r.HomeTeam==team;f=float(r.FTHG if home else r.FTAG);a=float(r.FTAG if home else r.FTHG)
        v={'Data':str(r.MatchDate.date()),'Rywal':r.AwayTeam if home else r.HomeTeam,'Wynik':f'{f:.0f}:{a:.0f}',
           'Gole':f,'Stracone':a,'Rezultat':'W' if f>a else 'R' if f==a else 'P'}
        for key,cols in [('Strzały',('HS','AS')),('Rożne',('HC','AC')),('Celne',('HST','AST'))]:
            col=cols[0 if home else 1];v[key]=float(r[col]) if col in r and pd.notna(r[col]) else None
        for k,cols in [('Strzały rywala',('AS','HS')),('Rożne rywala',('AC','HC')),('Celne rywala',('AST','HST'))]:
            col=cols[0 if home else 1];v[k]=float(r[col]) if col in r and pd.notna(r[col]) else None
        rows.append(v)
    return rows

def mean(rows,key,default=1.25):
    a=[float(r[key]) for r in rows if r.get(key) is not None and pd.notna(r[key])]
    return sum(a)/len(a) if a else default

def pmf(lam,k):return math.exp(-lam)*lam**k/math.factorial(k)
def poisson_grid(h,a):
    return {(i,j):pmf(h,i)*pmf(a,j) for i in range(16) for j in range(16)}
def make_market(name,p,why,n,kind='single'):
    return {'name':name,'p':max(0,min(1,p)),'why':why,'n':n,'kind':kind}
def football_markets(h,v,rh,rv,df,cutoff):
    hist=df[df.MatchDate<cutoff];avg=max(.6,float(pd.concat([hist.FTHG,hist.FTAG]).mean()))
    hmean=mean(rh,'Gole');vmean=mean(rv,'Gole');hc=mean(rh,'Stracone');vc=mean(rv,'Stracone')
    lh=max(.2,min(4.2,(hmean*vc/avg)*1.08));lv=max(.2,min(4.2,(vmean*hc/avg)*.93))
    grid=poisson_grid(lh,lv);n=min(len(rh),len(rv));markets=[]
    base=f'Z ostatnich {len(rh)} i {len(rv)} meczów: {h} zdobywa średnio {hmean:.2f} gola, {v} {vmean:.2f}. Model szacuje gole na {lh:.2f} do {lv:.2f}.'
    p1=sum(p for (i,j),p in grid.items() if i>j);p2=sum(p for (i,j),p in grid.items() if i<j);px=sum(p for (i,j),p in grid.items() if i==j)
    for name,p in [(f'{h} wygra',p1),('Remis',px),(f'{v} wygra',p2),(f'{h} lub remis',p1+px),(f'{v} lub remis',p2+px)]:markets.append(make_market(name,p,base,n))
    for line in (1.5,2.5,3.5,4.5):
        over=sum(p for (i,j),p in grid.items() if i+j>line)
        markets.extend([make_market(f'Powyżej {str(line).replace(".",",")} gola',over,base,n),make_market(f'Poniżej {str(line).replace(".",",")} gola',1-over,base,n)])
    btts=sum(p for (i,j),p in grid.items() if i>0 and j>0)
    markets.extend([make_market('Obie drużyny strzelą — TAK',btts,base,n),make_market('Obie drużyny strzelą — NIE',1-btts,base,n)])
    for who,win in [(h,lambda i,j:i>j),(v,lambda i,j:j>i)]:
        for line in (1.5,2.5,3.5):
            p=sum(prob for (i,j),prob in grid.items() if win(i,j) and i+j>line)
            markets.append(make_market(f'{who} wygra + powyżej {str(line).replace(".",",")} gola',p,base+' Prawdopodobieństwo kombinacji policzono ze wspólnego rozkładu wyników.',n,'combo'))
    for team,own,opponent,opp_rows in [(h,rh,v,rv),(v,rv,h,rh)]:
        for label,field,allowed,thresholds in [('strzału','Strzały','Strzały rywala',(7.5,10.5,13.5)),
                                               ('rożnego','Rożne','Rożne rywala',(3.5,5.5,7.5)),
                                               ('celnego strzału','Celne','Celne rywala',(2.5,4.5,6.5))]:
            ownvals=[float(r[field]) for r in own if r.get(field) is not None]
            allowedvals=[float(r[allowed]) for r in opp_rows if r.get(allowed) is not None]
            if len(ownvals)<5 or len(allowedvals)<5:continue
            expectation=.5*(sum(ownvals)/len(ownvals)+sum(allowedvals)/len(allowedvals))
            for line in thresholds:
                p=sum(pmf(expectation,k) for k in range(int(line)+1,60))
                why=(f'{team} w {len(ownvals)} meczach: średnio {sum(ownvals)/len(ownvals):.1f}; '
                     f'{opponent} w {len(allowedvals)} meczach dopuszczał średnio {sum(allowedvals)/len(allowedvals):.1f}. '
                     f'Prognoza uwzględnia atak i obronę przeciwnika; przybliżenie Poissona, bez pełnej korekty siły terminarza.')
                markets.append(make_market(f'{team}: powyżej {str(line).replace(".",",")} {label}',p,why,min(len(ownvals),len(allowedvals))))
    # Do not show unrelated league-average shot totals as a matchup prediction.
    return markets,(p1,px,p2),(lh,lv)

# Licensed CC BY 4.0 historical match data. No scraping of bookmaker websites.






NBA_NAMES=['Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets','Chicago Bulls','Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets','Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers','LA Clippers','Los Angeles Lakers','Memphis Grizzlies','Miami Heat','Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks','Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns','Portland Trail Blazers','Sacramento Kings','San Antonio Spurs','Toronto Raptors','Utah Jazz','Washington Wizards']
# Streamlit date picker represents the Polish calendar day for every sport.
POLISH_TZ=ZoneInfo('Europe/Warsaw')

def local_event_time(raw):
    if not raw:return None
    try:
        dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=ZoneInfo('UTC'))
        return dt.astimezone(POLISH_TZ)
    except (TypeError,ValueError,OverflowError):return None

def espn_competitors(comp,kind):
    """Return display names of actual two-player/team matchups, not tournament headers."""
    competitors=comp.get('competitors') or []
    if len(competitors)!=2:return None
    names=[]
    for c in competitors:
        obj=c.get('athlete') or c.get('team') or {}
        name=obj.get('displayName') or obj.get('fullName') or c.get('displayName')
        if not name:return None
        names.append(str(name))
    if names[0]==names[1]:return None
    if kind=='nba':
        mapping={c.get('homeAway'):c for c in competitors}
        if 'home' not in mapping or 'away' not in mapping:return None
        def cname(c):return (c.get('team') or {}).get('displayName') or c.get('displayName')
        return cname(mapping['home']),cname(mapping['away'])
    return tuple(names)

@st.cache_data(ttl=1200,show_spinner=False)
def dated_sport_fixtures(kind,tour,day_iso):
    """Read real ESPN schedule around local date, deduplicate, never invent fixtures."""
    chosen=date.fromisoformat(day_iso)
    path='basketball/nba'
    url=f'https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard'
    found={};errors=[];successful=0
    # ESPN date parameters use a US/UTC calendar; the previous and next day
    # may contain events belonging to the selected date in Warsaw.
    for offset in (-1,0,1):
        d=chosen+timedelta(days=offset)
        try:
            payload=fetch(url,{'dates':f'{d:%Y%m%d}','limit':500}).json()
            events=payload.get('events')
            if not isinstance(events,list):raise ValueError('Odpowiedź nie zawiera listy events')
            successful+=1
        except Exception as exc:
            errors.append(f'{d:%d.%m}: {str(exc)[:140]}')
            continue
        for event in events:
            comps=list(event.get('competitions') or [])
            for index,comp in enumerate(comps):
                pair=espn_competitors(comp,kind)
                if not pair:continue
                raw_time=comp.get('date') or event.get('date')
                when=local_event_time(raw_time)
                if when is None or when.date()!=chosen:continue
                label=f'{when:%H:%M} | {pair[0]} – {pair[1]}'
                cid=str(comp.get('id') or index)
                event_id=str(event.get('id') or '')
                key=(event_id,cid,tuple(pair))
                found[key]={'id':event_id,'competition_id':cid,'a':pair[0],'b':pair[1],
                            'label':label,'time':when.strftime('%H:%M'),
                            'timestamp':when.isoformat(),'source':'ESPN',
                            'completed':bool((comp.get('status') or {}).get('type',{}).get('completed',False)), 'home_logo':next((c.get('team',{}).get('logo','') for c in comp.get('competitors',[]) if c.get('homeAway')=='home'),''), 'away_logo':next((c.get('team',{}).get('logo','') for c in comp.get('competitors',[]) if c.get('homeAway')=='away'),'')}
    return sorted(found.values(),key=lambda x:(x['timestamp'],x['a'],x['b'])),errors,successful



@st.cache_data(ttl=7200,show_spinner=False)
def nba_day(day):
    data=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',{'dates':day.strftime('%Y%m%d'),'limit':100}).json();out=[]
    for e in data.get('events',[]):
        c=(e.get('competitions') or [{}])[0]
        if not c.get('status',{}).get('type',{}).get('completed',False):continue
        try:
            teams={x['homeAway']:(x['team']['displayName'],float(x['score'])) for x in c['competitors']}
            out.append((teams['home'],teams['away']))
        except (KeyError,TypeError,ValueError):pass
    return out

def nba_markets(h,a,day,lines=None):
    records={}
    for i in range(1,66):
        try:games=nba_day(day-timedelta(days=i))
        except Exception:continue
        for (hn,hs),(an,as_) in games:
            records.setdefault(hn,[]).append({'Gole':hs,'Stracone':as_,'Data':str(day-timedelta(days=i)),'Rywal':an,'Wynik':f'{hs:.0f}:{as_:.0f}'})
            records.setdefault(an,[]).append({'Gole':as_,'Stracone':hs,'Data':str(day-timedelta(days=i)),'Rywal':hn,'Wynik':f'{as_:.0f}:{hs:.0f}'})
    rh=records.get(h,[])[:15];ra=records.get(a,[])[:15]
    if min(len(rh),len(ra))<5:raise ValueError('Za mało zakończonych meczów NBA w ostatnich 65 dniach.')
    ph=.5*(mean(rh,'Gole')+mean(ra,'Stracone'))+1.5
    pa=.5*(mean(ra,'Gole')+mean(rh,'Stracone'))-1.5
    p=1/(1+math.exp(-(ph-pa)/13));n=min(len(rh),len(ra))
    why=(f'{h}: zdobywa {mean(rh,"Gole"):.1f} pkt; {a} pozwala rywalom na {mean(ra,"Stracone"):.1f} pkt. '
         f'{a}: zdobywa {mean(ra,"Gole"):.1f} pkt; {h} pozwala rywalom na {mean(rh,"Stracone"):.1f} pkt. '
         f'Prognoza {ph:.1f}:{pa:.1f}; uwzględnia ofensywę i defensywę, bez informacji o kontuzjach.')
    markets=[make_market(f'{h} wygra',p,why,n),make_market(f'{a} wygra',1-p,why,n)]
    for team,projection,own,opp in ((h,ph,rh,ra),(a,pa,ra,rh)):
        for line in (math.floor(projection/5)*5-0.5,):
            q=.5*math.erfc((line-projection)/(15*math.sqrt(2)))
            markets.append(make_market(f'{team} powyżej {str(line).replace(".",",")} punktu (próg modelowy)',q,
                f'{team} zdobywa średnio {mean(own,"Gole"):.1f}, a {a if team==h else h} traci średnio {mean(opp,"Stracone"):.1f} pkt. '+why,n))
    total=ph+pa
    chosen_lines=sorted(set(lines or []))
    if not chosen_lines:chosen_lines=[math.floor(total/5)*5-0.5]
    for line in chosen_lines[:3]:
        q=.5*math.erfc((line-total)/(22*math.sqrt(2)))
        label=' (próg modelowy)' if not lines else ''
        markets.extend([make_market(f'Łącznie powyżej {str(line).replace(".",",")} pkt'+label,q,why,n),
                        make_market(f'Łącznie poniżej {str(line).replace(".",",")} pkt'+label,1-q,why,n)])
    markets.sort(key=lambda m:m['p'],reverse=True)
    return markets,(p,1-p),(rh,ra)

# The Odds API: optional key configured in Streamlit Secrets; no invented or scraped odds.
@st.cache_data(ttl=900,show_spinner=False)
def odds_events(api_key,sport_key):
    if not api_key:return []
    data=fetch(f'https://api.the-odds-api.com/v4/sports/{sport_key}/odds/',{'apiKey':api_key,'regions':'eu','markets':'h2h,totals','oddsFormat':'decimal','dateFormat':'iso'}).json()
    return data if isinstance(data,list) else []
def find_odds(events,home,away,market):
    # Show odds only if both event and outcome are an exact normalized match.
    for ev in events:
        if {normalize(ev.get('home_team','')),normalize(ev.get('away_team',''))}!={normalize(home),normalize(away)}:continue
        for bookmaker in ev.get('bookmakers',[]):
            for m in bookmaker.get('markets',[]):
                for o in m.get('outcomes',[]):
                    label=o.get('name','');point=o.get('point')
                    match=(market in (f'{home} wygra',f'{home} wygra mecz') and normalize(label)==normalize(home)) or (market in (f'{away} wygra',f'{away} wygra mecz') and normalize(label)==normalize(away)) or (market=='Remis' and normalize(label)=='draw')
                    mt=re.match(r'^(Powyżej|Poniżej) (\d+,\d+) (gola|punktu)',market)
                    if mt and m.get('key')=='totals' and point is not None:
                        match=(normalize(label)==('over' if mt.group(1)=='Powyżej' else 'under') and abs(float(point)-float(mt.group(2).replace(',','.')))<.01)
                    if match and isinstance(o.get('price'),(int,float)):
                        return float(o['price']),bookmaker.get('title','Bukmacher'),bookmaker.get('last_update','brak czasu')
    return None

def available_total_lines(events,home,away):
    lines=set()
    for ev in events:
        if {normalize(ev.get('home_team','')),normalize(ev.get('away_team',''))}!={normalize(home),normalize(away)}:continue
        for bookmaker in ev.get('bookmakers',[]):
            for market in bookmaker.get('markets',[]):
                if market.get('key')!='totals':continue
                for outcome in market.get('outcomes',[]):
                    try:
                        line=float(outcome['point'])
                        if 170<=line<=300:lines.add(line)
                    except (KeyError,TypeError,ValueError):pass
    return sorted(lines)

def render(markets,probs,teams,rows=None,source='',api_key='',sport_key=''):
    if not markets:
        st.warning('Brak wystarczających danych do propozycji.')
        return
    # Statistical suggestions must not depend on the presence of bookmaker odds.
    # Odds are only an optional, independently verified annotation.
    events=[]
    if api_key and sport_key:
        try:
            events=odds_events(api_key,sport_key)
        except Exception:
            pass
    eligible=[m for m in markets if m['n']>=6 and .18<=m['p']<=.82]
    # A list of many alternate thresholds is not a list of independent ideas.
    # Keep at most one selection per family; never fill with near-duplicates.
    def family(m):
        name=m['name'].lower()
        if 'strzał' in name:return 'shots:'+normalize(name.split(':')[0]) if ':' in name else 'shots:total'
        if 'rożn' in name:return 'corners'
        if 'obie drużyny' in name:return 'btts'
        if 'handicap' in name:return 'handicap'
        if 'połow' in name or 'kwart' in name:return 'period'
        if 'punkt' in name or 'pkt' in name:
            if 'łącznie' in name or 'suma' in name or 'powyżej' in name or 'poniżej' in name:return 'total_points'
            return 'team_points:'+normalize(name.split(' ponad ')[0].split(' poniżej ')[0])
        if 'gola' in name:return 'goals'
        if 'wygra +' in name:return 'combo'
        if 'wygra' in name or 'remis' in name:return 'result'
        return normalize(name)
    eligible.sort(key=lambda m:(-m['p'], -min(m['n'],30)))
    picks=[];used=set()
    for m in eligible:
        group=family(m)
        if group in used:continue
        used.add(group);picks.append(m)
        if len(picks)>=4:break
    st.markdown(f'<div class="sl-hero"><div class="sl-kicker">ANALIZA SPOTKANIA</div><h2 style="margin:9px 0">{html.escape(teams[0])} &nbsp; <span style="color:#94a3b8">VS</span> &nbsp; {html.escape(teams[1])}</h2><div class="sl-sub">{html.escape(source)} · Szacunki na podstawie danych historycznych, nie gwarancja wyniku</div></div>',unsafe_allow_html=True)
    st.subheader('📊 Prawdopodobieństwa')
    cols=st.columns(len(probs))
    for c,(name,p) in zip(cols,probs):
        c.metric(name,f'{p:.1%}')
    st.subheader('🎯 Propozycje statystyczne')
    if not picks:
        st.info('Brak wystarczająco uzasadnionych propozycji dla tego meczu.')
    else:
        for i,m in enumerate(picks):
            odds=find_odds(events,teams[0],teams[1],m['name']) if events else None
            odds_label=(f'Potwierdzony kurs: {odds[0]:.2f} ({html.escape(str(odds[1]))})' if odds else 'Kurs: niezweryfikowany — sprawdź ofertę bukmachera')
            st.markdown(f'<div class="sl-card {"sl-main" if i==0 else ""}"><div class="sl-tag">{"PROPOZYCJA GŁÓWNA" if i==0 else "INNA PROPOZYCJA"}</div><div class="sl-name">{html.escape(m["name"])}</div><div class="sl-grid"><div class="sl-stat"><div class="sl-label">Szacowana szansa</div><div class="sl-value">{m["p"]:.1%}</div></div><div class="sl-stat"><div class="sl-label">Kurs</div><div class="sl-note">{odds_label}</div></div></div><div class="sl-explain"><b>Dlaczego?</b> {html.escape(m["why"])}</div><div class="sl-note">Próba: {m["n"]} spotkań. Szacunek statystyczny, nie potwierdzenie opłacalności zakładu.</div></div>',unsafe_allow_html=True)
    st.caption('Typy są propozycjami modelu, nie ofertami bukmacherskimi. Sam sprawdź dostępność rynku i kurs (np. własne minimum 1,35).')
    if rows:
        with st.expander('📋 Dane źródłowe i ostatnie mecze'):
            a,b=st.columns(2)
            for col,name,data in zip((a,b),teams,rows):
                with col:
                    st.markdown('**'+name+'**')
                    st.dataframe(pd.DataFrame(data).head(12),hide_index=True,use_container_width=True)


# Player box scores are fetched on demand from completed ESPN NBA games.
# ESPN boxscore statistics labels (PTS, REB, AST, 3PT, etc.) are verified per game.
@st.cache_data(ttl=3600,show_spinner=False)
def nba_completed_event_ids(team_name, cutoff_iso, max_games=18):
    cutoff=date.fromisoformat(cutoff_iso)
    ids=[]; seen=set()
    for offset in range(1,100):
        d=cutoff-timedelta(days=offset)
        try:
            payload=fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',
                          {'dates':d.strftime('%Y%m%d'),'limit':100}).json()
        except Exception:continue
        for event in payload.get('events',[]):
            comp=(event.get('competitions') or [{}])[0]
            if not comp.get('status',{}).get('type',{}).get('completed'):continue
            names=[x.get('team',{}).get('displayName','') for x in comp.get('competitors',[])]
            if not any(normalize(n)==normalize(team_name) for n in names):continue
            eid=str(event.get('id',''))
            if eid and eid not in seen:ids.append((eid,d.isoformat()));seen.add(eid)
        if len(ids)>=max_games:break
    return ids[:max_games]

@st.cache_data(ttl=21600,show_spinner=False)
def nba_boxscore(event_id):
    return fetch('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary',{'event':event_id}).json()

def player_game_rows(payload):
    result=[]
    for team in payload.get('boxscore',{}).get('players',[]):
        team_name=team.get('team',{}).get('displayName','')
        for block in team.get('statistics',[]):
            labels=block.get('labels',[])
            for athlete in block.get('athletes',[]):
                person=athlete.get('athlete',{})
                if not athlete.get('stats'):continue
                values=dict(zip(labels,athlete.get('stats',[])))
                result.append((person.get('displayName',''),team_name,values))
    return result

def stat_value(stats,kind):
    keys={'points':('PTS',),'rebounds':('REB',),'assists':('AST',),'threes':('3PM',),'steals':('STL',),'blocks':('BLK',)}[kind]
    for key in keys:
        if key in stats:
            try:return float(stats[key])
            except (ValueError,TypeError):return None
    if kind=='threes':
        for key in ('3PT','3P'):
            if key in stats:
                try:return float(str(stats[key]).split('-')[0])
                except (ValueError,TypeError):return None
    return None

def nba_player_analysis(question,context):
    q=normalize(question);line=numeric_line(question)
    if line is None:return 'Podaj próg zawodnika, np. „Stephen Curry powyżej 24,5 punktu”.'
    if any(x in q for x in ('zbiork','rebounds')):kind='rebounds';unit='zbiórek'
    elif any(x in q for x in ('asyst','assists')):kind='assists';unit='asyst'
    elif any(x in q for x in ('trojk','trójek','rzutow za trzy','3pm')):kind='threes';unit='trójek'
    elif 'przechwyt' in q:kind='steals';unit='przechwytów'
    elif 'blok' in q:kind='blocks';unit='bloków'
    else:kind='points';unit='punktów'
    cutoff=context.get('day',date.today().isoformat())
    names=context['teams'];games=[]
    for team in names:
        games.extend(nba_completed_event_ids(team,cutoff,18))
    # First locate a matching player on one of the two teams. Require a surname,
    # not a guessed association from an arbitrary substring.
    seen=set();matches=[];available=[]
    for eid,game_day in sorted(games,key=lambda v:v[1],reverse=True):
        if eid in seen:continue
        seen.add(eid)
        try:rows=player_game_rows(nba_boxscore(eid))
        except Exception:continue
        for player,team,stats in rows:
            if normalize(team) not in {normalize(n) for n in names}:continue
            available.append(player)
            parts=normalize(player).split()
            surname=parts[-1] if parts else ''
            tokens=q.split()
            if len(surname)<3 or not any(
                token==surname or (len(token)>=5 and difflib.SequenceMatcher(None,token,surname).ratio()>=0.83)
                for token in tokens
            ):continue
            val=stat_value(stats,kind)
            if val is not None:matches.append((player,team,game_day,val))
    exact=[r for r in matches if normalize(r[0]).split()[-1] in q.split()]
    if exact:matches=exact
    players={normalize(r[0]):r[0] for r in matches}
    if not players:
        return ('Nie znalazłem potwierdzonych występów wskazanego zawodnika w ostatnich meczach wybranych drużyn. '
                'Sprawdź nazwisko i czy zawodnik należy do jednej z drużyn tego spotkania. '
                'Nie podaję procentu bez danych meczowych ESPN.')
    if len(players)>1:
        return 'Nazwisko jest niejednoznaczne. Wpisz imię i nazwisko: '+', '.join(sorted(players.values()))
    target=next(iter(players))
    values=[];used=[]
    for player,team,game_day,val in matches:
        if normalize(player)==target and game_day not in used:
            values.append((game_day,val));used.append(game_day)
        if len(values)>=15:break
    if len(values)<5:return f'Znaleziono tylko {len(values)} potwierdzonych meczów zawodnika {players[target]} z tą statystyką. Potrzeba minimum 5.'
    over=not any(x in q for x in ('ponizej','mniej','under'))
    hits=sum(v>line if over else v<line for _,v in values)
    n=len(values);prob=(hits+1)/(n+2)
    verdict='Dobry pomysł pod względem szansy trafienia' if prob>=.65 else 'Ryzykowny pomysł' if prob>=.45 else 'Zły pomysł pod względem szansy trafienia'
    series=', '.join(f'{d}: {v:g}' for d,v in values)
    opponent=next((name for name in names if normalize(name)!=normalize(next(r[1] for r in matches if normalize(r[0])==target))),None)
    defensive=''
    if opponent:
        try:
            oppgames=nba_completed_event_ids(opponent,cutoff,15)
            allowed=[]
            for eid,_ in oppgames[:15]:
                try:
                    summary=nba_boxscore(eid)
                    competitors=(summary.get('header',{}).get('competitions') or [{}])[0].get('competitors',[])
                    opponent_row=next((c for c in competitors if normalize(c.get('team',{}).get('displayName',''))==normalize(opponent)),None)
                    rival_row=next((c for c in competitors if normalize(c.get('team',{}).get('displayName',''))!=normalize(opponent)),None)
                    if opponent_row and rival_row:allowed.append(float(rival_row['score']))
                except (KeyError,TypeError,ValueError,IndexError):continue
            if len(allowed)>=5:
                defensive=(f'\n\n**Defensywa rywala {opponent}:** w {len(allowed)} ostatnich meczach '
                           f'pozwalał przeciwnikom zdobywać średnio {sum(allowed)/len(allowed):.1f} punktu drużynowo. '
                           'To kontekst, nie bezpośrednia miara obrony przeciwko temu zawodnikowi.')
        except Exception:pass
    direction='powyżej' if over else 'poniżej'
    return (f'**{players[target]} — {direction} {str(line).replace(".",",")} {unit}**\n\n'
            f'**Ocena: {verdict}. Szacowana szansa: {prob:.1%}.**\n\n'
            f'Próg spełniony w **{hits}/{n}** ostatnich dostępnych występów; średnia: **{sum(v for _,v in values)/n:.1f}**.\n\n'
            f'**Ostatnie mecze (data: {unit}):** {series}.'+defensive+'\n\n'
            'Źródło: zakończone mecze i boxscore ESPN NBA. Procent to wygładzona częstość historyczna, '
            'bez korekty na minuty, kontuzje i obronę obecnego rywala; nie gwarantuje trafienia ani opłacalności.')

# SportLab 4.0: extra questions use only verified historical data.
def numeric_line(question):
    match=re.search(r'(\d{1,3}(?:[.,]\d+)?)',question)
    return float(match.group(1).replace(',','.')) if match else None

def is_player_question(question,context):
    """Recognize personal player markets without relying on a small name whitelist."""
    q=normalize(question)
    if any(t in q for t in ('zawodnik','gracz','koszykarz','stephen','lebron','haliburton','halliburton',
                             'curry','jokic','doncic','tatum','wembanyama','antetokounmpo',
                             'durant','brunson','edwards','embiid','harden','giannis')):
        return True
    # Team name in question means team market; otherwise a named subject before
    # 'powyżej/poniżej' is a player, never silently a team total.
    for team in context.get('teams',()):
        t=normalize(team)
        # Match full team name and recognizable nickname, not generic city words.
        nick=t.split()[-1] if t.split() else ''
        if t in q or (len(nick)>=4 and nick in q.split()) or any(part in q.split() for part in t.split() if len(part)>=6):
            return False
    subject=re.split(r'\\b(?:powyzej|ponizej|wiecej|mniej|over|under)\\b',q,maxsplit=1)[0].strip()
    stop={'czy','to','dobry','pomysl','punktow','punkty','pkt','w','tym','meczu','suma','lacznie','razem','druzyna','obie','zespoly','gospodarze','goscie','a','co','z'}
    words=[w for w in subject.split() if w not in stop]
    return bool(words and any(len(w)>=4 for w in words))

def suggest_player_line(question,context):
    q=normalize(question)
    kind='rebounds' if 'zbiork' in q else 'assists' if 'asyst' in q else 'threes' if 'trojk' in q else 'points'
    unit={'rebounds':'zbiórek','assists':'asyst','threes':'trójek','points':'punktów'}[kind]
    cutoff=context.get('day',date.today().isoformat())
    games=[]
    for team in context['teams']:
        games.extend(nba_completed_event_ids(team,cutoff,18))
    seen=set();found={}
    for eid,game_day in sorted(games,key=lambda x:x[1],reverse=True):
        if eid in seen:continue
        seen.add(eid)
        try:entries=player_game_rows(nba_boxscore(eid))
        except Exception:continue
        for player,team,stats in entries:
            if normalize(team) not in [normalize(t) for t in context['teams']]:continue
            surname=normalize(player).split()[-1] if player else ''
            if not surname or not any(token==surname or (len(token)>=5 and difflib.SequenceMatcher(None,token,surname).ratio()>=.83) for token in q.split()):continue
            value=stat_value(stats,kind)
            if value is not None:found.setdefault(player,[]).append(value)
    if not found:return 'Nie znalazłem występów wskazanego zawodnika. Podaj jego imię i nazwisko oraz statystykę.'
    if len(found)>1:return 'Doprecyzuj zawodnika: '+', '.join(sorted(found))
    player,values=next(iter(found.items()))
    if len(values)<5:return f'Znalazłem tylko {len(values)} występów {player}. Nie proponuję progu bez minimum 5.'
    avg=sum(values[:15])/len(values[:15]);step=1 if kind!='points' else 2
    line=max(.5,round(avg/step)*step-.5)
    return ('**Proponowany próg na podstawie występów:**\n\n'+
            nba_player_analysis(f'{player} powyżej {str(line).replace(".",",")} {unit}',context))

def suggested_markets(question,context):
    """Find a single supported, data-backed market when the user does not specify a line."""
    q=normalize(question)
    if context['sport']=='nba' and any(x in q for x in ('zawodnik','koszykarz','gracz','haliburton','halliburton','curry','jokic','doncic','lebron','tatum','durant','wembanyama')):
        return suggest_player_line(question,context)
    nba=context['sport']=='nba'
    kind='points' if nba else ('on_target' if 'celn' in q and 'strzal' in q else 'shots' if 'strzal' in q else 'corners' if 'rozn' in q else 'goals')
    names=context['teams'];team=None
    for i,name in enumerate(names):
        if normalize(name) in q:team=i;break
    field='Gole' if kind=='goals' else 'Strzały' if kind=='shots' else 'Rożne' if kind=='corners' else 'Celne' if kind=='on_target' else 'Gole'
    against='Stracone' if kind in ('goals','points') else 'Strzały rywala' if kind=='shots' else 'Rożne rywala' if kind=='corners' else 'Celne rywala'
    def vals(rows,key):return [float(r[key]) for r in rows if r.get(key) is not None]
    first,second=context['rows']
    if team is None:
        a,b,c,d=vals(first,field),vals(second,field),vals(first,against),vals(second,against)
        if min(map(len,(a,b,c,d)))<5:return 'Nie mam wystarczających danych obu drużyn, żeby samodzielnie proponować próg.'
        expected=(sum(a)/len(a)+sum(d)/len(d)+sum(b)/len(b)+sum(c)/len(c))/2
        sigma=22 if nba else None
    else:
        a,b=vals(context['rows'][team],field),vals(context['rows'][1-team],against)
        if min(len(a),len(b))<5:return 'Brakuje danych ofensywy i defensywy rywala, żeby zaproponować próg.'
        expected=(sum(a)/len(a)+sum(b)/len(b))/2
        sigma=12 if nba else None
    # Choose a line near the projected value; do not pick artificially tiny lines to inflate probability.
    step=5 if nba else 1
    center=round(expected/step)*step
    candidates=[max(0.5,center+offset*step-0.5) for offset in (-1,0,1)]
    options=[]
    for line in candidates:
        if nba:p=.5*math.erfc((line-expected)/(sigma*math.sqrt(2)))
        else:p=sum(pmf(max(.05,expected),k) for k in range(int(line)+1,150))
        for direction,prob in [('powyżej',p),('poniżej',1-p)]:
            options.append((abs(prob-.62),direction,line,prob))
    _,direction,line,prob=min(options)
    unit='punktów' if nba else 'strzałów' if kind=='shots' else 'rożnych' if kind=='corners' else 'celnych strzałów' if kind=='on_target' else 'goli'
    subject=names[team] if team is not None else 'Łącznie w meczu'
    return (f'**Moja propozycja: {subject} — {direction} {str(line).replace(".",",")} {unit}.**\n\n'
            f'**Szacowana szansa: {prob:.1%}.** Prognoza oparta na ataku i statystykach dopuszczanych przez rywala: **{expected:.1f}**.\n\n'
            'Próg jest propozycją modelu, a nie zweryfikowaną linią bukmachera. '
            'To przybliżenie bez pełnej korekty kontuzji, tempa i jakości przeciwników. '
            'Do oceny opłacalności potrzebny jest rzeczywisty kurs.')

def extra_analysis(question,context):
    q=normalize(question);line=numeric_line(question)
    if line is None:return suggested_markets(question,context)
    over=not any(word in q for word in ('ponizej','mniej','under'))
    is_nba=context['sport']=='nba'
    kind='points' if is_nba else ('on_target' if 'celn' in q and 'strzal' in q else 'shots' if 'strzal' in q else 'corners' if 'rozn' in q else 'goals' if 'gol' in q or 'bram' in q else None)
    if kind is None:return 'Nie rozpoznaję tego rynku. W piłce obsługuję gole, strzały i rożne; w NBA punkty drużyn i sumę punktów. Dla zawodników potrzebne są osobne dane meczowe.'
    if is_nba and is_player_question(question,context):
        return nba_player_analysis(question,context)
    rows=context['rows'];names=context['teams'];team=None
    for idx,name in enumerate(names):
        if normalize(name) in q or any(part in q for part in normalize(name).split() if len(part)>5):team=idx;break
    if kind=='points':field='Gole';against='Stracone'
    elif kind=='goals':field='Gole';against='Stracone'
    elif kind=='shots':field='Strzały';against='Strzały rywala'
    elif kind=='on_target':field='Celne';against='Celne rywala'
    else:field='Rożne';against='Rożne rywala'
    def values(rs,k):return [float(r[k]) for r in rs if r.get(k) is not None]
    first,second=rows
    if team is not None:
        own=values(rows[team],field)
        conceded=values(rows[1-team],against)
        if len(own)<5 or len(conceded)<5:
            return (f'Za mało danych dla tej statystyki: {names[team]} — {len(own)} meczów, '
                    f'{names[1-team]} (dopuszczone) — {len(conceded)} meczów. Minimum 5 na każdą stronę.')
        expected=.5*(sum(own)/len(own)+sum(conceded)/len(conceded))
        # NBA points approximated by normal distribution; soccer event counts by Poisson.
        if is_nba:
            sigma=max(9.0,(sum((x-sum(own)/len(own))**2 for x in own)/len(own))**.5)
            p=.5*math.erfc((line-expected)/(sigma*math.sqrt(2)))
        else:
            p=sum(pmf(max(.05,expected),k) for k in range(int(line)+1,100))
        prob=p if over else 1-p
        detail=(f'**{names[team]}**: ostatnie {len(own)} meczów, średnio **{sum(own)/len(own):.1f}**. '
                f'**{names[1-team]}**: w ostatnich {len(conceded)} meczach dopuszczał średnio **{sum(conceded)/len(conceded):.1f}**. '
                f'Prognoza dopasowana do przeciwnika: **{expected:.1f}**.\n\n'
                f'**Ostatnie wyniki {names[team]}:** '+', '.join(f'{v:g}' for v in own[:15])+'.\n\n'
                f'**Dopuszczane przez {names[1-team]}:** '+', '.join(f'{v:g}' for v in conceded[:15])+'.')
        n=min(len(own),len(conceded))
    else:
        own_a=values(first,field);against_a=values(first,against)
        own_b=values(second,field);against_b=values(second,against)
        if min(map(len,(own_a,against_a,own_b,against_b)))<5:
            return 'Brak co najmniej 5 kompletnych meczów z danymi ofensywnymi i defensywnymi dla obu drużyn. Nie wymyślam procentu.'
        ex_a=.5*(sum(own_a)/len(own_a)+sum(against_b)/len(against_b))
        ex_b=.5*(sum(own_b)/len(own_b)+sum(against_a)/len(against_a))
        expected=ex_a+ex_b
        if is_nba:p=.5*math.erfc((line-expected)/(22*math.sqrt(2)))
        else:p=sum(pmf(max(.05,expected),k) for k in range(int(line)+1,150))
        prob=p if over else 1-p
        detail=(f'Prognoza {names[0]}: **{ex_a:.1f}** (własne średnio {sum(own_a)/len(own_a):.1f}; '
                f'dopuszczane przez {names[1]}: {sum(against_b)/len(against_b):.1f}). '
                f'Prognoza {names[1]}: **{ex_b:.1f}** (własne średnio {sum(own_b)/len(own_b):.1f}; '
                f'dopuszczane przez {names[0]}: {sum(against_a)/len(against_a):.1f}). '
                f'Łącznie oczekiwane **{expected:.1f}**.')
        n=min(map(len,(own_a,against_a,own_b,against_b)))
    verdict='Dobry pomysł pod względem prawdopodobieństwa' if prob>=.65 else 'Ryzykowny pomysł' if prob>=.45 else 'Zły pomysł pod względem prawdopodobieństwa'
    direction='powyżej' if over else 'poniżej'
    return (f'**{verdict}** — szacowana szansa **{prob:.1%}** na {direction} {str(line).replace(".",",")}.\n\n'
            +detail+f'\n\nPróba: co najmniej **{n}** meczów na drużynę. '
            'To przybliżony model uwzględniający atak i statystyki dopuszczane przez przeciwnika, '
            'ale bez pełnej korekty siły rywali, składów i tempa. Bez kursu nie można ocenić opłacalności.')

def team_match_banner(game,home,away,competition,day):
    """Actual ESPN logos where provided; never fabricate badges."""
    st.markdown(f'<div class="sl-match-label">🏆 {html.escape(str(competition))} &nbsp; • &nbsp; {day:%d.%m.%Y} &nbsp; • &nbsp; {html.escape(game.get("time",""))} (PL)</div>',unsafe_allow_html=True)
    c1,mid,c2=st.columns([2,1,2],vertical_alignment='center')
    with c1:
        logo=game.get('home_logo','')
        if isinstance(logo,str) and logo.startswith('https://'):
            st.image(logo,width=72)
        else:st.markdown('### ⚽' if competition!='NBA' else '### 🏀')
        st.markdown(f'**{home}**')
    with mid:
        st.markdown('<div class="sl-vs">VS</div>',unsafe_allow_html=True)
    with c2:
        logo=game.get('away_logo','')
        if isinstance(logo,str) and logo.startswith('https://'):
            st.image(logo,width=72)
        else:st.markdown('### ⚽' if competition!='NBA' else '### 🏀')
        st.markdown(f'**{away}**')

def visual_analysis(teams,rows,sport):
    """Chart only historical, real collected data; no synthetic values."""
    if not rows:return
    st.markdown('### 📈 Forma i porównanie zespołów')
    first,second=rows
    key='Gole'
    unit='Punkty' if sport=='nba' else 'Gole'
    charts=[]
    for name,data in zip(teams,(first,second)):
        vals=[float(r[key]) for r in reversed(data[:12]) if r.get(key) is not None]
        charts.append(vals)
    if min(map(len,charts))>=3:
        count=min(map(len,charts))
        chart_df=pd.DataFrame({teams[0]:charts[0][-count:],teams[1]:charts[1][-count:]})
        chart_df.index=range(1,count+1)
        st.caption(f'{unit} w ostatnich {count} dostępnych meczach (od najstarszego do najnowszego)')
        st.line_chart(chart_df,color=['#ff963e','#28e0a0'],height=230)
    a,b=st.columns(2)
    for col,name,data in zip((a,b),teams,(first,second)):
        with col:
            scored=[float(r['Gole']) for r in data if r.get('Gole') is not None]
            conceded=[float(r['Stracone']) for r in data if r.get('Stracone') is not None]
            st.markdown(f'**{name}**')
            x,y=st.columns(2)
            x.metric('Śr. zdobyte',f'{sum(scored)/len(scored):.1f}' if scored else '—')
            y.metric('Śr. stracone',f'{sum(conceded)/len(conceded):.1f}' if conceded else '—')
            if sport=='football':
                extras=[('Strzały','Strzały'),('Celne','Celne strzały'),('Rożne','Rzuty rożne')]
                available={label:round(sum(float(r[k]) for r in data if r.get(k) is not None)/sum(r.get(k) is not None for r in data),1) for k,label in extras if any(r.get(k) is not None for r in data)}
                if available:st.bar_chart(pd.Series(available),color='#34d6b1',horizontal=True,height=155)
    st.caption('Wykresy pokazują wyłącznie pobrane wyniki historyczne. Brak statystyk nie jest uzupełniany szacunkami.')

def match_chat(context):
    key=context['id']
    if st.session_state.get('sl_chat_match')!=key:
        st.session_state.sl_chat_match=key
        st.session_state.sl_messages=[]
    st.markdown('### 💬 Zapytaj o ten mecz')
    st.caption('Pytaj o kolejne progi. Czat pamięta rozmowę dla wybranego meczu. Obliczenia korzystają z pobranych wyników, bez płatnego modelu AI.')
    for m in st.session_state.sl_messages:
        with st.chat_message(m['role']):st.markdown(m['content'])
    question=st.chat_input('Np. Real Madryt powyżej 2,5 gola?')
    if question:
        previous=next((m['content'] for m in reversed(st.session_state.sl_messages) if m['role']=='user'), '')
        # Allow follow-up thresholds: „a co z 25,5?” inherits the prior market.
        if numeric_line(question) is not None and not any(x in normalize(question) for x in ('strzal','rozn','gol','bram','punkt','pkt')) and previous:
            stem=re.sub(r'\d{1,3}(?:[.,]\d+)?','',previous)
            question_to_parse=question+' '+stem
        else:question_to_parse=question
        response=extra_analysis(question_to_parse,context)
        st.session_state.sl_messages.extend([{'role':'user','content':question},{'role':'assistant','content':response}])
        st.rerun()

st.markdown('''<div class="sl-topbar"><div class="sl-brand">↗ &nbsp;Sport<span>Lab</span> <small>4.6</small></div><div class="sl-topnote">⚽ PIŁKA NOŻNA &nbsp; • &nbsp; 🏀 NBA &nbsp; • &nbsp; 📈 ANALITYKA MECZOWA</div><div class="sl-live">● LIVE DATA</div></div>''',unsafe_allow_html=True)
with st.sidebar:
    st.markdown('''<div class="sl-side-brand">↗ Sport<span>Lab</span></div><div class="sl-side-label">CENTRUM ANALITYCZNE</div>''',unsafe_allow_html=True)
    st.markdown('### 🏠 Panel główny')
    st.markdown('⚽ Piłka nożna')
    st.markdown('🏀 NBA')
    st.markdown('💬 Czat meczowy')
    st.divider()
    st.caption('Wybierz dyscyplinę i spotkanie w głównym panelu. Czat pojawi się po analizie.')
st.markdown('''<div class="sl-page-title"><div><div class="sl-eyebrow">MATCH INTELLIGENCE / DASHBOARD</div><h1>Centrum analiz <em>SportLab</em></h1><p>Ostatnie mecze • ofensywa kontra defensywa • statystyczne propozycje • czat</p></div><div class="sl-version">SEZON 2026/27<br><strong>ANALIZA NA ŻYWO*</strong></div></div>''',unsafe_allow_html=True)
sport=st.radio('Wybierz dyscyplinę',['⚽ Piłka nożna','🏀 NBA'],horizontal=True)
day=st.date_input('Data spotkania',value=date.today())
try: api_key=st.secrets.get('THE_ODDS_API_KEY','')
except Exception:api_key=''

if sport.startswith('⚽'):
    with st.spinner('Pobieram prawdziwy terminarz...'):
        fixtures,errors=day_fixtures(day.isoformat())
    if not fixtures:
        st.warning('Nie znaleziono potwierdzonych spotkań dla tej daty lub źródło jest niedostępne.')
        if errors:
            with st.expander('Diagnostyka terminarzy'):
                for lg,err in errors.items():st.caption(f'{lg}: {err}')
    else:
        league=st.selectbox('Liga',list(fixtures))
        games=fixtures[league]
        selected=st.selectbox('Mecz (czas polski)',range(len(games)),format_func=lambda i:games[i]['label'])
        game=games[selected];h,v=game['home'],game['away']
        team_match_banner(game,h,v,league,day)
        match_id='football:'+str(day)+':'+league+':'+h+':'+v
        if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):
            st.session_state.sl_requested=match_id
        if st.session_state.get('sl_requested')==match_id:
            try:
                with st.spinner('Łączę wyniki z ligi i europejskich pucharów...'):
                    season=day.year if day.month>=7 else day.year-1
                    data=combine_football_history(league,season,game,day.isoformat())
                    rh=form(data,h,pd.Timestamp(day,tz='UTC'));rv=form(data,v,pd.Timestamp(day,tz='UTC'))
                    source_diagnostics=data.attrs.get('diagnostics',[])
                with st.expander('🔎 Diagnostyka źródeł i liczby pobranych meczów',expanded=min(len(rh),len(rv))<5):
                    st.write(f'{h}: {len(rh)} znalezionych meczów; {v}: {len(rv)} znalezionych meczów.')
                    for note in source_diagnostics:st.caption(note)
                    st.caption('Ostatnie mecze wybrano sprzed daty spotkania. Jeśli źródła zwracają błędy, skopiuj je do zgłoszenia.')
                if min(len(rh),len(rv))<5:
                    st.warning(f'Za mało dostępnych meczów po połączeniu lig krajowych i pucharów: {h} — {len(rh)}, {v} — {len(rv)}. Minimum 5. Rozwiń źródła, jeśli dostawcy nie udostępniają wyników.')
                else:
                    markets,probs,_=football_markets(h,v,rh,rv,data,pd.Timestamp(day,tz='UTC'))
                    code=LEAGUES[league][1]
                    odds_code={'E0':'soccer_epl','I1':'soccer_italy_serie_a','SP1':'soccer_spain_la_liga','D1':'soccer_germany_bundesliga','F1':'soccer_france_ligue_one'}.get(code,'')
                    analysis_col,chat_col=st.columns([1.7,1],gap='large')
                    with analysis_col:
                        render(markets,list(zip((h,'Remis',v),probs)),(h,v),(rh,rv),league+' · historyczne wyniki',api_key,odds_code)
                        visual_analysis((h,v),(rh,rv),'football')
                    with chat_col:
                        with st.container(border=True):match_chat({'id':match_id,'sport':'football','teams':(h,v),'rows':(rh,rv)})
            except Exception as exc:st.error('Nie udało się wykonać analizy: '+str(exc)[:220])
else:
    with st.spinner('Pobieram terminarz NBA...'):
        games,errors,successful=dated_sport_fixtures('nba','',day.isoformat())
    if not games:
        st.warning('Brak potwierdzonych meczów NBA na wybraną datę lub problem z pobraniem danych.')
    else:
        selected=st.selectbox('Mecz (czas polski)',range(len(games)),format_func=lambda i:games[i]['label'])
        game=games[selected];h,v=game['a'],game['b']
        match_id='nba:'+str(day)+':'+h+':'+v
        team_match_banner(game,h,v,'NBA',day)
        if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):st.session_state.sl_requested=match_id
        if st.session_state.get('sl_requested')==match_id:
            try:
                with st.spinner('Analizuję zakończone mecze NBA...'):
                    events=odds_events(api_key,'basketball_nba') if api_key else []
                    lines=available_total_lines(events,h,v)
                    markets,probs,rows=nba_markets(h,v,day,lines)
                analysis_col,chat_col=st.columns([1.7,1],gap='large')
                with analysis_col:
                    render(markets,list(zip((h,v),probs)),(h,v),rows,'NBA · ESPN',api_key,'basketball_nba')
                    visual_analysis((h,v),rows,'nba')
                with chat_col:
                    with st.container(border=True):match_chat({'id':match_id,'sport':'nba','teams':(h,v),'rows':rows,'day':day.isoformat()})
            except Exception as exc:st.error('Nie udało się wykonać analizy: '+str(exc)[:220])
    if errors:
        with st.expander('Diagnostyka terminarza'):
            for error in errors:st.caption(error)

with st.expander('Źródła i ograniczenia'):
    st.write('Piłka: ESPN (terminarz i Liga Mistrzów), Football-Data.co.uk (wyniki ligowe). NBA: ESPN. Kursy opcjonalnie z The Odds API, wyłącznie po ustawieniu THE_ODDS_API_KEY. Brak klucza nie blokuje analiz.')
    st.write('Czat to parser rynków i model historyczny, a nie generatywny chatbot. Dane zawodników NBA pobierane są na żądanie z boxscore ESPN. Nie wszystkie statystyki są dostępne; brakujące dane nie są zastępowane fikcyjnymi.')
