# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
import os

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"ok": True}

# static（ロゴ等）
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設定
FEE_RATE = float(os.getenv("FEE_RATE", "0.08"))  # 8%
TAX_RATE = float(os.getenv("TAX_RATE", "0.10"))

# -------------------------------
# 計算ユーティリティ
# -------------------------------
def pv_annuity(monthly: float, i: float, n: int) -> float:
    if n <= 0:
        return 0.0
    if i == 0:
        return monthly * n
    return monthly * (1 - (1 + i) ** (-n)) / i

def pv_bonuses(bonus_per_event: float, i: float, n: int, every_months: int = 6) -> float:
    if bonus_per_event <= 0 or n <= 0:
        return 0.0
    if i == 0:
        return bonus_per_event * (n // every_months)
    pv = 0.0
    m = every_months
    while m <= n:
        pv += bonus_per_event / ((1 + i) ** m)
        m += every_months
    return pv

def loan_capacity_by_payments(monthly_man: float, bonus_man: float, rate_percent: float, years: int) -> float:
    n = years * 12
    i = rate_percent / 100 / 12
    return pv_annuity(monthly_man, i, n) + pv_bonuses(bonus_man, i, n)

def monthly_payment_from_total_loan(total_loan_man: float, bonus_man: float, rate_percent: float, years: int) -> float:
    n = years * 12
    i = rate_percent / 100 / 12
    if n <= 0:
        return 0.0
    pv_bonus = pv_bonuses(bonus_man, i, n)
    pv_for_monthly = max(total_loan_man - pv_bonus, 0.0)
    if i == 0:
        return pv_for_monthly / n
    denom = (1 - (1 + i) ** (-n))
    return pv_for_monthly * i / denom

def full_renovation_cost(area_m2: int) -> float:
    return area_m2 * 12 + 350  # 万円

def solve_purchase_price(total_funds_man: float, fee_rate: float) -> float:
    return max(total_funds_man / (1 + max(fee_rate, 0)), 0.0)

# ★ 単位補正（UI変えずに自動推定）
def normalize_man_input(x: float) -> (float, bool):
    """
    入力が '円' っぽい巨大値なら万円に補正する。
    目安: 100,000万円(=10億円)を超えたら円入力とみなす。
    """
    if x is None:
        return 0.0, False
    x = float(x)
    if x >= 100000:  # 10億円以上は現実的に円入力の可能性が高い
        return x / 10000.0, True
    return x, False

# -------------------------------
# モデル
# -------------------------------
class CalcReq(BaseModel):
    self_man: float
    monthly_man: Optional[float] = None
    total_loan_input_man: Optional[float] = None
    rate_percent: float
    area_need_m2: int
    years: int
    reno_mode: Literal["full", "manual"]
    reno_cost_input_man: Optional[float] = None
    bonus_man: float = 0.0
    memo_text: Optional[str] = ""

    @field_validator("years")
    @classmethod
    def check_years(cls, v):
        if v <= 0 or v > 50:
            raise ValueError("借入期間は1〜50年で入力してください。")
        return v

class CalcRes(BaseModel):
    ok: bool
    monthly_man_out: float
    total_loan_man: float
    reno_cost_man: float
    reno_cost_tax_incl_man: float
    fee_man: float
    purchasable_price_man: float
    memo_text: str
    warning_text: Optional[str] = None  # ★追加（レイアウトは変えず alert 用）

# -------------------------------
# HTML
# -------------------------------
@app.get("/", response_class=HTMLResponse)
def root():
    html = f"""
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>中古×リノベ 資金計画シミュレーター</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ background:#F1F5F9 }}
    .box {{ border:1px solid #e5e7eb; border-radius:.75rem; padding:1rem; background:white; }}
    .label {{ color:#374151; font-size:.9rem; margin-bottom:.25rem; display:block; }}
    .valuebox {{ background:#F8FAFC; border-radius:.5rem; padding:.75rem 1rem; font-weight:600; width:100%; }}
    .kpi {{ font-size:1.25rem; }}
    .kpi-input {{ border:none; outline:none; background:#F8FAFC; width:100%; }}
    .manual-input {{ width:12rem; }}
  </style>
</head>
<body class="p-4">

  <div class="max-w-6xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">中古×リノベ 資金計画シミュレーター</h1>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">

      <!-- 左側：入力 -->
      <div class="box">
        <div class="grid grid-cols-2 gap-3">
          <label class="label">自己資金（万円）</label>
          <input id="self_man" type="number" step="0.1" class="valuebox"/>

          <label class="label">月々の支払可能額（万円）</label>
          <input id="monthly_man" type="number" step="0.1" class="valuebox"/>

          <label class="label">金利（%）</label>
          <input id="rate_percent" type="number" step="0.01" class="valuebox"/>

          <label class="label">借入期間（年）</label>
          <input id="years" type="number" step="1" class="valuebox"/>

          <label class="label">必要㎡数</label>
          <input id="area_need_m2" type="number" step="1" class="valuebox"/>

          <label class="label">ボーナス時返済額（万円/回）</label>
          <input id="bonus_man" type="number" step="0.1" class="valuebox"/>
        </div>

        <div class="mt-3">
          <span class="label">リノベ方式</span>
          <div class="flex gap-4 items-end">
            <label class="inline-flex items-center gap-1">
              <input type="radio" name="reno" value="full" checked>
              <span>フル</span>
            </label>

            <label class="inline-flex items-center gap-1">
              <input type="radio" name="reno" value="manual">
              <span>手入力</span>
            </label>

            <input id="reno_cost_input_man" type="number" step="0.1"
                   class="valuebox manual-input hidden ml-auto" placeholder="例：800" />
          </div>
        </div>

        <button id="calc_btn" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded">
          計算する
        </button>
      </div>

      <!-- 右側：結果 -->
      <div class="flex flex-col gap-4">

        <div class="grid grid-cols-2 gap-4">

          <div class="box">
            <div class="label">総借入額（万円）</div>
            <input id="total_loan" type="text" inputmode="decimal" class="valuebox kpi kpi-input" placeholder="-" />
          </div>

          <div class="box">
            <div class="label">リノベ費（税抜・万円）</div>
            <div id="reno_cost" class="valuebox kpi">-</div>
          </div>

          <div class="box">
            <div class="label">リノベ費（税込10%・万円）</div>
            <div id="reno_cost_tax_incl" class="valuebox kpi">-</div>
          </div>

          <div class="box">
            <div class="label">諸費用（万円）</div>
            <div id="fee_cost" class="valuebox kpi">-</div>
          </div>

          <div class="box">
            <div class="label">購入可能物件価格（万円）</div>
            <div id="buyable" class="valuebox kpi text-emerald-600">-</div>
          </div>

        </div>

        <div class="box">
          <textarea id="memo_text" class="w-full p-3 border rounded" style="min-height:150px;"></textarea>
        </div>

      </div>

    </div>
  </div>

  <script>
    function n(id){{ return parseFloat(document.getElementById(id).value || "0"); }}
    function t(id){{ return document.getElementById(id).value || ""; }}

    function normalizeNum(s){{
      return (s||"").replace(/[，,]/g,"")
                    .replace(/[０-９]/g, c=>String.fromCharCode(c.charCodeAt(0)-0xFEE0))
                    .replace(/[．。]/g,".");
    }}
    function getLoan(){{
      return parseFloat(normalizeNum(document.getElementById("total_loan").value));
    }}

    document.querySelectorAll("input[name='reno']").forEach(e=>{{
      e.addEventListener("change", ()=>{{
        const m = document.getElementById("reno_cost_input_man");
        (e.value==="manual") ? m.classList.remove("hidden") : (m.classList.add("hidden"), m.value="");
      }});
    }});

    let calcSource="monthly";
    document.getElementById("monthly_man").addEventListener("input", ()=>{{calcSource="monthly"}});
    document.getElementById("total_loan").addEventListener("input", ()=>{{calcSource="total"}});

    document.getElementById("calc_btn").addEventListener("click", async ()=>{{
      const mode = document.querySelector("input[name='reno']:checked").value;

      const loanEd = getLoan();
      const inputs = {{
        self_man: n("self_man"),
        monthly_man: calcSource==="monthly" ? n("monthly_man") : null,
        total_loan_input_man: calcSource==="total" && !isNaN(loanEd) ? loanEd : null,
        rate_percent: n("rate_percent"),
        area_need_m2: Math.trunc(n("area_need_m2")),
        years: Math.trunc(n("years")),
        reno_mode: mode,
        reno_cost_input_man:
          (mode==="manual" && document.getElementById("reno_cost_input_man").value !== "")
            ? n("reno_cost_input_man") : null,
        bonus_man: n("bonus_man"),
        memo_text: t("memo_text")
      }};

      const r = await fetch("/calc", {{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify(inputs)
      }});
      const res = await r.json();

      if(res.warning_text){{
        alert(res.warning_text);
      }}

      document.getElementById("total_loan").value =
        res.total_loan_man.toLocaleString(undefined,{{maximumFractionDigits:1}});

      document.getElementById("reno_cost").textContent =
        res.reno_cost_man.toLocaleString(undefined,{{maximumFractionDigits:1}});

      document.getElementById("reno_cost_tax_incl").textContent =
        res.reno_cost_tax_incl_man.toLocaleString(undefined,{{maximumFractionDigits:1}});

      document.getElementById("fee_cost").textContent =
        res.fee_man.toLocaleString(undefined,{{maximumFractionDigits:1}});

      document.getElementById("buyable").textContent =
        res.purchasable_price_man.toLocaleString(undefined,{{maximumFractionDigits:1}});

      if(res.monthly_man_out !== undefined){{
        document.getElementById("monthly_man").value =
          Number(res.monthly_man_out).toFixed(2);
      }}
    }});
  </script>

</body>
</html>
"""
    return HTMLResponse(html)

# -------------------------------
# 計算 API
# -------------------------------
@app.post("/calc", response_model=CalcRes)
def calc(req: CalcReq):
    warning_msgs = []

    # ★ 単位補正
    self_man, w1 = normalize_man_input(req.self_man)
    if w1:
        warning_msgs.append("自己資金が非常に大きいため『円入力』と判断し、万円に換算しました。")

    monthly_in, w2 = normalize_man_input(req.monthly_man) if req.monthly_man is not None else (0.0, False)
    total_in,  w3 = normalize_man_input(req.total_loan_input_man) if req.total_loan_input_man is not None else (0.0, False)
    bonus_man, w4 = normalize_man_input(req.bonus_man)

    if w2: warning_msgs.append("月々返済額が大きいため『円入力』と判断し、万円に換算しました。")
    if w3: warning_msgs.append("総借入額が大きいため『円入力』と判断し、万円に換算しました。")
    if w4: warning_msgs.append("ボーナス返済額が大きいため『円入力』と判断し、万円に換算しました。")

    if req.reno_mode == "full":
        reno = full_renovation_cost(req.area_need_m2)
    else:
        reno, w5 = normalize_man_input(req.reno_cost_input_man or 0.0)
        if w5:
            warning_msgs.append("リノベ費用が大きいため『円入力』と判断し、万円に換算しました。")

    reno_tax = reno * (1 + TAX_RATE)

    # 起点切り替え
    if total_in > 0 and monthly_in <= 0:
        total_loan = total_in
        monthly = monthly_payment_from_total_loan(
            total_loan, bonus_man, req.rate_percent, req.years
        )
    else:
        monthly = monthly_in
        total_loan = loan_capacity_by_payments(
            monthly, bonus_man, req.rate_percent, req.years
        )

    disposable = self_man + total_loan - reno_tax
    purch = solve_purchase_price(disposable, FEE_RATE)
    fee = purch * FEE_RATE

    warning_text = "\n".join(warning_msgs) if warning_msgs else None

    return JSONResponse({
        "ok": True,
        "monthly_man_out": round(monthly,2),
        "total_loan_man": round(total_loan,1),
        "reno_cost_man": round(reno,1),
        "reno_cost_tax_incl_man": round(reno_tax,1),
        "fee_man": round(fee,1),
        "purchasable_price_man": round(purch,1),
        "memo_text": req.memo_text or "",
        "warning_text": warning_text,
    })
