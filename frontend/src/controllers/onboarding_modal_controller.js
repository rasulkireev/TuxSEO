import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = [
    "backdrop",
    "modal",
    "urlInput",
    "urlError",
    "continueButton",
    "step1",
    "step2",
    "step3",
    "step1Indicator",
    "step2Indicator",
    "step3Indicator",
    "checkingIndicator",
    "reachableIndicator",
    "unreachableIndicator",
    "unreachableMessage",
    "projectLink",
  ];

  connect() {
    this.currentStep = 1;
    this.createdProjectId = null;
    this.validationTimeout = null;
    this.isUrlReachable = false;
  }

  validateUrl() {
    const url_value = this.urlInputTarget.value.trim();
    const url_pattern = /^https?:\/\/.+/i;

    const is_valid = url_pattern.test(url_value);

    this.hideAllIndicators();

    if (this.validationTimeout) {
      clearTimeout(this.validationTimeout);
    }

    if (is_valid) {
      this.urlErrorTarget.classList.add("hidden");
      this.continueButtonTarget.disabled = true;
      this.isUrlReachable = false;

      this.checkingIndicatorTarget.classList.remove("hidden");
      this.checkingIndicatorTarget.classList.add("flex");

      this.validationTimeout = setTimeout(() => {
        this.checkUrlReachability(url_value);
      }, 500);
    } else {
      if (url_value.length > 0) {
        this.urlErrorTarget.classList.remove("hidden");
      }
      this.continueButtonTarget.disabled = true;
      this.isUrlReachable = false;
    }
  }

  hideAllIndicators() {
    this.checkingIndicatorTarget.classList.add("hidden");
    this.checkingIndicatorTarget.classList.remove("flex");
    this.reachableIndicatorTarget.classList.add("hidden");
    this.reachableIndicatorTarget.classList.remove("flex");
    this.unreachableIndicatorTarget.classList.add("hidden");
    this.unreachableIndicatorTarget.classList.remove("flex");
  }

  async checkUrlReachability(url_value) {
    try {
      const csrf_token = document.querySelector("[name=csrfmiddlewaretoken]").value;

      const response = await fetch("/api/validate-url", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf_token,
        },
        body: JSON.stringify({ url: url_value }),
      });

      if (!response.ok) {
        throw new Error("Failed to validate URL");
      }

      const data = await response.json();

      this.hideAllIndicators();

      if (data.reachable) {
        this.reachableIndicatorTarget.classList.remove("hidden");
        this.reachableIndicatorTarget.classList.add("flex");
        this.isUrlReachable = true;
        this.continueButtonTarget.disabled = false;
      } else {
        this.unreachableIndicatorTarget.classList.remove("hidden");
        this.unreachableIndicatorTarget.classList.add("flex");
        this.unreachableMessageTarget.textContent = data.message || "URL is not reachable";
        this.isUrlReachable = false;
        this.continueButtonTarget.disabled = true;
      }
    } catch (error) {
      console.error("Error checking URL reachability:", error);
      this.hideAllIndicators();
      this.unreachableIndicatorTarget.classList.remove("hidden");
      this.unreachableIndicatorTarget.classList.add("flex");
      this.unreachableMessageTarget.textContent = "Could not verify URL reachability";
      this.isUrlReachable = false;
      this.continueButtonTarget.disabled = true;
    }
  }

  async submitProject() {
    const url_value = this.urlInputTarget.value.trim();

    if (!url_value || !this.isUrlReachable) {
      return;
    }

    this.goToStep(2);

    try {
      const csrf_token = document.querySelector("[name=csrfmiddlewaretoken]").value;

      const response = await fetch("/api/projects/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf_token,
        },
        body: JSON.stringify({ url: url_value }),
      });

      if (!response.ok) {
        throw new Error("Failed to create project");
      }

      const data = await response.json();

      if (data.status !== "success") {
        throw new Error(data.message || "Failed to create project");
      }

      this.createdProjectId = data.id;

      setTimeout(() => {
        this.goToStep(3);
      }, 1500);

    } catch (error) {
      console.error("Error creating project:", error);
      alert("There was an error creating your project. Please try again.");
      this.goToStep(1);
    }
  }

  goToStep(step_number) {
    this.currentStep = step_number;

    this.step1Target.classList.add("hidden");
    this.step2Target.classList.add("hidden");
    this.step3Target.classList.add("hidden");

    this.step1IndicatorTarget.classList.remove("bg-gray-800", "border-gray-800", "w-6");
    this.step1IndicatorTarget.classList.add("bg-gray-300", "border-gray-300", "w-4");

    this.step2IndicatorTarget.classList.remove("bg-gray-800", "border-gray-800", "w-6");
    this.step2IndicatorTarget.classList.add("bg-gray-300", "border-gray-300", "w-4");

    this.step3IndicatorTarget.classList.remove("bg-gray-800", "border-gray-800", "w-6");
    this.step3IndicatorTarget.classList.add("bg-gray-300", "border-gray-300", "w-4");

    if (step_number === 1) {
      this.step1Target.classList.remove("hidden");
      this.step1Target.classList.add("flex");
      this.step1IndicatorTarget.classList.remove("bg-gray-300", "border-gray-300", "w-4");
      this.step1IndicatorTarget.classList.add("bg-gray-800", "border-gray-800", "w-6");
    } else if (step_number === 2) {
      this.step2Target.classList.remove("hidden");
      this.step2Target.classList.add("flex");
      this.step2IndicatorTarget.classList.remove("bg-gray-300", "border-gray-300", "w-4");
      this.step2IndicatorTarget.classList.add("bg-gray-800", "border-gray-800", "w-6");
    } else if (step_number === 3) {
      this.step3Target.classList.remove("hidden");
      this.step3Target.classList.add("flex");
      this.step3IndicatorTarget.classList.remove("bg-gray-300", "border-gray-300", "w-4");
      this.step3IndicatorTarget.classList.add("bg-gray-800", "border-gray-800", "w-6");

      // Update the project link href when showing step 3
      if (this.createdProjectId) {
        const project_url = `/project/${this.createdProjectId}/`;

        if (this.hasProjectLinkTarget) {
          this.projectLinkTarget.href = project_url;
          console.log("Project link updated to:", project_url);
        } else {
          // Fallback: query the element directly using Stimulus convention
          const link_element = this.element.querySelector('a[href="#"]');
          if (link_element) {
            link_element.href = project_url;
            console.log("Project link updated via fallback to:", project_url);
          } else {
            console.error("Could not find project link element");
          }
        }
      }
    }
  }

  skipOnboarding() {
    this.closeModal();
  }

  closeModal() {
    this.backdropTarget.remove();
  }
}
