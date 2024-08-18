from pyrogram import Client, filters
from binance.client import Client as BinanceClient
import requests
import asyncio
import time

# Telegram bot token
api_id = "21508524"
api_hash = "5e36d59e9f452a6d4271637f8669a182"
bot_token = "7125720549:AAH-M0VFjcyqNMW0QkT357VssX7DHFgPJXA"

# Binance API keys
binance_api_key = "6KqDqNcv9ZjKUOGqIComs55Xd3rChP0ELYfiBO1a21sfFeN475qjtCmXnux7zVG4"
binance_api_secret = "bRzeHvFyteF9pWynihoKoEQLG0wsRoLKRCMNwpsigQCG8LGcUXz93ZmaOYhGR8ms"

# Bybit API endpoints
bybit_api_url = "https://api.bybit.com/v2/public/tickers"
bybit_open_interest_url = "https://api.bybit.com/v2/public/open-interest"
bybit_liquidation_url = "https://api.bybit.com/v2/public/liquidations"

# Initialize Pyrogram client
app = Client("price_monitor_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Initialize Binance client
binance_client = BinanceClient(binance_api_key, binance_api_secret)

# List of user IDs to notify
subscribed_users = []

# Fetch price from Binance
async def fetch_binance_price(symbol):
    try:
        ticker = binance_client.get_ticker(symbol=symbol)
        return float(ticker["lastPrice"])
    except Exception as e:
        print(f"Error fetching Binance price for {symbol}: {e}")
        return None

# Fetch price from Bybit
async def fetch_bybit_price(symbol):
    try:
        time.sleep(1)  # Delay to avoid rate limit
        response = requests.get(bybit_api_url)
        response.raise_for_status()  # Raises HTTPError for bad responses
        data = response.json()
        for ticker in data["result"]:
            if ticker["symbol"] == symbol:
                return float(ticker["last_price"])
        print(f"Symbol {symbol} not found in Bybit response")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bybit price for {symbol}: {e}")
        return None
    except ValueError as e:
        print(f"Error decoding Bybit response: {e}")
        return None

# Fetch open interest from Bybit
async def fetch_bybit_open_interest(symbol):
    try:
        time.sleep(1)  # Delay to avoid rate limit
        response = requests.get(bybit_open_interest_url, params={"symbol": symbol})
        response.raise_for_status()
        return response.json()["result"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bybit open interest for {symbol}: {e}")
        return None
    except ValueError as e:
        print(f"Error decoding Bybit open interest response: {e}")
        return None

# Fetch liquidations from Bybit
async def fetch_bybit_liquidations():
    try:
        response = requests.get(bybit_liquidation_url)
        response.raise_for_status()
        return response.json()["result"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Bybit liquidations: {e}")
        return None
    except ValueError as e:
        print(f"Error decoding Bybit liquidations response: {e}")
        return None

@app.on_message(filters.command(["start"]))
async def start(client, message):
    await message.reply("Привет! Я бот для мониторинга цен на Binance и Bybit. Используйте команду /price, чтобы получить текущие цены. Чтобы подписаться на уведомления, используйте команду /subscribe.")

@app.on_message(filters.command(["price"]))
async def price(client, message):
    args = message.text.split()
    if len(args) != 2:
        await message.reply("Использование: /price SYMBOL")
        return

    symbol = args[1].upper()
    binance_price = await fetch_binance_price(symbol)
    bybit_price = await fetch_bybit_price(symbol)

    if binance_price is None and bybit_price is None:
        await message.reply(f"Не удалось получить цену для символа {symbol}. Проверьте символ и попробуйте снова.")
    elif binance_price is None:
        await message.reply(f"Не удалось получить цену для символа {symbol} на Binance. Проверьте символ и попробуйте снова.")
    elif bybit_price is None:
        await message.reply(f"Не удалось получить цену для символа {symbol} на Bybit. Проверьте символ и попробуйте снова.")
    else:
        await message.reply(f"Текущая цена {symbol}:\nBinance: {binance_price} USD\nBybit: {bybit_price} USD")

@app.on_message(filters.command(["subscribe"]))
async def subscribe(client, message):
    user_id = message.from_user.id
    if user_id not in subscribed_users:
        subscribed_users.append(user_id)
        await message.reply("Вы подписались на уведомления о значительных изменениях на рынке.")
    else:
        await message.reply("Вы уже подписаны на уведомления.")

async def notify_users(text):
    for user_id in subscribed_users:
        try:
            await app.send_message(chat_id=user_id, text=text)
        except Exception as e:
            print(f"Failed to send message to {user_id}: {e}")

async def price_monitor():
    previous_open_interest = {}
    while True:
        # Example of monitoring BTCUSDT
        symbol = "BTCUSDT"
        binance_price = await fetch_binance_price(symbol)
        bybit_price = await fetch_bybit_price(symbol)
        open_interest = await fetch_bybit_open_interest(symbol)
        liquidations = await fetch_bybit_liquidations()

        if binance_price and bybit_price:
            price_diff = abs(binance_price - bybit_price)
            if price_diff > 100:  # Example threshold
                await notify_users(f"Significant price difference detected for {symbol}: Binance {binance_price} USD, Bybit {bybit_price} USD")

        if open_interest:
            new_open_interest = open_interest["open_interest"]
            if symbol in previous_open_interest:
                interest_diff = abs(new_open_interest - previous_open_interest[symbol])
                if interest_diff / previous_open_interest[symbol] > 0.05:  # Example threshold for 5% change
                    await notify_users(f"Significant open interest change detected for {symbol}: {new_open_interest}")
            previous_open_interest[symbol] = new_open_interest

        if liquidations:
            for liquidation in liquidations:
                if liquidation["symbol"] == symbol and liquidation["qty"] > 100000:  # Example threshold for large liquidation
                    await notify_users(f"Large liquidation detected for {symbol}: {liquidation['qty']}")

        await asyncio.sleep(60)  # Check every minute

if __name__ == "__main__":
    app.start()
    loop = asyncio.get_event_loop()
    loop.create_task(price_monitor())
    loop.run_forever()

