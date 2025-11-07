import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";

export default class extends Controller {
  static values = {
    suggestionId: Number,
    projectId: Number,
  };

  static targets = [
    "dialog",
    "steps",
    "progressBar",
    "errorMessage",
    "retryButton",
    "closeButton",
  ];

  connect() {
    this.blogPostId = null;
    this.currentStep = null;
    this.retryCount = {};
    this.maxRetries = 3;

    this.stepNames = [
      { key: "structure", label: "Generate Structure" },
      { key: "content", label: "Generate Content" },
      { key: "preliminary_validation", label: "Preliminary Validation" },
      { key: "internal_links", label: "Insert Internal Links" },
      { key: "final_validation", label: "Final Validation" },
    ];
  }

  async startPipeline(event) {
    event.preventDefault();

    // Show dialog
    if (this.hasDialogTarget) {
      this.dialogTarget.classList.remove("hidden");
    }

    // Initialize UI
    this.renderSteps();
    this.updateProgress(0);

    try {
      // Start the pipeline
      const response = await fetch(`/api/generate-blog-content-pipeline/${this.suggestionIdValue}/start`, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
        },
      });

      const data = await response.json();

      if (data.status === "error") {
        throw new Error(data.message || "Failed to start pipeline");
      }

      this.blogPostId = data.blog_post_id;

      // Execute each step sequentially
      for (let i = 0; i < this.stepNames.length; i++) {
        const step = this.stepNames[i];
        this.currentStep = step.key;

        const success = await this.executeStep(step, i);

        if (!success) {
          // Step failed, show retry option if available
          break;
        }
      }

      // All steps completed successfully
      this.onPipelineComplete();

    } catch (error) {
      this.showError(error.message || "Failed to start pipeline");
    }
  }

  async executeStep(step, stepIndex) {
    // Update UI to show step in progress
    this.updateStepStatus(stepIndex, "in-progress");

    try {
      const response = await fetch(
        `/api/generate-blog-content-pipeline/${this.blogPostId}/step/${step.key}`,
        {
          method: "POST",
          headers: {
            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
          },
        }
      );

      const data = await response.json();

      if (data.status === "error") {
        // Step failed
        this.updateStepStatus(stepIndex, "failed");

        // Check if we can retry
        const retryCount = this.retryCount[step.key] || 0;
        if (retryCount < this.maxRetries) {
          this.showRetryOption(step, stepIndex);
          return false;
        } else {
          this.showError(`Step "${step.label}" failed after ${this.maxRetries} attempts: ${data.message}`);
          return false;
        }
      }

      // Step succeeded
      this.updateStepStatus(stepIndex, "completed");
      this.updateProgress(((stepIndex + 1) / this.stepNames.length) * 100);
      return true;

    } catch (error) {
      this.updateStepStatus(stepIndex, "failed");
      this.showError(`Step "${step.label}" failed: ${error.message}`);
      return false;
    }
  }

  async retryStep(event) {
    event.preventDefault();

    const stepKey = event.target.dataset.stepKey;
    const stepIndex = event.target.dataset.stepIndex;
    const step = this.stepNames[stepIndex];

    // Increment retry count
    this.retryCount[stepKey] = (this.retryCount[stepKey] || 0) + 1;

    // Hide retry button and error
    this.hideError();

    // Reset step status to pending
    await fetch(
      `/api/generate-blog-content-pipeline/${this.blogPostId}/retry/${stepKey}`,
      {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
        },
      }
    );

    // Execute the step again
    const success = await this.executeStep(step, parseInt(stepIndex));

    if (success) {
      // Continue with remaining steps
      for (let i = parseInt(stepIndex) + 1; i < this.stepNames.length; i++) {
        const nextStep = this.stepNames[i];
        const nextSuccess = await this.executeStep(nextStep, i);

        if (!nextSuccess) {
          break;
        }
      }

      // Check if all steps completed
      if (parseInt(stepIndex) === this.stepNames.length - 1) {
        this.onPipelineComplete();
      }
    }
  }

  renderSteps() {
    if (!this.hasStepsTarget) return;

    this.stepsTarget.innerHTML = this.stepNames.map((step, index) => `
      <div class="flex items-center" data-step-index="${index}">
        <div class="flex items-center justify-center flex-shrink-0 w-8 h-8 border-2 border-gray-300 rounded-full" data-step-icon="${index}">
          <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" stroke-width="2" />
          </svg>
        </div>
        <div class="flex-1 ml-4">
          <div class="text-sm font-medium text-gray-900" data-step-label="${index}">
            ${step.label}
          </div>
          <div class="text-xs text-gray-500" data-step-status="${index}">
            Pending
          </div>
        </div>
      </div>
    `).join("");
  }

  updateStepStatus(stepIndex, status) {
    const iconElement = this.stepsTarget.querySelector(`[data-step-icon="${stepIndex}"]`);
    const statusElement = this.stepsTarget.querySelector(`[data-step-status="${stepIndex}"]`);

    if (!iconElement || !statusElement) return;

    // Update icon
    if (status === "in-progress") {
      iconElement.innerHTML = `
        <svg class="w-5 h-5 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      `;
      iconElement.className = "flex items-center justify-center flex-shrink-0 w-8 h-8 border-2 border-blue-600 rounded-full";
      statusElement.textContent = "In Progress...";
      statusElement.className = "text-xs text-blue-600";
    } else if (status === "completed") {
      iconElement.innerHTML = `
        <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
      `;
      iconElement.className = "flex items-center justify-center flex-shrink-0 w-8 h-8 border-2 border-green-600 rounded-full bg-green-50";
      statusElement.textContent = "Completed";
      statusElement.className = "text-xs text-green-600";
    } else if (status === "failed") {
      iconElement.innerHTML = `
        <svg class="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      `;
      iconElement.className = "flex items-center justify-center flex-shrink-0 w-8 h-8 border-2 border-red-600 rounded-full bg-red-50";
      statusElement.textContent = "Failed";
      statusElement.className = "text-xs text-red-600";
    }
  }

  updateProgress(percentage) {
    if (!this.hasProgressBarTarget) return;

    this.progressBarTarget.style.width = `${percentage}%`;
    this.progressBarTarget.setAttribute("aria-valuenow", percentage);
  }

  showError(message) {
    if (this.hasErrorMessageTarget) {
      this.errorMessageTarget.textContent = message;
      this.errorMessageTarget.classList.remove("hidden");
    }
  }

  hideError() {
    if (this.hasErrorMessageTarget) {
      this.errorMessageTarget.classList.add("hidden");
    }
  }

  showRetryOption(step, stepIndex) {
    const retryCount = this.retryCount[step.key] || 0;
    const remainingRetries = this.maxRetries - retryCount;

    if (this.hasRetryButtonTarget) {
      this.retryButtonTarget.innerHTML = `
        <button
          data-action="blog-generation-pipeline#retryStep"
          data-step-key="${step.key}"
          data-step-index="${stepIndex}"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
          Retry (${remainingRetries} attempts left)
        </button>
      `;
      this.retryButtonTarget.classList.remove("hidden");
    }
  }

  onPipelineComplete() {
    if (this.hasCloseButtonTarget) {
      this.closeButtonTarget.classList.remove("hidden");
      this.closeButtonTarget.innerHTML = `
        <a
          href="/project/${this.projectIdValue}/post/${this.blogPostId}/"
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500">
          <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
          </svg>
          View Generated Post
        </a>
      `;
    }

    showMessage("Blog post generated successfully!", "success");
    this.updateProgress(100);
  }

  closeDialog(event) {
    event.preventDefault();

    if (this.hasDialogTarget) {
      this.dialogTarget.classList.add("hidden");
    }

    // Reload the page to show the new blog post
    window.location.reload();
  }
}
