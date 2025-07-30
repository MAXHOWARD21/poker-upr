from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
from typing import List, Dict, Optional
import uuid
from datetime import datetime
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

PLAYER_DATA_FILE = 'players.json'
ACCOUNTS_DATA_FILE = 'accounts.json'


class Player:

    def __init__(self, user_id: str, rating: float = 2.0):
        self.user_id = user_id
        self.rating = rating
        self.sessions_played = 0
        self.total_profit = 0.0
        self.total_hours_played = 0.0
        self.uncertainty = 2.0  # Higher uncertainty for new players
        self.session_history = []  # Store recent session data
        self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'rating': self.rating,
            'sessions_played': self.sessions_played,
            'total_profit': self.total_profit,
            'total_hours_played': self.total_hours_played,
            'uncertainty': self.uncertainty,
            'session_history':
            self.session_history[-20:],  # Keep only last 20 sessions
            'created_at': self.created_at
        }

    @staticmethod
    def from_dict(data):
        player = Player(data['user_id'], data.get('rating', 2.0))
        player.sessions_played = data.get('sessions_played', 0)
        player.total_profit = data.get('total_profit', 0.0)
        player.total_hours_played = data.get('total_hours_played', 0.0)
        player.uncertainty = data.get('uncertainty', 2.0)
        player.session_history = data.get('session_history', [])
        player.created_at = data.get('created_at', datetime.now().isoformat())
        return player


class Account:

    def __init__(self,
                 user_id: str,
                 email: str,
                 password_hash: str,
                 first_name: str,
                 last_name: str,
                 username: str,
                 experience_level: str = 'average_home',
                 verified: bool = False,
                 verification_token: str = None):
        self.user_id = user_id
        self.email = email
        self.password_hash = password_hash
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.experience_level = experience_level
        self.created_at = datetime.now().isoformat()
        self.verified = verified
        self.verification_token = verification_token

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'email': self.email,
            'password_hash': self.password_hash,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'username': self.username,
            'experience_level': self.experience_level,
            'created_at': self.created_at,
            'verified': self.verified,
            'verification_token': self.verification_token
        }

    @staticmethod
    def from_dict(data):
        account = Account(data['user_id'], data['email'],
                          data['password_hash'], data.get('first_name', ''),
                          data.get('last_name', ''), data.get('username', ''),
                          data.get('experience_level', 'average_home'),
                          data.get('verified', False),
                          data.get('verification_token', None))
        account.created_at = data.get('created_at', datetime.now().isoformat())
        return account

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash"""
        return self.password_hash == self._hash_password(password)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()


class PlayerDatabase:

    def __init__(self, filename=PLAYER_DATA_FILE):
        self.filename = filename
        self.players: Dict[str, Player] = self.load_players()

    def load_players(self) -> Dict[str, Player]:
        if not os.path.exists(self.filename):
            return {}
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                return {p['user_id']: Player.from_dict(p) for p in data}
        except:
            return {}

    def save_players(self):
        with open(self.filename, 'w') as f:
            json.dump([p.to_dict() for p in self.players.values()],
                      f,
                      indent=2)

    def get_player(self, user_id: str, starting_rating: float = 2.0) -> Player:
        if user_id not in self.players:
            self.players[user_id] = Player(user_id, starting_rating)
            self.save_players()
        return self.players[user_id]

    def update_player(self, player: Player):
        self.players[player.user_id] = player
        self.save_players()


class AccountDatabase:

    def __init__(self, filename=ACCOUNTS_DATA_FILE):
        self.filename = filename
        self.accounts: Dict[str, Account] = self.load_accounts()

    def load_accounts(self) -> Dict[str, Account]:
        if not os.path.exists(self.filename):
            return {}
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                return {a['user_id']: Account.from_dict(a) for a in data}
        except:
            return {}

    def save_accounts(self):
        with open(self.filename, 'w') as f:
            json.dump([a.to_dict() for a in self.accounts.values()],
                      f,
                      indent=2)

    def create_account(self, email: str, password: str, first_name: str,
                       last_name: str, username: str,
                       experience_level: str) -> str:
        # Check if email already exists
        if self.get_account_by_email(email):
            raise ValueError("Email already exists")

        # Check if username already exists
        if self.get_account_by_username(username):
            raise ValueError("Username already exists")

        user_id = str(uuid.uuid4())
        password_hash = Account._hash_password(password)
        verification_token = secrets.token_urlsafe(32)
        account = Account(user_id, email, password_hash, first_name, last_name,
                          username, experience_level, False,
                          verification_token)
        self.accounts[user_id] = account
        self.save_accounts()
        return user_id

    def get_account(self, user_id: str) -> Optional[Account]:
        return self.accounts.get(user_id)

    def get_account_by_email(self, email: str) -> Optional[Account]:
        for account in self.accounts.values():
            if account.email == email:
                return account
        return None

    def get_account_by_username(self, username: str) -> Optional[Account]:
        for account in self.accounts.values():
            if account.username == username:
                return account
        return None

    def get_account_by_verification_token(self,
                                          token: str) -> Optional[Account]:
        for account in self.accounts.values():
            if account.verification_token == token:
                return account
        return None

    def verify_account(self, token: str) -> bool:
        account = self.get_account_by_verification_token(token)
        if account:
            account.verified = True
            account.verification_token = None
            self.save_accounts()
            return True
        return False


class Session:

    def __init__(self, player_ids: List[str], buyins: List[float],
                 cashouts: List[float], blind_size: float,
                 duration_hours: List[float]):
        self.player_ids = player_ids
        self.buyins = buyins
        self.cashouts = cashouts
        self.blind_size = blind_size
        self.duration_hours = duration_hours
        self.results = [c - b for b, c in zip(buyins, cashouts)]
        self.hourly_results = [
            r / d for r, d in zip(self.results, duration_hours) if d > 0
        ]

    def get_results(self):
        return dict(zip(self.player_ids, self.results))

    def get_hourly_results(self):
        return dict(zip(self.player_ids, self.hourly_results))


def update_uncertainty_for_inactivity(player: Player):
    """Increase uncertainty by 0.1 for each month of inactivity"""
    from datetime import datetime, timedelta

    if not player.session_history:
        return

    # Get the last session timestamp
    last_session_str = player.session_history[-1]['timestamp']
    last_session = datetime.fromisoformat(last_session_str)
    current_time = datetime.now()

    # Calculate months since last session
    time_diff = current_time - last_session
    months_inactive = time_diff.days // 30

    if months_inactive >= 1:
        uncertainty_increase = months_inactive * 0.1
        player.uncertainty = min(2.0,
                                 player.uncertainty + uncertainty_increase)


def update_player_upr(player: Player,
                      net_bb: float,
                      session_hours: float,
                      opponent_avg_upr: float,
                      opponent_hours_weighted_avg: float = None):
    """Enhanced UPR update with uncertainty-based volatility and rating difference scaling"""
    import math

    MAX_UNCERTAINTY = 2.0
    MIN_UNCERTAINTY = 0.1

    if session_hours < 0.5:
        return

    # Check for monthly inactivity and increase uncertainty
    update_uncertainty_for_inactivity(player)

    # Use hours-weighted opponent average if available
    effective_opponent_avg = opponent_hours_weighted_avg if opponent_hours_weighted_avg else opponent_avg_upr

    # Calculate the buy-ins won/lost (100bb = 1 buy-in)
    buyins_won = net_bb / 100.0

    # Rating difference between player and opponents
    rating_diff = player.rating - effective_opponent_avg

    # Base K-factor based on uncertainty
    # New players (uncertainty 2.0): base_k = 1.0
    # Experienced players (uncertainty < 0.5): base_k = 0.1
    if player.uncertainty >= 2.0:
        base_k = 1.0
    elif player.uncertainty <= 0.5:
        base_k = 0.1
    else:
        # Linear interpolation between 0.1 and 1.0
        base_k = 0.1 + (player.uncertainty - 0.5) / 1.5 * 0.9

    # Rating difference multiplier - bigger rewards for upsets
    if rating_diff <= 0:  # Player is underdog or equal
        if rating_diff == 0:
            rating_multiplier = 1.0
        elif rating_diff >= -2:
            rating_multiplier = 1.0 + abs(
                rating_diff) * 0.5  # Up to 2x for 2 point underdog
        else:  # More than 2 points underdog
            rating_multiplier = 2.0 + (abs(rating_diff) -
                                       2) * 0.25  # Diminishing returns
    else:  # Player is favorite
        rating_multiplier = max(0.5, 1.0 -
                                rating_diff * 0.1)  # Reduced gains, min 0.5x

    # Performance multiplier based on buy-ins won
    # Multiple buy-ins have diminishing returns to prevent extreme swings
    if buyins_won >= 0:
        performance_multiplier = math.sqrt(
            abs(buyins_won)) if buyins_won > 0 else 0
    else:
        performance_multiplier = -math.sqrt(abs(buyins_won))

    # Session length bonus (longer sessions are slightly more reliable)
    session_multiplier = min(1.2, 1.0 + (session_hours - 1) * 0.1)

    # Calculate final delta
    final_delta = base_k * buyins_won * rating_multiplier * session_multiplier

    # Safety caps for extreme cases only (should rarely trigger with proper algorithm)
    max_single_change = 10.0  # Extreme cap for statistical anomalies
    final_delta = max(min(final_delta, max_single_change), -max_single_change)

    # Update rating with safety bounds
    new_rating = player.rating + final_delta
    player.rating = max(min(new_rating, 16, 50),
                        1.0)  # Keep ratings in reasonable bounds

    # Update uncertainty (decreases with more sessions)
    uncertainty_decay = 0.95  # Gradual decay
    new_uncertainty = player.uncertainty * uncertainty_decay
    player.uncertainty = max(MIN_UNCERTAINTY, new_uncertainty)

    # Store session data for history
    session_data = {
        'net_bb': net_bb,
        'hours': session_hours,
        'opponent_avg_upr': effective_opponent_avg,
        'rating_before': player.rating - final_delta,
        'rating_after': player.rating,
        'timestamp': datetime.now().isoformat()
    }
    player.session_history.append(session_data)

    # Keep only last 20 sessions
    if len(player.session_history) > 20:
        player.session_history = player.session_history[-20:]

    player.sessions_played += 1
    player.total_hours_played += session_hours


def process_session(session: Session, player_db: PlayerDatabase):
    """Process a session by updating each player's UPR with enhanced algorithm"""
    all_players = [
        player_db.get_player(user_id) for user_id in session.player_ids
    ]

    for i, user_id in enumerate(session.player_ids):
        player = player_db.get_player(user_id)
        profit_dollars = session.results[i]
        net_bb = profit_dollars / session.blind_size
        session_hours = session.duration_hours[i]

        # Get opponents and their session hours
        opponents = [(p, session.duration_hours[j])
                     for j, p in enumerate(all_players) if j != i]

        if opponents:
            # Simple average
            opponent_avg_upr = sum(p.rating
                                   for p, _ in opponents) / len(opponents)

            # Hours-weighted average (more accurate)
            total_opponent_hours = sum(hours for _, hours in opponents)
            if total_opponent_hours > 0:
                opponent_hours_weighted_avg = sum(
                    p.rating * hours
                    for p, hours in opponents) / total_opponent_hours
            else:
                opponent_hours_weighted_avg = opponent_avg_upr
        else:
            opponent_avg_upr = player.rating
            opponent_hours_weighted_avg = player.rating

        update_player_upr(player, net_bb, session_hours, opponent_avg_upr,
                          opponent_hours_weighted_avg)
        player.total_profit += profit_dollars
        player_db.update_player(player)


def send_verification_email(email, first_name, verification_token):
    verify_url = f"http://localhost:5000/verify/{verification_token}"
    print(
        f"\n[DEV] Verification email for {email} ({first_name}): {verify_url}\n"
    )


# Load GTO questions
def load_gto_questions():
    try:
        with open('gto_questions.json', 'r') as f:
            return json.load(f)
    except:
        return []


gto_questions = load_gto_questions()

# Initialize databases
player_db = PlayerDatabase()
account_db = AccountDatabase()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Validate password confirmation
        if password != confirm_password:
            flash('Passwords do not match!')
            return render_template('register.html')

        # Validate password length
        if len(password) < 8:
            flash('Password must be at least 8 characters long!')
            return render_template('register.html')

        try:
            user_id = account_db.create_account(email, password, first_name,
                                                last_name, username, 'pending')
            # Store user_id in session for quiz
            session['pending_user_id'] = user_id
            return redirect(url_for('gto_quiz'))
        except ValueError as e:
            flash(str(e))
            return render_template('register.html')

    return render_template('register.html')


@app.route('/gto-quiz', methods=['GET', 'POST'])
def gto_quiz():
    if 'pending_user_id' not in session:
        return redirect(url_for('register'))

    user_id = session['pending_user_id']

    if request.method == 'POST':
        answer = int(request.form.get('answer', -1))
        current_question = int(request.form.get('current_question', 1))

        # Store the answer
        if 'quiz_answers' not in session:
            session['quiz_answers'] = []
        session['quiz_answers'].append(answer)
        session.modified = True  # Ensure session is saved

        if current_question >= 10:
            # Quiz completed, calculate rating
            return redirect(url_for('quiz_results'))
        else:
            # Continue to next question
            return redirect(url_for('gto_quiz'))

    # GET request - show current question
    current_question = len(session.get('quiz_answers', [])) + 1

    if current_question > 10:
        return redirect(url_for('quiz_results'))

    # Get random question
    if 'quiz_questions' not in session:
        session['quiz_questions'] = random.sample(gto_questions, 10)

    question = session['quiz_questions'][current_question - 1]

    return render_template('gto_quiz.html',
                           question=question,
                           current_question=current_question)


@app.route('/quiz-results')
def quiz_results():
    if 'pending_user_id' not in session or 'quiz_answers' not in session:
        return redirect(url_for('register'))

    user_id = session['pending_user_id']
    answers = session['quiz_answers']
    questions = session['quiz_questions']

    if len(answers) != 10:
        return redirect(url_for('gto_quiz'))

    # Calculate correct answers
    correct = 0
    for i, answer in enumerate(answers):
        if answer == questions[i]['correct']:
            correct += 1

    # Determine starting rating based on correct answers
    if correct <= 2:
        experience_level = 'losing_home'
        starting_rating = 1.0
    elif correct <= 4:
        experience_level = 'average_home'
        starting_rating = 2.5
    elif correct <= 6:
        experience_level = 'winning_home'
        starting_rating = 5.0
    elif correct == 7:
        experience_level = 'average_casino'
        starting_rating = 4.5
    elif correct <= 9:
        experience_level = 'winning_casino'
        starting_rating = 6.5
    else:  # 10 correct
        experience_level = 'professional'
        starting_rating = 10.0

    # Update account with experience level and create player
    account = account_db.get_account(user_id)
    if account:
        account.experience_level = experience_level
        account_db.save_accounts()
        player_db.get_player(user_id, starting_rating)

        # Send verification email
        send_verification_email(account.email, account.first_name,
                                account.verification_token)

        # Clear session data
        session.pop('pending_user_id', None)
        session.pop('quiz_answers', None)
        session.pop('quiz_questions', None)

        flash(
            f'Quiz completed! You got {correct}/10 correct. Your starting rating is {starting_rating}. Please check your email to verify your account.'
        )
        return redirect(url_for('login'))

    return redirect(url_for('register'))


@app.route('/verify/<token>')
def verify(token):
    if account_db.verify_account(token):
        flash('Email verified! You can now log in.')
        return redirect(url_for('login'))
    else:
        flash('Invalid or expired verification link.')
        return redirect(url_for('register'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        account = account_db.get_account_by_email(email)

        if account and account.check_password(password):
            if not getattr(account, 'verified', False):
                flash('Please verify your email before logging in.')
                return render_template('login.html')
            session['user_id'] = account.user_id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    account = account_db.get_account(user_id)
    player = player_db.get_player(user_id)

    # Get all players for rankings
    all_players = list(player_db.players.values())
    all_players.sort(key=lambda p: p.rating, reverse=True)

    # Find user's rank
    user_rank = next(
        (i + 1 for i, p in enumerate(all_players) if p.user_id == user_id),
        None)

    # Calculate recent performance trend (last 5 sessions)
    recent_trend = "N/A"
    if len(player.session_history) >= 2:
        recent_sessions = player.session_history[-5:]
        if len(recent_sessions) >= 2:
            rating_change = recent_sessions[-1][
                'rating_after'] - recent_sessions[0]['rating_before']
            recent_trend = f"{rating_change:+.2f}" if rating_change != 0 else "0.00"

    return render_template('dashboard.html',
                           account=account,
                           player=player,
                           all_players=all_players,
                           user_rank=user_rank,
                           account_db=account_db,
                           recent_trend=recent_trend)


@app.route('/session', methods=['GET', 'POST'])
def session_entry():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            player_usernames = [
                name.strip() for name in request.form['players'].split(',')
            ]
            buyins = [float(x) for x in request.form['buyins'].split(',')]
            cashouts = [float(x) for x in request.form['cashouts'].split(',')]
            blind_size = float(request.form['blind_size'])
            duration_hours = [
                float(x) for x in request.form['duration_hours'].split(',')
            ]

            # Convert usernames to user_ids
            player_ids = []
            for username in player_usernames:
                account = account_db.get_account_by_username(username.strip())
                if account:
                    player_ids.append(account.user_id)
                else:
                    flash(f'Player {username} not found!')
                    return render_template('session.html')

            if len(player_ids) != len(buyins) or len(player_ids) != len(
                    cashouts) or len(player_ids) != len(duration_hours):
                flash(
                    'Number of players, buy-ins, cash-outs, and durations must match!'
                )
                return render_template('session.html')

            poker_session = Session(player_ids, buyins, cashouts, blind_size,
                                    duration_hours)
            process_session(poker_session, player_db)

            flash('Session processed successfully!')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Error processing session: {str(e)}')

    return render_template('session.html')


@app.route('/rankings')
def rankings():
    all_players = list(player_db.players.values())
    all_players.sort(key=lambda p: p.rating, reverse=True)

    return render_template('rankings.html',
                           players=all_players,
                           account_db=account_db)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
