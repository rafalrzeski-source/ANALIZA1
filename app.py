"""SportLab 3.0: independent match analysis, not a bookmaker."""
import io, math, re, unicodedata
from datetime import date, timedelta
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='SportLab 3.0 | Analiza sportowa', page_icon='📈', layout='wide')
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

HEAD={'User-Agent':'SportLab/3.0 personal statistical analysis'}
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
    if not {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(d):raise ValueError('Niepoprawny format wyników')
    d['MatchDate']=pd.to_datetime(d.Date,dayfirst=True,errors='coerce')
    for col in ['FTHG','FTAG','HS','AS','HC','AC','HST','AST']:
        if col in d:d[col]=pd.to_numeric(d[col],errors='coerce')
    return d.dropna(subset=['MatchDate','HomeTeam','AwayTeam','FTHG','FTAG'])

# P1 is PORTUGAL's second tier, not Polish Ekstraklasa. Poland uses separate league feed.
LEAGUES={'🇵🇱 Ekstraklasa':('new','POL'),'🏴 Premier League':('classic','E0'),
'🇮🇹 Serie A':('classic','I1'),'🇪🇸 La Liga':('classic','SP1'),
'🇩🇪 Bundesliga':('classic','D1'),'🇫🇷 Ligue 1':('classic','F1'),
'🇳🇱 Eredivisie':('classic','N1'),'🇵🇹 Primeira Liga':('classic','P0'),
'🏴 Championship':('classic','E1')}
@st.cache_data(ttl=21600,show_spinner=False)
def league_data(league,year):
    mode,code=LEAGUES[league];frames=[];errors=[]
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
    needed={'date','genre','joueur1','joueur2','joueur1_id','joueur2_id','vainqueur_id'}
    if not needed.issubset(d):raise ValueError('Niepoprawny format Valuebetennis')
    d['MatchDate']=pd.to_datetime(d['date'],utc=True,errors='coerce').dt.tz_localize(None)
    # Winner is identified by ID, not by player order.
    d['winner_name']=d['joueur1'].where(d['joueur1_id'].astype(str)==d['vainqueur_id'].astype(str),d['joueur2'])
    d['loser_name']=d['joueur2'].where(d['joueur1_id'].astype(str)==d['vainqueur_id'].astype(str),d['joueur1'])
    d=d.dropna(subset=['winner_name','loser_name','MatchDate'])
    return d
@st.cache_data(ttl=86400,show_spinner=False)
def tennis_data(tour,year):
    frames=[]
    for y in range(min(year,2026),max(2020,min(year,2026)-3),-1):
        try:
            d=tennis_year(y)
            frames.append(d[d.genre.astype(str).str.lower()==tour.lower()])
        except Exception:pass
    if not frames:return pd.DataFrame(),[]
    return pd.concat(frames,ignore_index=True).drop_duplicates(subset=['MatchDate','winner_name','loser_name']),['Valuebetennis (CC BY 4.0)']

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
    # Only derive set totals when a verified set-count column is available.
    for player,rows in [(a,ra),(b,rb)]:
        if {'winner_sets','loser_sets'}.issubset(rows):
            totals=(pd.to_numeric(rows.winner_sets,errors='coerce')+pd.to_numeric(rows.loser_sets,errors='coerce')).dropna()
            if len(totals)>=8:
                q=(sum(totals>2.5)+1)/(len(totals)+2)
                note=f'W {len(totals)} ostatnich spotkaniach {player} rozegrano 3 lub więcej setów w {sum(totals>2.5)} przypadkach. Dotyczy wyłącznie meczów do dwóch wygranych setów.'
                markets.append(make_market('Powyżej 2,5 seta (forma '+player+')',q,note,len(totals)))
                markets.append(make_market('Poniżej 2,5 seta (forma '+player+')',1-q,note,len(totals)))
            break
    return markets,(p,1-p),(ra,rb)

NBA_NAMES=['Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets','Chicago Bulls','Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets','Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers','LA Clippers','Los Angeles Lakers','Memphis Grizzlies','Miami Heat','Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks','Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns','Portland Trail Blazers','Sacramento Kings','San Antonio Spurs','Toronto Raptors','Utah Jazz','Washington Wizards']
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

def nba_markets(h,a,day):
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
    for line in (209.5,219.5,229.5,239.5):
        z=(line-(ph+pa))/(18*math.sqrt(2));q=.5*math.erfc(z)
        markets.extend([make_market(f'Powyżej {str(line).replace(".",",")} punktu',q,why+' Model sumy punktów jest przybliżony.',n),make_market(f'Poniżej {str(line).replace(".",",")} punktu',1-q,why+' Model sumy punktów jest przybliżony.',n)])
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
                    match=(market==f'{home} wygra' and normalize(label)==normalize(home)) or (market==f'{away} wygra' and normalize(label)==normalize(away)) or (market=='Remis' and normalize(label)=='draw')
                    mt=re.match(r'^(Powyżej|Poniżej) (\d+,\d+) (gola|punktu)',market)
                    if mt and m.get('key')=='totals' and point is not None:
                        match=(normalize(label)==('over' if mt.group(1)=='Powyżej' else 'under') and abs(float(point)-float(mt.group(2).replace(',','.')))<.01)
                    if match and isinstance(o.get('price'),(int,float)):
                        return float(o['price']),bookmaker.get('title','Bukmacher'),bookmaker.get('last_update','brak czasu')
    return None

def render(markets,probs,teams,rows=None,source='',api_key='',sport_key=''):
    if not markets:st.warning('Brak wystarczających danych do propozycji.');return
    # Prioritize interpretable 60–85% markets; secondary alternatives should differ.
    valid=[m for m in markets if m['n']>=5 and .50<=m['p']<=.90]
    valid.sort(key=lambda m:(m['p']>=.60,m['p'],m['n']),reverse=True)
    if not valid:valid=sorted(markets,key=lambda m:m['p'],reverse=True)
    best=valid[0];extra=[]
    for m in valid[1:]:
        if m['name']!=best['name'] and (m['kind']=='combo' or m['name'].split(':')[0]!=best['name'].split(':')[0]):
            extra.append(m)
        if len(extra)>=3:break
    st.markdown(f'<div class="sl-hero"><div class="sl-kicker">ANALIZA SPOTKANIA</div><h2 style="margin:9px 0">{teams[0]} &nbsp; <span style="color:#7992b2">VS</span> &nbsp; {teams[1]}</h2><div class="sl-sub">{source} · Szacunki na podstawie danych historycznych, nie gwarancja wyniku</div></div>',unsafe_allow_html=True)
    st.subheader('📊 Prawdopodobieństwa')
    cols=st.columns(len(probs))
    for c,(name,p) in zip(cols,probs):c.metric(name,f'{p:.1%}')
    st.subheader('🎯 Propozycja główna')
    odds=None
    if api_key and sport_key:
        try:odds=find_odds(odds_events(api_key,sport_key),teams[0],teams[1],best['name'])
        except Exception:pass
    quote=f'<div class="sl-stat"><div class="sl-label">Kurs z rynku</div><div class="sl-value">{odds[0]:.2f}</div><div class="sl-note">{odds[1]} · {odds[2]}</div></div>' if odds else '<div class="sl-stat"><div class="sl-label">Kurs</div><div class="sl-value" style="font-size:17px">Brak potwierdzonego kursu</div></div>'
    st.markdown(f'<div class="sl-card sl-main"><div class="sl-tag">WYBÓR MODELU</div><div class="sl-name">{best["name"]}</div><div class="sl-grid"><div class="sl-stat"><div class="sl-label">Szacowana szansa</div><div class="sl-value">{best["p"]:.1%}</div></div>{quote}</div><div class="sl-explain"><b>Dlaczego?</b> {best["why"]}</div><div class="sl-note">Próba: {best["n"]} spotkań. Procenty są orientacyjne i nie zostały skalibrowane na niezależnym zbiorze danych.</div></div>',unsafe_allow_html=True)
    if extra:
        st.subheader('➕ Dodatkowe możliwości')
        for m in extra:
            st.markdown(f'<div class="sl-card"><div class="sl-name" style="font-size:18px">{m["name"]} <span style="float:right;color:#85e6b6">{m["p"]:.1%}</span></div><div class="sl-explain"><b>Dlaczego?</b> {m["why"]}</div></div>',unsafe_allow_html=True)
    if rows:
        with st.expander('📋 Dane źródłowe i ostatnie mecze'):
            a,b=st.columns(2)
            for col,name,data in zip((a,b),teams,rows):
                with col:
                    st.markdown('**'+name+'**')
                    st.dataframe(pd.DataFrame(data).head(12),hide_index=True,use_container_width=True)

st.markdown('<div class="sl-kicker">SPORTLAB / 3.0</div>',unsafe_allow_html=True)
st.title('Analiza sportowa. Bez zgadywania danych.')
st.caption('Wyszukaj mecz, zobacz szacunki i wyjaśnienie. Kursy wyświetlamy wyłącznie z rzeczywistego źródła.')
sport=st.radio('Dyscyplina',['⚽ Piłka nożna','🎾 Tenis','🏀 NBA'],horizontal=True)
day=st.date_input('Data spotkania',value=date.today())
try: api_key=st.secrets.get('THE_ODDS_API_KEY','')
except Exception:api_key=''

if sport.startswith('⚽'):
    league=st.selectbox('Liga',list(LEAGUES))
    season_year=day.year if day.month>=7 else day.year-1
    try:
        with st.spinner('Pobieram listę drużyn...'):data=league_data(league,season_year)
        # Don't show historical teams that no longer play in the selected season.
        recent=data[(data.MatchDate>=pd.Timestamp(day)-pd.Timedelta(days=420)) & (data.MatchDate<=pd.Timestamp(day))]
        if recent.empty:recent=data.sort_values('MatchDate').tail(150)
        names=sorted(set(recent.HomeTeam.dropna())|set(recent.AwayTeam.dropna()))
    except Exception as e:
        data=pd.DataFrame();names=[];st.warning('Nie udało się pobrać listy klubów: '+str(e)[:160])
    a,b=st.columns(2)
    h=a.selectbox('Gospodarze — wpisz kilka liter',['']+names,index=0)
    v=b.selectbox('Goście — wpisz kilka liter',['']+names,index=0)
    if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):
        if not h or not v or h==v:st.warning('Wybierz dwie różne drużyny.')
        elif data.empty:st.warning('Brak danych ligowych.')
        else:
            rh=form(data,h,pd.Timestamp(day));rv=form(data,v,pd.Timestamp(day))
            if min(len(rh),len(rv))<5:st.warning('Za mało wyników sprzed wybranej daty (minimum 5 na drużynę).')
            else:
                m,p,lam=football_markets(h,v,rh,rv,data,pd.Timestamp(day))
                key={'E0':'soccer_epl','I1':'soccer_italy_serie_a','SP1':'soccer_spain_la_liga','D1':'soccer_germany_bundesliga','F1':'soccer_france_ligue_one'}.get(LEAGUES[league][1],'')
                render(m,list(zip((h,'Remis',v),p)),(h,v),(rh,rv),f'{league} · Football-Data.co.uk',api_key,key)
elif sport.startswith('🎾'):
    tour=st.selectbox('Rozgrywki',['ATP','WTA'])
    with st.spinner('Sprawdzam dostępne archiwum ATP/WTA...'):td,sources=tennis_data(tour,day.year)
    names=sorted(set(td.winner_name.dropna())|set(td.loser_name.dropna())) if not td.empty else []
    if not names:st.info('Archiwum jest chwilowo niedostępne. Nadal możesz wpisać nazwiska ręcznie; analiza wymaga jednak historii spotkań.')
    a,b=st.columns(2)
    # Text inputs always work, even if the source server is down.
    p1=a.text_input('Zawodnik 1 — wpisz nazwisko',placeholder='np. Sinner')
    p2=b.text_input('Zawodnik 2 — wpisz nazwisko',placeholder='np. Alcaraz')
    def suggestions(query):
        if len(query.strip())<2:return []
        return [n for n in names if normalize(query) in normalize(n)][:12]
    if p1 and names:
        sug=suggestions(p1)
        if sug:st.caption('Podpowiedzi dla zawodnika 1: '+', '.join(sug))
    if p2 and names:
        sug=suggestions(p2)
        if sug:st.caption('Podpowiedzi dla zawodnika 2: '+', '.join(sug))
    if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):
        if not p1.strip() or not p2.strip():st.warning('Wpisz obu zawodników.')
        elif td.empty:st.error('Brak dostępnej historii meczów. Nie mogę wiarygodnie policzyć szans.')
        else:
            def choose(q):
                exact=[n for n in names if normalize(n)==normalize(q)]
                if exact:return exact[0]
                part=[n for n in names if normalize(q) in normalize(n)]
                if len(part)==1:return part[0]
                return None
            a,b=choose(p1),choose(p2)
            if not a or not b:st.warning('Nie udało się jednoznacznie rozpoznać nazwisk. Wpisz pełne nazwisko zgodne z podpowiedzią.')
            elif a==b:st.warning('Wybierz dwóch różnych zawodników.')
            else:
                try:
                    m,p,rows=tennis_markets(td,a,b,pd.Timestamp(day))
                    render(m,list(zip((a,b),p)),(a,b),None,'ATP/WTA · '+', '.join(sources),api_key,'tennis_atp' if tour=='ATP' else 'tennis_wta')
                except Exception as e:st.warning(str(e))
else:
    a,b=st.columns(2)
    h=a.selectbox('Gospodarze — wyszukaj',['']+NBA_NAMES)
    v=b.selectbox('Goście — wyszukaj',['']+NBA_NAMES)
    if st.button('🔎 Analizuj mecz',type='primary',use_container_width=True):
        if not h or not v or h==v:st.warning('Wybierz dwie różne drużyny.')
        else:
            with st.spinner('Analizuję zakończone mecze NBA...'):
                try:
                    m,p,rows=nba_markets(h,v,day)
                    render(m,list(zip((h,v),p)),(h,v),rows,'NBA · ESPN scoreboard',api_key,'basketball_nba')
                except Exception as e:st.warning(str(e))

with st.expander('ℹ️ Źródła, kursy i ograniczenia'):
    st.write('Piłka: Football-Data.co.uk. Ekstraklasa: osobny plik POL.csv, nie kod P1 (Portugalia). Tenis: Valuebetennis (CC BY 4.0), dane ATP/WTA od 2021; źródło może być niedostępne. NBA: ESPN.')
    st.write('Kursy: opcjonalnie The Odds API, po dodaniu klucza THE_ODDS_API_KEY w Streamlit Secrets. Dostępność polskich bukmacherów, dyscyplin i rynków zależy od dostawcy. Bez klucza lub dopasowania nie pokazujemy kursów. Nie udajemy, że pobraliśmy kurs z Superbet czy Betclic.')
    st.write('Model to uproszczona analiza historyczna, bez walidacji prognoz, pełnych kontuzji i składów. Zdarzenia o wysokim prawdopodobieństwie nie muszą być opłacalne. Przed postawieniem zakładu zweryfikuj dane i warunki.')
