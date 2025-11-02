import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static values = {
    referrer: String,
  };

  connect() {
    const dismissed_banners = this.getDismissedBanners();
    if (dismissed_banners.includes(this.referrerValue)) {
      this.element.remove();
    }
  }

  dismiss() {
    this.saveDismissedBanner(this.referrerValue);
    this.element.remove();
  }

  getDismissedBanners() {
    const dismissed = localStorage.getItem("dismissedReferrerBanners");
    return dismissed ? JSON.parse(dismissed) : [];
  }

  saveDismissedBanner(referrer) {
    const dismissed_banners = this.getDismissedBanners();
    if (!dismissed_banners.includes(referrer)) {
      dismissed_banners.push(referrer);
      localStorage.setItem("dismissedReferrerBanners", JSON.stringify(dismissed_banners));
    }
  }
}
