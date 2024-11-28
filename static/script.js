$(document).ready(function () {
    const usernameInput = $("#twitter-username");
    const startBtn = $("#start-btn");
    const scrambledHintEl = $("#scrambled-hint");
    const userAnswerEl = $("#user-answer");
    const hintBtn = $("#hint-btn");
    const submitBtn = $("#submit-btn");
    const resultMessageEl = $("#result-message");
    const totalScoreEl = $("#total-score");
    const hintsContainer = $("#hints-container span");
    const quizArea = $("#quiz-area");
    const userInputDiv = $("#user-input");
    const questionsRemainingEl = $("#questions-remaining");
    const leaderboardDiv = $("#leaderboard");
    const leaderboardList = $("#leaderboard-list");
    const timerEl = $("#timer");

    let currentQuestionId = null;
    let hintIndex = 0;
    let startTime = null;
    let timerInterval = null;
    let sessionId = null;

    // Start Quiz
    startBtn.on("click", async function () {
        const username = usernameInput.val().trim();
        if (!username) {
            alert("Please enter your Twitter username.");
            return;
        }

        const response = await $.ajax({
            url: "/start_quiz",
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ username })
        });

        sessionId = response.session_id;

        startTime = new Date();
        startTimer();

        loadNextQuestion();

        userInputDiv.hide();
        quizArea.removeClass("d-none");
    });

    // Timer
    function startTimer() {
        timerInterval = setInterval(() => {
            const elapsedTime = Math.floor((new Date() - startTime) / 1000);
            const hours = String(Math.floor(elapsedTime / 3600)).padStart(2, "0");
            const minutes = String(Math.floor((elapsedTime % 3600) / 60)).padStart(2, "0");
            const seconds = String(elapsedTime % 60).padStart(2, "0");
            timerEl.text(`Time: ${hours}:${minutes}:${seconds}`);
        }, 1000);
    }

    // Load Next Question
    async function loadNextQuestion() {
        const data = await $.get(`/get_question/${sessionId}`);
        if (data.status === "end") {
            alert(`🎉 Quiz complete! Your final score: ${totalScoreEl.text()}`);
            stopTimer();
            await endQuiz();
            showLeaderboard();  // Automatically show leaderboard
            return;
        }
    
        // Randomize question background color
        const colors = ["#fce4ec", "#e8f5e9", "#e3f2fd", "#fff3e0", "#f3e5f5"];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        $("#question-container").css("background-color", randomColor);
    
        // Animate question transition
        scrambledHintEl.addClass("animate__animated animate__fadeOut");
        setTimeout(() => {
            scrambledHintEl.text(data.scrambled_hint).removeClass("animate__fadeOut").addClass("animate__fadeIn");
        }, 500);
    
        currentQuestionId = data.id;
        resultMessageEl.text("");
        userAnswerEl.val("");
        hintIndex = 0;
    
        // Reset hints display
        hintsContainer.empty();
        hintsContainer.append(
            `<span id="hint1" class="badge bg-light text-dark p-2">Hints are on their way!!</span>`
        );
    
        questionsRemainingEl.text(`Questions Remaining: ${data.questions_remaining}`);
    }
    
    async function endQuiz() {
        await $.post(`/end_quiz/${sessionId}`);
        showLeaderboard();  // Automatically show leaderboard
    }
    

    // Stop Timer
    function stopTimer() {
        clearInterval(timerInterval);
    }

    // Show Hint
    hintBtn.on("click", async function () {
        const data = await $.get(`/get_hint/${sessionId}`);
        if (data.status === "error") {
            resultMessageEl.text(data.message).addClass("text-danger");
        } else {
            if (hintIndex === 0) hintsContainer.empty(); // Clear "Hints are on their way!!" text

            hintsContainer.append(
                `<span id="hint${hintIndex + 1}" class="badge bg-warning text-dark p-2 mx-2">${data.hint}</span>`
            );
            hintIndex++;
        }
    });

    // Submit Answer
    submitBtn.on("click", async function () {
        const userAnswer = userAnswerEl.val().trim();
        if (!userAnswer) {
            alert("Enter your guess!");
            return;
        }

        const response = await $.ajax({
            url: `/validate/${sessionId}`,
            method: "POST",
            contentType: "application/json",
            data: JSON.stringify({ id: currentQuestionId, answer: userAnswer })
        });

        resultMessageEl.text(response.message);

        if (response.total_score !== undefined) {
            totalScoreEl.text(`Total Score: ${response.total_score}`);
        }

        if (response.status === "correct" || response.status === "failed" || response.status === "end") {
            loadNextQuestion();
        }
    });

    async function endQuiz() {
        await $.post(`/end_quiz/${sessionId}`);
    }

    async function showLeaderboard() {
        const response = await $.get("/get_leaderboard");
        leaderboardDiv.removeClass("d-none");
        leaderboardList.empty();

        response.forEach((entry) => {
            leaderboardList.append(
                `<li class="list-group-item d-flex justify-content-between align-items-center">
                    <span><strong>${entry.username}</strong></span>
                    <span>${entry.final_score} points</span>
                    <span>Hints: ${entry.hints_used}</span>
                    <span>Attempts: ${entry.wrong_attempts}</span>
                    <span>Time: ${(entry.time_taken / 1000).toFixed(2)} sec</span>
                </li>`
            );
        });

        leaderboardDiv.addClass("animate__animated animate__fadeIn");
    }
});
