/**
 * 中古×リノベ 資金計画シミュレーター — 計算ロジック
 *
 * かつて FastAPI の POST /calc が担っていた計算をそのままブラウザへ移したもの。
 * 副作用も外部依存も無い純粋計算なので、ブラウザ・Node のどちらからでも使える。
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.RenoCalc = api;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // 設定 --------------------------------------------
  var FEE_RATE = 0.08; // 諸費用率 8%
  var TAX_RATE = 0.10; // 消費税 10%

  // 計算ユーティリティ -------------------------------

  /** 毎月返済から借入可能額(PV) */
  function pvAnnuity(monthly, i, n) {
    if (n <= 0) return 0;
    if (i === 0) return monthly * n;
    return (monthly * (1 - Math.pow(1 + i, -n))) / i;
  }

  /** ボーナス返済の現在価値(PV) */
  function pvBonuses(bonusPerEvent, i, n, everyMonths) {
    everyMonths = everyMonths || 6;
    if (bonusPerEvent <= 0 || n <= 0) return 0;
    if (i === 0) return bonusPerEvent * Math.floor(n / everyMonths);
    var pv = 0;
    for (var m = everyMonths; m <= n; m += everyMonths) {
      pv += bonusPerEvent / Math.pow(1 + i, m);
    }
    return pv;
  }

  /** 月額＋ボーナスから総借入額を逆算 */
  function loanCapacityByPayments(monthlyMan, bonusMan, ratePercent, years) {
    var n = years * 12;
    var i = ratePercent / 100 / 12;
    return pvAnnuity(monthlyMan, i, n) + pvBonuses(bonusMan, i, n);
  }

  /** 総借入額＋ボーナスから月々返済額を逆算 */
  function monthlyPaymentFromTotalLoan(totalLoanMan, bonusMan, ratePercent, years) {
    var n = years * 12;
    var i = ratePercent / 100 / 12;
    if (n <= 0) return 0;
    var pvBonus = pvBonuses(bonusMan, i, n);
    var pvForMonthly = Math.max(totalLoanMan - pvBonus, 0);
    if (i === 0) return pvForMonthly / n;
    return (pvForMonthly * i) / (1 - Math.pow(1 + i, -n));
  }

  /** フルリノベ概算（万円） */
  function fullRenovationCost(areaM2) {
    return areaM2 * 12 + 350;
  }

  /** 諸費用率込みの総資金から物件価格を逆算 */
  function solvePurchasePrice(totalFundsMan, feeRate) {
    return Math.max(totalFundsMan / (1 + Math.max(feeRate, 0)), 0);
  }

  /** 小数第 digits 位で四捨五入 */
  function round(value, digits) {
    var f = Math.pow(10, digits);
    return Math.round((value + Number.EPSILON) * f) / f;
  }

  /**
   * 入力値の検証。問題が無ければ null、あればメッセージを返す。
   * 借入期間の 1〜50 年チェックは、FastAPI 時代に pydantic が担っていたもの。
   */
  function validate(req) {
    if (!(req.years > 0) || req.years > 50) {
      return "借入期間は1〜50年で入力してください。";
    }
    return null;
  }

  /**
   * 資金計画の計算本体。
   * 旧 POST /calc と同じ入力キー・同じ出力キーを保つ。
   */
  function calc(req) {
    var monthlyIn = Number(req.monthly_man || 0);
    var totalIn = Number(req.total_loan_input_man || 0);

    // リノベ費
    var reno =
      req.reno_mode === "full"
        ? fullRenovationCost(req.area_need_m2)
        : Number(req.reno_cost_input_man || 0);

    var renoTax = reno * (1 + TAX_RATE);

    var monthly;
    var totalLoan;

    if (totalIn > 0 && monthlyIn <= 0) {
      // ①総借入額入力 → 月々返済を逆算
      totalLoan = totalIn;
      monthly = monthlyPaymentFromTotalLoan(
        totalLoan,
        req.bonus_man,
        req.rate_percent,
        req.years
      );
    } else {
      // ②月々返済入力 → 総借入額を逆算
      monthly = monthlyIn;
      totalLoan = loanCapacityByPayments(
        monthly,
        req.bonus_man,
        req.rate_percent,
        req.years
      );
    }

    // 総資金（自己資金 + 借入 - リノベ税込）
    var disposable = Number(req.self_man || 0) + totalLoan - renoTax;

    // 物件価格と諸費用
    var purch = solvePurchasePrice(disposable, FEE_RATE);
    var fee = purch * FEE_RATE;

    return {
      ok: true,
      monthly_man_out: round(monthly, 2),
      total_loan_man: round(totalLoan, 1),
      reno_cost_man: round(reno, 1),
      reno_cost_tax_incl_man: round(renoTax, 1),
      fee_man: round(fee, 1),
      purchasable_price_man: round(purch, 1),
      memo_text: req.memo_text || "",
    };
  }

  return {
    FEE_RATE: FEE_RATE,
    TAX_RATE: TAX_RATE,
    pvAnnuity: pvAnnuity,
    pvBonuses: pvBonuses,
    loanCapacityByPayments: loanCapacityByPayments,
    monthlyPaymentFromTotalLoan: monthlyPaymentFromTotalLoan,
    fullRenovationCost: fullRenovationCost,
    solvePurchasePrice: solvePurchasePrice,
    validate: validate,
    calc: calc,
  };
});
