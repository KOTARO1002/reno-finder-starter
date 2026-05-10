# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from pathlib import Path
import os

app = FastAPI()

@app.get("/healthz")
def healthz():
    return {"ok": True}

# ----------------------------
# static（ロゴ等）
#  app/main.py から見て「プロジェクト直下/static」を指す
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 設定
FEE_RATE = float(os.getenv("FEE_RATE", "0.08"))  # 8%
TAX_RATE = float(os.getenv("TAX_RATE", "0.10"))  # 10%

# 計算ユーティリティ -------------------------------
def pv_annuity(monthly: float, i: float, n: int) -> float:
    """毎月返済から借入可能額(PV)"""
    if n <= 0:
        return 0.0
    if i == 0:
        return monthly * n
    return monthly * (1 - (1 + i) ** (-n)) / i

def pv_bonuses(bonus_per_event: float, i: float, n: int, every_months: int = 6) -> float:
    """ボーナス返済の現在価値(PV)"""
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
    """月額＋ボーナスから総借入額を逆算"""
    n = years * 12
    i = rate_percent / 100 / 12
    return pv_annuity(monthly_man, i, n) + pv_bonuses(bonus_man, i, n)

def monthly_payment_from_total_loan(total_loan_man: float, bonus_man: float, rate_percent: float, years: int) -> float:
    """総借入額＋ボーナスから月々返済額を逆算"""
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
    """フルリノベ概算（万円）"""
    return area_m2 * 12 + 350

def solve_purchase_price(total_funds_man: float, fee_rate: float) -> float:
    """諸費用率込みの総資金から物件価格を逆算"""
    return max(total_funds_man / (1 + max(fee_rate, 0)), 0.0)

# モデル -----------------------
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

# ----------------------------------------------------------
# HTML
# ----------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def root():
    html = """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>中古×リノベ 資金計画シミュレーター</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    html, body {
      font-family: 'Inter', system-ui, -apple-system, "Helvetica Neue",
                   "Yu Gothic UI", "Hiragino Sans", "Noto Sans JP", sans-serif;
    }
    body { background: #F8FAFC; color: #0F172A; }
    .num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }

    .card {
      background: #ffffff;
      border: 1px solid #E2E8F0;
      border-radius: 1rem;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .card-pad { padding: 1.25rem; }

    .label-sm {
      font-size: 0.7rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #64748B;
      font-weight: 600;
    }
    .field-label {
      font-size: 0.875rem;
      color: #334155;
      font-weight: 500;
    }

    .field-input {
      width: 100%;
      background: #F8FAFC;
      border: 1px solid transparent;
      border-radius: 0.5rem;
      padding: 0.625rem 0.875rem;
      font-weight: 600;
      transition: all 0.15s ease;
    }
    .field-input:focus {
      outline: none;
      border-color: #10B981;
      background: #ffffff;
      box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18);
    }

    .kpi-num {
      font-size: 1.5rem;
      font-weight: 700;
      color: #0F172A;
    }
    .hero-num {
      font-size: 3rem;
      font-weight: 800;
      color: #059669;
      line-height: 1.05;
      letter-spacing: -0.025em;
    }
    @media (min-width: 768px) { .hero-num { font-size: 3.75rem; } }
    .hero-unit {
      font-size: 1.25rem;
      font-weight: 600;
      color: #047857;
      margin-left: 0.5rem;
    }

    .btn-primary {
      background: #0F172A;
      color: #fff;
      padding: 0.75rem 1.25rem;
      border-radius: 0.5rem;
      font-weight: 600;
      transition: all 0.15s ease;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12);
    }
    .btn-primary:hover { background: #1E293B; transform: translateY(-1px); }
    .btn-primary:active { transform: translateY(0); }

    .info-tip {
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1rem;
      height: 1rem;
      border-radius: 9999px;
      background: #E2E8F0;
      color: #475569;
      font-size: 0.7rem;
      font-weight: 700;
      cursor: help;
      user-select: none;
    }
    .info-tip:hover::after,
    .info-tip:focus::after {
      content: attr(data-tip);
      position: absolute;
      bottom: 130%;
      left: 50%;
      transform: translateX(-50%);
      white-space: nowrap;
      background: #0F172A;
      color: #fff;
      font-size: 0.75rem;
      font-weight: 500;
      padding: 0.375rem 0.625rem;
      border-radius: 0.375rem;
      z-index: 10;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.18);
    }

    .reno-manual-input { width: 12rem; }
    @media (min-width: 1024px) { .reno-manual-input { width: 16rem; } }

    details > summary { list-style: none; }
    details > summary::-webkit-details-marker { display: none; }
    .chevron { transition: transform 0.2s ease; display: inline-block; }
    details[open] .chevron { transform: rotate(90deg); }
  </style>
</head>
<body class="antialiased">

  <div class="max-w-6xl mx-auto px-4 py-6 md:py-8">

    <header class="mb-6">
      <h1 class="text-2xl md:text-3xl font-bold tracking-tight">
        中古×リノベ 資金計画シミュレーター
      </h1>
      <p class="mt-1 text-sm text-slate-500">
        条件を入力すると、購入可能な物件価格を自動で逆算します。
      </p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">

      <!-- 左：入力 -->
      <section class="card card-pad">
        <h2 class="label-sm mb-4">条件入力</h2>

        <div class="grid grid-cols-2 gap-x-4 gap-y-4">
          <div>
            <label class="field-label block mb-1.5" for="self_man">自己資金（万円）</label>
            <input id="self_man" type="number" step="0.1" class="field-input num" placeholder="例：300"/>
          </div>
          <div>
            <label class="field-label block mb-1.5" for="monthly_man">月々の支払可能額（万円）</label>
            <input id="monthly_man" type="number" step="0.1" class="field-input num" placeholder="例：10"/>
          </div>
          <div>
            <label class="field-label block mb-1.5" for="rate_percent">金利（%）</label>
            <input id="rate_percent" type="number" step="0.01" class="field-input num" placeholder="例：0.8"/>
          </div>
          <div>
            <label class="field-label block mb-1.5" for="years">借入期間（年）</label>
            <input id="years" type="number" step="1" class="field-input num" placeholder="例：35"/>
          </div>
          <div>
            <label class="field-label block mb-1.5" for="area_need_m2">必要㎡数</label>
            <input id="area_need_m2" type="number" step="1" class="field-input num" placeholder="例：60"/>
          </div>
          <div>
            <label class="field-label block mb-1.5" for="bonus_man">ボーナス時返済額（万円/回）</label>
            <input id="bonus_man" type="number" step="0.1" class="field-input num" placeholder="例：10"/>
          </div>
        </div>

        <div class="mt-5 pt-5 border-t border-slate-100">
          <span class="field-label block mb-2">リノベ方式</span>
          <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
            <label class="inline-flex items-center gap-2 cursor-pointer">
              <input type="radio" name="reno" value="full" class="accent-emerald-600" checked>
              <span class="text-sm">フル</span>
            </label>
            <label class="inline-flex items-center gap-2 cursor-pointer">
              <input type="radio" name="reno" value="manual" class="accent-emerald-600">
              <span class="text-sm">手入力</span>
            </label>
            <input id="reno_cost_input_man" type="number" step="0.1"
                   class="field-input num reno-manual-input hidden ml-auto"
                   placeholder="例：800" />
          </div>
        </div>

        <button id="calc_btn" type="button" class="btn-primary mt-5 w-full md:w-auto">
          計算する
        </button>

        <p class="text-xs text-slate-400 mt-3">
          ※ 諸費用率は <b class="text-slate-500">8.0%</b> に設定されています。
        </p>
      </section>

      <!-- 右：結果 -->
      <section class="flex flex-col gap-4">

        <!-- ヒーロー：購入可能物件価格 -->
        <div class="card card-pad" style="background:linear-gradient(135deg,#ffffff 0%,#ECFDF5 100%);">
          <div class="label-sm text-emerald-700 mb-2">購入可能物件価格</div>
          <div class="flex items-baseline">
            <span id="buyable" class="hero-num num">-</span>
            <span class="hero-unit">万円</span>
          </div>
          <p id="buyable_breakdown" class="text-xs text-slate-500 mt-3">
            条件を入力して「計算する」を押すと、ここに内訳が表示されます。
          </p>
        </div>

        <!-- 内訳：3カード -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">

          <div class="card card-pad">
            <div class="label-sm mb-2">総借入額</div>
            <div class="flex items-baseline gap-1">
              <input id="total_loan" type="text" inputmode="decimal"
                     class="kpi-num num bg-transparent border-0 outline-none w-full focus:bg-slate-50 rounded px-1 -ml-1"
                     placeholder="-" />
              <span class="text-sm text-slate-500">万円</span>
            </div>
            <p class="text-xs text-slate-400 mt-1">直接編集して逆算も可</p>
          </div>

          <div class="card card-pad">
            <div class="label-sm mb-2">諸費用</div>
            <div class="flex items-baseline gap-1">
              <span id="fee_cost" class="kpi-num num">-</span>
              <span class="text-sm text-slate-500">万円</span>
            </div>
            <p class="text-xs text-slate-400 mt-1">物件価格 × 8%</p>
          </div>

          <div class="card card-pad">
            <div class="label-sm mb-2 flex items-center gap-1.5">
              リノベ費
              <span id="reno_tip" class="info-tip" tabindex="0" data-tip="税抜: -">i</span>
            </div>
            <div class="flex items-baseline gap-1">
              <span id="reno_cost_tax_incl" class="kpi-num num">-</span>
              <span class="text-sm text-slate-500">万円</span>
            </div>
            <p class="text-xs text-slate-400 mt-1">税込（10%）</p>
            <span id="reno_cost" class="hidden"></span>
          </div>

        </div>

        <!-- メモ：折りたたみ -->
        <details class="card card-pad">
          <summary class="flex items-center gap-2 cursor-pointer text-sm font-medium text-slate-700 select-none">
            <span class="chevron text-slate-400">▶</span>
            <span>メモ</span>
            <span class="text-xs text-slate-400 font-normal ml-1">（内見の所感、優先順位など）</span>
          </summary>
          <textarea id="memo_text"
                    class="w-full mt-3 p-3 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/15"
                    style="min-height:140px;"
                    placeholder="例：内見の所感、優先順位、気づき・要望など自由に記入"></textarea>
        </details>

      </section>

    </div>

    <footer class="mt-8 pb-4">
      <div class="flex justify-center md:justify-end items-center">
        <img src="/static/SHロゴ横長.png"
             alt="SIMPLE HOUSE logo"
             class="h-8 md:h-9 opacity-90" />
      </div>
    </footer>

  </div>

  <script>
    function n(id){ return parseFloat(document.getElementById(id).value || "0"); }
    function t(id){ return document.getElementById(id).value || ""; }

    function normalizeNum(s){
      return (s||"").replace(/[，,]/g,"")
                    .replace(/[０-９]/g, c=>String.fromCharCode(c.charCodeAt(0)-0xFEE0))
                    .replace(/[．。]/g,".");
    }
    function getLoan(){
      return parseFloat(normalizeNum(document.getElementById("total_loan").value));
    }
    function fmt(v){
      return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
    }

    // リノベ方式の手入力欄表示切替
    document.querySelectorAll("input[name='reno']").forEach(e=>{
      e.addEventListener("change", ()=>{
        const m = document.getElementById("reno_cost_input_man");
        (e.value==="manual") ? m.classList.remove("hidden")
                             : (m.classList.add("hidden"), m.value="");
      });
    });

    // どっちを基準に計算するか（デフォは月々）
    let calcSource="monthly";
    document.getElementById("monthly_man").addEventListener("input", ()=>{calcSource="monthly"});
    document.getElementById("total_loan").addEventListener("input",  ()=>{calcSource="total"});

    document.getElementById("calc_btn").addEventListener("click", async ()=>{
      const mode = document.querySelector("input[name='reno']:checked").value;
      const loanEd = getLoan();
      const inputs = {
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
      };

      const r = await fetch("/calc", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(inputs)
      });
      const res = await r.json();
      if(!res.ok){
        alert("計算に失敗しました");
        return;
      }

      // 表示反映
      document.getElementById("total_loan").value = fmt(res.total_loan_man);
      document.getElementById("reno_cost").textContent = fmt(res.reno_cost_man);
      document.getElementById("reno_cost_tax_incl").textContent = fmt(res.reno_cost_tax_incl_man);
      document.getElementById("fee_cost").textContent = fmt(res.fee_man);
      document.getElementById("buyable").textContent = fmt(res.purchasable_price_man);

      // ツールチップに税抜を反映
      document.getElementById("reno_tip").setAttribute(
        "data-tip", "税抜: " + fmt(res.reno_cost_man) + " 万円"
      );

      // 内訳テキスト
      document.getElementById("buyable_breakdown").textContent =
        "自己資金 " + fmt(n("self_man")) +
        " + 借入 " + fmt(res.total_loan_man) +
        " − リノベ " + fmt(res.reno_cost_tax_incl_man) +
        " − 諸費用 " + fmt(res.fee_man) + " 万円";

      // 総額入力→月々逆算のとき、月々欄へ反映
      if(res.monthly_man_out !== undefined){
        document.getElementById("monthly_man").value =
          Number(res.monthly_man_out).toFixed(2);
      }
    });
  </script>

</body>
</html>
"""
    return HTMLResponse(html)


# ---------------------------------------------
# 計算 API
# ---------------------------------------------
@app.post("/calc", response_model=CalcRes)
def calc(req: CalcReq):

    monthly_in = float(req.monthly_man or 0)
    total_in = float(req.total_loan_input_man or 0)

    # リノベ費
    if req.reno_mode == "full":
        reno = full_renovation_cost(req.area_need_m2)
    else:
        reno = float(req.reno_cost_input_man or 0)

    reno_tax = reno * (1 + TAX_RATE)

    # ①総借入額入力 → 月々返済を逆算
    if total_in > 0 and monthly_in <= 0:
        total_loan = total_in
        monthly = monthly_payment_from_total_loan(
            total_loan, req.bonus_man, req.rate_percent, req.years
        )
    # ②月々返済入力 → 総借入額を逆算
    else:
        monthly = monthly_in
        total_loan = loan_capacity_by_payments(
            monthly, req.bonus_man, req.rate_percent, req.years
        )

    # 総資金（自己資金 + 借入 - リノベ税込）
    disposable = req.self_man + total_loan - reno_tax

    # 物件価格と諸費用
    purch = solve_purchase_price(disposable, FEE_RATE)
    fee = purch * FEE_RATE

    return JSONResponse({
        "ok": True,
        "monthly_man_out": round(monthly, 2),
        "total_loan_man": round(total_loan, 1),
        "reno_cost_man": round(reno, 1),
        "reno_cost_tax_incl_man": round(reno_tax, 1),
        "fee_man": round(fee, 1),
        "purchasable_price_man": round(purch, 1),
        "memo_text": req.memo_text or "",
    })
