from flask import Flask, render_template, request, jsonify
import pandas as pd
import random
import uuid
import logging
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read environment variables
LEADERBOARD_FILE = os.getenv('LEADERBOARD_FILE', 'leaderboard.csv')
MOVIES_FILE = os.getenv('MOVIES_FILE', 'movies.csv')
PORT = int(os.getenv('PORT', 5000))

app = Flask(__name__)

# Configure logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load movie data from the CSV
try:
    movies_df = pd.read_csv(MOVIES_FILE)
except FileNotFoundError:
    logging.error(f"The '{MOVIES_FILE}' file is missing. Make sure the file is available.")
    raise FileNotFoundError(f"The '{MOVIES_FILE}' file is missing.")

# Ensure leaderboard file exists
try:
    pd.read_csv(LEADERBOARD_FILE)
except FileNotFoundError:
    pd.DataFrame(columns=["username", "final_score", "hints_used", "wrong_attempts", "time_taken"]).to_csv(LEADERBOARD_FILE, index=False)

# Session storage (to hold session-specific data for each user)
session_store = {}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    data = request.get_json()  # Parse JSON data
    username = data.get("username", "").strip()

    if not username:
        return jsonify({"status": "error", "message": "Username is required"}), 400

    session_id = str(uuid.uuid4())  # Generate a unique session ID

    # Initialize session data
    session_store[session_id] = {
        "username": username,
        "total_score": 0,
        "questions_answered": 0,
        "used_hints": 0,
        "wrong_attempts": 0,
        "remaining_hints": 5,
        "current_hint_index": 0,
        "hints_list": [],
        "seen_ids": [],
        "start_time": int(time.time() * 1000)  # Start time in milliseconds
    }

    logging.info(f"New quiz started by user: {username}, session ID: {session_id}")
    return jsonify({"message": "Quiz started!", "session_id": session_id})


@app.route('/get_question/<session_id>', methods=['GET'])
def get_question(session_id):
    session_data = session_store.get(session_id)

    if not session_data:
        return jsonify({"status": "error", "message": "Invalid session ID!"}), 400

    if session_data["questions_answered"] >= 10:
        return jsonify({"status": "end", "message": "Quiz completed!"})

    seen_ids = session_data["seen_ids"]
    available_questions = movies_df[~movies_df["id"].isin(seen_ids)]

    if available_questions.empty:
        return jsonify({"status": "end", "message": "No more unique questions available!"})

    # Reset hints, attempts, and scoring fields for each new question
    new_question = available_questions.sample(1).iloc[0].to_dict()
    session_data.update({
        "current_question": new_question,
        "seen_ids": session_data["seen_ids"] + [new_question["id"]],
        "remaining_hints": 5,
        "used_hints": 0,
        "wrong_attempts": 0,
        "current_hint_index": 0,
        "hints_list": [
            f"Category: {new_question['category']}",
            f"Director: {new_question['director_name']}",
            f"Genre: {new_question['genre']}",
            f"Lead Actor: {new_question['lead_actor']}",
            f"Answer: {new_question['original_title']}"  # Final answer as the last hint
        ]
    })

    return jsonify({
        "status": "question",
        "scrambled_hint": new_question["scrambled_hint"],
        "id": new_question["id"],
        "questions_remaining": 10 - session_data["questions_answered"]
    })

@app.route('/get_hint/<session_id>', methods=['GET'])
def get_hint(session_id):
    session_data = session_store.get(session_id)

    if not session_data:
        return jsonify({"status": "error", "message": "Invalid session ID!"}), 400

    if not session_data["current_question"]:
        return jsonify({"status": "error", "message": "No active question!"}), 400

    if session_data["remaining_hints"] <= 0:
        return jsonify({"status": "error", "message": "No hints left!"})

    index = session_data["current_hint_index"]
    hint_value = session_data["hints_list"][index]

    # Update hints usage for the current question
    session_data.update({
        "used_hints": session_data["used_hints"] + 1,
        "current_hint_index": index + 1,
        "remaining_hints": session_data["remaining_hints"] - 1
    })

    return jsonify({
        "status": "success",
        "hint": hint_value,
        "hints_left": session_data["remaining_hints"]
    })

@app.route('/validate/<session_id>', methods=['POST'])
def validate(session_id):
    session_data = session_store.get(session_id)

    if not session_data:
        return jsonify({"status": "error", "message": "Invalid session ID!"}), 400

    data = request.get_json()
    movie_id = data.get("id")
    user_answer = data.get("answer", "").strip().upper()

    question = session_data["current_question"]
    if not question or question["id"] != movie_id:
        return jsonify({
            "status": "error",
            "message": "Invalid question ID!",
            "total_score": session_data["total_score"]
        }), 400

    correct_answer = question["original_title"].strip().upper()

    if user_answer == correct_answer:
        # Calculate score deduction based on the hints used in the current question
        question_score = max(0, 10 - (2 * session_data["used_hints"]))
        session_data.update({
            "total_score": session_data["total_score"] + question_score,
            "questions_answered": session_data["questions_answered"] + 1
        })

        if session_data["questions_answered"] >= 10:
            return jsonify({
                "status": "end",
                "message": f"Correct! You earned {question_score} points. Quiz completed! 🎉",
                "total_score": session_data["total_score"],
                "show_leaderboard": True
            })

        return jsonify({
            "status": "correct",
            "message": f"Correct! You earned {question_score} points. 👏",
            "total_score": session_data["total_score"]
        })

    # Increment wrong attempts for the current question
    session_data["wrong_attempts"] += 1
    if session_data["wrong_attempts"] >= 5:
        session_data["questions_answered"] += 1
        if session_data["questions_answered"] >= 10:
            return jsonify({
                "status": "end",
                "message": f"Too many wrong attempts! The correct answer was '{correct_answer}'. Quiz completed! 🤷",
                "total_score": session_data["total_score"],
                "show_leaderboard": True
            })

        return jsonify({
            "status": "failed",
            "message": f"Too many wrong attempts! The correct answer was '{correct_answer}'. Moving to the next question. 🤦",
            "total_score": session_data["total_score"]
        })

    return jsonify({
        "status": "incorrect",
        "message": "Wrong guess! Try again. 🤔",
        "total_score": session_data["total_score"]
    })

@app.route('/end_quiz/<session_id>', methods=['POST'])
def end_quiz(session_id):
    session_data = session_store.get(session_id)

    if not session_data:
        return jsonify({"status": "error", "message": "Invalid session ID!"}), 400

    username = session_data["username"]
    end_time = int(time.time() * 1000)  # End time in milliseconds
    total_time = end_time - session_data["start_time"]

    leaderboard = pd.read_csv(LEADERBOARD_FILE)
    new_entry = pd.DataFrame([{
        "username": username,
        "final_score": session_data["total_score"],
        "hints_used": session_data["used_hints"],
        "wrong_attempts": session_data["wrong_attempts"],
        "time_taken": total_time
    }])
    leaderboard = pd.concat([leaderboard, new_entry], ignore_index=True)
    leaderboard.to_csv(LEADERBOARD_FILE, index=False)

    logging.info(f"Quiz ended for user: {username}, session ID: {session_id}")
    return jsonify({"status": "success", "message": "Leaderboard updated!", "time_taken": total_time})

@app.route('/get_leaderboard', methods=['GET'])
def get_leaderboard():
    leaderboard = pd.read_csv(LEADERBOARD_FILE)
    leaderboard = leaderboard.sort_values(by=["final_score", "time_taken"], ascending=[False, True]).to_dict(orient="records")
    return jsonify(leaderboard)


# # if __name__ == '__main__':
#     # Production settings
#     from waitress import serve
#     serve(app, host='0.0.0.0', port=PORT)
