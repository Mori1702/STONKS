import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps

import yfinance as yf
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-geheimes-passwort-fuer-lokal")
DB_NAME = "stocks_app.db"

# ==========================================
# 1. DATENBANK SETUP
# ==========================================
def init_db():
   with sqlite3.connect(DB_NAME) as conn:    
      cursor = conn.cursor()
       # Benutzer-Tabelle
      cursor.execute('''
           CREATE TABLE IF NOT EXISTS users (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               email TEXT UNIQUE NOT NULL,
               password TEXT NOT NULL
           )
       ''')
       # Aktien-Tabelle (welcher User verfolgt welche Aktie)
       cursor.execute('''
           CREATE TABLE IF NOT EXISTS user_stocks (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               user_id INTEGER NOT NULL,
               ticker TEXT NOT NULL,
               FOREIGN KEY(user_id) REFERENCES users(id)
           )
       ''')
       conn.commit()
#FIX-VERSUCH
init_db()

# ==========================================
# 2. AKTIEN-LOGIK (yfinance)
# ==========================================
def get_stock_analysis(ticker):
   """Holt die Daten von yfinance und berechnet die Empfehlung."""
   try:
       stock = yf.Ticker(ticker)
       # Hole die Daten der letzten 200 Tage
       hist = stock.history(period="200d")
       
       if hist.empty or len(hist) < 2:
           return {"error": f"Keine ausreichenden Daten für {ticker} gefunden."}
       
       current_price = hist['Close'].iloc[-1]
       sma_200 = hist['Close'].mean()
       
       # Prozentuale Abweichung berechnen
       diff_percent = ((current_price - sma_200) / sma_200) * 100
       
       # Empfehlung basierend auf deinen Vorgaben
       recommendation = "Halten (-5% bis +5%)"
       if diff_percent <= -21:
           recommendation = "KAUFEN (lohnt sich sehr, >21% günstiger)"
       elif -20 <= diff_percent <= -11:
           recommendation = "KAUFEN (lohnt sich, 11-20% günstiger)"
       elif -10 <= diff_percent <= -5:
           recommendation = "KAUFEN (lohnt sich ein bisschen, 5-10% günstiger)"
       elif 5 <= diff_percent <= 10:
           recommendation = "VERKAUFEN (lohnt sich ein bisschen, 5-10% teurer)"
       elif 11 <= diff_percent <= 20:
           recommendation = "VERKAUFEN (lohnt sich, 11-20% teurer)"
       elif diff_percent >= 21:
           recommendation = "VERKAUFEN (lohnt sich sehr, >21% teurer)"
           
       return {
           "ticker": ticker.upper(),
           "current": round(current_price, 2),
           "sma_200": round(sma_200, 2),
           "diff_percent": round(diff_percent, 2),
           "recommendation": recommendation
       }
   except Exception as e:
       return {"error": str(e)}

# ==========================================
# 3. E-MAIL LOGIK
# ==========================================
def send_daily_emails():
   """Wird täglich vom Scheduler aufgerufen."""
   print(f"[{datetime.now()}] Starte E-Mail-Versand...")
   
   # SMTP Konfiguration (für Render über Environment Variables setzen!)
   SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
   SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
   SMTP_USER = os.environ.get("SMTP_USER", "deine-email@gmail.com")
   SMTP_PASS = os.environ.get("SMTP_PASS", "dein-app-passwort")
   
   # Wenn keine echten Zugangsdaten da sind, nur in der Konsole simulieren
   simulate_only = SMTP_USER == "deine-email@gmail.com"
   
   with sqlite3.connect(DB_NAME) as conn:
       cursor = conn.cursor()
       users = cursor.execute("SELECT id, email FROM users").fetchall()
       
       for user_id, email in users:
           stocks = cursor.execute("SELECT ticker FROM user_stocks WHERE user_id = ?", (user_id,)).fetchall()
           if not stocks:
               continue
           
           # E-Mail Text aufbauen
           body = "Hallo!\n\nHier ist dein tägliches Aktien-Update:\n\n"
           for (ticker,) in stocks:
               data = get_stock_analysis(ticker)
               if "error" not in data:
                   body += f"--- {data['ticker']} ---\n"
                   body += f"Aktueller Wert: {data['current']} USD\n"
                   body += f"Ø 200 Tage (SMA): {data['sma_200']} USD\n"
                   body += f"Abweichung: {data['diff_percent']}%\n"
                   body += f"Empfehlung: {data['recommendation']}\n\n"
               else:
                   body += f"--- {ticker.upper()} ---\nFehler beim Abrufen: {data['error']}\n\n"
           
           body += "Viele Grüße,\nDein Stock Tracker"
           
           if simulate_only:
               print(f"SIMULIERE E-MAIL AN: {email}\nINHALT:\n{body}")
           else:
               # Echte E-Mail senden
               try:
                   msg = MIMEMultipart()
                   msg['From'] = SMTP_USER
                   msg['To'] = email
                   msg['Subject'] = "Dein tägliches Aktien-Update"
                   msg.attach(MIMEText(body, 'plain'))
                   
                   server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
                   server.starttls()
                   server.login(SMTP_USER, SMTP_PASS)
                   server.send_message(msg)
                   server.quit()
                   print(f"E-Mail an {email} gesendet.")
               except Exception as e:
                   print(f"Fehler beim Senden an {email}: {e}")

# Scheduler einrichten
scheduler = BackgroundScheduler()
# Sende jeden Tag um 18:00 Uhr
scheduler.add_job(func=send_daily_emails, trigger="cron", hour=18, minute=0)
scheduler.start()

# ==========================================
# 4. FLASK ROUTES & HTML TEMPLATES
# ==========================================
# Ein einfaches Bootstrap-Template für alles
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
   <meta charset="UTF-8">
   <title>Stock Tracker</title>
   <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
   <style> body { background-color: #f8f9fa; padding-top: 2rem; } </style>
</head>
<body>
<div class="container">
   <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4 rounded">
       <div class="container-fluid">
           <a class="navbar-brand" href="/">📈 Stock Tracker</a>
           <div class="d-flex">
               {% if session.get('user_id') %}
                   <span class="navbar-text me-3 text-white">Eingeloggt</span>
                   <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
               {% else %}
                   <a href="/login" class="btn btn-outline-light btn-sm me-2">Login</a>
                   <a href="/register" class="btn btn-light btn-sm">Registrieren</a>
               {% endif %}
           </div>
       </div>
   </nav>

   {% with messages = get_flashed_messages(with_categories=true) %}
     {% if messages %}
       {% for category, message in messages %}
         <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }}">{{ message }}</div>
       {% endfor %}
     {% endif %}
   {% endwith %}

   {% block content %}{% endblock %}
</div>
</body>
</html>
"""

def login_required(f):
   @wraps(f)
   def decorated_function(*args, **kwargs):
       if 'user_id' not in session:
           flash("Bitte logge dich ein.", "danger")
           return redirect(url_for('login'))
       return f(*args, **kwargs)
   return decorated_function

@app.route("/")
def index():
   if 'user_id' not in session:
       return redirect(url_for('login'))
   
   with sqlite3.connect(DB_NAME) as conn:
       cursor = conn.cursor()
       stocks = cursor.execute("SELECT id, ticker FROM user_stocks WHERE user_id = ?", (session['user_id'],)).fetchall()
   
   portfolio_data = []
   for stock_id, ticker in stocks:
       data = get_stock_analysis(ticker)
       data['db_id'] = stock_id
       portfolio_data.append(data)
       
   html = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
   <div class="row">
       <div class="col-md-8">
           <h3>Meine verfolgten Aktien (Tägliches E-Mail-Update)</h3>
           {% if portfolio %}
               {% for stock in portfolio %}
                   <div class="card mb-3 shadow-sm">
                       <div class="card-body">
                           <div class="d-flex justify-content-between align-items-center">
                               <h5 class="card-title mb-0">{{ stock.ticker if not stock.error else stock.error }}</h5>
                               {% if stock.db_id %}
                               <form action="/remove_stock" method="POST" class="m-0">
                                   <input type="hidden" name="stock_id" value="{{ stock.db_id }}">
                                   <button type="submit" class="btn btn-danger btn-sm">Entfernen</button>
                               </form>
                               {% endif %}
                           </div>
                           {% if not stock.error %}
                           <hr>
                           <div class="row text-center">
                               <div class="col"><strong>Aktuell:</strong><br>{{ stock.current }} $</div>
                               <div class="col"><strong>SMA 200:</strong><br>{{ stock.sma_200 }} $</div>
                               <div class="col"><strong>Abweichung:</strong><br>
                                   <span class="badge {% if stock.diff_percent > 0 %}bg-success{% else %}bg-danger{% endif %}">
                                       {{ stock.diff_percent }} %
                                   </span>
                               </div>
                           </div>
                           <div class="mt-3 text-center">
                               <strong>Empfehlung:</strong> {{ stock.recommendation }}
                           </div>
                           {% endif %}
                       </div>
                   </div>
               {% endfor %}
           {% else %}
               <p class="text-muted">Du verfolgst noch keine Aktien. Füge rechts eine hinzu!</p>
           {% endif %}
       </div>
       
       <div class="col-md-4">
           <div class="card mb-4 shadow-sm">
               <div class="card-body">
                   <h5>Aktie zum Portfolio hinzufügen</h5>
                   <form action="/add_stock" method="POST">
                       <div class="input-group">
                           <input type="text" name="ticker" class="form-control" placeholder="z.B. AAPL, TSLA" required>
                           <button type="submit" class="btn btn-primary">Hinzufügen</button>
                       </div>
                       <small class="text-muted">Wird in die tägliche E-Mail aufgenommen.</small>
                   </form>
               </div>
           </div>

           <div class="card shadow-sm">
               <div class="card-body">
                   <h5>Schnellabfrage (Live)</h5>
                   <form action="/lookup" method="POST">
                       <div class="input-group">
                           <input type="text" name="ticker" class="form-control" placeholder="Ticker prüfen..." required>
                           <button type="submit" class="btn btn-secondary">Prüfen</button>
                       </div>
                   </form>
               </div>
           </div>
       </div>
   </div>
   ''')
   return render_template_string(html, portfolio=portfolio_data)

@app.route("/lookup", methods=["POST"])
@login_required
def lookup():
   ticker = request.form.get("ticker").strip().upper()
   data = get_stock_analysis(ticker)
   
   html = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
   <a href="/" class="btn btn-secondary mb-3">← Zurück zum Dashboard</a>
   <div class="card shadow">
       <div class="card-header bg-primary text-white">
           <h4 class="mb-0">Schnellabfrage: {{ data.get('ticker', 'Fehler') }}</h4>
       </div>
       <div class="card-body">
           {% if data.error %}
               <div class="alert alert-danger">{{ data.error }}</div>
           {% else %}
               <ul class="list-group list-group-flush">
                   <li class="list-group-item d-flex justify-content-between">
                       <span>Aktueller Wert:</span> <strong>{{ data.current }} $</strong>
                   </li>
                   <li class="list-group-item d-flex justify-content-between">
                       <span>Ø 200 Tage (SMA 200):</span> <strong>{{ data.sma_200 }} $</strong>
                   </li>
                   <li class="list-group-item d-flex justify-content-between">
                       <span>Abweichung:</span> 
                       <strong class="{% if data.diff_percent > 0 %}text-success{% else %}text-danger{% endif %}">
                           {{ data.diff_percent }} %
                       </strong>
                   </li>
                   <li class="list-group-item d-flex justify-content-between bg-light mt-2">
                       <span>Fazit / Empfehlung:</span> <strong>{{ data.recommendation }}</strong>
                   </li>
               </ul>
           {% endif %}
       </div>
   </div>
   ''')
   return render_template_string(html, data=data)

@app.route("/add_stock", methods=["POST"])
@login_required
def add_stock():
   ticker = request.form.get("ticker").strip().upper()
   if not ticker:
       flash("Bitte Ticker eingeben.", "danger")
       return redirect(url_for('index'))
       
   with sqlite3.connect(DB_NAME) as conn:
       cursor = conn.cursor()
       # Prüfen ob schon vorhanden
       existing = cursor.execute("SELECT id FROM user_stocks WHERE user_id = ? AND ticker = ?", (session['user_id'], ticker)).fetchone()
       if existing:
           flash(f"{ticker} wird bereits verfolgt.", "danger")
       else:
           cursor.execute("INSERT INTO user_stocks (user_id, ticker) VALUES (?, ?)", (session['user_id'], ticker))
           conn.commit()
           flash(f"{ticker} erfolgreich hinzugefügt!", "success")
           
   return redirect(url_for('index'))

@app.route("/remove_stock", methods=["POST"])
@login_required
def remove_stock():
   stock_id = request.form.get("stock_id")
   with sqlite3.connect(DB_NAME) as conn:
       cursor = conn.cursor()
       cursor.execute("DELETE FROM user_stocks WHERE id = ? AND user_id = ?", (stock_id, session['user_id']))
       conn.commit()
   flash("Aktie entfernt.", "success")
   return redirect(url_for('index'))

@app.route("/register", methods=["GET", "POST"])
def register():
   if request.method == "POST":
       email = request.form.get("email")
       password = request.form.get("password")
       hashed_pw = generate_password_hash(password)
       
       try:
           with sqlite3.connect(DB_NAME) as conn:
               cursor = conn.cursor()
               cursor.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_pw))
               conn.commit()
           flash("Registrierung erfolgreich! Bitte einloggen.", "success")
           return redirect(url_for('login'))
       except sqlite3.IntegrityError:
           flash("E-Mail existiert bereits.", "danger")
           
   html = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
   <div class="row justify-content-center">
       <div class="col-md-6">
           <div class="card shadow">
               <div class="card-body">
                   <h3 class="card-title text-center">Registrieren</h3>
                   <form method="POST">
                       <div class="mb-3">
                           <label>E-Mail Adresse</label>
                           <input type="email" name="email" class="form-control" required>
                       </div>
                       <div class="mb-3">
                           <label>Passwort</label>
                           <input type="password" name="password" class="form-control" required>
                       </div>
                       <button type="submit" class="btn btn-primary w-100">Konto erstellen</button>
                   </form>
               </div>
           </div>
       </div>
   </div>
   ''')
   return render_template_string(html)

@app.route("/login", methods=["GET", "POST"])
def login():
   if request.method == "POST":
       email = request.form.get("email")
       password = request.form.get("password")
       
       with sqlite3.connect(DB_NAME) as conn:
           cursor = conn.cursor()
           user = cursor.execute("SELECT id, password FROM users WHERE email = ?", (email,)).fetchone()
           
           if user and check_password_hash(user[1], password):
               session['user_id'] = user[0]
               session['email'] = email
               flash("Erfolgreich eingeloggt!", "success")
               return redirect(url_for('index'))
           else:
               flash("Falsche E-Mail oder Passwort.", "danger")

   html = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', '''
   <div class="row justify-content-center">
       <div class="col-md-6">
           <div class="card shadow">
               <div class="card-body">
                   <h3 class="card-title text-center">Login</h3>
                   <form method="POST">
                       <div class="mb-3">
                           <label>E-Mail Adresse</label>
                           <input type="email" name="email" class="form-control" required>
                       </div>
                       <div class="mb-3">
                           <label>Passwort</label>
                           <input type="password" name="password" class="form-control" required>
                       </div>
                       <button type="submit" class="btn btn-success w-100">Einloggen</button>
                   </form>
               </div>
           </div>
       </div>
   </div>
   ''')
   return render_template_string(html)

@app.route("/logout")
def logout():
   session.clear()
   flash("Du wurdest ausgeloggt.", "success")
   return redirect(url_for('login'))

if __name__ == "__main__":
   init_db()
   # Für den lokalen Test aktivieren wir debug=True
   app.run(debug=True, use_reloader=False) # use_reloader=False verhindert, dass der Scheduler doppelt startet
