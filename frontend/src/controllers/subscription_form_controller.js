import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["button", "buttonText", "spinner"];

  submit() {
    this.buttonTarget.disabled = true;

    if (this.hasButtonTextTarget) {
      this.buttonTextTarget.textContent = "Processing...";
    }

    if (this.hasSpinnerTarget) {
      this.spinnerTarget.classList.remove("hidden");
    }
  }
}
