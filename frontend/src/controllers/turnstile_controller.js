import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["container"];
  static values = {
    siteKey: String
  };

  connect() {
    this.hasRendered = false;
    this.scriptLoaded = false;
  }

  renderWidget() {
    if (this.hasRendered) {
      return;
    }

    if (!this.hasContainerTarget) {
      console.error("Turnstile container not found");
      return;
    }

    if (!this.scriptLoaded) {
      this.loadTurnstileScript();
    } else {
      this.initializeTurnstile();
    }
  }

  loadTurnstileScript() {
    if (document.querySelector('script[src*="turnstile"]')) {
      this.scriptLoaded = true;
      this.waitForTurnstile();
      return;
    }

    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.onload = () => {
      this.scriptLoaded = true;
      this.waitForTurnstile();
    };
    script.onerror = () => {
      console.error("Failed to load Turnstile script");
    };
    document.head.appendChild(script);
  }

  waitForTurnstile() {
    const checkTurnstile = () => {
      if (typeof window.turnstile !== "undefined" && window.turnstile.render) {
        this.initializeTurnstile();
      } else {
        setTimeout(checkTurnstile, 50);
      }
    };
    checkTurnstile();
  }

  initializeTurnstile() {
    if (this.hasRendered || !this.hasContainerTarget) {
      return;
    }

    if (typeof window.turnstile === "undefined") {
      console.error("Turnstile not available");
      return;
    }

    if (!this.siteKeyValue) {
      console.error("Turnstile site key not configured");
      return;
    }

    try {
      window.turnstile.render(this.containerTarget, {
        sitekey: this.siteKeyValue,
        size: "flexible",
      });
      this.hasRendered = true;
    } catch (error) {
      console.error("Error rendering Turnstile:", error);
    }
  }
}
