"""
PEC Load Estimator — Flask / Vercel version
==========================================
This file is the Vercel-deployable version of the PEC calculator.
It uses Flask (a lightweight Python web framework) so it can run as a
serverless function on Vercel 

Deployment steps:
  1. Copy the contents of this `vercel/` folder to a new Git repository.
  2. Run: pip install vercel (or use the Vercel CLI: npm i -g vercel)
  3. Push to GitHub, then import the repo in https://vercel.com/new
  4. Vercel auto-detects Python and deploys — no extra config needed.
"""

from flask import Flask, request, render_template_string

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DATA TABLES 
# ─────────────────────────────────────────────────────────────────────────────

# Table t9 — Single-Phase AC Motor Full-Load Currents (Amperes)
# Key = horsepower string, Value = {voltage: full_load_amps}
MOTOR_TABLE = {
    "1/6":  {115: 4.4,  200: 2.5,  208: 2.4,  230: 2.2},
    "1/4":  {115: 5.8,  200: 3.3,  208: 3.2,  230: 2.9},
    "1/3":  {115: 7.2,  200: 4.1,  208: 4.0,  230: 3.6},
    "1/2":  {115: 9.8,  200: 5.6,  208: 5.4,  230: 4.9},
    "3/4":  {115: 13.8, 200: 7.9,  208: 7.6,  230: 6.9},
    "1":    {115: 16,   200: 9.2,  208: 8.8,  230: 8.0},
    "1.5":  {115: 20,   200: 11.5, 208: 11.0, 230: 10.0},
    "2":    {115: 24,   200: 13.8, 208: 13.2, 230: 12.0},
    "3":    {115: 34,   200: 19.6, 208: 18.7, 230: 17.0},
    "5":    {115: 56,   200: 32.2, 208: 30.8, 230: 28.0},
    "7.5":  {115: 80,   200: 46.0, 208: 44.0, 230: 40.0},
    "10":   {115: 100,  200: 57.5, 208: 55.0, 230: 50.0},
}

# Table t8 — Cooking Appliance Demand Factors
# Index = number of appliances (1-based).  Three columns:
#   COL_A : fixed kW demand for large appliances (> 8.75 kW each)
#   COL_B : percentage factor for small appliances (< 3.5 kW each)
#   COL_C : percentage factor for medium appliances (3.5 – 8.75 kW each)
COL_A = [0, 8,  11, 14, 17, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
         31, 32, 33, 34, 35, 36, 37, 38, 39, 40]
COL_B = [0, 80, 75, 70, 66, 62, 59, 56, 53, 51, 49, 47, 45, 43, 41, 40,
         39, 38, 37, 36, 35, 34, 33, 32, 31, 30]
COL_C = [0, 80, 65, 55, 50, 45, 43, 40, 36, 35, 34, 32, 32, 32, 32, 32,
         28, 28, 28, 28, 28, 26, 26, 26, 26, 26]


# ─────────────────────────────────────────────────────────────────────────────
# CALCULATION FUNCTIONS  
# ─────────────────────────────────────────────────────────────────────────────

def calc_lighting(connected_va: float) -> float:
    """
    General Lighting — Dwelling Units (PEC)
    Rule: 100 % on first 3,000 VA, then 35 % on the remainder.
    """
    if connected_va <= 3000:
        return connected_va
    return 3000 + (connected_va - 3000) * 0.35


def calc_cooking(qty: int, va_per_unit: float) -> float:
    """
    Fixed Cooking Appliances (Table t8)
    Rule: choose Column A / B / C based on individual unit kW rating.
    """
    if qty == 0 or va_per_unit == 0:
        return 0.0
    qty = min(qty, 25)
    kw = va_per_unit / 1000
    if kw < 3.5:
        return va_per_unit * qty * (COL_B[qty] / 100)
    elif kw <= 8.75:
        return va_per_unit * qty * (COL_C[qty] / 100)
    else:
        return COL_A[qty] * 1000


def calc_dryer(qty: int, va_per_unit: float) -> float:
    """
    Clothes Dryers (Table t6)
    Rule: Minimum 5,000 VA per unit; multiply by quantity.
    """
    if qty == 0:
        return 0.0
    return max(5000, va_per_unit) * qty


def calc_motor(hp_str: str, volts: int) -> float:
    """
    Largest Motor Load
    Rule: Demand = Full-Load Current × Voltage × 1.25  (125 % per PEC)
    """
    if not hp_str or hp_str == "none":
        return 0.0
    amps = MOTOR_TABLE[hp_str][volts]
    return amps * volts * 1.25


# ─────────────────────────────────────────────────────────────────────────────
# HTML TEMPLATE  (inline so there are no extra template files to manage)
# ─────────────────────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PEC Load Estimator</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root { --primary:#2563eb; --accent:#059669; --bg:#f8fafc; --card:#fff;
            --border:#e2e8f0; --text:#1e293b; }
    * { box-sizing: border-box; }
    body { font-family:'Inter',sans-serif; background:var(--bg); color:var(--text);
           margin:0; padding:20px 0 60px; }
    h1 { text-align:center; color:var(--primary); margin-bottom:4px; }
    .sub { text-align:center; color:#64748b; margin-bottom:30px; font-size:.9rem; }
    .container { max-width:700px; margin:0 auto; padding:0 16px; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:14px;
            padding:22px; margin-bottom:18px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
    h3 { margin:0 0 14px; font-size:1rem; display:flex; align-items:center; gap:8px; }
    label { font-size:.72rem; text-transform:uppercase; letter-spacing:.05em;
            font-weight:700; color:var(--primary); display:block; margin-bottom:5px; }
    input, select { width:100%; padding:10px 12px; border:2px solid var(--border);
                    border-radius:8px; font-size:1rem; outline:none; }
    input:focus, select:focus { border-color:var(--primary); }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    .result { margin-top:12px; background:rgba(16,185,129,.1); color:var(--accent);
              padding:7px 12px; border-radius:7px; font-weight:700; font-size:.85rem; }
    .total-bar { background:var(--primary); color:#fff; border-radius:12px;
                 padding:18px 24px; display:flex; justify-content:space-between;
                 align-items:center; font-weight:700; margin-top:10px; }
    .total-bar span:last-child { font-size:1.5rem; }
    button { background:var(--primary); color:#fff; border:none; border-radius:8px;
             padding:12px 28px; font-size:1rem; font-weight:600; cursor:pointer;
             width:100%; margin-top:8px; }
    button:hover { background:#1d4ed8; }
    @media(max-width:500px) { .row { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<div class="container">
  <h1>⚡ PEC Load Estimator</h1>
  <p class="sub">Philippine Electrical Code — Demand Factor Calculator</p>

  <form method="POST">

    <!-- Section 1: General Lighting -->
    <div class="card">
      <h3>💡 1. General Lighting</h3>
      <label>Total Connected VA</label>
      <input type="number" name="lighting_va" value="{{ form.lighting_va }}" min="0" step="100" placeholder="e.g. 5000">
      {% if results %}
      <div class="result">Demand: {{ "{:,.0f}".format(results.d_lighting) }} VA</div>
      {% endif %}
    </div>

    <!-- Section 2: Fixed Appliances (Cooking) -->
    <div class="card">
      <h3>🍳 2. Fixed Appliances (Cooking)</h3>
      <div class="row">
        <div>
          <label>Quantity</label>
          <input type="number" name="qty_fixed" value="{{ form.qty_fixed }}" min="0" max="25" placeholder="0">
        </div>
        <div>
          <label>VA per Unit</label>
          <input type="number" name="fixed_va" value="{{ form.fixed_va }}" min="0" step="100" placeholder="0">
        </div>
      </div>
      {% if results %}
      <div class="result">Demand: {{ "{:,.0f}".format(results.d_fixed) }} VA</div>
      {% endif %}
    </div>

    <!-- Section 3: Clothes Dryers -->
    <div class="card">
      <h3>🧺 3. Clothes Dryers</h3>
      <div class="row">
        <div>
          <label>Quantity</label>
          <input type="number" name="qty_dryer" value="{{ form.qty_dryer }}" min="0" placeholder="0">
        </div>
        <div>
          <label>VA per Unit</label>
          <input type="number" name="dryer_va" value="{{ form.dryer_va }}" min="0" step="100" placeholder="5000">
        </div>
      </div>
      {% if results %}
      <div class="result">Demand: {{ "{:,.0f}".format(results.d_dryer) }} VA</div>
      {% endif %}
    </div>

    <!-- Section 4: Largest Motor Load -->
    <div class="card">
      <h3>🌀 4. Largest Motor Load</h3>
      <div class="row">
        <div>
          <label>Horsepower (HP)</label>
          <select name="motor_hp">
            <option value="none">— None —</option>
            {% for hp in motor_options %}
            <option value="{{ hp }}" {{ 'selected' if form.motor_hp == hp }}>{{ hp }} HP</option>
            {% endfor %}
          </select>
        </div>
        <div>
          <label>Voltage (V)</label>
          <select name="motor_volts">
            {% for v in volt_options %}
            <option value="{{ v }}" {{ 'selected' if form.motor_volts == v|string }}>{{ v }} V</option>
            {% endfor %}
          </select>
        </div>
      </div>
      {% if results %}
      <div class="result">Demand: {{ "{:,.2f}".format(results.d_motor) }} VA</div>
      {% endif %}
    </div>

    <button type="submit">CALCULATE DEMAND</button>

    <!-- Grand Total — only shown after a calculation -->
    {% if results %}
    <div class="total-bar">
      <span>TOTAL DEMAND</span>
      <span>{{ "{:,.2f}".format(results.total) }} VA</span>
    </div>
    {% endif %}

  </form>
</div>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────

# Default form values shown on first page load
DEFAULT_FORM = {
    "lighting_va": 0,
    "qty_fixed":   0,
    "fixed_va":    0,
    "qty_dryer":   0,
    "dryer_va":    5000,
    "motor_hp":    "none",
    "motor_volts": "230",
}


@app.route("/", methods=["GET", "POST"])
def index():
    """
    GET  → render the blank form.
    POST → read form inputs, run all four PEC calculations, render results.
    """
    results = None
    form = dict(DEFAULT_FORM)  # start with defaults so the form repopulates

    if request.method == "POST":
        # --- Read and parse every form field ---
        form["lighting_va"] = request.form.get("lighting_va", 0)
        form["qty_fixed"]   = request.form.get("qty_fixed", 0)
        form["fixed_va"]    = request.form.get("fixed_va", 0)
        form["qty_dryer"]   = request.form.get("qty_dryer", 0)
        form["dryer_va"]    = request.form.get("dryer_va", 5000)
        form["motor_hp"]    = request.form.get("motor_hp", "none")
        form["motor_volts"] = request.form.get("motor_volts", "230")

        # --- Run all four demand calculations ---
        d_lighting = calc_lighting(float(form["lighting_va"] or 0))
        d_fixed    = calc_cooking(int(form["qty_fixed"] or 0), float(form["fixed_va"] or 0))
        d_dryer    = calc_dryer(int(form["qty_dryer"] or 0), float(form["dryer_va"] or 0))
        d_motor    = calc_motor(form["motor_hp"], int(form["motor_volts"]))

        # --- Bundle results for the template ---
        results = {
            "d_lighting": d_lighting,
            "d_fixed":    d_fixed,
            "d_dryer":    d_dryer,
            "d_motor":    d_motor,
            "total":      d_lighting + d_fixed + d_dryer + d_motor,
        }

        # Convert results dict to a simple object so template uses dot notation
        class R:
            pass
        r = R()
        for k, v in results.items():
            setattr(r, k, v)
        results = r

    return render_template_string(
        HTML,
        form=form,
        results=results,
        motor_options=list(MOTOR_TABLE.keys()),
        volt_options=[115, 200, 208, 230],
    )


# Entry point for local testing: `python api/index.py`
if __name__ == "__main__":
    app.run(debug=True, port=5000)
