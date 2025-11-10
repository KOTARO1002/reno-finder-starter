# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
import os

app = FastAPI()

# static（ロゴ等）
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 設定
FEE_RATE = float(os.getenv("FEE_RATE", "0.08"))
TAX_RATE  = float(os.getenv("TAX_RATE",  "0.10"))

# 計算ユーティリティ
def pv_annuity(monthly: float, i: float, n: int) -> float:
    if n <= 0: return 0.0
    if i == 0: return monthly * n
    return monthly * (1 - (1 + i) ** (-n)) / i

def pv_bonuses(bonus_per_event: float, i: float, n: int, every_months: int = 6) -> float:
    if bonus_per_event <= 0 or n <= 0: return 0.0
    if i == 0: return bonus_per_event * (n // every_months)
    pv = 0.0
    m = every_months
    while m <= n:
        pv += bonus_per_event / ((1 + i) ** m)
        m += every_months
    return pv

def loan_capacity_by_payments(monthly_man: float, bonus_man: float, rate_percent: float, years: int) -> float:
    n = years * 12
    i = rate_percent / 100.0 / 12.0
    return pv_annuity(monthly_man, i, n) + pv_bonuses(bonus_man, i, n, every_months=6)

def full_renovation_cost(area_m2: int) -> float:
    # 単純モデル（万円）
    return area_m2 * 12.0 + 350.0

def solve_purchase_price(total_funds_man: float, fee_rate: float) -> float:
    return max(total_funds_man / (1.0 + max(fee_rate, 0.0)), 0.0)

# 入出力モデル
class CalcReq(BaseModel):
    self_man: float = Field(..., description="自己資金（万円）")
    monthly_man: float = Field(..., description="月々の支払可能額（万円）")
    rate_percent: float = Field(..., description="金利（%）")
    area_need_m2: int = Field(..., description="必要㎡数（整数）")
    years: int = Field(..., description="借入期間（年, 最大50）")
    reno_mode: Literal["full", "manual"] = Field(..., description="フル/手入力")
    reno_cost_input_man: Optional[float] = Field(None, description="（手入力）リノベ費用（万円）")
    bonus_man: float = Field(0.0, description="ボーナス時返済額（万円/回・年2回）")
    memo_text: Optional[str] = Field("", description="メモ")

    @field_validator("years")
    @classmethod
    def _years_ok(cls, v: int) -> int:
        if v <= 0 or v > 50:
            raise ValueError("借入期間は1〜50年で入力してください。")
        return v

class CalcRes(BaseModel):
    ok: bool
    total_loan_man: float
    reno_cost_man: float
    reno_cost_tax_incl_man: float
    fee_man: float
    purchasable_price_man: float
    memo_text: str

# 画面
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
    .valuebox { background:#F8FAFC; border-radius:.5rem; padding:.75rem 1rem; font-weight:600; }
    .kpi { font-size:1.25rem; }
    .hint { color:#6B7280; font-size:.85rem; }
    /* ラジオ行の手入力欄はラベル無し・右横に配置 */
    .manual-input { width: 12rem; }            /* 画面幅に応じて調整 */
    @media (min-width: 1024px) { .manual-input { width: 16rem; } }
    /* 左右の下端を常に揃える（A案：自動連動） */
    .grid-stretch { align-items: stretch; }    /* 親グリッドで各列の高さを揃える */
    .left-col-box { height: 100%; }            /* 左の大ボックスを列の高さに合わせて伸ばす */
    .right-col     { display:flex; flex-direction:column; height:100%; } /* 右列を縦フレックス */
    .kpi-area      { /* 上部KPIは高さなり */ }
    .memo-wrap     { flex:1 1 auto; display:flex; flex-direction:column; }
    .memo-box      { flex:1 1 auto; min-height: 12rem; } /* KPIが少ない時の最低高だけ確保 */
  </style>
</head>
<body class="p-4">
  <div class="max-w-6xl mx-auto">
    <h1 class="text-2xl font-bold mb-4">中古×リノベ 資金計画シミュレーター</h1>

    <!-- 親グリッドで items-stretch（= grid-stretch） -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 grid-stretch">

      <!-- 左：入力（この .box を列の高さに合わせて100%に） -->
      <div class="left-col-box box">
        <h2 class="font-semibold mb-2">① 条件入力</h2>

        <div class="grid grid-cols-2 gap-3">
          <label class="label">自己資金（万円）</label>
          <input id="self_man" type="number" step="0.1" class="valuebox" placeholder="例：300" />

          <label class="label">月々の支払可能額（万円）</label>
          <input id="monthly_man" type="number" step="0.1" class="valuebox" placeholder="例：10" />

          <label class="label">金利（%）</label>
          <input id="rate_percent" type="number" step="0.01" class="valuebox" placeholder="例：0.8" />

          <label class="label">借入期間（年）</label>
          <input id="years" type="number" step="1" class="valuebox" placeholder="例：35" />

          <label class="label">必要㎡数</label>
          <input id="area_need_m2" type="number" step="1" class="valuebox" placeholder="例：60" />

          <label class="label">ボーナス時返済額（万円/回）</label>
          <input id="bonus_man" type="number" step="0.1" class="valuebox" placeholder="例：10" />
        </div>

        <!-- リノベ方式（右横にラベル無しの手入力欄を配置） -->
        <div class="mt-4">
          <span class="label mb-1">リノベ方式</span>
          <div class="flex flex-wrap items-end gap-4">
            <label class="inline-flex items-center gap-1">
              <input type="radio" name="reno" value="full" checked />
              <span>フルリノベ</span>
            </label>
            <label class="inline-flex items-center gap-1">
              <input type="radio" name="reno" value="manual" />
              <span>リノベ費用手入力</span>
            </label>

            <!-- ラベル無しの手入力欄（青枠位置） -->
            <input id="reno_cost_input_man"
                   type="number" step="0.1"
                   class="valuebox manual-input ml-auto hidden" placeholder="例：800" />
          </div>
        </div>

        <button id="calc_btn" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded">計算する</button>
        <div class="hint mt-2">※ 諸費用率は現在 <b>""" + f"{FEE_RATE:.4f}" + """</b>（≒""" + f"{FEE_RATE*100:.1f}" + """%）に設定。</div>
      </div>

      <!-- 右：KPI + メモ（右列全体で高さ100% → メモが残りを埋める） -->
      <div class="right-col">
        <div class="kpi-area">
          <div class="grid grid-cols-2 gap-4">
            <div class="box">
              <div class="label">総借入額（万円）</div>
              <div id="total_loan" class="valuebox kpi">-</div>
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
        </div>

        <!-- メモが残りスペースを flex:1 で埋めるので、左のボックスと下端が自動で揃う -->
        <div class="memo-wrap mt-4">
          <div class="box" style="display:flex; flex-direction:column; height:100%;">
            <h2 class="font-semibold mb-2">② メモ欄</h2>
            <textarea id="memo_text" class="w-full p-3 border rounded memo-box"
              placeholder="例：内見の所感、優先順位、気づき・要望など自由に記入"
              style="flex:1 1 auto;"></textarea>
          </div>
        </div>
      </div>

    </div>

    <!-- ロゴ（任意） -->
    <div class="absolute bottom-4 right-0 opacity-80 pointer-events-none select-none">
      <img src="/static/SHロゴ横長.png" alt="logo" class="h-10" />
    </div>
  </div>

  <script>
    function num(id){ return parseFloat(document.getElementById(id).value || "0"); }
    function txt(id){ return (document.getElementById(id).value || ""); }

    async function postJSON(url, payload){
      const r = await fetch(url, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      return await r.json();
    }

    // ラジオ切替：manual時のみ手入力欄を表示（右横、ラベル無し）
    function updateManualVisibility(){
      const mode = document.querySelector('input[name="reno"]:checked').value;
      const input = document.getElementById('reno_cost_input_man');
      if(mode === 'manual'){ input.classList.remove('hidden'); }
      else{ input.classList.add('hidden'); input.value=''; }
    }
    document.querySelectorAll('input[name="reno"]').forEach(el => el.addEventListener('change', updateManualVisibility));
    updateManualVisibility();

    document.getElementById('calc_btn').addEventListener('click', async ()=>{
      try{
        const mode = document.querySelector('input[name="reno"]:checked').value;
        const inputs = {
          self_man: num('self_man'),
          monthly_man: num('monthly_man'),
          rate_percent: num('rate_percent'),
          area_need_m2: Math.trunc(num('area_need_m2')),
          years: Math.trunc(num('years')),
          reno_mode: mode,
          reno_cost_input_man: (mode==='manual' && document.getElementById('reno_cost_input_man').value !== '')
                                ? num('reno_cost_input_man') : null,
          bonus_man: num('bonus_man'),
          memo_text: txt('memo_text')
        };
        const res = await postJSON('/calc', inputs);
        if(!res.ok) throw new Error('計算に失敗しました');

        document.getElementById('total_loan').textContent =
          res.total_loan_man.toLocaleString(undefined,{maximumFractionDigits:1});
        document.getElementById('reno_cost').textContent  =
          res.reno_cost_man.toLocaleString(undefined,{maximumFractionDigits:1});
        document.getElementById('reno_cost_tax_incl').textContent  =
          res.reno_cost_tax_incl_man.toLocaleString(undefined,{maximumFractionDigits:1});
        document.getElementById('fee_cost').textContent   =
          res.fee_man.toLocaleString(undefined,{maximumFractionDigits:1});
        document.getElementById('buyable').textContent    =
          res.purchasable_price_man.toLocaleString(undefined,{maximumFractionDigits:1});
      }catch(e){
        alert(e.message || 'エラーが発生しました');
      }
    });
  </script>
</body>
</html>
"""
    return HTMLResponse(html)

# 計算API
@app.post("/calc", response_model=CalcRes)
def calc(req: CalcReq):
    if req.self_man < 0 or req.monthly_man <= 0 or req.rate_percent < 0 or req.area_need_m2 <= 0:
        return JSONResponse({"ok": False, "detail": "入力値を確認してください。"}, status_code=400)
    total_loan = loan_capacity_by_payments(req.monthly_man, req.bonus_man, req.rate_percent, req.years)

    if req.reno_mode == "full":
        reno_cost = full_renovation_cost(req.area_need_m2)
    else:
        if req.reno_cost_input_man is None:
            return JSONResponse({"ok": False, "detail": "リノベ費用（手入力・万円）を入力してください。"}, status_code=400)
        reno_cost = float(req.reno_cost_input_man)

    reno_cost_tax_incl = reno_cost * (1.0 + TAX_RATE)

    disposable = req.self_man + total_loan - reno_cost
    purch_price = solve_purchase_price(disposable, FEE_RATE)
    fee = purch_price * FEE_RATE

    return CalcRes(
        ok=True,
        total_loan_man=round(total_loan, 1),
        reno_cost_man=round(reno_cost, 1),
        reno_cost_tax_incl_man=round(reno_cost_tax_incl, 1),
        fee_man=round(fee, 1),
        purchasable_price_man=round(purch_price, 1),
        memo_text=req.memo_text or "",
    )
