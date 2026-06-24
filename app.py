#liberias
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración Pagina
st.set_page_config(page_title="Proyecto Finanzas")
st.title("Análisis de Activos Financieros")


#opciones
PERIODOS = {"1 mes": "1mo","3 meses": "3mo","6 meses": "6mo","1 año": "1y","2 años": "2y","5 años": "5y"}
INTERVALOS = {"1 día": "1d","1 semana": "1wk","1 mes": "1mo"}
ACTIVOS = ["SPY","QQQ","NVDA","AAPL","MSFT","TSLA","META","AMZN"]
CAPITAL_INI = 10000.0
COMISION    = 0.001

# session state
for key, default in {
    "datos":     {},
    "tickers":   ["SPY"],
    "periodo":   "1 año",
    "intervalo": "1 día",
    "pesos_opt":   None,      # np.array con pesos del portafolio óptimo
    "tickers_port": [],      
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# descarga de datos
@st.cache_data(ttl=60)
def descargar_datos(ticker, periodo, intervalo):
    df = yf.download(ticker, period=periodo, interval=intervalo,
                     auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df

# sidebar
with st.sidebar:
    st.title("Barra")
    opcion = st.radio("Selecciona módulo", ["Perfil de Riesgo","Inicio","Portafolio Óptimo","Backtest"])
    st.divider()

    tickers = st.multiselect("Selecciona activos", ACTIVOS,
                             default=st.session_state["tickers"])
    periodo   = st.selectbox("Periodo",      list(PERIODOS.keys()),
                             index=list(PERIODOS.keys()).index(st.session_state["periodo"]))
    intervalo = st.selectbox("Periodicidad", list(INTERVALOS.keys()),
                             index=list(INTERVALOS.keys()).index(st.session_state["intervalo"]))

    if st.button("Cargar datos"):
        if not tickers:
            st.warning("")
        else:
            nuevos = {}
            with st.spinner(""):
                for t in tickers:
                    df = descargar_datos(t, PERIODOS[periodo], INTERVALOS[intervalo])
                    if not df.empty:
                        nuevos[t] = df
            st.session_state["datos"]     = nuevos
            st.session_state["tickers"]   = tickers
            st.session_state["periodo"]   = periodo
            st.session_state["intervalo"] = intervalo


# parámetros portafolio 
if opcion == "Portafolio Óptimo":
    with st.sidebar:
        st.divider()
        st.markdown("**Parámetros para el portafolio**")
        num_ports       = st.slider("Número de portafolios", 1000, 3000, 10000, step=1000)
        ventas_en_corto = st.checkbox("Permitir ventas en corto", value=False)
#----------------------------------------------------------------------
if opcion == "Perfil de Riesgo":

    st.header("Perfilamiento de Riesgo")
    st.markdown("Responde las siguientes preguntas para determinar tu coeficiente de aversión al riesgo")

    preguntas = {
        "¿Cuánto tiempo planeas mantener tu inversión?": {
            "Menos de 1 año": 3,
            "1 a 5 años": 2,
            "Más de 5 años": 1,
        },
        "Si tu portafolio cae 20% en un mes, ¿qué harías?": {
            "Vendo todo inmediatamente": 3,
            "No hago nada y espero": 2,
            "Compro más aprovechando el precio": 1,
        },
        "¿Cuál es tu principal objetivo de inversión?": {
            "Preservar mi capital, no perder nada": 3,
            "Crecer mi capital moderadamente": 2,
            "Que tu dinero crezca sin importar los riesgos": 1,
        },
        "¿Qué porcentaje de tus ahorros destinarías a esta inversión?": {
            "Menos del 10%": 3,
            "Entre 10% y 50%": 2,
            "Más del 50%": 1,
        },
        "¿Cómo describirías tu grado de conocimiento en inversiones?": {
            "Baja": 3,
            "Media": 2,
            "Alta": 1,
        },
        "¿Cómo reaccionas emocionalmente ante pérdidas?": {
            "Me genera mucho estrés, no puedo tolerarlo": 3,
            "Me incomoda pero lo manejo": 2,
            "Lo veo como una oportunidad": 1,},
            }

    respuestas = {}
    for pregunta, opciones in preguntas.items():
        respuestas[pregunta] = st.radio(pregunta, list(opciones.keys()), index=None)

    st.divider()

    if st.button("Calcular mi perfil", type="primary"):
        if None in respuestas.values():
            st.warning("Por favor responde todas las preguntas.")
        else:
            total = sum(preguntas[p][r] for p, r in respuestas.items())

            # Escala 6 pts (agresivo) a 18 pts (conservador)
            # A va de 1 (agresivo) a 10 (conservador)
            A = round(1 + (total - 6) * (9 / 12), 2)

            if total <= 9:
                perfil = "Agresivo",
            elif total <= 13:
                perfil = "Moderado",
            else:
                perfil= "Conservador",

            st.success(f"Perfil: **{perfil}**")

            st.session_state["coef_A"] = A
            st.session_state["perfil"] = perfil
#---------------------------------------------------------------------------------
# INICIO

elif opcion == "Inicio":
    datos = st.session_state["datos"]

    def calcular_estadisticas(df):
        close = df["close"]
        rendimientos = close.pct_change().dropna()
        precio_actual = close.iloc[-1]
        retorno = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0]) * 100
        return {
            "precio":      precio_actual,
            "rendimiento": retorno,
            "maximo":      close.max(),
            "minimo":      close.min()}

    def grafico_precio(df, ticker):

        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Precio"))
        #bandas de media movil
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=ema12,
                name="EMA 12",
                line=dict(width=1.5)))

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=ema26,
                name="EMA 26",
                line=dict(width=1.5)))

        fig.update_layout(
            title=f"{ticker}",
            yaxis_title="Precio",
            xaxis_rangeslider_visible=False,
            height=600)

        return fig

    def grafico_comparacion(datos):
        fig = go.Figure()
        for ticker, df in datos.items():
            base100 = (df["close"] / df["close"].iloc[0]) * 100
            fig.add_trace(go.Scatter(x=df.index, y=base100, mode="lines", name=ticker))
        fig.update_layout(title="Comparación de activos (Base 100)",
                          xaxis_title="Fecha", yaxis_title="Índice Base 100")
        return fig

    # pestañas
    tab1, tab2 = st.tabs(["Precios individuales", "Comparación"])

    with tab1:
        for ticker, df in datos.items():
            st.subheader(ticker)
            stats = calcular_estadisticas(df)
            col1, col2 = st.columns(2)
            col1.metric("Precio", f"${stats['precio']:.2f}")
            col2.metric("Rendimiento %", f"{stats['rendimiento']:.2f}%")
            st.write(f"Desde: {df.index.min().date()} | Hasta: {df.index.max().date()}")
            st.plotly_chart(grafico_precio(df, ticker), use_container_width=True)
            tabla = pd.DataFrame({
                "Indicador": ["Máximo", "Mínimo"],
                "Valor": [round(stats["maximo"], 2), round(stats["minimo"], 2)]})
            st.dataframe(tabla, use_container_width=True)
    
            csv = df.to_csv(index=True).encode("utf-8")
            st.download_button(
            label=f"Descargar {ticker} CSV",
            data=csv,
            file_name=f"{ticker}_{PERIODOS[st.session_state['periodo']]}.csv",
            mime="text/csv",
        )

    with tab2:
        st.plotly_chart(grafico_comparacion(datos), use_container_width=True)
        resumen = []
        for ticker, df in datos.items():
            stats = calcular_estadisticas(df)
            resumen.append({
                "Ticker":    ticker,
                "Precio":    round(stats["precio"], 2),
                "Retorno %": round(stats["rendimiento"], 2)})
        st.dataframe(pd.DataFrame(resumen), use_container_width=True)
        
        if datos:
            df_todos = pd.concat(
        {t: df["close"].rename(t) for t, df in datos.items()}, axis=1)
    
            csv_todos = df_todos.to_csv(index=True).encode("utf-8")
            st.download_button(
            label="Descargar precio de cierre todos los activos CSV)",
            data=csv_todos,
            file_name="activos_comparacion.csv",
            mime="text/csv",)   

#--------------------------------------------------------------------------------------------
#portafolio optimo
elif opcion == "Portafolio Óptimo":

    from scipy.optimize import minimize
    datos = st.session_state["datos"]

    if len(datos) < 2:
        st.warning("Selecciona al menos 2 activos y carga los datos.")
        st.stop()

    coef_A = st.session_state.get("coef_A")
    perfil = st.session_state.get("perfil")
    if isinstance(perfil, tuple):
        perfil = perfil[0]

    tiene_perfil = coef_A is not None
    if tiene_perfil:
        st.write(f"Perfil: {perfil} ")

    #Preparar datos
    cierres = pd.concat(
        {t: df["close"].rename(t) for t, df in datos.items()}, axis=1).dropna()

    tickers_port = list(cierres.columns)
    rendimientos = cierres.pct_change().dropna()

    e_ret = rendimientos.mean() * 252
    cov   = rendimientos.cov()  * 252
    std   = rendimientos.std()  * np.sqrt(252)

    # Simulación
    min_omega = -1.0 if ventas_en_corto else 0.0
    n = len(tickers_port)

    np.random.seed(42)
    port_sigmas, port_rends, port_pesos, port_utilidades = [], [], [], []

    for _ in range(num_ports):
        w = np.random.uniform(min_omega, 1.0, n)
        w = w / w.sum()
        r = float(w @ e_ret) * 100
        s = float(np.sqrt(w @ cov.values @ w)) * 100
        port_rends.append(r)
        port_sigmas.append(s)
        port_pesos.append(w)
        u = float(w @ e_ret) - 0.5 * coef_A * float(w @ cov.values @ w) if tiene_perfil else None
        port_utilidades.append(u)

    #Frontera eficiente con Jansen
    def portfolio_returns(weights, mean_returns):
        return np.sum(mean_returns * weights)

    def min_vol_target(mean_ret, cov, target, minOmega, maxOmega):
        n_assets = len(mean_ret)
        x0 = np.ones(n_assets) / n_assets

        def portfolio_std(wt, mean_ret=None, cov=None):
            return np.sqrt(wt.T @ cov @ wt)

        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'eq', 'fun': lambda x: x.T @ mean_ret - target},
        ]
        bounds = tuple((minOmega, maxOmega) for _ in range(n_assets))
        return minimize(portfolio_std, x0=x0, args=(mean_ret, cov),
                        method='SLSQP', bounds=bounds, constraints=constraints,
                        options={'tol': 1e-10, 'maxiter': int(1e4)})

    with st.spinner(""):
        ret_range = np.linspace(e_ret.min(), e_ret.max(), 80)
        front = [min_vol_target(e_ret.values, cov.values, r, min_omega, 1.0)
                 for r in ret_range]

    ef_risks, ef_returns, ef_pesos = [], [], []
    for res in front:
        if res.success:
            ef_risks.append(res.fun * 100)
            ef_returns.append(portfolio_returns(res.x, e_ret) * 100)
            ef_pesos.append(res.x)

    #Portafolio con maximo Sharpe
    sharpes_ef = [r / s if s > 0 else -np.inf for r, s in zip(ef_returns, ef_risks)]
    idx_sharpe = int(np.argmax(sharpes_ef))
    w_sharpe   = ef_pesos[idx_sharpe]
    r_sharpe   = ef_returns[idx_sharpe]
    s_sharpe   = ef_risks[idx_sharpe]
    sh_sharpe  = sharpes_ef[idx_sharpe]

    #Portafolio optimo segun perfil
    if tiene_perfil:
        utilidades_ef = [
            (r / 100) - 0.5 * coef_A * (s / 100) ** 2
            for r, s in zip(ef_returns, ef_risks)]
        
        idx_util = int(np.argmax(utilidades_ef))
        w_util   = ef_pesos[idx_util]
        r_util   = ef_returns[idx_util]
        s_util   = ef_risks[idx_util]
        u_util   = utilidades_ef[idx_util]
        sh_util  = r_util / s_util if s_util > 0 else 0

    #grafica
    color_nube = "red" if ventas_en_corto else "#1269dc"
    label_nube = "Con ventas en corto" if ventas_en_corto else "Sin ventas en corto"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=port_sigmas, y=port_rends,
        mode="markers",
        marker=dict(size=4, color=color_nube, opacity=0.35),
        name=f"Portafolios simulados ({label_nube})",
    ))

    fig.add_trace(go.Scatter(
        x=ef_risks, y=ef_returns,
        mode="lines",
        line=dict(color="green", width=3),
        name="Frontera eficiente",
    ))

    fig.add_trace(go.Scatter(
        x=(std * 100).values, y=(e_ret * 100).values,
        mode="markers+text",
        text=tickers_port,
        textposition="top center",
        marker=dict(size=10, color="black"),
        name="Activos individuales",
    ))

    fig.add_trace(go.Scatter(
        x=[s_sharpe], y=[r_sharpe],
        mode="markers+text",
        textposition="middle right",
        marker=dict(size=16, color="orange", symbol="x"),
        name=f"Portafolio óptimo con maximo Sharpe",
    ))

    if tiene_perfil:
        fig.add_trace(go.Scatter(
            x=[s_util], y=[r_util],
            mode="markers+text",
            textposition="middle right",
            marker=dict(size=18, color="purple", symbol="star",
                        line=dict(color="white", width=1)),
            name=f"Portafolio óptimo perfil {perfil}",
        ))

    fig.update_layout(
        title="Frontera Eficiente y Portafolios Optimos",
        xaxis_title="Riesgo — Desviacion estandar anualizada (%)",
        yaxis_title="Retorno esperado anualizado (%)",
        height=580,
        legend=dict(orientation="h", yanchor="bottom", y=-0.35),
    )
    st.plotly_chart(fig, use_container_width=True)

    #comparacion de portafolios
    st.subheader("Comparacion de portafolios")

    #portafolio con maximo sharpe
    st.markdown(" Maximo Sharpe")
    m1, m2, m3 = st.columns(3)
    m1.metric("Retorno",      f"{r_sharpe:.2f}%")
    m2.metric("Riesgo",       f"{s_sharpe:.2f}%")
    m3.metric("Sharpe Ratio", f"{sh_sharpe:.3f}")

    df_p_sharpe = pd.DataFrame({
            "Activo":    tickers_port,
            "Peso (%)": (w_sharpe * 100).round(2),
        }).sort_values("Peso (%)", ascending=False)
    st.dataframe(df_p_sharpe, use_container_width=True, hide_index=True)

    fig_pie_s = go.Figure(go.Pie(
            labels=tickers_port,
            values=np.abs(w_sharpe),
            hole=0.4,
            textinfo="label+percent",))
    
    fig_pie_s.update_layout(title="Pesos — Maximo Sharpe", height=340, margin=dict(t=40, b=0))
    st.plotly_chart(fig_pie_s, use_container_width=True)

    st.markdown(f"Optimo para perfil: {perfil}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Retorno",      f"{r_util:.2f}%")
    m2.metric("Riesgo",       f"{s_util:.2f}%")
    m3.metric("Sharpe Ratio", f"{sh_util:.3f}")

    d1, d2 = st.columns(2)
    d1.metric("Retorno vs Sharpe max", f"{r_util - r_sharpe:+.2f}%", delta_color="normal")
    d2.metric("Riesgo vs Sharpe max",  f"{s_util - s_sharpe:+.2f}%", delta_color="inverse")

    df_p_util = pd.DataFrame({
                "Activo":    tickers_port,
                "Peso (%)": (w_util * 100).round(2),
            }).sort_values("Peso (%)", ascending=False)
    st.dataframe(df_p_util, use_container_width=True, hide_index=True)

    fig_pie_u = go.Figure(go.Pie(
                labels=tickers_port,
                values=np.abs(w_util),
                hole=0.4,
                textinfo="label+percent",))
    fig_pie_u.update_layout(
                title=f"Pesos {perfil}",
                height=340, margin=dict(t=40, b=0))
    st.plotly_chart(fig_pie_u, use_container_width=True)


#-------------------------------------------------------------------------------------------------------------
# BACKTEST
elif opcion == "Backtest":

    datos = st.session_state["datos"]

# -------------------------------------------------------------------------
#Estrategias 
    import types
    import ta
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # --- Bollinger Bands ---
    bollinger = types.ModuleType("bollinger")
    def _bollinger_ejecutar(df, window=20, dev=2.0, ma_type='sma'):
        if ma_type == 'ema':
            middle = ta.trend.ema_indicator(df['close'], window=window)
            std = df['close'].rolling(window=window).std()
            upper = middle + dev * std
            lower = middle - dev * std
        else:
            bb = ta.volatility.BollingerBands(df['close'], window=window, window_dev=dev)
            upper = bb.bollinger_hband()
            lower = bb.bollinger_lband()
        buy_sig  = (df['close'] < lower).astype(int)
        sell_sig = (df['close'] > upper).astype(int)
        return buy_sig, sell_sig
    bollinger.ejecutar = _bollinger_ejecutar

    # --- EMA Crossover ---
    ema = types.ModuleType("ema")
    def _ema_ejecutar(df, fast=8, slow=21):
        ema_fast = ta.trend.ema_indicator(df['close'], window=fast)
        ema_slow = ta.trend.ema_indicator(df['close'], window=slow)
        buy_sig  = ((ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))).astype(int)
        sell_sig = ((ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))).astype(int)
        return buy_sig, sell_sig
    ema.ejecutar = _ema_ejecutar

    # --- Regresión Logística ---
    def _calcular_indicadores_comunes(df):
        df_feat = df.copy()
        df_feat['RSI']      = ta.momentum.rsi(df_feat['close'], window=14)
        df_feat['Momentum'] = df_feat['close'].diff(14)
        macd_ind = ta.trend.MACD(df_feat['close'])
        df_feat['MACD']   = macd_ind.macd()
        df_feat['Signal'] = macd_ind.macd_signal()
        df_feat['EMA20']  = ta.trend.ema_indicator(df_feat['close'], window=20)
        df_feat['EMA50']  = ta.trend.ema_indicator(df_feat['close'], window=50)
        df_feat['EMA200'] = ta.trend.ema_indicator(df_feat['close'], window=200)
        df_feat['EMA8']   = ta.trend.ema_indicator(df_feat['close'], window=8)
        df_feat['EMA21']  = ta.trend.ema_indicator(df_feat['close'], window=21)
        df_feat['VWAP20'] = ta.volume.VolumeWeightedAveragePrice(
            high=df_feat['high'], low=df_feat['low'], close=df_feat['close'],
            volume=df_feat['volume'], window=20).volume_weighted_average_price()
        bb = ta.volatility.BollingerBands(df_feat['close'], window=20)
        df_feat['BB_upper']  = bb.bollinger_hband()
        df_feat['BB_middle'] = bb.bollinger_mavg()
        df_feat['BB_lower']  = bb.bollinger_lband()
        stoch_14 = ta.momentum.StochasticOscillator(
            high=df_feat['high'], low=df_feat['low'], close=df_feat['close'], window=14, smooth_window=7)
        df_feat['Stochastic_%K_14_7_7'] = stoch_14.stoch()
        df_feat['Stochastic_%D_14_7_7'] = stoch_14.stoch_signal()
        stoch_7 = ta.momentum.StochasticOscillator(
            high=df_feat['high'], low=df_feat['low'], close=df_feat['close'], window=7, smooth_window=3)
        df_feat['Stochastic_%K_7_3_3'] = stoch_7.stoch()
        df_feat['Stochastic_%D_7_3_3'] = stoch_7.stoch_signal()
        df_feat['Close_val']  = df_feat['close']
        df_feat['Volume_val'] = df_feat['volume']
        return df_feat

    logit = types.ModuleType("logit")
    def _logit_ejecutar(df, features_list=None):
        if features_list is None:
            features_list = [
                'RSI','Momentum','MACD','Signal','EMA20','EMA50','EMA200','VWAP20',
                'BB_upper','BB_middle','BB_lower',
                'Stochastic_%K_14_7_7','Stochastic_%D_14_7_7',
                'Stochastic_%K_7_3_3','Stochastic_%D_7_3_3',
                'Close_val','Volume_val']
        df_feat = _calcular_indicadores_comunes(df)
        lagged_features = []
        for col in features_list:
            df_feat[col + '_lag1'] = df_feat[col].shift(1)
            lagged_features.append(col + '_lag1')
        df_feat['Direccion'] = (df_feat['close'] > df_feat['close'].shift(1)).astype(int)
        df_clean = df_feat[['close','Direccion'] + lagged_features].dropna()
        split_date_idx = int(len(df) * 0.7)
        train_idx = df_clean.index[df_clean.index < split_date_idx]
        test_idx  = df_clean.index[df_clean.index >= split_date_idx]
        X_train = df_clean.loc[train_idx, lagged_features]
        y_train = df_clean.loc[train_idx, 'Direccion']
        X_test  = df_clean.loc[test_idx,  lagged_features]
        y_test  = df_clean.loc[test_idx,  'Direccion']
        if len(X_train) == 0 or len(X_test) == 0:
            split_idx = int(len(df_clean) * 0.7)
            X_train = df_clean.iloc[:split_idx][lagged_features]
            y_train = df_clean.iloc[:split_idx]['Direccion']
            X_test  = df_clean.iloc[split_idx:][lagged_features]
            y_test  = df_clean.iloc[split_idx:]['Direccion']
            test_idx = df_clean.iloc[split_idx:].index
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled  = scaler.transform(X_test)
        model = LogisticRegression(max_iter=1000)
        model.fit(X_train_scaled, y_train)
        preds = model.predict(X_test_scaled)
        pred_series = pd.Series(0, index=df.index)
        pred_series.loc[test_idx] = preds
        buy_sig  = ((pred_series == 1) & (pred_series.shift(1) != 1)).astype(int)
        sell_sig = ((pred_series == 0) & (pred_series.shift(1) == 1)).astype(int)
        return buy_sig, sell_sig
    logit.ejecutar = _logit_ejecutar

    # --- MACD Crossover ---
    macd = types.ModuleType("macd")
    def _macd_ejecutar(df, fast=12, slow=26, signal=9):
        macd_ind    = ta.trend.MACD(df['close'], window_fast=fast, window_slow=slow, window_sign=signal)
        macd_line   = macd_ind.macd()
        signal_line = macd_ind.macd_signal()
        buy_sig  = ((macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))).astype(int)
        sell_sig = ((macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))).astype(int)
        return buy_sig, sell_sig
    macd.ejecutar = _macd_ejecutar

    # --- MACD + Estocástico ---
    macd_stoch = types.ModuleType("macd_stoch")
    def _macd_stoch_ejecutar(df, macd_fast=12, macd_slow=26, macd_signal=9,
                             stoch_window=14, stoch_k_smooth=7, stoch_d_smooth=7,
                             usar_guardia_stoch=False, usar_guardia_macd=False):
        macd_ind  = ta.trend.MACD(close=df['close'], window_fast=macd_fast,
                                  window_slow=macd_slow, window_sign=macd_signal)
        macd_val  = macd_ind.macd()
        macd_sig  = macd_ind.macd_signal()
        stoch_ind = ta.momentum.StochasticOscillator(
            high=df['high'], low=df['low'], close=df['close'],
            window=stoch_window, smooth_window=stoch_k_smooth)
        stoch_k = stoch_ind.stoch()
        stoch_d = stoch_ind.stoch_signal()
        base_buy  = (macd_val > 0) & (stoch_k < 80)
        base_sell = (macd_val < 0) | ((macd_val > 0) & (stoch_k > 80))
        buy_sig = base_buy.copy()
        if usar_guardia_stoch:
            buy_sig = buy_sig & (stoch_k > stoch_d)
        if usar_guardia_macd:
            buy_sig = buy_sig & (macd_val > macd_sig)
        return buy_sig.astype(int), base_sell.astype(int)
    macd_stoch.ejecutar = _macd_stoch_ejecutar

    # --- Red Neuronal (RNN) ---
    rnn = types.ModuleType("rnn")
    def _rnn_ejecutar(df, features_list=None, lookback=10, epochs=30, batch_size=32, model_save_path=None):
        import os, tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import SimpleRNN, Dense, Dropout
        if features_list is None:
            features_list = [
                'RSI','Momentum','MACD','Signal','EMA20','EMA50','EMA200','VWAP20',
                'BB_upper','BB_middle','BB_lower',
                'Stochastic_%K_14_7_7','Stochastic_%D_14_7_7',
                'Stochastic_%K_7_3_3','Stochastic_%D_7_3_3',
                'Close_val','Volume_val']
        df_feat = _calcular_indicadores_comunes(df)
        lagged_features = []
        for col in features_list:
            df_feat[col + '_lag1'] = df_feat[col].shift(1)
            lagged_features.append(col + '_lag1')
        df_feat['Direccion'] = (df_feat['close'] > df_feat['close'].shift(1)).astype(int)
        df_clean = df_feat[['close','Direccion'] + lagged_features].dropna()
        split_date_idx = int(len(df) * 0.7)
        train_idx = df_clean.index[df_clean.index < split_date_idx]
        test_idx  = df_clean.index[df_clean.index >= split_date_idx]
        X_train = df_clean.loc[train_idx, lagged_features]
        y_train = df_clean.loc[train_idx, 'Direccion']
        X_test  = df_clean.loc[test_idx,  lagged_features]
        y_test  = df_clean.loc[test_idx,  'Direccion']
        if len(X_train) <= lookback or len(X_test) == 0:
            split_idx = int(len(df_clean) * 0.7)
            X_train  = df_clean.iloc[:split_idx][lagged_features]
            y_train  = df_clean.iloc[:split_idx]['Direccion']
            X_test   = df_clean.iloc[split_idx:][lagged_features]
            y_test   = df_clean.iloc[split_idx:]['Direccion']
            test_idx = df_clean.iloc[split_idx:].index
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled  = scaler.transform(X_test)
        def create_sequences(X, y):
            X_seq, y_seq = [], []
            for i in range(lookback, len(X)):
                X_seq.append(X[i-lookback:i])
                y_seq.append(y.iloc[i])
            return np.array(X_seq), np.array(y_seq)
        X_train_rnn, y_train_rnn = create_sequences(X_train_scaled, y_train)
        X_scaled_all = np.vstack([X_train_scaled[-lookback:], X_test_scaled])
        y_all = pd.concat([y_train.iloc[-lookback:], y_test])
        X_test_rnn, y_test_rnn = create_sequences(X_scaled_all, y_all)
        np.random.seed(42)
        tf.random.set_seed(42)
        rnn_model = Sequential([
            SimpleRNN(32, input_shape=(lookback, len(lagged_features)), activation='relu'),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')])
        rnn_model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
        rnn_model.fit(X_train_rnn, y_train_rnn, epochs=epochs, batch_size=batch_size, verbose=0)
        if model_save_path:
            os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
            rnn_model.save(model_save_path)
        rnn_prob = rnn_model.predict(X_test_rnn, verbose=0).flatten()
        preds = (rnn_prob > 0.5).astype(int)
        pred_series = pd.Series(0, index=df.index)
        pred_series.loc[test_idx] = preds
        buy_sig  = ((pred_series == 1) & (pred_series.shift(1) != 1)).astype(int)
        sell_sig = ((pred_series == 0) & (pred_series.shift(1) == 1)).astype(int)
        return buy_sig, sell_sig
    rnn.ejecutar = _rnn_ejecutar

    # --- RSI ---
    rsi = types.ModuleType("rsi")
    def _rsi_ejecutar(df, window=14, limit_buy=30, limit_sell=70):
        rsi_val  = ta.momentum.rsi(df['close'], window=window)
        buy_sig  = (rsi_val < limit_buy).astype(int)
        sell_sig = (rsi_val > limit_sell).astype(int)
        return buy_sig, sell_sig
    rsi.ejecutar = _rsi_ejecutar

    # --- Doble Estocástico ---
    stoch_double = types.ModuleType("stoch_double")
    def _stoch_double_ejecutar(df, w1=14, k1=7, d1=7, w2=7, k2=3, d2=3, usar_guardia=False):
        stoch1  = ta.momentum.StochasticOscillator(
            high=df['high'], low=df['low'], close=df['close'], window=w1, smooth_window=k1)
        stoch_k1 = stoch1.stoch()
        stoch_d1 = stoch1.stoch_signal()
        stoch2  = ta.momentum.StochasticOscillator(
            high=df['high'], low=df['low'], close=df['close'], window=w2, smooth_window=k2)
        stoch_k2 = stoch2.stoch()
        stoch_d2 = stoch2.stoch_signal()
        if usar_guardia:
            buy_sig  = ((stoch_k1 < 20) & (stoch_k2 < 20) & (stoch_k1 > stoch_d1) & (stoch_k2 > stoch_d2)).astype(int)
            sell_sig = ((stoch_k1 > 80) & (stoch_k2 > 80) & (stoch_k1 < stoch_d1) & (stoch_k2 < stoch_d2)).astype(int)
        else:
            buy_sig  = ((stoch_k1 < 20) & (stoch_k2 < 20)).astype(int)
            sell_sig = ((stoch_k1 > 80) & (stoch_k2 > 80)).astype(int)
        return buy_sig, sell_sig
    stoch_double.ejecutar = _stoch_double_ejecutar

    # --- Estocástico + Momentum ---
    stoch_momentum = types.ModuleType("stoch_momentum")
    def _stoch_momentum_ejecutar(df, stoch_window=14, stoch_smooth=3,
                                 stoch_limit_buy=20, stoch_limit_sell=80, momentum_window=14):
        stoch   = ta.momentum.StochasticOscillator(
            high=df['high'], low=df['low'], close=df['close'],
            window=stoch_window, smooth_window=stoch_smooth)
        stoch_k  = stoch.stoch()
        momentum = df['close'].diff(momentum_window)
        buy_sig  = ((stoch_k < stoch_limit_buy)  & (momentum > 0)).astype(int)
        sell_sig = ((stoch_k > stoch_limit_sell) & (momentum < 0)).astype(int)
        return buy_sig, sell_sig
    stoch_momentum.ejecutar = _stoch_momentum_ejecutar

    # --- Estocástico Simple ---
    stoch_simple = types.ModuleType("stoch_simple")
    def _stoch_simple_ejecutar(df, window=14, k_smooth=7, d_smooth=7, usar_guardia=False):
        stoch   = ta.momentum.StochasticOscillator(
            high=df['high'], low=df['low'], close=df['close'],
            window=window, smooth_window=k_smooth)
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()
        if usar_guardia:
            buy_sig  = ((stoch_k < 20) & (stoch_k > stoch_d)).astype(int)
            sell_sig = ((stoch_k > 80) & (stoch_k < stoch_d)).astype(int)
        else:
            buy_sig  = (stoch_k < 20).astype(int)
            sell_sig = (stoch_k > 80).astype(int)
        return buy_sig, sell_sig
    stoch_simple.ejecutar = _stoch_simple_ejecutar

    # -------------------------------------------------------------------------

    ESTRATEGIAS = {
        "Bollinger Bands":        bollinger,
        "EMA Crossover":          ema,
        "Regresión Logística":    logit,
        "MACD Crossover":         macd,
        "MACD + Estocástico":     macd_stoch,
        "Red Neuronal (RNN)":     rnn,
        "RSI":                    rsi,
        "Doble Estocástico":      stoch_double,
        "Estocástico + Momentum": stoch_momentum,
        "Estocástico Simple":     stoch_simple,
    }

    def descubrir_estrategias():
        return ESTRATEGIAS
    #backtest
    def ejecutar_backtest(df_raw, modulo, nombre):
        df = df_raw.copy().reset_index(drop=True)
        try:
            buy_sig, sell_sig = modulo.ejecutar(df)
        except Exception as e:
            return {"error": str(e)}

        buy_sig  = buy_sig.fillna(0).astype(int)
        sell_sig = sell_sig.fillna(0).astype(int)

        capital, posicion = CAPITAL_INI, 0.0
        equity, operaciones = [], []

        for i in range(len(df)):
            precio = df["close"].iloc[i]
            if buy_sig.iloc[i] == 1 and posicion == 0 and precio > 0:
                com      = capital * COMISION
                posicion = (capital - com) / precio
                capital  = 0.0
                operaciones.append({"tipo": "compra", "costo_com": com})
            elif sell_sig.iloc[i] == 1 and posicion > 0 and precio > 0:
                ingresos = posicion * precio
                com      = ingresos * COMISION
                capital  = ingresos - com
                posicion = 0.0
                operaciones.append({"tipo": "venta", "costo_com": com})
            equity.append(capital + posicion * precio)

        if posicion > 0:
            equity[-1] = posicion * df["close"].iloc[-1] * (1 - COMISION)

        eq      = pd.Series(equity, index=df_raw.index[:len(equity)])
        retorno = (eq.iloc[-1] / CAPITAL_INI - 1) * 100
        rets    = eq.pct_change().dropna()
        sharpe  = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
        dd      = (eq - eq.cummax()) / eq.cummax() * 100
        costos  = sum(o["costo_com"] for o in operaciones)
        n_ventas = sum(1 for o in operaciones if o["tipo"] == "venta")

        return {
            "nombre": nombre, "equity": eq, "error": None,
            "Retorno Total (%)":  round(retorno, 2),
            "Max Drawdown (%)":   round(dd.min(), 2),
            "Sharpe Ratio":       round(sharpe, 4),
            "Núm. Operaciones":   n_ventas,
            "Costos Totales ($)": round(costos, 2),
        }

    COLORES = ['#1f77b4','#d62728','#2ca02c','#ff7f0e','#9467bd',
               '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']
    COLS_METRICAS = ["Retorno Total (%)", "Max Drawdown (%)",
                     "Sharpe Ratio", "Núm. Operaciones", "Costos Totales ($)"]
    
    st.header("Backtest de Estrategias")
    tickers_bt = st.multiselect("Activos a analizar", list(datos.keys()),
                                default=list(datos.keys()))

    if st.button("Ejecutar Backtest", type="primary"):

        estrategias = descubrir_estrategias()

        # iterar por cada activo seleccionado
        for ticker_bt in tickers_bt:
            st.subheader(f" {ticker_bt}")
            df_raw = datos[ticker_bt]

            resultados = {}
            prog  = st.progress(0)
            total = len(estrategias)

            for i, (nombre, modulo) in enumerate(estrategias.items()):
                res = ejecutar_backtest(df_raw.copy(), modulo, nombre)
                if res.get("error"):
                    st.warning(f" {nombre}: {res['error']}")
                else:
                    resultados[nombre] = res
                prog.progress((i + 1) / total)
            prog.empty()

            if not resultados:
                st.error(f"Ninguna estrategia pudo ejecutarse para {ticker_bt}.")
                continue

            # resumen
            resumen = pd.DataFrame(
                {n: {c: r[c] for c in COLS_METRICAS} for n, r in resultados.items()}
            ).T

            # ranking
            ranking = pd.DataFrame(index=resumen.index)
            ranking['Rank Retorno']     = resumen['Retorno Total (%)'].rank(ascending=False).astype(int)
            ranking['Rank Drawdown']    = resumen['Max Drawdown (%)'].rank(ascending=False).astype(int)
            ranking['Rank Sharpe']      = resumen['Sharpe Ratio'].rank(ascending=False).astype(int)
            ranking['Rank Operaciones'] = resumen['Núm. Operaciones'].rank(ascending=True).astype(int)
            ranking['Rank Costos']      = resumen['Costos Totales ($)'].rank(ascending=True).astype(int)
            ranking['Score Promedio']   = ranking.mean(axis=1)
            ranking['Ranking General']  = ranking['Score Promedio'].rank(ascending=True).astype(int)
            ranking = ranking.sort_values('Ranking General')
            mejor   = ranking.index[0]

            st.success(f"Mejor estrategia para **{ticker_bt}**: **{mejor}** "
                       f"(Score: {ranking.loc[mejor, 'Score Promedio']:.2f})")

            tab_m, tab_r, tab_radar, tab_eq = st.tabs(
                ["Métricas", "Ranking", "Gráfica", "Gráfica de curvas"])

            with tab_m:
                def color_celda(val, col):
                    if col == "Retorno Total (%)":
                        return "color: green; font-weight:bold" if val > 0 else "color: red; font-weight:bold"
                    if col == "Max Drawdown (%)":
                        return "color: green" if val > -10 else "color: red"
                    if col == "Sharpe Ratio":
                        return "color: green" if val > 0 else "color: red"
                    return ""

                styled = resumen.style.format({
                    "Retorno Total (%)":  "{:.2f}%",
                    "Max Drawdown (%)":   "{:.2f}%",
                    "Sharpe Ratio":       "{:.4f}",
                    "Núm. Operaciones":   "{:.0f}",
                    "Costos Totales ($)": "{:.2f}",
                })
                for col in ["Retorno Total (%)", "Max Drawdown (%)", "Sharpe Ratio"]:
                    styled = styled.map(lambda v, c=col: color_celda(v, c), subset=[col])

                st.dataframe(styled, use_container_width=True)


            with tab_r:
                # highlight mejor fila
                def highlight_mejor(row):
                    return ["background-color: #d4edda; font-weight:bold"
                            if row.name == mejor else "" for _ in row]

                st.dataframe(
                    ranking.style
                        .apply(highlight_mejor, axis=1)
                        .format({"Score Promedio": "{:.2f}"}),
                    use_container_width=True
                )

            with tab_radar:
                eps = 1e-9
                rd  = pd.DataFrame(index=resumen.index)
                rd['Retorno'] = (resumen['Retorno Total (%)'] - resumen['Retorno Total (%)'].min()) / \
                                (resumen['Retorno Total (%)'].max() - resumen['Retorno Total (%)'].min() + eps)
                rd['Drawdown'] = 1 - (abs(resumen['Max Drawdown (%)']) - abs(resumen['Max Drawdown (%)']).min()) / \
                                 (abs(resumen['Max Drawdown (%)']).max() - abs(resumen['Max Drawdown (%)']).min() + eps)
                sp = resumen['Sharpe Ratio'] - resumen['Sharpe Ratio'].min()
                rd['Sharpe'] = sp / (sp.max() + eps)
                rd['Eficiencia Ops'] = 1 - (resumen['Núm. Operaciones'] - resumen['Núm. Operaciones'].min()) / \
                                       (resumen['Núm. Operaciones'].max() - resumen['Núm. Operaciones'].min() + eps)
                rd['Eficiencia Costos'] = 1 - (resumen['Costos Totales ($)'] - resumen['Costos Totales ($)'].min()) / \
                                          (resumen['Costos Totales ($)'].max() - resumen['Costos Totales ($)'].min() + eps)

                cats = ['Retorno','Drawdown','Sharpe','Eficiencia Ops','Eficiencia Costos']
                fig_radar = go.Figure()
                for i, est in enumerate(rd.index):
                    v = rd.loc[est].values.tolist()
                    fig_radar.add_trace(go.Scatterpolar(
                        r=v + [v[0]], theta=cats + [cats[0]],
                        name=est, line=dict(color=COLORES[i % len(COLORES)])))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 1])))
                st.plotly_chart(fig_radar, use_container_width=True)

            with tab_eq:
                fig_eq = go.Figure()
                bh = (df_raw["close"] / df_raw["close"].iloc[0]) * CAPITAL_INI
                fig_eq.add_trace(go.Scatter(x=df_raw.index, y=bh, mode="lines",
                                            name="Buy & Hold",
                                            line=dict(dash="dash", color="gray")))
                for i, (nombre, res) in enumerate(resultados.items()):
                    fig_eq.add_trace(go.Scatter(x=res["equity"].index,
                                                y=res["equity"].values,
                                                mode="lines", name=nombre,
                                                line=dict(color=COLORES[i % len(COLORES)])))
                fig_eq.update_layout(title=f" {ticker_bt}",
                                     xaxis_title="Fecha", yaxis_title="Capital ($)",
                                     height=500, hovermode="x unified")
                st.plotly_chart(fig_eq, use_container_width=True)

            st.divider()
