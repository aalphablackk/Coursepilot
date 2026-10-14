
/**
 * CoursePilot — Shared JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
    // Automatically dismiss eligible Django success messages.
    document.querySelectorAll("[data-cp-autodismiss]").forEach((alert) => {
        window.setTimeout(() => {
            if (typeof bootstrap !== "undefined") {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        }, 5000);
    });
});
