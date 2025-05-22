from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_apscheduler import APScheduler
import mysql.connector
from datetime import datetime, timedelta
import time
from plyer import notification
import threading
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from win10toast import ToastNotifier
import calendar

toaster = ToastNotifier()

app= Flask(__name__)
app.secret_key = 'project#123@456'

@app.route('/')
def home():
    return render_template('home.html')
'''
class Config:
    SCHEDULER_API_ENABLED = True
app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
'''
def get_db_connection():
    db=mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "Ayu274@shi#",
        database = "reminder_db"
    )
    return db

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, username, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user:
        return User(user['id'], user['username'], user['email'])
    cursor.close()
    db.close()
    return None



@app.route('/index')
@login_required
def index():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, title, description, category, DATE_FORMAT(date_time, '%Y-%m-%d %h:%i %p') AS formatted_time FROM reminders WHERE user_id = %s AND status = 'upcoming' ORDER BY date_time ASC", (current_user.id,))
    upcoming_reminders = cursor.fetchall()
    cursor.execute("SELECT id, title, DATE_FORMAT(date_time, '%Y-%m-%d %h:%i %p') AS formatted_time FROM reminders WHERE user_id = %s AND status = 'past' ORDER BY date_time DESC", (current_user.id,))
    past_reminders = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template("index.html", upcoming_reminders=upcoming_reminders, past_reminders=past_reminders)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)", (username, email, password))
            db.commit()
            flash('Account created, Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            flash('Username or email already exists!')
            return redirect(url_for('signup'))
        finally:
            cursor.close()
            db.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, password_hash FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['email'])
            login_user(user_obj)
            cursor.close()
            db.close()
            return redirect(url_for('index'))
        else:
            cursor.close()
            db.close()
            flash("Invalid username or password", "error")
            return "Invalid credentials.."
    return render_template('login.html')

@app.route('/logout')
@login_required 
def logout():
    logout_user()
    return redirect(url_for('login'))          






@app.route('/filter')
def filter_reminders():
    category = request.args.get('category')
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    if category:
        cursor.execute("SELECT * FROM reminders WHERE status = 'upcoming' AND category = %s AND user_id = %s", (category,current_user.id))
    else:
        cursor.execute("SELECT * FROM reminders WHERE status = 'upcoming' AND user_id = %s", (current_user.id,))
        
    reminders = cursor.fetchall()
    cursor.execute("SELECT * FROM reminders WHERE user_id = %s AND status = 'past' ORDER BY date_time DESC", (current_user.id,))
    past_reminders = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('index.html', upcoming_reminders=reminders, past_reminders=past_reminders)
    


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_reminder(id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        time = request.form['datetime']
        recurrence = request.form['recurrence']
        category = request.form['category']
        dt = datetime.strptime(time, '%Y-%m-%dT%H:%M')
        cursor.execute("""
            UPDATE reminders 
            SET title = %s, description = %s, date_time = %s, recurring = %s, category = %s
            WHERE id = %s
                       """, (title, description, dt, recurrence, category, id))
        db.commit()
        return redirect('/index')
    cursor.execute("SELECT * FROM reminders WHERE id = %s", (id,))
    reminder = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template('edit.html', reminder=reminder)
        

@app.route('/search')
def search():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    q = request.args.get('search')
    category = request.args.get('category')
    query = "SELECT * FROM reminders WHERE 1=1"
    values = []
    if q:
        query += " AND (title LIKE %s OR description LIKE %s)"
        values.extend([f"%{q}%", f"%{q}%"])
    if category:
        query += " AND category = %s"
        values.append(category)
            
    query += " AND status = 'upcoming' ORDER BY date_time"
    print("Search SQL:", q)
    print("With values:", values)
    cursor.execute(query, values)
    reminders = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template('search_result.html', reminders=reminders, q=q, category=category)



def show_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        timeout=5
    )
    time.sleep(1)

@app.route('/add', methods=['POST'])
def add_reminder():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    title = request.form['title']
    description = request.form['description']
    datetime_str = request.form['datetime']
    recurrence = request.form.get('recurrence', 'None')
    category = request.form.get('category')
    user_id = current_user.id
    dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
    cursor.execute("INSERT INTO reminders (title, description, date_time, recurring, category, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                   (title, description, dt, recurrence, category, user_id)
                   )
    db.commit()
    
    threading.Thread(target=show_notification, args=(f"Reminder Added: {title}", f"Due: {dt.strftime('%Y-%m-%d %H:%M')}")).start()
    cursor.close()
    db.close()
    return redirect('/index')

@app.route('/delete/<int:id>', methods=['POST'])
def delete_reminder(id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("DELETE FROM reminders WHERE id = %s AND user_id = %s", (id, current_user.id))
    db.commit()
    
    threading.Thread(target=show_notification, args=("Reminder deleted", f"ID: {id}")).start()
    cursor.close()
    db.close()
    return redirect('/index')

def check_due_reminders():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    now = datetime.now()
    future_time = now + timedelta(minutes=1)
    cursor.execute("SELECT * FROM reminders WHERE status = 'upcoming' AND date_time <= %s AND user_id = %s", (now, current_user.id))
    due_reminders = cursor.fetchall()
    for reminder in due_reminders:

        toaster.show_toast(
            "ReMinderly",
            f"{reminder['title']}- {reminder['description']} Due at: {reminder['date_time'].strftime('%Y-%m-%d %I:%M:%S %p')}",
            duration=5,
            threaded=True
        )
        if reminder['recurring'] == 'None':
            cursor.execute("UPDATE reminders SET status = 'past' WHERE id = %s", (reminder['id'],))
    db.commit()

    cursor.execute("SELECT * FROM reminders WHERE date_time < %s AND status = 'upcoming'", (now,))
    p_reminders = cursor.fetchall()
    for reminder in p_reminders:
        if reminder['recurring'] == 'None':
            cursor.execute("UPDATE reminders SET status = 'past' WHERE id = %s", (reminder['id'],))

    db.commit()
    cursor.close()
    db.close()

def check_recurring_reminders():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    now = datetime.now()

    cursor.execute("SELECT * FROM reminders WHERE status = 'upcoming'")
    reminders = cursor.fetchall()
    for reminder in reminders:
        id, title, description, date_time, recurring, category, user_id, status = reminder
        if recurring == 'Daily':
            new_time = date_time + timedelta(days=1)
        elif recurring == 'Weekly':
            new_time = date_time + timedelta(weeks=1)
        elif recurring == 'Monthly':
            new_time = date_time + timedelta(days=30)
        else:
            continue
        cursor.execute("UPDATE reminders SET date_time = %s WHERE id = %s", (new_time, id))
    db.commit()
    cursor.close()
    db.close()

@app.route('/past/<int:id>', methods=['POST'])
def delete_past_reminders(id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("DELETE FROM reminders WHERE id = %s AND user_id = %s", (id, current_user.id))
    db.commit()
    cursor.close()
    db.close()
    flash('Reminder deleted successfully.', 'success')

    return redirect('/index')

@app.route('/get_reminders')
def get_reminders():
    user_id = current_user.id
    

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, title, date_time, recurring 
        FROM reminders 
        WHERE user_id = %s AND status = 'upcoming'
    """, (user_id,))
    reminders = cursor.fetchall()
    cursor.close()
    db.close()

    events = []
    today = datetime.today().date()
    end_date = today + timedelta(days=60)  # Show occurrences for the next 60 days

    for reminder in reminders:
        base_date = reminder["date_time"].date()
        recurrence = reminder.get("recurring", "None")
        title = reminder["title"]
        reminder_id = reminder["id"]

        def add_event(date):
            events.append({
                "id": f"{reminder_id}-{date}",
                "title": title,
                "start": date.strftime('%Y-%m-%d')
            })

        if recurrence == "None":
            if base_date >= today and base_date <= end_date:
                add_event(base_date)

        elif recurrence == "Daily":
            current = max(base_date, today)
            while current <= end_date:
                add_event(current)
                current += timedelta(days=1)

        elif recurrence == "Weekly":
            current = max(base_date, today)
            # Align current to the next same weekday if today is after base_date weekday
            days_ahead = (base_date.weekday() - current.weekday()) % 7
            current += timedelta(days=days_ahead)
            while current <= end_date:
                add_event(current)
                current += timedelta(weeks=1)

        elif recurrence == "Monthly":
            current = base_date
            if current < today:
                # Skip to the next month after today
                while current < today:
                    month = current.month + 1 if current.month < 12 else 1
                    year = current.year if current.month < 12 else current.year + 1
                    day = min(base_date.day, calendar.monthrange(year, month)[1])
                    current = datetime(year, month, day).date()
            while current <= end_date:
                add_event(current)
                month = current.month + 1 if current.month < 12 else 1
                year = current.year if current.month < 12 else current.year + 1
                day = min(base_date.day, calendar.monthrange(year, month)[1])
                current = datetime(year, month, day).date()

    return jsonify(events)

@app.route('/get_todays_reminders')
def get_todays_reminders():
    today = datetime.today().date()
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, title, DATE_FORMAT(date_time, '%Y-%m-%d %h:%i %p') AS formatted_time FROM reminders WHERE DATE(date_time) = %s AND status = 'upcoming' AND user_id = %s", (today, current_user.id))
    reminders = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify({'reminders': reminders})

@app.route('/get_reminders_for_date')
def get_reminders_for_date():
    selected_date = request.args.get('date')  # Date in YYYY-MM-DD format
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, title, DATE_FORMAT(date_time, '%Y-%m-%d %h:%i %p') AS formatted_time FROM reminders WHERE DATE(date_time) = %s AND status = 'upcoming' AND user_id = %s", (selected_date, current_user.id))
    reminders = cursor.fetchall()
    cursor.close()
    db.close()

    return jsonify({'reminders': reminders})


scheduler = BackgroundScheduler()
scheduler.add_job(func=check_due_reminders, trigger="interval", seconds=60)
scheduler.add_job(func=check_recurring_reminders, trigger="interval", minutes=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

if __name__=='__main__':
    app.run(debug=True)