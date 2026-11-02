"""SportLab 3.1: independent match analysis, not a bookmaker."""
import io, math, re, unicodedata, html
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='SportLab 3.6 | Analiza sportowa', page_icon='📈', layout='wide')
st.markdown('''<style>
:root{color-scheme:dark} .stApp{background:radial-gradient(circle at 80% 0%,#182a46 0,#0a101d 46%,#090e19 100%);color:#eef3fb}
.block-container{max-width:1160px;padding-top:1.7rem;padding-bottom:4rem}
h1,h2,h3{letter-spacing:-.025em} h1{font-size:2.65rem!important}
[data-testid="stMetric"]{background:#17243a;border:1px solid #2b3c56;border-radius:15px;padding:17px}
[data-testid="stMetricValue"]{color:#f3f7ff} [data-testid="stMetricLabel"]{color:#a7bad5}
div.stButton>button[kind="primary"]{background:#4d74ec;border:0;border-radius:12px;padding:.65rem 1.2rem}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
.sl-hero{border:1px solid #30435d;border-radius:22px;padding:22px 25px;background:linear-gradient(115deg,#162742,#111b2e);margin:8px 0 22px}
.sl-kicker{font-size:12px;letter-spacing:2px;color:#95b3ff;font-weight:700}
.sl-sub{color:#a8b8cf;font-size:14px;margin-top:7px}
.sl-card{background:#142338;border:1px solid #30425b;border-radius:17px;padding:19px;margin:10px 0}
.sl-main{background:linear-gradient(125deg,#103e34,#122e32);border-color:#276c59}
.sl-tag{font-size:12px;letter-spacing:1.4px;font-weight:700;color:#76e3b4}
.sl-name{font-size:24px;font-weight:750;line-height:1.3;margin:8px 0 13px}
.sl-explain{font-size:14px;color:#d2e0ed;line-height:1.7;margin-top:10px}
.sl-note{color:#9fb0c8;font-size:12px}
.sl-grid{display:flex;gap:16px;flex-wrap:wrap}.sl-stat{min-width:120px;flex:1}
.sl-value{font-size:27px;font-weight:800}.sl-label{font-size:12px;color:#b3c8d9}
.sl-pill{display:inline-block;border:1px solid #47627b;border-radius:30px;padding:5px 12px;color:#bed0e4;font-size:12px}
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
            match=[n for n in names if normalize(n)==normalize(team)]
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
            for days in range(7,105,7):
                start=chosen-timedelta(days=days)
                try:
                    payload=fetch(f'https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard',
                        {'dates':f'{start:%Y%m%d}-{start+timedelta(days=6):%Y%m%d}','limit':100}).json()
                    for ev in payload.get('events',[]):
                        c=(ev.get('competitions') or [{}])[0]
                        if not c.get('status',{}).get('type',{}).get('completed'):continue
                        competitors={x.get('homeAway'):x for x in c.get('competitors',[])}
                        if not {'home','away'}.issubset(competitors):continue
                        h,v=competitors['home'],competitors['away']
                        hn=h['team']['displayName'];vn=v['team']['displayName']
                        if normalize(team) not in (normalize(hn),normalize(vn)):continue
                        rows.append({'Date':ev['date'],'HomeTeam':hn,'AwayTeam':vn,
                                     'FTHG':float(h['score']),'FTAG':float(v['score'])})
                except Exception:continue
                if len(rows)>=10:break
            if rows:
                frames.append(clean_match_data(pd.DataFrame(rows)));sources.append('ESPN '+code);break
    if not frames:return pd.DataFrame(),[]
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam']),sources

def form(df,team,cutoff,n=12):
    d=df[((df.HomeTeam==team)|(df.AwayTeam==team))&(df.MatchDate<cutoff)].sort_values('MatchDate',ascending=False).head(n)
    rows=[]
    for _,r in d.iterrows():
        home=r.HomeTeam==team;f=float(r.FTHG if home else r.FTAG);a=float(r.FTAG if home else r.FTHG)
        v={'Data':str(r.MatchDate.date()),'Rywal':r.AwayTeam if home else r.HomeTeam,'Wynik':f'{f:.0f}:{a:.0f}',
           'Gole':f,'Stracone':a,'Rezultat':'W' if f>a else 'R' if f==a else 'P'}
        for key,cols in [('Strzały',('HS','AS')),('Rożne',('HC','AC')),('Celne',('HST','AST'))]:
            col=cols[0 if home else 1];v[key]=float(r[col]) if col in r and pd.notna(r[col]) else None
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
                p=(sum(x>line for x in vals)+1)/(len(vals)+2)
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
@st.cache_data(ttl=86400,show_spinner=False)
def tennis_year(year):
    url=f'https://www.valuebetennis.com/datasets/valuebetennis-matchs-{year}.csv'
    d=csv(url)
    d.columns=[str(c).strip().lower() for c in d.columns]
    needed={'date','genre','joueur1','joueur2','joueur1_id','joueur2_id','vainqueur_id'}
    if not needed.issubset(d):raise ValueError('Niepoprawny format Valuebetennis')
    d['MatchDate']=pd.to_datetime(d['date'],utc=True,errors='coerce').dt.tz_localize(None)
    # Winner is identified by ID, not by player order.
    d['winner_name']=d['joueur1'].where(d['joueur1_id'].astype(str)==d['vainqueur_id'].astype(str),d['joueur2'])
    d['loser_name']=d['joueur2'].where(d['joueur1_id'].astype(str)==d['vainqueur_id'].astype(str),d['joueur1'])
    d=d.dropna(subset=['winner_name','loser_name','MatchDate'])
    return d
@st.cache_data(ttl=86400,show_spinner=False)
def tennis_espn(tour,year):
    """Alternative ESPN ATP/WTA scoreboard feed, using actual completed events."""
    slug='atp' if tour=='ATP' else 'wta'
    url=f'https://site.api.espn.com/apis/site/v2/sports/tennis/{slug}/scoreboard'
    rows=[]
    # Short date windows prevent server 400 responses.
    end=min(date.today(),date(year,12,31))
    start=end-timedelta(days=150)
    for offset in range(0,(end-start).days+1,7):
        d=start+timedelta(days=offset);e=min(d+timedelta(days=6),end)
        try:events=fetch(url,{'dates':f'{d:%Y%m%d}-{e:%Y%m%d}','limit':200}).json().get('events',[])
        except Exception:continue
        for event in events:
            for comp in event.get('competitions',[]):
                try:
                    if not comp['status']['type']['completed']:continue
                    competitors=comp['competitors']
                    if len(competitors)!=2:continue
                    winner=next(c for c in competitors if c.get('winner') is True)
                    loser=next(c for c in competitors if c is not winner)
                    def name(c):
                        t=c.get('athlete') or c.get('team') or {}
                        return t.get('displayName') or c.get('displayName') or ''
                    w,l=name(winner),name(loser)
                    if w and l:rows.append({'MatchDate':event['date'],'winner_name':w,'loser_name':l})
                except (KeyError,StopIteration,TypeError):continue
    if not rows:return pd.DataFrame()
    d=pd.DataFrame(rows)
    d['MatchDate']=pd.to_datetime(d.MatchDate,utc=True,errors='coerce').dt.tz_localize(None)
    return d.dropna().drop_duplicates(subset=['MatchDate','winner_name','loser_name'])

@st.cache_data(ttl=21600,show_spinner=False)
def tennis_data(tour,year):
    """Independent verified archives; expose failures instead of silently swallowing them."""
    frames, sources, diagnostics = [], [], []
    years=list(range(min(year,2026),max(2022,min(year,2026)-2)-1,-1))
    for y in years:
        try:
            d=tennis_year(y)
            filtered=d[d.genre.astype(str).str.strip().str.lower()==tour.lower()]
            if not filtered.empty:
                frames.append(filtered[['MatchDate','winner_name','loser_name']])
                sources.append(f'Valuebetennis {y}')
            else:
                diagnostics.append(f'Valuebetennis {y}: brak meczów {tour}')
        except Exception as exc:
            diagnostics.append(f'Valuebetennis {y}: {str(exc)[:120]}')
    # Independent public archives. Sources are attempted independently; failed endpoints are reported.
    # Jeff Sackmann repositories are CC BY-NC-SA and intended for non-commercial use.
    for y in years:
        if any(f' {y}' in src for src in sources):
            continue
        for origin,url in [
            ('JeffSackmann',f'https://raw.githubusercontent.com/JeffSackmann/tennis_{tour.lower()}/master/{tour.lower()}_matches_{y}.csv'),
            ('tennis-data.co.uk',f'https://www.tennis-data.co.uk/{y}/{tour.lower()}.csv'),
        ]:
            try:
                d=csv(url)
                d.columns=[str(c).strip().lower() for c in d.columns]
                if {'winner_name','loser_name','tourney_date'}.issubset(d.columns):
                    raw=d.tourney_date.astype(str).str.replace(r'\.0$','',regex=True)
                    dt=pd.to_datetime(raw,format='%Y%m%d',errors='coerce')
                    t=pd.DataFrame({'MatchDate':dt,'winner_name':d.winner_name,'loser_name':d.loser_name}).dropna()
                elif {'winner','loser','date'}.issubset(d.columns):
                    t=pd.DataFrame({'MatchDate':pd.to_datetime(d.date,errors='coerce',dayfirst=True),
                                    'winner_name':d.winner,'loser_name':d.loser}).dropna()
                else:raise ValueError('Nieobsługiwany format archiwum')
                if t.empty:raise ValueError('Archiwum jest puste')
                frames.append(t);sources.append(f'{origin} {y}')
                break
            except Exception as exc:
                diagnostics.append(f'{origin} {y}: {str(exc)[:110]}')
    if not frames:
        # ESPN may expose match results, but not necessarily the full archive.
        try:
            d=tennis_espn(tour,year)
            if not d.empty:
                frames.append(d)
                sources.append('ESPN tenis')
            else:
                diagnostics.append('ESPN: brak poprawnych wyników')
        except Exception as exc:
            diagnostics.append(f'ESPN: {str(exc)[:120]}')
    if not frames:
        return pd.DataFrame(columns=['MatchDate','winner_name','loser_name']),[],diagnostics
    d=pd.concat(frames,ignore_index=True)
    d['MatchDate']=pd.to_datetime(d.MatchDate,utc=True,errors='coerce').dt.tz_localize(None)
    d=d.dropna(subset=['MatchDate','winner_name','loser_name'])
    d=d[(d.winner_name.astype(str).str.strip()!='') & (d.loser_name.astype(str).str.strip()!='')]
    return d.drop_duplicates(subset=['MatchDate','winner_name','loser_name']),list(dict.fromkeys(sources)),diagnostics

def parse_tennis_upload(file):
    """Import real match results from an uploaded ATP/WTA season CSV."""
    raw=file.getvalue()
    try:d=pd.read_csv(io.BytesIO(raw),sep=None,engine='python')
    except Exception as exc:raise ValueError(f'Nie udało się odczytać CSV: {exc}')
    d.columns=[str(x).strip().lower() for x in d.columns]
    def col(*candidates):
        for c in candidates:
            if c in d.columns:return c
        return None
    datecol=col('date','match_date','start_time','start_date','tourney_date','matchdate')
    if not datecol:raise ValueError('Brak kolumny daty (date/match_date).')
    d['MatchDate']=pd.to_datetime(d[datecol],errors='coerce',dayfirst=False,utc=True).dt.tz_localize(None)
    w=col('winner_name','winner','winning_player','winner_player')
    l=col('loser_name','loser','losing_player','loser_player')
    if w and l:
        d['winner_name']=d[w];d['loser_name']=d[l]
    else:
        h=col('home_player_name','home_name','home_player','player1','player_1','joueur1')
        a=col('away_player_name','away_name','away_player','player2','player_2','joueur2')
        wc=col('winner_code','winner_id','winner_side')
        if not all([h,a,wc]):raise ValueError('CSV wymaga winner_name/loser_name albo home_player_name/away_player_name/winner_code.')
        code=pd.to_numeric(d[wc],errors='coerce')
        d['winner_name']=d[h].where(code==1,d[a].where(code==2))
        d['loser_name']=d[a].where(code==1,d[h].where(code==2))
    d=d.dropna(subset=['MatchDate','winner_name','loser_name']).copy()
    d['winner_name']=d['winner_name'].astype(str).str.strip()
    d['loser_name']=d['loser_name'].astype(str).str.strip()
    return d[['MatchDate','winner_name','loser_name']].drop_duplicates()

def tennis_markets(df,a,b,cutoff):
    past=df[df.MatchDate<cutoff].sort_values('MatchDate',ascending=False)
    ra=past[(past.winner_name==a)|(past.loser_name==a)].head(30)
    rb=past[(past.winner_name==b)|(past.loser_name==b)].head(30)
    if min(len(ra),len(rb))<6:raise ValueError(f'Za mało historycznych spotkań: {a} — {len(ra)}, {b} — {len(rb)}. Potrzeba co najmniej 6.')
    wa=(ra.winner_name==a).sum();wb=(rb.winner_name==b).sum()
    fa=(wa+2)/(len(ra)+4);fb=(wb+2)/(len(rb)+4)
    # Relative strength of recent win rates, conservative shrinkage toward 50%.
    p=.5+.75*(fa-fb);p=max(.15,min(.85,p))
    why=f'{a}: {wa}/{len(ra)} wygranych ({wa/len(ra):.0%}); {b}: {wb}/{len(rb)} ({wb/len(rb):.0%}). Szacunek oparty na formie, bez rankingu i kontuzji.'
    markets=[make_market(f'{a} wygra mecz',p,why,min(len(ra),len(rb))),make_market(f'{b} wygra mecz',1-p,why,min(len(ra),len(rb)))]
    # Set/game markets need verified score-by-set data and a separately calibrated model.
    return markets,(p,1-p),(ra,rb)

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
            event_id=str(event.get('id',''))
            for index,comp in enumerate(event.get('competitions') or []):
                pair=espn_competitors(comp,kind)
                if not pair:continue
                # Individual tennis match times can be in competitions, while
                # the event time can represent a whole tournament session.
                raw_time=comp.get('date') or event.get('date')
                when=local_event_time(raw_time)
                if when is None or when.date()!=chosen:continue
                if kind=='tennis':
                    # Tennis competitions can contain doubles; only analyse singles.
                    ctype=comp.get('type') or {}
                    typename=str(ctype.get('text','') if isinstance(ctype,dict) else ctype).lower()
                    if 'double' in typename or any('/' in n for n in pair):continue
                label=f'{when:%H:%M} | {pair[0]} – {pair[1]}'
                cid=str(comp.get('id') or index)
                key=(event_id,cid,tuple(pair))
                found[key]={'id':event_id,'competition_id':cid,'a':pair[0],'b':pair[1],
                            'label':label,'time':when.strftime('%H:%M'),
                            'timestamp':when.isoformat(),
                            'completed':bool((comp.get('status') or {}).get('type',{}).get('completed',False))}
    return sorted(found.values(),key=lambda x:(x['timestamp'],x['a'],x['b'])),errors,successful

@st.cache_data(ttl=1200,show_spinner=False)
def tennis_alternative_fixtures(tour,day_iso):
    """Try independent schedule providers, never generate matches from names alone."""
    chosen=date.fromisoformat(day_iso)
    matches={}; diagnostics=[];ok=0
    # SofaScore daily schedule; its public endpoint may rate-limit or block cloud servers.
    try:
        payload=fetch(f'https://www.sofascore.com/api/v1/sport/tennis/scheduled-events/{day_iso}').json()
        events=payload.get('events',[])
        if not isinstance(events,list):raise ValueError('Brak listy wydarzeń')
        ok+=1
        for ev in events:
            category=ev.get('tournament',{}).get('category',{})
            info=' '.join(str(x) for x in [category.get('name',''),ev.get('tournament',{}).get('name','')]).lower()
            if tour.lower() not in info:continue
            home=ev.get('homeTeam') or {};away=ev.get('awayTeam') or {}
            a=home.get('name');b=away.get('name')
            if not a or not b or '/' in a or '/' in b:continue
            stamp=ev.get('startTimestamp')
            if not isinstance(stamp,(int,float)):continue
            when=datetime.fromtimestamp(stamp,ZoneInfo('UTC')).astimezone(POLISH_TZ)
            if when.date()!=chosen:continue
            key=(normalize(a),normalize(b),when.isoformat())
            matches[key]={'a':a,'b':b,'label':f'{when:%H:%M} | {a} – {b}',
                'time':when.strftime('%H:%M'),'timestamp':when.isoformat(),'source':'SofaScore'}
    except Exception as exc:diagnostics.append(f'SofaScore: {str(exc)[:130]}')
    # TheSportsDB free API: coverage varies by tournament and day.
    try:
        payload=fetch('https://www.thesportsdb.com/api/v1/json/3/eventsday.php',
                      {'d':day_iso,'s':'Tennis'}).json()
        events=payload.get('events') or []
        if not isinstance(events,list):raise ValueError('Niepoprawne dane')
        ok+=1
        for ev in events:
            text=' '.join(str(ev.get(k) or '') for k in ['strLeague','strEvent']).lower()
            if tour.lower() not in text:continue
            a=ev.get('strHomeTeam');b=ev.get('strAwayTeam')
            if not a or not b or '/' in a or '/' in b:continue
            when=local_event_time(ev.get('strTimestamp') or f'{ev.get("dateEvent",day_iso)}T{ev.get("strTime") or "12:00:00"}Z')
            if when is None or when.date()!=chosen:continue
            key=(normalize(a),normalize(b),when.isoformat())
            matches[key]={'a':a,'b':b,'label':f'{when:%H:%M} | {a} – {b}',
                'time':when.strftime('%H:%M'),'timestamp':when.isoformat(),'source':'TheSportsDB'}
    except Exception as exc:diagnostics.append(f'TheSportsDB: {str(exc)[:130]}')
    return sorted(matches.values(),key=lambda x:x['timestamp']),diagnostics,ok

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
    for i in range(1,51):
        try:games=nba_day(day-timedelta(days=i))
        except Exception:continue
        for (hn,hs),(an,as_) in games:
            records.setdefault(hn,[]).append({'Gole':hs,'Stracone':as_,'Data':str(day-timedelta(days=i)),'Rywal':an,'Wynik':f'{hs:.0f}:{as_:.0f}'})
            records.setdefault(an,[]).append({'Gole':as_,'Stracone':hs,'Data':str(day-timedelta(days=i)),'Rywal':hn,'Wynik':f'{as_:.0f}:{hs:.0f}'})
    rh=records.get(h,[])[:12];ra=records.get(a,[])[:12]
    if min(len(rh),len(ra))<5:raise ValueError('Za mało zakończonych meczów NBA w ostatnich 50 dniach.')
    ph=(mean(rh,'Gole')+mean(ra,'Stracone'))/2+1.5;pa=(mean(ra,'Gole')+mean(rh,'Stracone'))/2-1.5
    p=1/(1+math.exp(-(ph-pa)/13));n=min(len(rh),len(ra))
    why=f'Średnie z ostatnich spotkań: {h} {mean(rh,"Gole"):.1f} pkt, {a} {mean(ra,"Gole"):.1f} pkt. Model oczekuje około {ph:.1f}–{pa:.1f}. Bez kontuzji i składów.'
    markets=[make_market(f'{h} wygra',p,why,n),make_market(f'{a} wygra',1-p,why,n)]
    # Normal approximation of total points, using a fixed conservative spread (not validated).
    for line in sorted(set(lines or [])):
        z=(line-(ph+pa))/(18*math.sqrt(2));q=.5*math.erfc(z)
        markets.extend([make_market(f'Powyżej {str(line).replace(".",",")} punktu',q,why+' Model sumy punktów jest przybliżony.',n),make_market(f'Poniżej {str(line).replace(".",",")} punktu',1-q,why+' Model sumy punktów jest przybliżony.',n)])
    # Statistical point thresholds are explicitly NOT bookmaker lines.
    # Empirical frequencies from actual completed games; no fabricated prices.
    totals=[r['Gole']+r['Stracone'] for r in rh+ra]
    for line in [199.5,209.5,219.5,229.5,239.5,249.5]:
        if len(totals)>=10:
            q=sum(t>line for t in totals)/len(totals)
            explanation=(f'Historyczny odsetek przekroczeń progu {line:g} pkt w {len(totals)} '
                         'ostatnich meczach obu drużyn. To próg statystyczny, NIE zweryfikowana linia bukmachera.')
            markets.extend([make_market(f'Łącznie ponad {str(line).replace(".",",")} pkt (próg statystyczny)',q,explanation,len(totals)),
                            make_market(f'Łącznie poniżej {str(line).replace(".",",")} pkt (próg statystyczny)',1-q,explanation,len(totals))])
    for team,rows in [(h,rh),(a,ra)]:
        for line in [99.5,109.5,119.5]:
            q=sum(r['Gole']>line for r in rows)/len(rows)
            explanation=f'{team}: {sum(r["Gole"]>line for r in rows)}/{len(rows)} ostatnich meczów powyżej progu. Próg statystyczny, nie kurs bukmachera.'
            markets.append(make_market(f'{team} ponad {str(line).replace(".",",")} pkt (próg statystyczny)',q,explanation,len(rows)))
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
    eligible=[m for m in markets if m['n']>=5 and 0.08<=m['p']<=0.92 and not ('4,5 gola' in m['name'])]
    # Avoid misleading near-certain, low-value suggestions; this is not an odds filter.
    eligible.sort(key=lambda m:m['p'],reverse=True)
    picks=eligible[:4]
    st.markdown(f'<div class="sl-hero"><div class="sl-kicker">ANALIZA SPOTKANIA</div><h2 style="margin:9px 0">{html.escape(teams[0])} &nbsp; <span style="color:#7992b2">VS</span> &nbsp; {html.escape(teams[1])}</h2><div class="sl-sub">{html.escape(source)} · Szacunki na podstawie danych historycznych, nie gwarancja wyniku</div></div>',unsafe_allow_html=True)
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

st.markdown('<div class="sl-kicker">SPORTLAB / 3.6</div>',unsafe_allow_html=True)
st.title('Analiza sportowa. Bez zgadywania danych.')
st.caption('Wybierz datę, ligę i mecz z prawdziwego terminarza. Zobacz szacunki i wyjaśnienie. Kursy wyświetlamy wyłącznie z rzeczywistego źródła.')
sport=st.radio('Dyscyplina',['⚽ Piłka nożna','🎾 Tenis','🏀 NBA'],horizontal=True)
day=st.date_input('Data spotkania',value=date.today())
try: api_key=st.secrets.get('THE_ODDS_API_KEY','')
except Exception:api_key=''

if sport.startswith('⚽'):
    st.markdown('#### 📅 Mecze w wybranym dniu')
    with st.spinner('Sprawdzam terminarze lig dla wybranej daty...'):
        fixtures,fixture_errors=day_fixtures(day.isoformat())
    if not fixtures:
        st.warning('Nie znaleziono potwierdzonych meczów w wybranym dniu. Może nie być spotkań albo terminarze są chwilowo niedostępne. Nie pokazuję wymyślonych par.')
        if fixture_errors:
            with st.expander('Szczegóły dostępności terminarzy'):
                for lg,err in fixture_errors.items():st.caption(f'{lg}: {err}')
    else:
        league=st.selectbox('Liga — tylko rozgrywki z meczami w tym dniu',list(fixtures))
        games=fixtures[league]
        chosen=st.selectbox('Mecz — godzina polska',range(len(games)),
                            format_func=lambda i:games[i]['label'])
        game=games[chosen]
        h,v=game['home'],game['away']
        st.caption(f'Potwierdzony terminarz ESPN · {day:%d.%m.%Y} · {game["time"]} (czas polski)')
        if st.button('🔎 Analizuj wybrany mecz',type='primary',use_container_width=True):
            season_year=day.year if day.month>=7 else day.year-1
            try:
                with st.spinner('Pobieram wyniki historyczne i liczę szanse...'):
                    data=league_data(league,season_year)
                    if LEAGUES[league][0]=='espn':
                        extra=[]
                        for club in (h,v):
                            domestic,dom_sources=domestic_history(club,day.isoformat())
                            if not domestic.empty:extra.append(domestic)
                        if extra:
                            data=pd.concat([data]+extra,ignore_index=True).drop_duplicates(subset=['MatchDate','HomeTeam','AwayTeam'])
                # ESPN and Football-Data can use different official team labels.
                # Normalize exact names, and allow uniquely identifiable shortened names.
                names=sorted(set(data.HomeTeam.dropna())|set(data.AwayTeam.dropna()))
                def resolve(name):
                    key=normalize(name)
                    exact=[n for n in names if normalize(n)==key]
                    if len(exact)==1:return exact[0]
                    # No risky fuzzy matching: incorrect clubs would corrupt analysis.
                    return None
                hh,vv=resolve(h),resolve(v)
                if not hh or not vv:
                    st.warning('Terminarz został pobrany, ale nazwy klubów nie pasują jednoznacznie do archiwum wyników. Nie wykonuję analizy na danych innej drużyny.')
                    st.caption(f'Terminarz: {h} – {v}. Archiwum: {", ".join(names[:18])}')
                else:
                    rh=form(data,hh,pd.Timestamp(day,tz='UTC'));rv=form(data,vv,pd.Timestamp(day,tz='UTC'))
                    if min(len(rh),len(rv))<5:
                        st.warning('Za mało historycznych meczów obu drużyn przed wybraną datą (minimum 5 na drużynę).')
                    else:
                        m,p,lam=football_markets(hh,vv,rh,rv,data,pd.Timestamp(day,tz='UTC'))
                        key={'E0':'soccer_epl','I1':'soccer_italy_serie_a','SP1':'soccer_spain_la_liga','D1':'soccer_germany_bundesliga','F1':'soccer_france_ligue_one'}.get(LEAGUES[league][1],'')
                        render(m,list(zip((hh,'Remis',vv),p)),(hh,vv),(rh,rv),f'{league} · terminarz ESPN · wyniki historyczne',api_key,key)
            except Exception as exc:
                st.warning('Nie udało się przeprowadzić wiarygodnej analizy: '+str(exc)[:200])
elif sport.startswith('🎾'):
    st.markdown('#### 📅 Mecze tenisowe w wybranym dniu')
    tour=st.selectbox('Rozgrywki',['ATP','WTA'])
    with st.spinner('Pobieram terminarz ATP/WTA (czas polski)...'):
        games,errors,successful=dated_sport_fixtures('tennis',tour,day.isoformat())
    if not games:
        with st.spinner('Sprawdzam dodatkowe źródła tenisa...'):
            alt,alt_errors,alt_success=tennis_alternative_fixtures(tour,day.isoformat())
        games=alt
        errors+=alt_errors
        successful+=alt_success
    if not games:
        if successful:
            st.info('Sprawdzone źródła nie udostępniły potwierdzonych singlowych meczów w tym dniu. Nie oznacza to na pewno braku spotkań.')
        else:
            st.warning('Nie udało się pobrać terminarza tenisa. To nie oznacza, że mecze się nie odbywają.')
    else:
        chosen=st.selectbox('Mecz — godzina polska',range(len(games)),format_func=lambda i:games[i]['label'])
        game=games[chosen]
        st.caption(f'{game.get("source","ESPN")} · {day:%d.%m.%Y} · {game["time"]} (Europe/Warsaw)')
        if st.button('🔎 Analizuj wybrany mecz',type='primary',use_container_width=True):
            with st.spinner('Pobieram prawdziwe historyczne wyniki tenisowe...'):
                td,sources,diagnostics=tennis_data(tour,day.year)
            if td.empty:
                st.warning('Terminarz działa, ale źródła historii ATP/WTA nie dostarczyły wyników. Nie wyliczam fikcyjnych szans.')
            else:
                names=sorted(set(td.winner_name.dropna())|set(td.loser_name.dropna()))
                def resolve_player(name):
                    key=normalize(name)
                    exact=[n for n in names if normalize(n)==key]
                    return exact[0] if len(exact)==1 else None
                a,b=resolve_player(game['a']),resolve_player(game['b'])
                if not a or not b:
                    st.warning('Brak jednoznacznego dopasowania zawodników do historii wyników. Nie używam danych innych osób.')
                    st.caption(f'Terminarz: {game["a"]} – {game["b"]}')
                else:
                    try:
                        cutoff=pd.Timestamp(day)
                        markets,probs,_=tennis_markets(td,a,b,cutoff)
                        render(markets,list(zip((a,b),probs)),(a,b),None,
                               f'{tour} · ESPN terminarz · '+', '.join(sources),api_key,
                               'tennis_atp' if tour=='ATP' else 'tennis_wta')
                    except Exception as exc:
                        st.warning('Nie udało się obliczyć analizy: '+str(exc)[:180])
            with st.expander('🔧 Diagnostyka historii ATP/WTA'):
                for msg in diagnostics:st.caption(msg)
    if errors:
        with st.expander('ℹ️ Diagnostyka terminarza ATP/WTA'):
            for msg in errors:st.caption(msg)
else:
    st.markdown('#### 📅 Mecze NBA w wybranym dniu')
    with st.spinner('Pobieram terminarz NBA (czas polski)...'):
        games,errors,successful=dated_sport_fixtures('nba','',day.isoformat())
    if not games:
        if successful:st.info('ESPN nie pokazał meczów NBA na tę datę w Polsce.')
        else:st.warning('Nie udało się pobrać terminarza NBA. Spróbuj ponownie później.')
    else:
        chosen=st.selectbox('Mecz — godzina polska',range(len(games)),format_func=lambda i:games[i]['label'])
        game=games[chosen]
        h,v=game['a'],game['b']
        st.caption(f'{game.get("source","ESPN")} · {day:%d.%m.%Y} · {game["time"]} (Europe/Warsaw)')
        if st.button('🔎 Analizuj wybrany mecz',type='primary',use_container_width=True):
            with st.spinner('Analizuję zakończone mecze NBA...'):
                try:
                    events=[]
                    if api_key:
                        try:events=odds_events(api_key,'basketball_nba')
                        except Exception:pass
                    lines=available_total_lines(events,h,v)
                    # NBA history is anchored to the local date. Only past games count.
                    m,p,rows=nba_markets(h,v,day,lines)
                    render(m,list(zip((h,v),p)),(h,v),rows,
                           'NBA · ESPN · terminarz według czasu polskiego',api_key,'basketball_nba')
                except Exception as exc:
                    st.warning('Nie udało się przeprowadzić analizy: '+str(exc)[:180])
    if errors:
        with st.expander('ℹ️ Diagnostyka terminarza NBA'):
            for msg in errors:st.caption(msg)

with st.expander('ℹ️ Źródła, kursy i ograniczenia'):
    st.write('Piłka: Football-Data.co.uk (Ekstraklasa używa Home/Away/HG/AG), Liga Mistrzów: ESPN. Tenis: terminarze ESPN/SofaScore/TheSportsDB, historia Valuebetennis/JeffSackmann/tennis-data.co.uk/ESPN. Dostępność i warunki użycia źródeł mogą się zmieniać. NBA: ESPN. Linie NBA wyłącznie z faktycznej oferty dostawcy kursów.')
    st.write('Kursy: opcjonalnie The Odds API, po dodaniu klucza THE_ODDS_API_KEY w Streamlit Secrets. Dostępność polskich bukmacherów, dyscyplin i rynków zależy od dostawcy. Bez klucza lub dopasowania nie pokazujemy kursów. Nie udajemy, że pobraliśmy kurs z Superbet czy Betclic.')
    st.write('Model to uproszczona analiza historyczna, bez walidacji prognoz, pełnych kontuzji i składów. Zdarzenia o wysokim prawdopodobieństwie nie muszą być opłacalne. Przed postawieniem zakładu zweryfikuj dane i warunki.')
