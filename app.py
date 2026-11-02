import io, math, re, unicodedata
from datetime import date, timedelta
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='SportLab • Analiza meczów', page_icon='📊', layout='wide')
st.markdown('''<style>.block-container{max-width:1050px;padding-top:2rem}div[data-testid="stMetric"]{background:#15243a12;border:1px solid #8899aa44;border-radius:12px;padding:15px}</style>''',unsafe_allow_html=True)
st.title('📊 SportLab 2.0 — analiza meczów')
st.caption('Wybierz drużyny lub zawodników z podpowiedzi. Program pobiera dane i wskazuje propozycję statystyczną — bez wymyślonych kursów.')
HEAD={'User-Agent':'SportLabPersonalResearch/1.0 (non-commercial personal match analysis)'}
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()
def get(url, params=None):
    r=requests.get(url,params=params,headers=HEAD,timeout=18)
    r.raise_for_status()
    return r
@st.cache_data(ttl=21600,show_spinner=False)
def csv_url(url):
    r=get(url)
    return pd.read_csv(io.BytesIO(r.content),on_bad_lines='skip',low_memory=False)
def resolve(name,choices):
    target=norm(name)
    exact=[x for x in choices if norm(x)==target]
    if exact:return exact[0]
    near=[x for x in choices if target in norm(x) or norm(x) in target]
    if len(near)==1:return near[0]
    return None

def weighted_avg(xs, default):
    if not xs:return default
    w=list(range(len(xs),0,-1))
    return sum(float(x)*k for x,k in zip(xs,w))/sum(w)
def poisson(k, lam):return math.exp(-lam)*lam**k/math.factorial(k)
def football_probs(a,b,league_avg):
    h=max(.15,min(4.5,(a['scored']*b['conceded']/league_avg)*1.12))
    v=max(.15,min(4.5,(b['scored']*a['conceded']/league_avg)*.90))
    p1=pd= p2=over=btts=0.
    for i in range(13):
        for j in range(13):
            p=poisson(i,h)*poisson(j,v)
            if i>j:p1+=p
            elif i==j:pd+=p
            else:p2+=p
            if i+j>=3:over+=p
            if i and j:btts+=p
    return h,v,[p1,pd,p2,over,btts]
def team_form(df,team,cutoff,n=8):
    rows=df[((df.HomeTeam==team)|(df.AwayTeam==team))&(df.MatchDate<cutoff)].sort_values('MatchDate',ascending=False).head(n)
    out=[]
    for _,r in rows.iterrows():
        home=r.HomeTeam==team
        f=r.FTHG if home else r.FTAG; ag=r.FTAG if home else r.FTHG
        d={'date':r.MatchDate.date().isoformat(),'opponent':r.AwayTeam if home else r.HomeTeam,'score':f'{int(f)}:{int(ag)}','scored':float(f),'conceded':float(ag),'result':'W' if f>ag else 'D' if f==ag else 'L'}
        for k,col1,col2 in [('shots','HS','AS'),('on_target','HST','AST'),('corners','HC','AC')]:
            d[k]=pd.to_numeric(r.get(col1 if home else col2),errors='coerce')
        out.append(d)
    return out
def summarize(rows):
    return {'scored':weighted_avg([x['scored'] for x in rows],1.25),'conceded':weighted_avg([x['conceded'] for x in rows],1.25)}
def render_history(rows):
    if not rows:return
    df=pd.DataFrame(rows)
    cols=[x for x in ['date','opponent','score','result','shots','on_target','corners'] if x in df]
    st.dataframe(df[cols],hide_index=True,use_container_width=True)
    for key,label in [('shots','Strzały'),('on_target','Celne strzały'),('corners','Rzuty rożne')]:
        if key in df and df[key].notna().any():st.caption(f'{label}: średnio {df[key].mean():.1f} na mecz ({df[key].notna().sum()} dostępnych spotkań).')
def recommendation(items):
    """items: (name, probability, explanation, evidence_count)."""
    viable=[x for x in items if x[1] is not None and x[3]>=5]
    if not viable:
        st.warning("Brak wystarczających danych do wskazania propozycji.")
        return
    # Prefer meaningful, interpretable markets rather than a nearly certain trivial event.
    viable.sort(key=lambda x: (x[1], x[3]),reverse=True)
    name,prob,why,n=viable[0]
    st.success(f"🎯 **Propozycja: {name}**")
    st.write(f"Szacowana szansa: **{prob:.0%}** · {why}")
    st.caption(f"Podstawa: {n} spotkań. Kurs niedostępny — to propozycja statystyczna, nie ocena opłacalności zakładu. Model nie jest skalibrowany, więc procent może być niedokładny.")

def empirical_over(rows,field,threshold):
    vals=[float(r[field]) for r in rows if pd.notna(r.get(field))]
    if len(vals)<5:return None,len(vals)
    # Laplace smoothing avoids reporting 0% or 100% on tiny samples
    return (sum(v>threshold for v in vals)+1)/(len(vals)+2),len(vals)

def show_probs(names,probs):
    st.subheader('Szacunki modelu')
    cols=st.columns(len(names))
    for c,name,p in zip(cols,names,probs):c.metric(name,f'{p*100:.1f}%')
    st.caption('To uproszczony model statystyczny, bez walidacji historycznej i bez uwzględnienia aktualnych kontuzji. Nie jest to pewne przewidywanie.')

with st.sidebar:
    st.header('Źródła i ograniczenia')
    st.write('⚽ Football-Data.co.uk: wyniki, gole, czasem strzały i rożne.')
    st.write('🏀 ESPN: zakończone mecze NBA, punkty.')
    st.write('🎾 Jeff Sackmann tennis_atp / tennis_wta: historyczne mecze turniejowe.')
    st.warning('Kursy Superbet/Betclic nie są jeszcze podłączone. Bez danych nie wyświetlamy wymyślonych kursów ani prognoz.')
    st.caption('Dane mogą być opóźnione. Źródła mogą ograniczyć dostęp. Nie pobieramy stron Flashscore ani SofaScore.')

sport=st.radio('Wybierz dyscyplinę',['⚽ Piłka nożna','🎾 Tenis','🏀 NBA'],horizontal=True)
match_date=st.date_input('Data meczu',value=date.today())

if sport.startswith('⚽'):
    leagues={'Premier League':'E0','Serie A':'I1','La Liga':'SP1','Bundesliga':'D1','Ligue 1':'F1','Ekstraklasa':'P1','Eredivisie':'N1','Primeira Liga':'P0','Championship':'E1'}
    league=st.selectbox('Liga',list(leagues))
    # Team names come from the downloaded league CSV, not from a hardcoded list.
    yy=match_date.year if match_date.month>=7 else match_date.year-1
    frames=[]
    with st.spinner('Wczytuję drużyny z wybranej ligi...'):
        for year in [yy,yy-1]:
            season=f'{year%100:02d}{(year+1)%100:02d}'
            try:
                d=csv_url(f'https://www.football-data.co.uk/mmz4281/{season}/{leagues[league]}.csv')
                if {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(d.columns):
                    d['MatchDate']=pd.to_datetime(d.Date,dayfirst=True,errors='coerce')
                    frames.append(d.dropna(subset=['MatchDate','HomeTeam','AwayTeam','FTHG','FTAG']))
            except Exception:pass
    df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    choices=sorted(set(df.HomeTeam)|set(df.AwayTeam)) if not df.empty else []
    if not choices:st.warning('Nie można teraz pobrać listy drużyn z tej ligi.')
    a,b=st.columns(2)
    home=a.selectbox('Gospodarze — wpisz kilka liter', ['']+choices, index=0, key='soc_home')
    away=b.selectbox('Goście — wpisz kilka liter', ['']+choices, index=0, key='soc_away')
    if st.button('🔎 Pobierz dane i analizuj',type='primary',use_container_width=True):
        if not home.strip() or not away.strip():st.error('Podaj obie drużyny.')
        elif home==away:st.error('Wybierz dwie różne drużyny.')
        else:
            with st.spinner('Pobieram wyniki ligowe...'):
                try:
                    if df.empty:raise ValueError('Brak aktualnych danych ligowych.')
                    h=resolve(home,choices);v=resolve(away,choices)
                    if not h or not v:raise ValueError(f'Nie rozpoznano drużyny. Dostępne nazwy: {", ".join(choices)}')
                    r1=team_form(df,h,pd.Timestamp(match_date));r2=team_form(df,v,pd.Timestamp(match_date))
                    if len(r1)<4 or len(r2)<4:raise ValueError(f'Za mało spotkań przed datą meczu: {h}: {len(r1)}, {v}: {len(r2)}. Wymagane minimum 4.')
                    past=df[df.MatchDate<pd.Timestamp(match_date)]
                    avg=max(.7,float(pd.concat([past.FTHG,past.FTAG]).mean()))
                    x,y,pr=football_probs(summarize(r1),summarize(r2),avg)
                    st.success(f'Znaleziono {len(r1)} meczów {h} i {len(r2)} meczów {v} przed {match_date}.')
                    st.caption('Źródło: https://www.football-data.co.uk/ • mecze z dwóch sezonów, dane wyłącznie sprzed wskazanej daty.')
                    show_probs([f'1 — {h}','X — remis',f'2 — {v}','Powyżej 2,5 gola','Obie strzelą'],pr)
                    candidates=[
                        (f'{h} wygra',pr[0], 'Model goli (Poisson)',min(len(r1),len(r2))),
                        ('Powyżej 2,5 gola w meczu',pr[3], 'Model goli (Poisson)',min(len(r1),len(r2))),
                        ('Obie drużyny strzelą gola',pr[4], 'Model goli (Poisson)',min(len(r1),len(r2))),
                        (f'{h} powyżej 9,5 strzału',empirical_over(r1,'shots',9.5)[0], 'Strzały z ostatnich spotkań (bez korekty siły rywala)',empirical_over(r1,'shots',9.5)[1]),
                        (f'{v} powyżej 9,5 strzału',empirical_over(r2,'shots',9.5)[0], 'Strzały z ostatnich spotkań (bez korekty siły rywala)',empirical_over(r2,'shots',9.5)[1]),
                    ]
                    recommendation(candidates)
                    st.write(f'Modelowa średnia goli: **{h}: {x:.2f}**, **{v}: {y:.2f}**')
                    c1,c2=st.columns(2)
                    with c1:st.subheader(h);render_history(r1)
                    with c2:st.subheader(v);render_history(r2)
                except Exception as e:st.error(f'Nie można wykonać rzetelnej analizy: {e}')

elif sport.startswith('🏀'):
    a,b=st.columns(2)
    nba_names=['Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets','Chicago Bulls','Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets','Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers','LA Clippers','Los Angeles Lakers','Memphis Grizzlies','Miami Heat','Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks','Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns','Portland Trail Blazers','Sacramento Kings','San Antonio Spurs','Toronto Raptors','Utah Jazz','Washington Wizards']
    home=a.selectbox('Gospodarze — wyszukaj', ['']+nba_names)
    away=b.selectbox('Goście — wyszukaj', ['']+nba_names)
    @st.cache_data(ttl=3600,show_spinner=False)
    def nba_results(day):
        data=get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard',{'dates':day.strftime('%Y%m%d'),'limit':100}).json()
        out=[]
        for ev in data.get('events',[]):
            comp=(ev.get('competitions') or [{}])[0]
            if not comp.get('status',{}).get('type',{}).get('completed',False):continue
            sides=comp.get('competitors',[])
            if len(sides)!=2:continue
            try:
                teams={x['homeAway']:(x['team']['displayName'],float(x['score'])) for x in sides}
                out.append((teams['home'],teams['away']))
            except (KeyError,TypeError,ValueError):continue
        return out
    if st.button('🔎 Pobierz dane i analizuj',type='primary',use_container_width=True):
        if not home.strip() or not away.strip():st.error('Podaj obie drużyny.')
        elif home==away:st.error('Wybierz dwie różne drużyny.')
        else:
            with st.spinner('Pobieram ostatnie zakończone mecze NBA (może potrwać chwilę)...'):
                try:
                    records={};fail=0
                    # Recent schedule, only dates prior to selected match. Use spaced windows to reduce requests.
                    for offset in range(1,36):
                        day=match_date-timedelta(days=offset)
                        try:games=nba_results(day)
                        except Exception:fail+=1;continue
                        for (hn,hs),(an,as_) in games:
                            records.setdefault(hn,[]).append({'date':str(day),'opponent':an,'score':f'{int(hs)}:{int(as_)}','scored':hs,'conceded':as_,'result':'W' if hs>as_ else 'L'})
                            records.setdefault(an,[]).append({'date':str(day),'opponent':hn,'score':f'{int(as_)}:{int(hs)}','scored':as_,'conceded':hs,'result':'W' if as_>hs else 'L'})
                    h=resolve(home,records);v=resolve(away,records)
                    if not h or not v:raise ValueError(f'Nie znaleziono drużyn w dostępnych meczach. Błędnych odpowiedzi źródła: {fail}. Sprawdź pełne angielskie nazwy.')
                    r1=records[h][:10];r2=records[v][:10]
                    if len(r1)<4 or len(r2)<4:raise ValueError(f'Za mało danych: {h} {len(r1)}, {v} {len(r2)}. Potrzeba co najmniej 4 meczów.')
                    s1=summarize(r1);s2=summarize(r2)
                    pred_h=(s1['scored']+s2['conceded'])/2+1.5
                    pred_a=(s2['scored']+s1['conceded'])/2-1.5
                    margin=pred_h-pred_a
                    p=1/(1+math.exp(-margin/12))
                    st.success(f'Znaleziono {len(r1)} i {len(r2)} zakończonych meczów.')
                    st.caption('Źródło: ESPN scoreboard • ostatnie 35 dni przed wskazaną datą. Uproszczony model punktowy, bez kontuzji i składów.')
                    show_probs([f'Wygrana {h}',f'Wygrana {v}'],[p,1-p])
                    recommendation([(f'{h} wygra',p,'Model punktowy NBA',min(len(r1),len(r2))),
                                    (f'{v} wygra',1-p,'Model punktowy NBA',min(len(r1),len(r2)))])
                    st.write(f'Szacowane punkty: **{h}: {pred_h:.1f}** · **{v}: {pred_a:.1f}** · suma **{pred_h+pred_a:.1f}**')
                    c1,c2=st.columns(2)
                    with c1:st.subheader(h);render_history(r1)
                    with c2:st.subheader(v);render_history(r2)
                except Exception as e:st.error(f'Nie można wykonać rzetelnej analizy: {e}')

else:
    tour=st.selectbox('Rozgrywki',['ATP','WTA'])
    @st.cache_data(ttl=86400,show_spinner=False)
    def tennis_season(tour,year):
        url=f'https://raw.githubusercontent.com/JeffSackmann/tennis_{tour.lower()}/master/{tour.lower()}_matches_{year}.csv'
        d=csv_url(url)
        if not {'winner_name','loser_name','tourney_date'}.issubset(d.columns):raise ValueError('Nieprawidłowy format danych.')
        d['MatchDate']=pd.to_datetime(d.tourney_date.astype(str),format='%Y%m%d',errors='coerce')
        return d
    frames=[]
    with st.spinner('Pobieram listę zawodników i historię meczów...'):
        for yr in range(match_date.year,match_date.year-4,-1):
            try:frames.append(tennis_season(tour,yr))
            except Exception:pass
    df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    if not df.empty:df=df[df.MatchDate<pd.Timestamp(match_date)]
    names=sorted(set(df.winner_name.dropna())|set(df.loser_name.dropna())) if not df.empty else []
    if not names:st.warning('Źródło ATP/WTA jest obecnie niedostępne. Nie można potwierdzić nazwisk ani wyników.')
    a,b=st.columns(2)
    first=a.selectbox('Zawodnik 1 — wpisz początek nazwiska', ['']+names, key='tennis_a')
    second=b.selectbox('Zawodnik 2 — wpisz początek nazwiska', ['']+names, key='tennis_b')
    if st.button('🔎 Pobierz dane i analizuj',type='primary',use_container_width=True):
        if not first.strip() or not second.strip():st.error('Podaj obu zawodników.')
        elif first==second:st.error('Wybierz dwóch różnych zawodników.')
        else:
            with st.spinner('Pobieram historię turniejową...'):
                try:
                    if df.empty:raise ValueError('Nie udało się pobrać historii meczów ATP/WTA. Źródło może ograniczać dostęp.')
                    p1=resolve(first,names);p2=resolve(second,names)
                    if not p1 or not p2:raise ValueError('Nie rozpoznano zawodnika. Spróbuj pełnego imienia i nazwiska zgodnego z ATP/WTA.')
                    def form(p):
                        d=df[(df.winner_name==p)|(df.loser_name==p)].sort_values('MatchDate',ascending=False).head(15)
                        return [{'date':r.MatchDate.date().isoformat(),'opponent':r.loser_name if r.winner_name==p else r.winner_name,'result':'W' if r.winner_name==p else 'L','surface':r.get('surface','?'),'tournament':r.get('tourney_name','?')} for _,r in d.iterrows()]
                    r1=form(p1);r2=form(p2)
                    if len(r1)<5 or len(r2)<5:raise ValueError(f'Za mało meczów: {p1}: {len(r1)}, {p2}: {len(r2)}. Wymagane 5.')
                    def rate(rs):
                        w=[max(.25,1-i*.045) for i in range(len(rs))]
                        return (sum(k for k,r in zip(w,rs) if r['result']=='W')+2)/(sum(w)+4)
                    q1=rate(r1);q2=rate(r2)
                    prob=max(.05,min(.95,.5+(q1-q2)*.65))
                    st.success(f'Znaleziono {len(r1)} i {len(r2)} ostatnich spotkań.')
                    st.caption('Źródło: github.com/JeffSackmann/tennis_atp lub tennis_wta • historia turniejowa; dane mogą nie obejmować wszystkich meczów. Heurystyka, nie skalibrowany model.')
                    show_probs([f'Wygrana {p1}',f'Wygrana {p2}'],[prob,1-prob])
                    recommendation([(f'{p1} wygra mecz',prob,'Forma z ostatnich spotkań',min(len(r1),len(r2))),
                                    (f'{p2} wygra mecz',1-prob,'Forma z ostatnich spotkań',min(len(r1),len(r2)))])
                    c1,c2=st.columns(2)
                    with c1:st.subheader(p1);st.dataframe(pd.DataFrame(r1),hide_index=True,use_container_width=True)
                    with c2:st.subheader(p2);st.dataframe(pd.DataFrame(r2),hide_index=True,use_container_width=True)
                except Exception as e:st.error(f'Nie można wykonać rzetelnej analizy: {e}')

st.divider()
st.caption('SportLab 2.0 • Projekt niekomercyjny • Źródła zewnętrzne mogą zmieniać format i dostępność. Nie pobiera kursów bukmacherskich. Nie używaj uproszczonych prawdopodobieństw jako jedynej podstawy decyzji finansowych.')
