import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Database configuration - uses DATABASE_URL env var on Render, SQLite locally
database_url = os.environ.get('DATABASE_URL', 'sqlite:///polls.db')
# Render PostgreSQL URLs start with postgres://, SQLAlchemy needs postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy(app)

# --- Models ---

class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    options = db.relationship('Option', backref='poll', cascade='all, delete-orphan')

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    votes = db.Column(db.Integer, default=0)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)

# --- Routes ---

@app.route('/')
def index():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    return render_template('index.html', polls=polls)

@app.route('/create', methods=['GET', 'POST'])
def create_poll():
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        options = [o.strip() for o in request.form.getlist('options') if o.strip()]
        if question and len(options) >= 2:
            poll = Poll(question=question)
            db.session.add(poll)
            db.session.flush()
            for opt_text in options:
                option = Option(text=opt_text, poll_id=poll.id)
                db.session.add(option)
            db.session.commit()
            return redirect(url_for('view_poll', poll_id=poll.id))
    return render_template('create.html')

@app.route('/poll/<int:poll_id>')
def view_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    total_votes = sum(o.votes for o in poll.options)
    return render_template('poll.html', poll=poll, total_votes=total_votes)

@app.route('/vote/<int:poll_id>', methods=['POST'])
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    option_id = request.form.get('option_id', type=int)
    option = Option.query.filter_by(id=option_id, poll_id=poll_id).first()
    if option:
        option.votes += 1
        db.session.commit()
    return redirect(url_for('view_poll', poll_id=poll_id))

@app.route('/api/poll/<int:poll_id>/results')
def poll_results_api(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    total = sum(o.votes for o in poll.options)
    return jsonify({
        'question': poll.question,
        'total_votes': total,
        'options': [
            {
                'id': o.id,
                'text': o.text,
                'votes': o.votes,
                'percent': round((o.votes / total * 100) if total > 0 else 0, 1)
            } for o in poll.options
        ]
    })

@app.route('/delete/<int:poll_id>', methods=['POST'])
def delete_poll(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    db.session.delete(poll)
    db.session.commit()
    return redirect(url_for('index'))

# Create tables on startup
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)
