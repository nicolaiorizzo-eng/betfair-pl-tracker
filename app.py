import streamlit as st
import pandas as pd

st.set_page_config(page_title="Betfair Analytics Dashboard", layout="wide")

st.title("🎯 Betfair Automated Analytics Dashboard")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv("betfair_history.csv")
        df['settledDate'] = pd.to_datetime(df['settledDate'])
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("No trading data found. Please run your sync engine script first.")
else:
    # --- Performance Metrics Calculation ---
    total_net_profit = df['profit'].sum()
    total_liability = df['liability'].sum()
    
    # ROI based on total liability exposed over time
    overall_roi = (total_net_profit / total_liability * 100) if total_liability > 0 else 0
    
    total_trades = len(df)
    winning_trades = len(df[df['profit'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    # --- High-Level KPI Blocks ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Net Profit", f"£{total_net_profit:,.2f}")
    col2.metric("Total Liability Exposed", f"£{total_liability:,.2f}")
    col3.metric("Total ROI", f"{overall_roi:.2f}%")
    col4.metric("Win Rate", f"{win_rate:.1f}% ({winning_trades}/{total_trades})")

    st.markdown("---")

    # --- Analytics & Visualizations Breakdown ---
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("📈 Cumulative Profit/Loss Trend")
        df_sorted = df.sort_values('settledDate')
        df_sorted['Cumulative P&L'] = df_sorted['profit'].cumsum()
        st.line_chart(data=df_sorted, x='settledDate', y='Cumulative P&L')

    with right_col:
        st.subheader("⚽ ROI & Profit breakdown by Event/Game")
        # Aggregating metrics per specific game traded
        game_stats = df.groupby('event').agg(
            Trades=('profit', 'count'),
            Net_Profit=('profit', 'sum'),
            Total_Liability=('liability', 'sum')
        ).reset_index()
        
        game_stats['ROI (%)'] = (game_stats['Net_Profit'] / game_stats['Total_Liability'] * 100).round(2)
        game_stats = game_stats.sort_values(by='Net_Profit', ascending=False)
        
        st.dataframe(game_stats, use_container_width=True)

    # --- Detailed Historical Table ---
    st.subheader("🔍 Detailed Trade Log")
    st.dataframe(df.sort_values(by='settledDate', ascending=False), use_container_width=True)