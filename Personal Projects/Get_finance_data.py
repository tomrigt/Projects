import yfinance as yahooFinance
import plotly.graph_objects as go
import pandas as pd
from matplotlib.pyplot import title
import mplfinance as mpl

GetStockInformation = yahooFinance.Ticker("PHIA.AS")

df_raw = GetStockInformation.history(period="2y", interval="1h")
#df_raw.reset_index(inplace=True)

#mpl.plot(
#    df_raw,
#    type="candle",
#    mav =(9,50,200),
#   title = "Philips Price",
#    style="yahoo"
#    )


def signal_gap(Data, opening, close, width, buy, sell):
    for i in range(len(Data)):

        print(Data[i, opening])

        if Data[i, opening] < Data[i - 1, close] and abs(Data[i, opening] - Data[i - 1, close]) >= width:
            Data[i, buy] = 1

        if Data[i, opening] > Data[i - 1, close] and abs(Data[i, opening] - Data[i - 1, close]) >= width:
            Data[i, sell] = -1

    return Data

df_raw['Buy'] = ""
df_raw['Sell'] = ""

width = 0.0005
open = "Open"
close = "Close"
buy = "Buy"
sell = "Sell"
signal_gap(df_raw, open, close, width, buy, sell)
print(df_raw)