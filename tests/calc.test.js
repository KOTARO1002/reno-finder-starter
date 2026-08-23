/**
 * 計算ロジックのリグレッションテスト。
 *
 * expected の値は、静的化する前の FastAPI 実装（旧 myapp/main.py の POST /calc）を
 * そのまま実行して得た出力です。ここが緑である限り、ブラウザ側の計算は
 * サーバー時代と同じ数字を返します。
 *
 *   実行: npm test   （Node 18 以降。追加の依存はありません）
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const RenoCalc = require("../assets/calc.js");

const KEYS = [
  "monthly_man_out",
  "total_loan_man",
  "reno_cost_man",
  "reno_cost_tax_incl_man",
  "fee_man",
  "purchasable_price_man",
];

const CASES = [
  {
    name: "月々から逆算・フルリノベ（代表ケース）",
    req: {"self_man": 300, "monthly_man": 10, "total_loan_input_man": null, "rate_percent": 0.8, "area_need_m2": 60, "years": 35, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 0},
    expected: {"monthly_man_out": 10.0, "total_loan_man": 3662.2, "reno_cost_man": 1070, "reno_cost_tax_incl_man": 1177.0, "fee_man": 206.3, "purchasable_price_man": 2578.9},
  },
  {
    name: "総借入額から月々を逆算",
    req: {"self_man": 300, "monthly_man": null, "total_loan_input_man": 4000, "rate_percent": 0.8, "area_need_m2": 60, "years": 35, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 0},
    expected: {"monthly_man_out": 10.92, "total_loan_man": 4000.0, "reno_cost_man": 1070, "reno_cost_tax_incl_man": 1177.0, "fee_man": 231.3, "purchasable_price_man": 2891.7},
  },
  {
    name: "リノベ費を手入力",
    req: {"self_man": 300, "monthly_man": null, "total_loan_input_man": 4000, "rate_percent": 0.8, "area_need_m2": 60, "years": 35, "reno_mode": "manual", "reno_cost_input_man": 800, "bonus_man": 0},
    expected: {"monthly_man_out": 10.92, "total_loan_man": 4000.0, "reno_cost_man": 800.0, "reno_cost_tax_incl_man": 880.0, "fee_man": 253.3, "purchasable_price_man": 3166.7},
  },
  {
    name: "ボーナス返済あり・月々から逆算",
    req: {"self_man": 500, "monthly_man": 12, "total_loan_input_man": null, "rate_percent": 1.2, "area_need_m2": 70, "years": 35, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 10},
    expected: {"monthly_man_out": 12.0, "total_loan_man": 4683.7, "reno_cost_man": 1190, "reno_cost_tax_incl_man": 1309.0, "fee_man": 287.0, "purchasable_price_man": 3587.7},
  },
  {
    name: "ボーナス返済あり・総借入額から逆算",
    req: {"self_man": 500, "monthly_man": null, "total_loan_input_man": 4000, "rate_percent": 1.2, "area_need_m2": 70, "years": 35, "reno_mode": "manual", "reno_cost_input_man": 800, "bonus_man": 10},
    expected: {"monthly_man_out": 10.01, "total_loan_man": 4000.0, "reno_cost_man": 800.0, "reno_cost_tax_incl_man": 880.0, "fee_man": 268.1, "purchasable_price_man": 3351.9},
  },
  {
    name: "金利0%・月々から逆算",
    req: {"self_man": 0, "monthly_man": 12, "total_loan_input_man": null, "rate_percent": 0.0, "area_need_m2": 55, "years": 30, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 20},
    expected: {"monthly_man_out": 12.0, "total_loan_man": 5520.0, "reno_cost_man": 1010, "reno_cost_tax_incl_man": 1111.0, "fee_man": 326.6, "purchasable_price_man": 4082.4},
  },
  {
    name: "金利0%・総借入額から逆算",
    req: {"self_man": 0, "monthly_man": null, "total_loan_input_man": 3000, "rate_percent": 0.0, "area_need_m2": 55, "years": 1, "reno_mode": "manual", "reno_cost_input_man": 0, "bonus_man": 0},
    expected: {"monthly_man_out": 250.0, "total_loan_man": 3000.0, "reno_cost_man": 0.0, "reno_cost_tax_incl_man": 0.0, "fee_man": 222.2, "purchasable_price_man": 2777.8},
  },
  {
    name: "費用が資金を上回り購入可能額が0になる",
    req: {"self_man": 10, "monthly_man": 1, "total_loan_input_man": null, "rate_percent": 3.5, "area_need_m2": 100, "years": 10, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 0},
    expected: {"monthly_man_out": 1.0, "total_loan_man": 101.1, "reno_cost_man": 1550, "reno_cost_tax_incl_man": 1705.0, "fee_man": 0.0, "purchasable_price_man": 0.0},
  },
  {
    name: "借入期間の下限1年",
    req: {"self_man": 1000, "monthly_man": 30, "total_loan_input_man": null, "rate_percent": 1.0, "area_need_m2": 50, "years": 1, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 0},
    expected: {"monthly_man_out": 30.0, "total_loan_man": 358.1, "reno_cost_man": 950, "reno_cost_tax_incl_man": 1045.0, "fee_man": 23.2, "purchasable_price_man": 289.9},
  },
  {
    name: "借入期間の上限50年",
    req: {"self_man": 1000, "monthly_man": 30, "total_loan_input_man": null, "rate_percent": 1.0, "area_need_m2": 50, "years": 50, "reno_mode": "full", "reno_cost_input_man": null, "bonus_man": 0},
    expected: {"monthly_man_out": 30.0, "total_loan_man": 14160.3, "reno_cost_man": 950, "reno_cost_tax_incl_man": 1045.0, "fee_man": 1045.6, "purchasable_price_man": 13069.8},
  },
  {
    name: "ボーナスだけで総借入額を満たし月々が0になる",
    req: {"self_man": 200, "monthly_man": null, "total_loan_input_man": 100, "rate_percent": 1.5, "area_need_m2": 40, "years": 35, "reno_mode": "manual", "reno_cost_input_man": 100, "bonus_man": 50},
    expected: {"monthly_man_out": 0.0, "total_loan_man": 100.0, "reno_cost_man": 100.0, "reno_cost_tax_incl_man": 110.0, "fee_man": 14.1, "purchasable_price_man": 175.9},
  },
  {
    name: "高金利・長期",
    req: {"self_man": 800, "monthly_man": 25, "total_loan_input_man": null, "rate_percent": 4.5, "area_need_m2": 85, "years": 40, "reno_mode": "manual", "reno_cost_input_man": 1500, "bonus_man": 15},
    expected: {"monthly_man_out": 25.0, "total_loan_man": 6111.9, "reno_cost_man": 1500.0, "reno_cost_tax_incl_man": 1650.0, "fee_man": 389.8, "purchasable_price_man": 4872.1},
  },
];

for (const c of CASES) {
  test("旧FastAPI実装と一致すること: " + c.name, () => {
    const got = RenoCalc.calc(c.req);
    for (const k of KEYS) {
      assert.equal(got[k], c.expected[k], k + " が一致しません");
    }
  });
}

test("借入期間は1〜50年の範囲外を弾くこと", () => {
  const base = {
    self_man: 300,
    monthly_man: 10,
    total_loan_input_man: null,
    rate_percent: 0.8,
    area_need_m2: 60,
    reno_mode: "full",
    reno_cost_input_man: null,
    bonus_man: 0,
  };
  const message = "借入期間は1〜50年で入力してください。";
  assert.equal(RenoCalc.validate(Object.assign({}, base, { years: 0 })), message);
  assert.equal(RenoCalc.validate(Object.assign({}, base, { years: 51 })), message);
  assert.equal(RenoCalc.validate(Object.assign({}, base, { years: -5 })), message);
  assert.equal(RenoCalc.validate(Object.assign({}, base, { years: 1 })), null);
  assert.equal(RenoCalc.validate(Object.assign({}, base, { years: 50 })), null);
});

test("購入可能物件価格は0を下回らないこと", () => {
  const res = RenoCalc.calc({
    self_man: 0,
    monthly_man: 0,
    total_loan_input_man: null,
    rate_percent: 1,
    area_need_m2: 200,
    years: 35,
    reno_mode: "full",
    reno_cost_input_man: null,
    bonus_man: 0,
  });
  assert.equal(res.purchasable_price_man, 0);
  assert.equal(res.fee_man, 0);
});

test("諸費用は購入可能物件価格の8パーセントであること", () => {
  const res = RenoCalc.calc({
    self_man: 300,
    monthly_man: 10,
    total_loan_input_man: null,
    rate_percent: 0.8,
    area_need_m2: 60,
    years: 35,
    reno_mode: "full",
    reno_cost_input_man: null,
    bonus_man: 0,
  });
  assert.ok(Math.abs(res.fee_man - res.purchasable_price_man * RenoCalc.FEE_RATE) < 0.1);
});

test("フルリノベ概算は 平米数×12＋350 万円であること", () => {
  assert.equal(RenoCalc.fullRenovationCost(60), 1070);
  assert.equal(RenoCalc.fullRenovationCost(0), 350);
});

test("リノベ費の税込は税抜の1.1倍であること", () => {
  const res = RenoCalc.calc({
    self_man: 300,
    monthly_man: 10,
    total_loan_input_man: null,
    rate_percent: 0.8,
    area_need_m2: 60,
    years: 35,
    reno_mode: "manual",
    reno_cost_input_man: 1000,
    bonus_man: 0,
  });
  assert.equal(res.reno_cost_man, 1000);
  assert.equal(res.reno_cost_tax_incl_man, 1100);
});
