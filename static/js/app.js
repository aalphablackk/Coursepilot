
/**
 * CoursePilot - Shared JavaScript
 */

document.addEventListener("DOMContentLoaded", () => {
    /*
     * 1. Automatically dismiss eligible Django success messages.
     */
    document.querySelectorAll("[data-cp-autodismiss]").forEach((alert) => {
        window.setTimeout(() => {
            if (typeof bootstrap !== "undefined") {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            }
        }, 5000);
    });

    /*
     * 2. Reusable quiz navigation and progress.
     */
    function updateQuizNavigation(quiz) {
        if (!quiz) return;

        const questions = Array.from(
            quiz.querySelectorAll("[data-quiz-question]")
        );

        const currentIndex = questions.findIndex(
            (item) => !item.classList.contains("d-none")
        );

        if (!questions.length || currentIndex < 0) return;

        const currentWrapper = questions[currentIndex];
        const currentCard = currentWrapper.querySelector("[data-question]");

        const previousButton = quiz.querySelector("[data-quiz-previous]");
        const nextButton = quiz.querySelector("[data-quiz-next]");
        const counter = quiz.querySelector("[data-quiz-counter]");
        const progress = quiz.querySelector("[data-quiz-progress]");
        const score = quiz.querySelector("[data-quiz-score]");
        const result = quiz.querySelector("[data-quiz-result]");

        const isChecked =
            currentCard?.dataset.quizChecked === "true";

        const percentage = Math.round(
            ((currentIndex + 1) / questions.length) * 100
        );

        if (counter) {
            counter.textContent =
                `Question ${currentIndex + 1} of ${questions.length}`;
        }

        if (progress) {
            progress.setAttribute("aria-valuenow", String(percentage));

            const fill = progress.querySelector(".progress-bar");

            if (fill) {
                fill.style.width = `${percentage}%`;
            } else {
                progress.style.width = `${percentage}%`;
            }
        }

        if (score) {
            const correctCount = questions.filter((item) => {
                const card = item.querySelector("[data-question]");
                return card?.dataset.quizCorrect === "true";
            }).length;

            score.textContent = `${correctCount} correct`;
        }

        if (previousButton) {
            previousButton.disabled = currentIndex === 0;
        }

        if (nextButton) {
            nextButton.disabled = !isChecked;
            nextButton.textContent =
                currentIndex === questions.length - 1
                    ? "Finish quiz"
                    : "Next question";
        }

        if (result) {
            result.classList.add("d-none");
        }
    }

    function showQuizQuestion(questions, index) {
        questions.forEach((item, itemIndex) => {
            const isVisible = itemIndex === index;

            item.classList.toggle("d-none", !isVisible);
            item.setAttribute("aria-hidden", String(!isVisible));
        });
    }

    function finishQuiz(quiz, questions) {
        const correctCount = questions.filter((item) => {
            const card = item.querySelector("[data-question]");
            return card?.dataset.quizCorrect === "true";
        }).length;

        const result = quiz.querySelector("[data-quiz-result]");
        const counter = quiz.querySelector("[data-quiz-counter]");
        const progress = quiz.querySelector("[data-quiz-progress]");
        const previousButton = quiz.querySelector("[data-quiz-previous]");
        const nextButton = quiz.querySelector("[data-quiz-next]");

        if (result) {
            result.textContent =
                `Quiz complete! Your score is ${correctCount} out of ${questions.length}.`;

            result.classList.remove("d-none");
        }

        if (counter) {
            counter.textContent = "Quiz completed";
        }

        if (progress) {
            progress.setAttribute("aria-valuenow", "100");

            const fill = progress.querySelector(".progress-bar");

            if (fill) {
                fill.style.width = "100%";
            } else {
                progress.style.width = "100%";
            }
        }

        if (previousButton) {
            previousButton.disabled = true;
        }

        if (nextButton) {
            nextButton.disabled = true;
            nextButton.textContent = "Quiz completed";
        }
    }

    document.querySelectorAll("[data-lesson-quiz]").forEach((quiz) => {
        const questions = Array.from(
            quiz.querySelectorAll("[data-quiz-question]")
        );

        if (!questions.length) return;

        updateQuizNavigation(quiz);

        quiz.addEventListener("click", (event) => {
            const target = event.target;

            if (!(target instanceof Element)) return;

            const previousButton = target.closest("[data-quiz-previous]");
            const nextButton = target.closest("[data-quiz-next]");

            if (!previousButton && !nextButton) return;

            const currentIndex = questions.findIndex(
                (item) => !item.classList.contains("d-none")
            );

            if (currentIndex < 0) return;

            if (previousButton) {
                if (currentIndex === 0) return;

                showQuizQuestion(questions, currentIndex - 1);
                updateQuizNavigation(quiz);
                return;
            }

            const currentCard = questions[currentIndex].querySelector(
                "[data-question]"
            );

            if (currentCard?.dataset.quizChecked !== "true") return;

            if (currentIndex < questions.length - 1) {
                showQuizQuestion(questions, currentIndex + 1);
                updateQuizNavigation(quiz);
                return;
            }

            finishQuiz(quiz, questions);
        });
    });

    /*
     * 3. Question interactions: hints, answer checking and feedback.
     */
    document.addEventListener("click", (event) => {
        const target = event.target;

        if (!(target instanceof Element)) return;

        const hintButton = target.closest("[data-show-hint]");
        const checkButton = target.closest("[data-check-answer]");

        if (hintButton) {
            const question = hintButton.closest("[data-question]");

            question
                ?.querySelector("[data-hint]")
                ?.classList.remove("d-none");

            return;
        }

        if (!checkButton) return;

        const question = checkButton.closest("[data-question]");

        if (!question) return;

        const feedback = question.querySelector("[data-feedback]");
        const explanation = question.querySelector("[data-explanation]");
        const selected = question.querySelector(
            'input[type="radio"]:checked'
        );
        const shortAnswer = question.querySelector("[data-short-answer]");

        if (!feedback) return;

        const response = (
            selected?.value ??
            shortAnswer?.value ??
            ""
        ).trim();

        if (!response) {
            feedback.className = "alert alert-warning mt-3";
            feedback.textContent =
                "Please enter or select an answer first.";
            return;
        }

        const expected = (
            question.dataset.correctAnswer ?? ""
        ).trim();

        if (!expected) {
            feedback.className = "alert alert-info mt-3";
            feedback.textContent =
                "Your response is recorded on this page, but an answer key is not available for automatic checking.";

            question.dataset.quizChecked = "true";
            question.dataset.quizCorrect = "false";

            updateQuizNavigation(
                question.closest("[data-lesson-quiz]")
            );

            return;
        }

        const correct = response.localeCompare(expected, undefined, {
            sensitivity: "accent"
        }) === 0;

        feedback.className = correct
            ? "alert alert-success mt-3"
            : "alert alert-danger mt-3";

        feedback.textContent = correct
            ? "Correct! Well done."
            : "Not quite. Review your answer and try again.";

        explanation?.classList.remove("d-none");

        question.dataset.quizChecked = "true";
        question.dataset.quizCorrect = String(correct);

        if (correct) {
            checkButton.disabled = true;
        }

        updateQuizNavigation(
            question.closest("[data-lesson-quiz]")
        );
    });

    /*
     * 4. Reset quiz validation when the learner changes an answer.
     * The learner must check the new answer before proceeding.
     */
    document.addEventListener("change", (event) => {
        const target = event.target;

        if (!(target instanceof Element)) return;

        if (
            !target.matches(
                'input[type="radio"], [data-short-answer]'
            )
        ) {
            return;
        }

        const question = target.closest("[data-question]");

        if (!question) return;

        const checkButton = question.querySelector("[data-check-answer]");
        const feedback = question.querySelector("[data-feedback]");
        const explanation = question.querySelector("[data-explanation]");

        question.dataset.quizChecked = "false";
        question.dataset.quizCorrect = "false";

        if (checkButton) {
            checkButton.disabled = false;
        }

        if (feedback) {
            feedback.className = "d-none";
            feedback.textContent = "";
        }

        explanation?.classList.add("d-none");

        updateQuizNavigation(
            question.closest("[data-lesson-quiz]")
        );
    });

    /*
     * 5. Paginated lesson player and connected sidebar.
     */
    const player = document.getElementById("coursePlayer");

    if (!player) return;

    const sidebar = document.getElementById("lessonNavigator");

    const steps = Array.from(
        player.querySelectorAll("[data-player-step]")
    );

    const previous = document.getElementById("playerPrevious");
    const next = document.getElementById("playerNext");
    const stepLabel = document.getElementById("playerStepLabel");

    const playerProgress = document.getElementById("playerProgress");
    const playerProgressFill = document.getElementById(
        "playerProgressFill"
    );

    const sidebarLinks = sidebar
        ? Array.from(sidebar.querySelectorAll("[data-lesson-link]"))
        : [];

    const sidebarProgress = document.getElementById("lessonProgressBar");
    const sidebarProgressFill = document.getElementById(
        "lessonProgressFill"
    );
    const sidebarProgressText = document.getElementById(
        "lessonProgressText"
    );

    if (steps.length === 0) {
        if (previous) previous.disabled = true;
        if (next) next.disabled = true;
        return;
    }

    let currentStep = 0;

    function updateProgress(percentage) {
        if (playerProgress) {
            playerProgress.setAttribute(
                "aria-valuenow",
                String(percentage)
            );
        }

        if (playerProgressFill) {
            playerProgressFill.style.width = `${percentage}%`;
        }

        if (sidebarProgress) {
            sidebarProgress.setAttribute(
                "aria-valuenow",
                String(percentage)
            );
        }

        if (sidebarProgressFill) {
            sidebarProgressFill.style.width = `${percentage}%`;
        }

        if (sidebarProgressText) {
            sidebarProgressText.textContent = `${percentage}%`;
        }
    }

    function updateSidebar() {
        sidebarLinks.forEach((link) => {
            const linkIndex = Number(link.dataset.playerIndex);
            const isActive = linkIndex === currentStep;

            link.classList.toggle("active", isActive);

            if (isActive) {
                link.setAttribute("aria-current", "step");
            } else {
                link.removeAttribute("aria-current");
            }
        });

        const activeLink = sidebarLinks.find(
            (link) => Number(link.dataset.playerIndex) === currentStep
        );

        const scrollContainer = document.getElementById(
            "lessonContentsPanel"
        );

        if (
            activeLink &&
            scrollContainer &&
            scrollContainer.classList.contains("show")
        ) {
            const linkTop = activeLink.offsetTop;
            const linkBottom = linkTop + activeLink.offsetHeight;
            const visibleTop = scrollContainer.scrollTop;
            const visibleBottom =
                visibleTop + scrollContainer.clientHeight;

            if (linkTop < visibleTop) {
                scrollContainer.scrollTop = linkTop;
            } else if (linkBottom > visibleBottom) {
                scrollContainer.scrollTop =
                    linkBottom - scrollContainer.clientHeight;
            }
        }
    }

    function renderStep() {
        steps.forEach((step, index) => {
            const isVisible = index === currentStep;

            step.classList.toggle("d-none", !isVisible);
            step.setAttribute("aria-hidden", String(!isVisible));
        });

        const percentage = Math.round(
            ((currentStep + 1) / steps.length) * 100
        );

        if (stepLabel) {
            stepLabel.textContent =
                `Step ${currentStep + 1} of ${steps.length}`;
        }

        updateProgress(percentage);
        updateSidebar();

        if (previous) {
            previous.disabled = currentStep === 0;
        }

        if (next) {
            const isLastStep = currentStep === steps.length - 1;

            next.textContent = isLastStep
                ? "Restart lesson"
                : "Continue";

            next.classList.toggle("btn-success", isLastStep);
            next.classList.toggle("btn-primary", !isLastStep);

            next.disabled = false;
        }
    }

    function goToStep(index, shouldScroll = true) {
        if (!Number.isInteger(index)) return;
        if (index < 0 || index >= steps.length) return;

        currentStep = index;
        renderStep();

        if (shouldScroll) {
            player.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }
    }

    previous?.addEventListener("click", () => {
        goToStep(currentStep - 1);
    });

    next?.addEventListener("click", () => {
        const isLastStep = currentStep === steps.length - 1;

        goToStep(isLastStep ? 0 : currentStep + 1);
    });

    sidebarLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            event.preventDefault();

            const index = Number(link.dataset.playerIndex);

            goToStep(index);
        });
    });

    // Initialize the player and progress displays.
    renderStep();
});
// Randomize multiple-choice options once when the page loads.
document.querySelectorAll("[data-question]").forEach((question) => {
    const optionsContainer = question.querySelector(".d-grid");

    if (!optionsContainer) return;

    const options = Array.from(optionsContainer.children);

    // Fisher-Yates shuffle
    for (let i = options.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));

        [options[i], options[j]] = [options[j], options[i]];
    }

    // Reorder existing labels without changing their values.
    options.forEach((option) => {
        optionsContainer.appendChild(option);
    });
});

