/**
 * 画面まわりの処理。
 * 旧 index の inline <script> と同じ挙動を保ちつつ、
 * fetch("/calc") を RenoCalc.calc() のローカル呼び出しに置き換えている。
 */
(function () {
  "use strict";

  function n(id) {
    return parseFloat(document.getElementById(id).value || "0");
  }
  function t(id) {
    return document.getElementById(id).value || "";
  }

  function normalizeNum(s) {
    return (s || "")
      .replace(/[，,]/g, "")
      .replace(/[０-９]/g, function (c) {
        return String.fromCharCode(c.charCodeAt(0) - 0xfee0);
      })
      .replace(/[．。]/g, ".");
  }
  function getLoan() {
    return parseFloat(normalizeNum(document.getElementById("total_loan").value));
  }
  function fmt(v) {
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
  }

  var errorEl = document.getElementById("calc_error");
  function showError(message) {
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
  }
  function clearError() {
    errorEl.textContent = "";
    errorEl.classList.add("hidden");
  }

  // リノベ方式の手入力欄表示切替
  document.querySelectorAll("input[name='reno']").forEach(function (e) {
    e.addEventListener("change", function () {
      var m = document.getElementById("reno_cost_input_man");
      if (e.value === "manual") {
        m.classList.remove("hidden");
      } else {
        m.classList.add("hidden");
        m.value = "";
      }
    });
  });

  // どっちを基準に計算するか（デフォは月々）
  var calcSource = "monthly";
  document.getElementById("monthly_man").addEventListener("input", function () {
    calcSource = "monthly";
  });
  document.getElementById("total_loan").addEventListener("input", function () {
    calcSource = "total";
  });

  document.getElementById("calc_btn").addEventListener("click", function () {
    var mode = document.querySelector("input[name='reno']:checked").value;
    var loanEd = getLoan();
    var manualCost = document.getElementById("reno_cost_input_man").value;

    var inputs = {
      self_man: n("self_man"),
      monthly_man: calcSource === "monthly" ? n("monthly_man") : null,
      total_loan_input_man:
        calcSource === "total" && !isNaN(loanEd) ? loanEd : null,
      rate_percent: n("rate_percent"),
      area_need_m2: Math.trunc(n("area_need_m2")),
      years: Math.trunc(n("years")),
      reno_mode: mode,
      reno_cost_input_man:
        mode === "manual" && manualCost !== "" ? n("reno_cost_input_man") : null,
      bonus_man: n("bonus_man"),
      memo_text: t("memo_text"),
    };

    var problem = RenoCalc.validate(inputs);
    if (problem) {
      showError(problem);
      return;
    }
    clearError();

    var res = RenoCalc.calc(inputs);

    // 表示反映
    document.getElementById("total_loan").value = fmt(res.total_loan_man);
    document.getElementById("reno_cost").textContent = fmt(res.reno_cost_man);
    document.getElementById("reno_cost_tax_incl").textContent = fmt(
      res.reno_cost_tax_incl_man
    );
    document.getElementById("fee_cost").textContent = fmt(res.fee_man);
    document.getElementById("buyable").textContent = fmt(
      res.purchasable_price_man
    );

    // ツールチップに税抜を反映
    document
      .getElementById("reno_tip")
      .setAttribute("data-tip", "税抜: " + fmt(res.reno_cost_man) + " 万円");

    // 内訳テキスト
    document.getElementById("buyable_breakdown").textContent =
      "自己資金 " +
      fmt(inputs.self_man) +
      " + 借入 " +
      fmt(res.total_loan_man) +
      " − リノベ " +
      fmt(res.reno_cost_tax_incl_man) +
      " − 諸費用 " +
      fmt(res.fee_man) +
      " 万円";

    // 総額入力→月々逆算のとき、月々欄へ反映
    if (res.monthly_man_out !== undefined) {
      document.getElementById("monthly_man").value = Number(
        res.monthly_man_out
      ).toFixed(2);
    }
  });
})();
