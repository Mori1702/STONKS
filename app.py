from flask import Flask, request, render_template_string
import yfinance as yf
import pandas as pd

app = Flask(__name__)

# ---------------------------
# Bewertungssystem
# ---------------------------
def bewertung(diff_percent):
    abs_diff = abs(diff_percent)

    if abs_diff < 5:
        return None
    elif abs_diff < 10:
        level = "lohnt sich ein bisschen"
    elif abs_diff < 20:
        level = "lohnt sich"
    elif abs_diff < 50:
        level = "lohnt sich sehr"
    else:
        level = "🔥 EXTREM gute Gelegenheit"

    action = "KAUF" if diff_percent < 0 else "VERKAUF"
    return action, level, abs_diff


# ---------------------------
# HTML Template
# ---------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Aktien Analyzer</title>
    <style>
        body {
            font-family: Arial;
            background: #0f172a;
            color: white;
            text-align: center;
            padding: 40px;
        }

        h1 {
            margin-bottom: 30px;
        }

        form input {
            padding: 10px;
            font-size: 16px;
            border-radius: 8px;
            border: none;
        }

        form button {
            padding: 10px 20px;
            font-size: 16px;
            border-radius: 8px;
            border: none;
            background: #3b82f6;
            color: white;
            cursor: pointer;
        }

        .card {
            margin-top: 30px;
            padding: 20px;
            border-radius: 15px;
            background: #1e293b;
            display: inline-block;
            min-width: 300px;
        }

        .buy {
            border: 2px solid #22c55e;
        }

        .sell {
            border: 2px solid #ef4444;
        }

        .neutral {
            border: 2px solid gray;
        }

        .big {
            font-size: 24px;
            margin-top: 10px;
        }

        .small {
            color: #94a3b8;
        }
    </style>
</head>
<body>

    <h1>📊 Aktien Analyzer</h1>

    <form method="post">
        <input type="text" name="ticker" placeholder="z.B. AAPL" required>
        <button type="submit">Analysieren</button>
    </form>

    {% if result %}
        <div class="card {{color}}">
            <h2>{{ticker}}</h2>

            <p class="small">Preis: {{price}} $</p>
            <p class="small">MA200: {{ma}} $</p>
            <p class="small">Abweichung: {{diff}}%</p>

            <div class="big">{{action}}</div>
            <div>{{level}}</div>
        </div>
    {% endif %}

    {% if error %}
        <p style="color:red;">{{error}}</p>
    {% endif %}

</body>
</html>
"""

# ---------------------------
# Route
# ---------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        ticker = request.form["ticker"]

        try:
            data = yf.download(ticker, period="250d")

            if data.empty:
                return render_template_string(HTML, error="Ticker nicht gefunden.")

            data["MA200"] = data["Close"].rolling(window=200).mean()

            latest = data.iloc[-1]
            price = float(latest["Close"])
            ma200 = float(latest["MA200"])

            diff_percent = ((price - ma200) / ma200) * 100

            result = bewertung(diff_percent)

            if result:
                 action, level, abs_diff = result

                 if action == "KAUF":
                     color = "buy"
                 elif action == "VERKAUF":
                     color = "sell"
                 else:
                     color = "neutral"
            else:
               action = "KEIN SIGNAL"
               level = "Zu geringe Abweichung"
               color = "neutral"

            return render_template_string(
                HTML,
                result=True,
                ticker=ticker.upper(),
                price=round(price, 2),
                ma=round(ma200, 2),
                diff=round(diff_percent, 2),
                action=action,
                level=level,
                color=color
            )

        except Exception as e:
            return render_template_string(HTML, error=str(e))

    return render_template_string(HTML)


if __name__ == "__main__":
    app.run(debug=True)
