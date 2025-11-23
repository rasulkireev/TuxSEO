import { Controller } from "@hotwired/stimulus";
import { showMessage } from "../utils/messages";
export default class extends Controller {
  static values = {
    url: String,
    suggestionId: Number,
    projectId: Number,
    hasProSubscription: Boolean,
    hasAutoSubmissionSetting: Boolean,
    pricingUrl: String,
    projectSettingsUrl: String
  };

  static targets = [
    "status",
    "content",
    "buttonContainer",
    "dropdown",
    "chevron",
    "postButtonContainer"
  ];

  connect() {
    this.expandedValue = false;
    this.pollingTimeoutId = null;

    // Check if there's an ongoing task for this suggestion
    this._checkForOngoingTask();
  }

  _checkForOngoingTask() {
    const taskKey = `blog_generation_task_${this.suggestionIdValue}`;
    const taskData = localStorage.getItem(taskKey);

    if (taskData) {
      try {
        const { taskId, startTime } = JSON.parse(taskData);
        const elapsedMinutes = (Date.now() - startTime) / 1000 / 60;

        // Only resume if task started less than 10 minutes ago
        if (elapsedMinutes < 10) {
          // Update UI to show generating state
          this.buttonContainerTarget.innerHTML = `
            <button
              disabled
              class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 opacity-75 cursor-not-allowed">
              <svg class="mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Generating...
            </button>
          `;

          if (this.hasStatusTarget) {
            this.statusTarget.innerHTML = `
              <div class="flex gap-1.5 items-center">
                <div class="w-3 h-3 bg-amber-500 rounded-full animate-pulse"></div>
                <span class="text-sm font-medium text-amber-700">Generating...</span>
              </div>
            `;
          }

          // Resume polling
          this._pollTaskStatus(taskId);
        } else {
          // Task too old, clean up
          localStorage.removeItem(taskKey);
        }
      } catch (error) {
        // Invalid data, clean up
        localStorage.removeItem(taskKey);
      }
    }
  }

  disconnect() {
    // Clean up any ongoing polling when controller is disconnected
    if (this.pollingTimeoutId) {
      clearTimeout(this.pollingTimeoutId);
      this.pollingTimeoutId = null;
    }
  }

  toggle() {
    this.expandedValue = !this.expandedValue;

    if (this.hasDropdownTarget) {
      this.dropdownTarget.classList.toggle("hidden");
    }

    if (this.hasChevronTarget) {
      this.chevronTarget.classList.toggle("rotate-180");
    }
  }

  async generate(event) {
    event.preventDefault();

    try {
      // Update button to show loading state
      this.buttonContainerTarget.innerHTML = `
        <button
          disabled
          class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 opacity-75 cursor-not-allowed">
          <svg class="mr-2 w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Generating...
        </button>
      `;

      // Update status to show generating state
      if (this.hasStatusTarget) {
        this.statusTarget.innerHTML = `
          <div class="flex gap-1.5 items-center">
            <div class="w-3 h-3 bg-amber-500 rounded-full animate-pulse"></div>
            <span class="text-sm font-medium text-amber-700">Generating...</span>
          </div>
        `;
      }

      // Start the content generation task
      const response = await fetch(`/api/generate-blog-content/${this.suggestionIdValue}`, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || "Generation failed");
      }

      const data = await response.json();

      // Check if the response indicates an error
      if (data.status === "error") {
        throw new Error(data.message || "Generation failed");
      }

      // Check if task was queued successfully
      if (data.status === "processing" && data.task_id) {
        // Save task info to localStorage for persistence across reloads
        const taskKey = `blog_generation_task_${this.suggestionIdValue}`;
        localStorage.setItem(taskKey, JSON.stringify({
          taskId: data.task_id,
          startTime: Date.now()
        }));

        // Show informative message to user
        showMessage(
          "Blog post generation started! We're doing extensive research which can take several minutes. We'll send you an email once it's ready.",
          "success"
        );

        // Start polling for task completion
        await this._pollTaskStatus(data.task_id);
      } else {
        throw new Error("Unexpected response status");
      }

    } catch (error) {
      showMessage(error.message || "Failed to generate content. Please try again later.", "error");
      this._resetToInitialState();
    }
  }

  async _pollTaskStatus(taskId) {
    const pollInterval = 3000; // Poll every 3 seconds
    const initialDelay = 2000; // Wait 2 seconds before first poll
    const maxAttempts = 100; // 5 minutes maximum (100 * 3 seconds)
    let attempts = 0;

    const poll = async () => {
      attempts++;

      try {
        const response = await fetch(`/api/task-status/${taskId}`, {
          headers: {
            "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value
          }
        });

        if (!response.ok) {
          throw new Error("Failed to check task status");
        }

        const statusData = await response.json();

        if (statusData.status === "completed") {
          // Success! Update UI with the generated content
          this._updateToCompletedState(statusData.blog_post_id);
          return;
        } else if (statusData.status === "failed") {
          throw new Error(statusData.message || "Content generation failed");
        } else if (statusData.status === "processing") {
          // Still processing, continue polling
          if (attempts >= maxAttempts) {
            throw new Error("Content generation is taking longer than expected. Please refresh the page to check status.");
          }

          // Update status message to show progress
          if (this.hasStatusTarget) {
            const minutes = Math.floor((attempts * pollInterval) / 60000);
            const seconds = Math.floor(((attempts * pollInterval) % 60000) / 1000);
            const timeElapsed = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

            this.statusTarget.innerHTML = `
              <div class="flex gap-1.5 items-center">
                <div class="w-3 h-3 bg-amber-500 rounded-full animate-pulse"></div>
                <span class="text-sm font-medium text-amber-700">Generating... (${timeElapsed})</span>
              </div>
            `;
          }

          // Schedule next poll
          this.pollingTimeoutId = setTimeout(poll, pollInterval);
        } else if (statusData.status === "error") {
          throw new Error(statusData.message || "Content generation encountered an error");
        }
      } catch (error) {
        showMessage(error.message || "Failed to check generation status", "error");
        this._resetToInitialState();
      }
    };

    // Wait a bit before starting to poll to allow task to be created in DB
    this.pollingTimeoutId = setTimeout(poll, initialDelay);
  }

  _updateToCompletedState(blogPostId) {
    // Clean up localStorage - task is complete
    const taskKey = `blog_generation_task_${this.suggestionIdValue}`;
    localStorage.removeItem(taskKey);

    // Update button to "View Post"
    this.buttonContainerTarget.innerHTML = `
      <a
        href="/project/${this.projectIdValue}/post/${blogPostId}/"
        class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
        <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
        </svg>
        View Post
      </a>
    `;

    // Update status to show completed state
    if (this.hasStatusTarget) {
      this.statusTarget.innerHTML = `
        <div class="flex gap-1.5 items-center">
          <div class="w-3 h-3 bg-green-500 rounded-full"></div>
          <span class="text-sm font-medium text-green-700">Generated</span>
        </div>
      `;
    }

    // Handle the post button
    this._appendPostButton(this.postButtonContainerTarget, blogPostId);

    // Show success message
    showMessage("Content generated successfully!", "success");
  }

  _resetToInitialState() {
    // Clean up localStorage - task failed or was cancelled
    const taskKey = `blog_generation_task_${this.suggestionIdValue}`;
    localStorage.removeItem(taskKey);

    // Reset the button to original state
    this.buttonContainerTarget.innerHTML = `
      <button
        data-action="generate-content#generate"
        class="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-md border border-gray-900 hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-500">
        <svg class="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
        </svg>
        Generate
      </button>
    `;

    // Reset status if available
    if (this.hasStatusTarget) {
      this.statusTarget.innerHTML = `
        <div class="flex gap-1.5 items-center">
          <div class="w-3 h-3 bg-gray-400 rounded-full"></div>
          <span class="text-sm text-gray-600">Ready to generate</span>
        </div>
      `;
    }
  }

  _appendPostButton(container, generatedPostId) {
    container.innerHTML = '';

    const profileSettingsJSON = localStorage.getItem("userProfileSettings");
    const projectSettingsJSON = localStorage.getItem(`projectSettings:${this.projectIdValue}`);

    const profileSettings = profileSettingsJSON ? JSON.parse(profileSettingsJSON) : {};
    const projectSettings = projectSettingsJSON ? JSON.parse(projectSettingsJSON) : {};

    const hasPro = profileSettings.has_pro_subscription || false;
    const hasAutoSubmit = projectSettings.has_auto_submission_setting || false;

    let buttonHtml;

    if (hasPro && hasAutoSubmit) {
      // Pro user with settings: Enabled Post button
      buttonHtml = `
        <button
          data-action="post-button#post"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-white bg-gray-800 rounded border border-gray-800 transition-colors hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-500"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
          </svg>
          Post
        </button>
      `;
    } else if (hasPro && !hasAutoSubmit) {
      // Pro user without settings: Disabled link to settings
      buttonHtml = `
        <a
          href="${this.projectSettingsUrlValue}#blogging-agent-settings"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-100 rounded border border-gray-200 transition-colors hover:bg-gray-50"
          data-controller="tooltip"
          data-tooltip-message-value="You need to set up the API endpoint for automatic posting in your project settings."
          data-action="mouseenter->tooltip#show mouseleave->tooltip#hide"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
          </svg>
          Setup
        </a>
      `;
    } else {
      // Not a pro user: Disabled link to pricing
      buttonHtml = `
        <a
          href="${this.pricingUrlValue}"
          class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-100 rounded border border-gray-200 transition-colors hover:bg-gray-50"
          data-controller="tooltip"
          data-tooltip-message-value="This feature is available for Pro subscribers only."
          data-action="mouseenter->tooltip#show mouseleave->tooltip#hide"
        >
          <svg class="mr-1 w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
          </svg>
          Pro Only
        </a>
      `;
    }

    const wrapperDiv = document.createElement('div');
    wrapperDiv.setAttribute('data-controller', 'post-button');
    wrapperDiv.setAttribute('data-post-button-generated-post-id-value', generatedPostId);
    wrapperDiv.setAttribute('data-post-button-project-id-value', this.projectIdValue);
    wrapperDiv.innerHTML = buttonHtml.trim();

    container.appendChild(wrapperDiv);
  }

  createFormGroup(id, value, label, isTextarea = false, extraClasses = "") {
    const div = document.createElement("div");
    div.setAttribute("data-controller", "copy");
    div.className = "relative" + (isTextarea ? " mb-4" : "");

    // Create label
    const labelEl = document.createElement("label");
    labelEl.className = "block text-sm font-medium text-gray-700";
    labelEl.textContent = label;

    // Create input/textarea
    const input = document.createElement(isTextarea ? "textarea" : "input");
    input.value = value;
    input.id = id;
    input.setAttribute("data-copy-target", "source");
    input.className = `block mt-1 ${isTextarea ? "mb-2" : ""} w-full font-mono text-sm rounded-md border sm:text-sm pr-20 ${extraClasses}`;
    input.readOnly = true;

    // Create copy button
    const copyButton = document.createElement("button");
    copyButton.setAttribute("data-action", "copy#copy");
    copyButton.setAttribute("data-copy-target", "button");
    copyButton.className = "absolute right-2" + (isTextarea ? " bottom-2" : " top-[30px]") + " px-3 py-1 text-sm font-semibold text-white bg-pink-600 rounded-md hover:bg-pink-700";
    copyButton.textContent = "Copy";

    // Add elements to the div
    div.appendChild(labelEl);
    div.appendChild(input);
    div.appendChild(copyButton);

    return div;
  }
}
