import requests
import pandas as pd
import ta
import time
from datetime import datetime

# ============================================
# APNI SETTINGS YAHAN LIKHO
# ============================================
TELEGRAM_TOKEN = "APNA_TOKEN_YAHAN_LIKHO"
CHAT_ID = "APNA_CHAT_ID_YAHAN_LIKHO"
PAIR = "EURUSD"
TIMEFRAME = "5min"
# ============================================

def send_telegram(message):
    """Telegram pe message bhejo"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=data)
        print("✅ Telegram message bheja gaya!")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def get_market_data():
    """Alpha Vantage se EUR/USD ka data fetch karo (Free API)"""
    # Free API use kar rahe hain - koi key nahi chahiye
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=1d"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        # Data extract karo
        timestamps = data['chart']['result'][0]['timestamp']
        ohlcv = data['chart']['result'][0]['indicators']['quote'][0]
        
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'open': ohlcv['open'],
            'high': ohlcv['high'],
            'low': ohlcv['low'],
            'close': ohlcv['close'],
            'volume': ohlcv['volume']
        })
        
        df = df.dropna()
        df = df.reset_index(drop=True)
        return df
        
    except Exception as e:
        print(f"❌ Data fetch error: {e}")
        return None

def analyze_market(df):
    """Technical analysis karo"""
    
    if df is None or len(df) < 30:
        return None
    
    close = df['close']
    high = df['high']
    low = df['low']
    
    # ---- INDICATORS ----
    
    # 1. RSI (14)
    rsi = ta.momentum.RSIIndicator(close, window=14)
    df['rsi'] = rsi.rsi()
    
    # 2. MACD
    macd = ta.trend.MACD(close)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()
    
    # 3. Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_mid'] = bb.bollinger_mavg()
    
    # 4. EMA
    df['ema9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    
    # 5. Stochastic
    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()
    
    return df

def generate_signal(df):
    """Signal generate karo - UP ya DOWN"""
    
    if df is None or len(df) < 2:
        return None, 0, []
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    up_signals = []
    down_signals = []
    
    # ---- RSI Check ----
    if last['rsi'] < 35:
        up_signals.append("RSI Oversold (BUY zone)")
    elif last['rsi'] > 65:
        down_signals.append("RSI Overbought (SELL zone)")
    
    # ---- MACD Check ----
    if last['macd'] > last['macd_signal'] and prev['macd'] <= prev['macd_signal']:
        up_signals.append("MACD Bullish Cross")
    elif last['macd'] < last['macd_signal'] and prev['macd'] >= prev['macd_signal']:
        down_signals.append("MACD Bearish Cross")
    elif last['macd_diff'] > 0:
        up_signals.append("MACD Positive")
    else:
        down_signals.append("MACD Negative")
    
    # ---- Bollinger Bands Check ----
    if last['close'] <= last['bb_lower']:
        up_signals.append("Price at Lower BB (Bounce expected)")
    elif last['close'] >= last['bb_upper']:
        down_signals.append("Price at Upper BB (Reversal expected)")
    
    # ---- EMA Cross Check ----
    if last['ema9'] > last['ema21'] and prev['ema9'] <= prev['ema21']:
        up_signals.append("EMA9 crossed above EMA21 (Bullish)")
    elif last['ema9'] < last['ema21'] and prev['ema9'] >= prev['ema21']:
        down_signals.append("EMA9 crossed below EMA21 (Bearish)")
    elif last['ema9'] > last['ema21']:
        up_signals.append("EMA Bullish trend")
    else:
        down_signals.append("EMA Bearish trend")
    
    # ---- Stochastic Check ----
    if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d']:
        up_signals.append("Stochastic Oversold + Bullish Cross")
    elif last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d']:
        down_signals.append("Stochastic Overbought + Bearish Cross")
    
    # ---- Final Decision ----
    up_count = len(up_signals)
    down_count = len(down_signals)
    total = up_count + down_count
    
    if total == 0:
        return "WAIT", 0, ["Koi clear signal nahi"]
    
    if up_count > down_count:
        confidence = int((up_count / total) * 100)
        return "UP ✅", confidence, up_signals
    elif down_count > up_count:
        confidence = int((down_count / total) * 100)
        return "DOWN 🔴", confidence, down_signals
    else:
        return "WAIT ⏳", 50, ["Signals mixed hain - wait karo"]

def format_message(signal, confidence, reasons, last_row):
    """Telegram message format karo"""
    
    now = datetime.now().strftime("%H:%M:%S")
    
    # Confidence ke hisaab se emoji
    if confidence >= 80:
        strength = "💪 STRONG"
    elif confidence >= 60:
        strength = "👍 MEDIUM"
    else:
        strength = "⚠️ WEAK"
    
    reasons_text = "\n".join([f"  • {r}" for r in reasons])
    
    message = f"""
🤖 <b>TRADING SIGNAL</b>
━━━━━━━━━━━━━━━━━━
📊 Pair: <b>EUR/USD</b>
⏱ Timeframe: <b>5 Minute</b>
🕐 Time: <b>{now}</b>
━━━━━━━━━━━━━━━━━━
🎯 Signal: <b>{signal}</b>
📈 Confidence: <b>{confidence}%</b>
💡 Strength: <b>{strength}</b>
━━━━━━━━━━━━━━━━━━
📋 <b>Reasons:</b>
{reasons_text}
━━━━━━━━━━━━━━━━━━
💰 Current Price: <b>{last_row['close']:.5f}</b>
📊 RSI: <b>{last_row['rsi']:.1f}</b>
━━━━━━━━━━━━━━━━━━
⚠️ <i>Apni risk apni - sirf demo pe test karo pehle!</i>
"""
    return message

def main():
    """Main bot loop"""
    print("🚀 Trading Bot Shuru Ho Gaya!")
    print(f"📊 Pair: EUR/USD | Timeframe: 5 Min")
    print("=" * 40)
    
    # Start message bhejo
    send_telegram("🤖 <b>Trading Bot Active Ho Gaya!</b>\n📊 EUR/USD | 5 Min\n⏳ Pehla signal aa raha hai...")
    
    last_signal = None
    
    while True:
        try:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Data analyze ho raha hai...")
            
            # Data fetch karo
            df = get_market_data()
            
            if df is not None:
                # Analysis karo
                df = analyze_market(df)
                
                # Signal generate karo
                signal, confidence, reasons = generate_signal(df)
                
                print(f"🎯 Signal: {signal} | Confidence: {confidence}%")
                
                # Sirf strong signals bhejo (60% se upar)
                # Aur sirf naya signal bhejo agar pehle se alag ho
                if signal and confidence >= 60 and signal != last_signal:
                    last_row = df.iloc[-1]
                    message = format_message(signal, confidence, reasons, last_row)
                    send_telegram(message)
                    last_signal = signal
                    print("📱 Signal Telegram pe bheja gaya!")
                elif confidence < 60:
                    print("⏳ Signal weak hai, wait kar raha hoon...")
                else:
                    print("🔄 Signal same hai, naya signal aane ka intezaar...")
            
            # 5 minute wait karo
            print("⏳ 5 minute baad phir check karunga...")
            time.sleep(300)  # 300 seconds = 5 minutes
            
        except KeyboardInterrupt:
            print("\n🛑 Bot band ho gaya!")
            send_telegram("🛑 <b>Trading Bot Band Ho Gaya!</b>")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(60)  # Error pe 1 minute wait karo

if __name__ == "__main__":
    main()
