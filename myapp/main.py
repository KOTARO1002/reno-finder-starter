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
  <style>
    body { background:#F1F5F9 }
    .box { border:1px solid #e5e7eb; border-radius:.75rem; padding:1rem; background:white; }
    .label { color:#374151; font-size:.9rem; margin-bottom:.25rem; display:block; }
    .valuebox { background:#F8FAFC; border-radius:.5rem; padding:.75rem 1rem; font-weight:600; width:100%; }
    .kpi { font-size:1.25rem; }
    .kpi-input { border:none; outline:none; background:#F8FAFC; width:100%; }
    .manual-input { width:12rem; }
    @media (min-width: 1024px){ .manual-input{ width:16rem; } }

    /* 印刷（PDF化）最適化 */
    @media print {
      /* A4 1枚に収める（縮小98%を不要に寄せる） */
      @page { size: A4 portrait; margin: 8mm; }

      html, body { background:#fff !important; }
      body { padding: 0 !important; }

      /* ブラウザが色を落としがちなので、残せる環境では残す */
      * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

      /* 余白・文字サイズを少し締める */
      h1 { font-size: 16pt !important; margin-bottom: 10px !important; }

      .main-grid { gap: 10px !important; grid-template-columns: 1fr 1fr !important; }
      .results-grid { gap: 10px !important; }
      .input-grid { gap: 8px !important; }

      .box {
        padding: 10px !important;
        border: 1px solid #111827 !important; /* 線を強めに */
        box-shadow: none !important;
      }

      /* 背景色が消えても読めるように、枠線で視認性を担保 */
      .valuebox {
        background: #fff !important;
        border: 1px solid #9ca3af !important;
        padding: 8px 10px !important;
      }

      /* KPIは少しだけ小さくして縦方向を圧縮 */
      .kpi { font-size: 1.05rem !important; }

      /* 購入可能価格を“線で目立たせる” */
      #buyable {
        color: #065f46 !important;
        border: 2px solid #065f46 !important;
      }

      /* 入力ボタンなど、印刷に不要なものは非表示 */
      #calc_btn { display: none !important; }

      /* テキストエリアは罫線をしっかり */
      textarea {
        border: 1px solid #111827 !important;
        border-radius: 8px !important;
        min-height: 110px !important;
      }

      /* フッターを詰める */
      footer { margin-top: 8px !important; padding-bottom: 0 !important; }

      /* 変な改ページを避ける */
      .box, .results-grid { break-inside: avoid; page-break-inside: avoid; }
    }
  </style>
</head>
<body class="p-4">

  <div class="max-w-6xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">中古×リノベ 資金計画シミュレーター</h1>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 main-grid">

      <!-- 左側：入力 -->
      <div class="box">
        <div class="grid grid-cols-2 gap-3 input-grid">
          <label class="label">自己資金（万円）</label>
          <input id="self_man" type="number" step="0.1" class="valuebox" placeholder="例：300"/>

          <label class="label">月々の支払可能額（万円）</label>
          <input id="monthly_man" type="number" step="0.1" class="valuebox" placeholder="例：10"/>

          <label class="label">金利（%）</label>
          <input id="rate_percent" type="number" step="0.01" class="valuebox" placeholder="例：0.8"/>

          <label class="label">借入期間（年）</label>
          <input id="years" type="number" step="1" class="valuebox" placeholder="例：35"/>

          <label class="label">必要㎡数</label>
          <input id="area_need_m2" type="number" step="1" class="valuebox" placeholder="例：60"/>

          <label class="label">ボーナス時返済額（万円/回）</label>
          <input id="bonus_man" type="number" step="0.1" class="valuebox" placeholder="例：10"/>
        </div>

        <div class="mt-3">
          <span class="label">リノベ方式</span>
          <div class="flex flex-wrap gap-4 items-end">
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

        <div class="text-sm text-gray-500 mt-2">
          ※ 諸費用率は現在 <b>0.0800</b>（≒8.0%）に設定。
        </div>
      </div>

      <!-- 右側：結果 -->
      <div class="flex flex-col gap-4">

        <div class="grid grid-cols-2 gap-4 results-grid">

          <div class="box">
            <div class="label">総借入額（万円）</div>
            <input id="total_loan" type="text" inputmode="decimal"
                   class="valuebox kpi kpi-input" placeholder="-" />
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
          <textarea id="memo_text" class="w-full p-3 border rounded"
                    style="min-height:150px;"
                    placeholder="例：内見の所感、優先順位、気づき・要望など自由に記入"></textarea>
        </div>

      </div>

    </div>

    <!-- フッター：PCは右端ラインに合わせて右寄せ／スマホは最下部センター -->
    <!-- ロゴは少し小さく＆少し上（= 余白を下に足して持ち上げる） -->
    <footer class="mt-4 pb-4">
      <div class="max-w-6xl mx-auto">
        <div class="flex justify-center md:justify-end items-center">
          <img src="/static/SHロゴ横長.png"
               alt="SIMPLE HOUSE logo"
               class="h-8 md:h-9 opacity-90" />
        </div>
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
      document.getElementById("total_loan").value =
        res.total_loan_man.toLocaleString(undefined,{maximumFractionDigits:1});

      document.getElementById("reno_cost").textContent =
        res.reno_cost_man.toLocaleString(undefined,{maximumFractionDigits:1});

      document.getElementById("reno_cost_tax_incl").textContent =
        res.reno_cost_tax_incl_man.toLocaleString(undefined,{maximumFractionDigits:1});

      document.getElementById("fee_cost").textContent =
        res.fee_man.toLocaleString(undefined,{maximumFractionDigits:1});

      document.getElementById("buyable").textContent =
        res.purchasable_price_man.toLocaleString(undefined,{maximumFractionDigits:1});

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
