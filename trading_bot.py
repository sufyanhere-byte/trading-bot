import requests
import pandas as pd
import ta
import time
from datetime import datetime, timezone
import os

# ============================================
# SETTINGS - Railway Variables se aayengi
# ============================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "APNA_TOKEN_YAHAN_LIKHO")
CHAT_ID = os.environ.get("CHAT_ID", "APNA_CHAT_ID_YAHAN_LIKHO")
# ============================================

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("âœ… Telegram message bheja gaya!")
        else:
            print(f"âŒ Telegram error: {response.text}")
    except Exception as e:
        print(f"âŒ Telegram error: {e}")

def is_market_open():
    """
    Forex market hours check karo (GMT time)
    Market open: Monday 00:00 GMT â€” Friday 22:00 GMT
    Market band: Friday 22:00 GMT â€” Monday 00:00 GMT
    """
    now_gmt = datetime.now(timezone.utc)
    weekday = now_gmt.weekday()  # 0=Monday, 6=Sunday
    hour = now_gmt.hour

    # Saturday = 5, Sunday = 6
    if weekday == 5:  # Saturday
        return False, "ðŸ”´ Market BAND hai (Saturday)"
    elif weekday == 6:  # Sunday
        return False, "ðŸ”´ Market BAND hai (Sunday)"
    elif weekday == 4 and hour >= 22:  # Friday 22:00+ GMT
        return False, "ðŸ”´ Market BAND hai (Weekend shuru ho gaya)"
    elif weekday == 0 and hour < 1:  # Monday 00:00 GMT
        return False, "ðŸ”´ Market abhi khuli nahi (Monday early)"
    else:
        return True, "âœ… Market OPEN hai"

def get_market_data():
    url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=1d"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
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
        df = df.dropna().reset_index(drop=True)
        return df
    except Exception as e:
        print(f"âŒ Data fetch error: {e}")
        return None

def analyze_market(df):
    if df is None or len(df) < 30:
        return None
    close = df['close']
    high = df['high']
    low = df['low']

    df['rsi'] = ta.momentum.RSIIndicator(close, window=14).rsi()

    macd = ta.trend.MACD(close)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    bb = ta.volatility.BollingerBands(close, window=20)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()

    df['ema9'] = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df['ema21'] = ta.trend.EMAIndicator(close, window=21).ema_indicator()

    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df['stoch_k'] = stoch.stoch()
    df['stoch_d'] = stoch.stoch_signal()

    return df

def generate_signal(df):
    if df is None or len(df) < 2:
        return None, 0, []

    last = df.iloc[-1]
    prev = df.iloc[-2]
    up_signals = []
    down_signals = []

    if last['rsi'] < 35:
        up_signals.append("RSI Oversold ðŸ“‰â†’ðŸ“ˆ")
    elif last['rsi'] > 65:
        down_signals.append("RSI Overbought ðŸ“ˆâ†’ðŸ“‰")

    if last['macd'] > last['macd_signal'] and prev['macd'] <= prev['macd_signal']:
        up_signals.append("MACD Bullish Cross âœ…")
    elif last['macd'] < last['macd_signal'] and prev['macd'] >= prev['macd_signal']:
        down_signals.append("MACD Bearish Cross âŒ")
    elif last['macd_diff'] > 0:
        up_signals.append("MACD Positive Momentum")
    else:
        down_signals.append("MACD Negative Momentum")

    if last['close'] <= last['bb_lower']:
        up_signals.append("BB Lower Bounce ðŸ”„")
    elif last['close'] >= last['bb_upper']:
        down_signals.append("BB Upper Rejection ðŸ”„")

    if last['ema9'] > last['ema21'] and prev['ema9'] <= prev['ema21']:
        up_signals.append("EMA Bullish Cross ðŸ“ˆ")
    elif last['ema9'] < last['ema21'] and prev['ema9'] >= prev['ema21']:
        down_signals.append("EMA Bearish Cross ðŸ“‰")
    elif last['ema9'] > last['ema21']:
        up_signals.append("EMA Bullish Trend")
    else:
        down_signals.append("EMA Bearish Trend")

    if last['stoch_k'] < 20 and last['stoch_k'] > last['stoch_d']:
        up_signals.append("Stochastic Oversold ðŸ“ˆ")
    elif last['stoch_k'] > 80 and last['stoch_k'] < last['stoch_d']:
        down_signals.append("Stochastic Overbought ðŸ“‰")

    up_count = len(up_signals)
    down_count = len(down_signals)
    total = up_count + down_count

    if total == 0:
        return "WAIT", 0, ["Koi clear signal nahi"]

    if up_count > down_count:
        return "UP âœ…", int((up_count / total) * 100), up_signals
    elif down_count > up_count:
        return "DOWN ðŸ”´", int((down_count / total) * 100), down_signals
    else:
        return "WAIT â³", 50, ["Mixed signals - wait karo"]

def wait_for_signal_time():
    """
    Exact signal time ka wait karo
    Signal: X:04, X:09, X:14, X:19, X:24...
    Trade:  X:05, X:10, X:15, X:20, X:25...
    """
    while True:
        now = datetime.now()
        minute = now.minute
        second = now.second

        # Signal time check: minute jo (5n - 1) ho, second = 0
        if (minute + 1) % 5 == 0 and second == 0:
            next_trade_minute = minute + 1
            next_trade_hour = now.hour
            if next_trade_minute >= 60:
                next_trade_minute = 0
                next_trade_hour += 1
            trade_time = now.replace(
                hour=next_trade_hour,
                minute=next_trade_minute,
                second=0, microsecond=0
            )
            return trade_time

        # Kitna time bacha hai
        current_block = minute // 5
        next_signal_minute = (current_block + 1) * 5 - 1
        if next_signal_minute >= 60:
            next_signal_minute = 4
            seconds_left = (60 - minute - 1) * 60 + (60 - second) + 4 * 60
        else:
            seconds_left = (next_signal_minute - minute) * 60 - second

        print(f"â³ {now.strftime('%H:%M:%S')} â€” Signal {seconds_left}s baad")
        sleep_time = min(seconds_left - 2, 30)
        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            time.sleep(1)

def format_message(signal, confidence, reasons, last_row, trade_time):
    now = datetime.now().strftime("%H:%M:%S")
    trade_time_str = trade_time.strftime("%H:%M")

    if confidence >= 80:
        strength = "ðŸ’ª STRONG"
    elif confidence >= 60:
        strength = "ðŸ‘ MEDIUM"
    else:
        strength = "âš ï¸ WEAK"

    reasons_text = "\n".join([f"  â€¢ {r}" for r in reasons])

    return f"""
ðŸ¤– <b>TRADING SIGNAL</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
ðŸ“Š Pair: <b>EUR/USD</b>
â± Timeframe: <b>5 Minute</b>
ðŸ• Signal Time: <b>{now}</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
ðŸŽ¯ Direction: <b>{signal}</b>
ðŸ“ˆ Confidence: <b>{confidence}%</b>
ðŸ’¡ Strength: <b>{strength}</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
â° <b>TRADE KARO: {trade_time_str} pe!</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
ðŸ“‹ <b>Reasons:</b>
{reasons_text}
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
ðŸ’° Price: <b>{last_row['close']:.5f}</b>
ðŸ“Š RSI: <b>{last_row['rsi']:.1f}</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
âš ï¸ <i>Pehle demo pe test karo!</i>
"""

def main():
    print("ðŸš€ Trading Bot Shuru Ho Gaya!")
    print("ðŸ“Š EUR/USD | 5 Min")
    print("=" * 40)

    send_telegram("""ðŸ¤– <b>Trading Bot Active!</b>
ðŸ“Š EUR/USD | 5 Min

â° <b>Signal Schedule:</b>
â€¢ Signal aayega: X:04, X:09, X:14...
â€¢ Trade karo: X:05, X:10, X:15...

ðŸ—“ <b>Market Days:</b> Monday â€” Friday
âŒ Weekend pe koi signal nahi aayega

<i>Intezaar karo pehle signal ka...</i>""")

    market_closed_notified = False  # Baar baar message na bheje

    while True:
        try:
            # Market hours check karo
            market_open, market_status = is_market_open()

            if not market_open:
                print(f"ðŸ’¤ {market_status}")

                # Sirf ek baar message bhejo jab market band ho
                if not market_closed_notified:
                    now_gmt = datetime.now(timezone.utc)
                    send_telegram(f"""ðŸ˜´ <b>Market Band Hai</b>
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”
{market_status}

ðŸ—“ <b>Market kab khulegi?</b>
Monday subah 12:00 AM GMT pe

ðŸ‡µðŸ‡° <b>Pakistan Time:</b> Monday 5:00 AM PKT

<i>Bot automatically start ho jayega jab market khulegi!</i>""")
                    market_closed_notified = True

                # 30 minute baad dobara check karo
                time.sleep(1800)
                continue

            # Market open hai â€” normal flow
            if market_closed_notified:
                send_telegram("ðŸŸ¢ <b>Market Khul Gayi!</b>\nðŸ“Š EUR/USD signals shuru ho rahe hain...\n\nâ° Pehla signal aa raha hai!")
                market_closed_notified = False

            # Exact signal time ka wait karo
            trade_time = wait_for_signal_time()

            # Market dobara check karo signal time pe
            market_open, market_status = is_market_open()
            if not market_open:
                continue

            now = datetime.now()
            print(f"\nðŸ“¡ {now.strftime('%H:%M:%S')} - Analyzing...")

            df = get_market_data()

            if df is not None:
                df = analyze_market(df)
                signal, confidence, reasons = generate_signal(df)
                print(f"ðŸŽ¯ Signal: {signal} | Confidence: {confidence}%")

                if signal and "WAIT" not in signal and confidence >= 60:
                    last_row = df.iloc[-1]
                    message = format_message(signal, confidence, reasons, last_row, trade_time)
                    send_telegram(message)
                    print(f"ðŸ“± Signal bheja! Trade: {trade_time.strftime('%H:%M')}")
                else:
                    msg = f"â³ <b>Weak Signal â€” Skip</b>\nðŸ“Š EUR/USD | {now.strftime('%H:%M')}\nðŸ’¡ Confidence: {confidence}%\n\n<i>Is candle pe mat trade karo</i>"
                    send_telegram(msg)
                    print("âš ï¸ Weak signal â€” skipped")
            else:
                send_telegram("âš ï¸ <b>Data Error</b> â€” Internet check karo")

            time.sleep(65)

        except KeyboardInterrupt:
            print("\nðŸ›‘ Bot band ho gaya!")
            send_telegram("ðŸ›‘ <b>Trading Bot Band Ho Gaya!</b>")
            break
        except Exception as e:
            print(f"âŒ Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()    df['rsi'] = rsi.rsi()
    
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
