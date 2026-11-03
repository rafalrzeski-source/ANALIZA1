"""SportLab 3.1: independent match analysis, not a bookmaker."""
import io, math, re, unicodedata, html
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='SportLab 4.0 | Analiza sportowa', page_icon='📈', layout='wide')
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
                teams={c['homeAway']:c['team']['displayName'] for c in comp['competitors']}
                h,v=teams['home'],teams['away']
                event_id=str(event['id'])
                unique[event_id]={'id':event_id,'home':h,'away':v,'time':dt.strftime('%H:%M'),
                                  'label':f'{dt:%H:%M}  |  {h} – {v}',
                                  'completed':bool(comp.get('status',{}).get('type',{}).get('completed',False))}
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
    'fc barcelona':('barcelona','fc barcelona'),
    'inter milan':('inter','inter milan','internazionale'),
    'manchester united':('manchester united','man united','man utd','manchester utd'),
    'as roma':('as roma','roma','roma fc'),
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
    """Retrieve real domestic league results for a club before the requested match."""
    chosen=date.fromisoformat(day_iso)
    # Look up in Football-Data leagues first (team names must match unambiguously).
    frames=[];sources=[]
    for league in ['🏴 Premier League','🇮🇹 Serie A','🇪🇸 La Liga','🇩🇪 Bundesliga',
                   '🇫🇷 Ligue 1','🇳🇱 Eredivisie','🇵🇹 Primeira Liga','🇵🇱 Ekstraklasa']:
        try:
            d=league_data(league,chosen.year if chosen.month>=7 else chosen.year-1)
            names=set(d.HomeTeam.dropna())|set(d.AwayTeam.dropna())
            match=[n for n in names if same_club(n,team)]
            if len(match)==1:
                sub=d[(d.HomeTeam==match[0])|(d.AwayTeam==match[0])].copy()
                if not sub.empty:frames.append(sub);sources.append(league)
                break
        except Exception:continue
    # Additional ESPN league sources, especially Turkish Süper Lig.
    if not frames:
        # Restrict API fallback to the most likely domestic league to avoid hundreds of requests.
        key=normalize(team)
        if any(x in key for x in ['galatasaray','fenerbahce','besiktas','trabzonspor']):codes=['tur.1']
        elif any(x in key for x in ['stuttgart','bayern','dortmund','leipzig','leverkusen']):codes=['ger.1']
        else:codes=[]
        for code in codes:
            rows=[]
            for days in range(7,245,14):
                start=chosen-timedelta(days=days)
                try:
                    payload=fetch(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard',
                        {'dates':f'{start:%Y%m%d}-{start+timedelta(days=13):%Y%m%d}','limit':100}).json()
                    for ev in payload.get('events',[]):
                        c=(ev.get('competitions') or [{}])[0]
                        if not c.get('status',{}).get('type',{}).get('completed'):continue
                        competitors={x.get('homeAway'):x for x in c.get('competitors',[])}
                        if not {'home','away'}.issubset(competitors):continue
                        h,v=competitors['home'],competitors['away']
                        hn=h['team']['displayName'];vn=v['team']['displayName']
                        if not (same_club(team,hn) or same_club(team,vn)):continue
                        rows.append({'Date':ev['date'],'HomeTeam':hn,'AwayTeam':vn,
                                     'FTHG':float(h['score']),'FTAG':float(v['score'])})
                except Exception:continue
                if len(rows)>=10:break
            if rows:
                frames.append(clean_match_data(pd.DataFrame(rows)));sources.append('ESPN '+code);break
    if not frames:return pd.DataFrame(),[]
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam']),sources

def form(df,team,cutoff,n=15):
    d=df[((df.HomeTeam==team)|(df.AwayTeam==team))&(df.MatchDate<cutoff)].sort_values('MatchDate',ascending=False).head(n)
    rows=[]
    for _,r in d.iterrows():
        home=r.HomeTeam==team;f=float(r.FTHG if home else r.FTAG);a=float(r.FTAG if home else r.FTHG)
        v={'Data':str(r.MatchDate.date()),'Rywal':r.AwayTeam if home else r.HomeTeam,'Wynik':f'{f:.0f}:{a:.0f}',
           'Gole':f,'Stracone':a,'Rezultat':'W' if f>a else 'R' if f==a else 'P'}
        for key,cols in [('Strzały',('HS','AS')),('Rożne',('HC','AC')),('Celne',('HST','AST'))]:
            col=cols[0 if home else 1];v[key]=float(r[col]) if col in r and pd.notna(r[col]) else None
        for k,cols in [('Strzały rywala',('AS','HS')),('Rożne rywala',('AC','HC'))]:
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
    # Only real, observed shot counts, not made-up figures.
    for team,rows in [(h,rh),(v,rv)]:
        vals=[float(r['Strzały']) for r in rows if r.get('Strzały') is not None]
        if len(vals)>=6:
            for line in (7.5,9.5,11.5,13.5,15.5):
                p=(sum(x>line for x in vals)+2)/(len(vals)+4)
                why=f'{team}: średnio {sum(vals)/len(vals):.1f} strzału w {len(vals)} meczach z dostępnymi danymi. Szacunek oparty na częstości historycznej, bez korekty siły przeciwnika.'
                markets.extend([make_market(f'{team}: powyżej {str(line).replace(".",",")} strzału',p,why,len(vals)),make_market(f'{team}: poniżej {str(line).replace(".",",")} strzału',1-p,why,len(vals))])
    totals=[]
    for r in hist.sort_values('MatchDate',ascending=False).head(160).itertuples():
        if hasattr(r,'HS') and hasattr(r,'AS') and pd.notna(r.HS) and pd.notna(r.AS):totals.append(float(r.HS+r.AS))
    if len(totals)>=12:
        for line in (19.5,23.5,27.5,29.5):
            p=(sum(x>line for x in totals)+1)/(len(totals)+2)
            why=f'W {len(totals)} ostatnich meczach ligi z danymi średnia wynosi {sum(totals)/len(totals):.1f} strzału. To orientacyjny szacunek ligowy.'
            markets.extend([make_market(f'Powyżej {str(line).replace(".",",")} strzału w meczu',p,why,len(totals)),make_market(f'Poniżej {str(line).replace(".",",")} strzału w meczu',1-p,why,len(totals))])
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
    # For tennis, draw order is not a home/away advantage.
    return tuple(names)

@st.cache_data(ttl=1200,show_spinner=False)
def dated_sport_fixtures(kind,tour,day_iso):
    """Read real ESPN schedule around local date, deduplicate, never invent fixtures."""
    chosen=date.fromisoformat(day_iso)
    path=('basketball/nba' if kind=='nba' else 'tennis/'+tour.lower())
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
            comps=list(espn_tennis_competitions(event)) if kind=='tennis' else list(event.get('competitions') or [])
            for index,comp in enumerate(comps):
                pair=espn_competitors(comp,kind)
                if not pair:continue
                raw_time=comp.get('date') or event.get('date')
                when=local_event_time(raw_time)
                if when is None or when.date()!=chosen:continue
                if kind=='tennis':
                    ctype=comp.get('type') or {}
                    typename=str(ctype.get('text','') if isinstance(ctype,dict) else ctype).lower()
                    if 'double' in typename or 'mixed' in typename or any('/' in n or n.upper()=='TBD' for n in pair):continue
                label=f'{when:%H:%M} | {pair[0]} – {pair[1]}'
                cid=str(comp.get('id') or index)
                event_id=str(event.get('id') or '')
                key=(event_id,cid,tuple(pair))
                found[key]={'id':event_id,'competition_id':cid,'a':pair[0],'b':pair[1],
                            'label':label,'time':when.strftime('%H:%M'),
                            'timestamp':when.isoformat(),'source':'ESPN',
                            'completed':bool((comp.get('status') or {}).get('type',{}).get('completed',False))}
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
    if min(len(rh),len(ra))<5:raise ValueError('Za mało zakończonych meczów NBA w ostatnich 50 dniach.')
    ph=(mean(rh,'Gole')+mean(ra,'Stracone'))/2+1.5;pa=(mean(ra,'Gole')+mean(rh,'Stracone'))/2-1.5
    p=1/(1+math.exp(-(ph-pa)/13));n=min(len(rh),len(ra))
    why=f'Średnie z ostatnich spotkań: {h} {mean(rh,"Gole"):.1f} pkt, {a} {mean(ra,"Gole"):.1f} pkt. Model oczekuje około {ph:.1f}–{pa:.1f}. Bez kontuzji i składów.'
    markets=[make_market(f'{h} wygra',p,why,n),make_market(f'{a} wygra',1-p,why,n)]
    # Normal approximation of total points, using a fixed conservative spread (not validated).
    for line in sorted(set(lines or [])):
        z=(line-(ph+pa))/(18*math.sqrt(2));q=.5*math.erfc(z)
        markets.extend([make_market(f'Powyżej {str(line).replace(".",",")} punktu',q,why+' Model sumy punktów jest przybliżony.',n),make_market(f'Poniżej {str(line).replace(".",",")} punktu',1-q,why+' Model sumy punktów jest przybliżony.',n)])
    # No ladder of arbitrary totals. If no real market line is available,
    # show at most one clearly labeled descriptive total from the matchup model.
    if not lines:
        line=math.floor((ph+pa)/10)*10-0.5
        totals=[r['Gole']+r['Stracone'] for r in rh+ra]
        if len(totals)>=16:
            wins=sum(t>line for t in totals)
            q=(wins+3)/(len(totals)+6)
            markets.append(make_market(f'Łącznie powyżej {str(line).replace(".",",")} pkt (próg modelowy)',q,
                f'{wins}/{len(totals)} wcześniejszych spotkań obu zespołów przekroczyło próg. To NIE linia bukmachera.',len(totals)))
    # A team points market is offered only when a provider verifies a line.
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


# SportLab 4.0: extra questions use only verified historical data.
def numeric_line(question):
    match=re.search(r'(\d{1,3}(?:[.,]\d+)?)',question)
    return float(match.group(1).replace(',','.')) if match else None

def extra_analysis(question,context):
    q=normalize(question);line=numeric_line(question)
    if line is None:return 'Podaj konkretny próg, np. „powyżej 30,5 strzału” albo „poniżej 225,5 punktu”.'
    over=not any(word in q for word in ('ponizej','mniej','under'))
    is_nba=context['sport']=='nba'
    kind='points' if is_nba else ('shots' if 'strzal' in q else 'corners' if 'rozn' in q else 'goals' if 'gol' in q or 'bram' in q else None)
    if kind is None:return 'Nie rozpoznaję tego rynku. W piłce obsługuję gole, strzały i rożne; w NBA punkty drużyn i sumę punktów. Dla zawodników potrzebne są osobne dane meczowe.'
    if is_nba and any(w in q for w in ('zawodnik','gracz','lebron','tatum','doncic','jokic','curry')):
        return 'Analiza konkretnego zawodnika wymaga zweryfikowanych statystyk meczowych tego zawodnika. Nie mam ich w obecnym zestawie wyników drużyn, więc nie podaję fikcyjnego procentu.'
    rows=context['rows'];names=context['teams'];team=None
    for idx,name in enumerate(names):
        if normalize(name) in q or any(part in q for part in normalize(name).split() if len(part)>5):team=idx;break
    if kind=='points':field='Gole';against='Stracone'
    elif kind=='goals':field='Gole';against='Stracone'
    elif kind=='shots':field='Strzały';against='Strzały rywala'
    else:field='Rożne';against='Rożne rywala'
    # For totals: each team's recent match total = own + conceded, when verified.
    samples=[];descs=[]
    for idx,teamrows in enumerate(rows):
        vals=[]
        for r in teamrows:
            val=r.get(field)
            if val is None:continue
            if team is not None and idx!=team:continue
            if team is None:
                if against is None:continue  # never assume team shots equal match shots
                opp=r.get(against)
                if opp is None:continue
                val=float(val)+float(opp)
            vals.append(float(val))
        if vals:
            samples.extend(vals)
            descs.append(f'{names[idx]}: '+', '.join(str(round(x,1)).replace('.',',') for x in vals[:10]))
    if not samples:
        if team is None and kind in ('shots','corners'):
            return 'Nie mogę rzetelnie obliczyć ŁĄCZNEJ liczby strzałów lub rożnych: dostępne dane zawierają statystyki drużyn, ale nie zawsze sumy z obu stron każdego meczu. Wpisz nazwę drużyny, np. „Real Madryt powyżej 15,5 strzału”, albo wybierz ligę z kompletnymi statystykami.'
        return f'Brak zweryfikowanych danych dla rynku {kind} i wskazanego zespołu. Nie obliczam prawdopodobieństwa bez próby.'
    n=len(samples)
    if n<6:return f'Znaleziono tylko {n} meczów z tymi statystykami. Potrzeba co najmniej 6, aby pokazać ocenę.\n\n'+ '\n\n'.join(descs)
    hits=sum((x>line if over else x<line) for x in samples)
    # Jeffreys-like smoothing avoids 0% and 100% on small samples
    prob=(hits+1)/(n+2)
    verdict='Dobry pomysł pod względem szansy trafienia' if prob>=.65 else 'Ryzykowny pomysł' if prob>=.45 else 'Zły pomysł pod względem szansy trafienia'
    direction='powyżej' if over else 'poniżej'
    return (f'**{verdict}** — szacowana szansa **{prob:.1%}** dla {direction} {str(line).replace(".",",")} ({"punkty" if is_nba else kind}).\n\n'
            f'Próg spełniono w **{hits} z {n}** ostatnich dostępnych występów (średnia: **{sum(samples)/n:.1f}**). '
            f'Wyniki użyte w analizie:\n\n'+ '\n\n'.join(descs)+
            '\n\nTo częstość historyczna z wygładzeniem, nie gwarancja ani ocena opłacalności bez kursu. Dane dotyczą ostatnich występów, nie zawsze podobnych rywali.')

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
        if not any(x in normalize(question) for x in ('strzal','rozn','gol','bram','punkt','pkt')) and previous:
            stem=re.sub(r'\d{1,3}(?:[.,]\d+)?','',previous)
            question_to_parse=question+' '+stem
        else:question_to_parse=question
        response=extra_analysis(question_to_parse,context)
        st.session_state.sl_messages.extend([{'role':'user','content':question},{'role':'assistant','content':response}])
        st.rerun()

st.markdown('<div class="sl-kicker">SPORTLAB / 4.0</div>',unsafe_allow_html=True)
st.title('Twój panel analiz sportowych')
st.caption('⚡ Prawdziwe terminarze · 📊 Historia spotkań · 💬 Pytania o własne rynki')
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
        st.caption(f'{day:%d.%m.%Y} · {game["time"]} · Europe/Warsaw · terminarz ESPN')
        match_id='football:'+str(day)+':'+league+':'+h+':'+v
        if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):
            st.session_state.sl_requested=match_id
        if st.session_state.get('sl_requested')==match_id:
            try:
                with st.spinner('Łączę wyniki z ligi i europejskich pucharów...'):
                    season=day.year if day.month>=7 else day.year-1
                    data=league_data(league,season)
                    if LEAGUES[league][0]=='espn':
                        extra=[]
                        for club in (h,v):
                            domestic,sources=domestic_history(club,day.isoformat())
                            if not domestic.empty:extra.append(align_club_names(domestic,club))
                        if extra:data=pd.concat([data]+extra,ignore_index=True).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])
                    data=align_club_names(align_club_names(data,h),v)
                    rh=form(data,h,pd.Timestamp(day,tz='UTC'));rv=form(data,v,pd.Timestamp(day,tz='UTC'))
                if min(len(rh),len(rv))<5:
                    st.warning(f'Za mało danych: {h} — {len(rh)}, {v} — {len(rv)} meczów. Minimum 5 na drużynę.')
                else:
                    markets,probs,_=football_markets(h,v,rh,rv,data,pd.Timestamp(day,tz='UTC'))
                    code=LEAGUES[league][1]
                    odds_code={'E0':'soccer_epl','I1':'soccer_italy_serie_a','SP1':'soccer_spain_la_liga','D1':'soccer_germany_bundesliga','F1':'soccer_france_ligue_one'}.get(code,'')
                    render(markets,list(zip((h,'Remis',v),probs)),(h,v),(rh,rv),league+' · historyczne wyniki',api_key,odds_code)
                    match_chat({'id':match_id,'sport':'football','teams':(h,v),'rows':(rh,rv)})
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
        st.caption(f'{day:%d.%m.%Y} · {game["time"]} · Europe/Warsaw · terminarz ESPN')
        if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):st.session_state.sl_requested=match_id
        if st.session_state.get('sl_requested')==match_id:
            try:
                with st.spinner('Analizuję zakończone mecze NBA...'):
                    events=odds_events(api_key,'basketball_nba') if api_key else []
                    lines=available_total_lines(events,h,v)
                    markets,probs,rows=nba_markets(h,v,day,lines)
                render(markets,list(zip((h,v),probs)),(h,v),rows,'NBA · ESPN',api_key,'basketball_nba')
                match_chat({'id':match_id,'sport':'nba','teams':(h,v),'rows':rows})
            except Exception as exc:st.error('Nie udało się wykonać analizy: '+str(exc)[:220])
    if errors:
        with st.expander('Diagnostyka terminarza'):
            for error in errors:st.caption(error)

with st.expander('Źródła i ograniczenia'):
    st.write('Piłka: ESPN (terminarz i Liga Mistrzów), Football-Data.co.uk (wyniki ligowe). NBA: ESPN. Kursy opcjonalnie z The Odds API, wyłącznie po ustawieniu THE_ODDS_API_KEY. Brak klucza nie blokuje analiz.')
    st.write('Czat to parser rynków i model historyczny, a nie generatywny chatbot. Nie wszystkie statystyki, zwłaszcza zawodników NBA i łączne strzały, są dostępne w bazie. W takich przypadkach aplikacja zgłasza brak danych zamiast podawać wymyślone szanse.')
