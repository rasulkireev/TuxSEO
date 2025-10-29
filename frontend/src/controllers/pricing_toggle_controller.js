import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = [
    "monthlyPriceDisplay",
    "yearlyPriceDisplay",
    "monthlyLabel",
    "yearlyLabel",
    "monthlyCheckout",
    "yearlyCheckout",
    "toggle"
  ];

  connect() {
    this.isMonthly = true;
    this.updateUI();
  }

  switch() {
    this.isMonthly = !this.isMonthly;
    this.updateUI();
  }

  updateUI() {
    if (this.isMonthly) {
      this.monthlyPriceDisplayTargets.forEach(target => target.classList.remove("hidden"));
      this.yearlyPriceDisplayTargets.forEach(target => target.classList.add("hidden"));

      this.monthlyCheckoutTargets.forEach(target => target.classList.remove("hidden"));
      this.yearlyCheckoutTargets.forEach(target => target.classList.add("hidden"));

      this.monthlyLabelTarget.classList.add("bg-white", "text-gray-900", "shadow-md");
      this.monthlyLabelTarget.classList.remove("text-gray-500", "bg-transparent");
      this.yearlyLabelTarget.classList.add("text-gray-500", "bg-transparent");
      this.yearlyLabelTarget.classList.remove("bg-white", "text-gray-900", "shadow-md");

    } else {
      this.yearlyPriceDisplayTargets.forEach(target => target.classList.remove("hidden"));
      this.monthlyPriceDisplayTargets.forEach(target => target.classList.add("hidden"));

      this.yearlyCheckoutTargets.forEach(target => target.classList.remove("hidden"));
      this.monthlyCheckoutTargets.forEach(target => target.classList.add("hidden"));

      this.yearlyLabelTarget.classList.add("bg-white", "text-gray-900", "shadow-md");
      this.yearlyLabelTarget.classList.remove("text-gray-500", "bg-transparent");
      this.monthlyLabelTarget.classList.add("text-gray-500", "bg-transparent");
      this.monthlyLabelTarget.classList.remove("bg-white", "text-gray-900", "shadow-md");
    }
  }
}
