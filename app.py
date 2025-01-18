from flask import Flask, render_template, request, redirect, url_for, session,jsonify
import pymysql
import openai

from flask_mail import Mail, Message

# Flask-Mail configuration





app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'p7975263788@gmail.com'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'sbwk lbdy wsfm guxp'      # Replace with your password
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)

# MySQL Database Configuration
db = pymysql.connect(
    host="localhost",
    user="root",
    password="Prajwal@123",
    database="task_management"
)
cursor = db.cursor()

# Admin Routes (Already given)





@app.route('/update_progress/<int:task_id>', methods=['POST'])
def update_progress(task_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))  # Redirect to login if not logged in

    # Get the new progress value from the form
    new_progress = request.form.get('progress')

    if new_progress:
        # Update the task's progress in the database
        cursor.execute("UPDATE tasks SET progress = %s WHERE id = %s", (new_progress, task_id))
        db.commit()  # Commit changes to the database

    return redirect(url_for('user_dashboard'))  # Redirect to the user dashboard after the update




@app.route("/get_ai_suggestions", methods=["POST"])
def get_ai_suggestions():
    if 'user' in session:
        username = session['user']
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        if not user_data:
            return jsonify({"error": "User not found."}), 404

        user_id = user_data[0]
        cursor.execute("SELECT title FROM tasks WHERE user_id = %s", (user_id,))
        tasks = cursor.fetchall()

        task_list = [task[0] for task in tasks]
        task_prompt = (
            f"Here are the user's recent tasks: {', '.join(task_list)}. "
            f"Based on these, suggest new relevant tasks for the user."
        )

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a task management assistant."},
                    {"role": "user", "content": task_prompt}
                ]
            )
            task_suggestions = response.choices[0].message.content
            return jsonify({"suggestions": task_suggestions})
        except Exception as ai_error:
            return jsonify({"error": f"AI error: {str(ai_error)}"}), 500

    return jsonify({"error": "User not logged in."}), 401

@app.route('/')
def home():
    if 'admin' in session:
        return redirect(url_for('admin_dashboard'))
    elif 'user' in session:
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('user_login'))



 # You can create this as needed for user dashboard



# Admin Login
@app.route('/send_reminders')
def send_reminders():
    cursor.execute("""
        SELECT t.id, t.title, t.due_date, u.email
        FROM tasks t
        JOIN users u ON t.user_id = u.id
        WHERE t.due_date = CURDATE() + INTERVAL 1 DAY AND t.reminder_sent = FALSE
    """)
    tasks = cursor.fetchall()

    for task in tasks:
        task_id, task_title, due_date, user_email = task

        # Send email reminder
        msg = Message(
            subject="Task Due Date Reminder",
            sender="p7975263788@gmail.com",
            recipients=[user_email]
        )
        msg.body = f"Hello,\n\nThis is a reminder that your task '{task_title}' is due on {due_date}.\n\nPlease make sure to complete it on time!"
        mail.send(msg)

        # Mark reminder as sent
        cursor.execute("UPDATE tasks SET reminder_sent = TRUE WHERE id = %s", (task_id,))
        db.commit()

    return "Reminders sent successfully!"


from apscheduler.schedulers.background import BackgroundScheduler

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=send_reminders, trigger="interval", hours=24)
    scheduler.start()

# Start the scheduler when the app starts
start_scheduler()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password))
        admin = cursor.fetchone()
        if admin:
            session['admin'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            return "Invalid Credentials"
    return render_template('login.html')

# Route to display tasks with a priority filter for admin
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('login'))  # Redirect to admin login if not logged in

    # Default: Show all tasks
    query = "SELECT tasks.id, users.username, tasks.title, tasks.description, tasks.due_date, tasks.priority, tasks.status FROM tasks JOIN users ON tasks.user_id = users.id"
    params = []

    # Apply priority filter if selected and it's not "All"
    priority = request.args.get('priority')
    if priority and priority != "All":
        query += " WHERE tasks.priority = %s"
        params.append(priority)

    cursor.execute(query, params)
    tasks = cursor.fetchall()

    return render_template('admin_dashboard.html', tasks=tasks)


# Route to edit task status
@app.route('/edit_status/<int:task_id>', methods=['GET', 'POST'])
def edit_status(task_id):
    # Ensure user is logged in
    if 'user' not in session and 'admin' not in session:
        return redirect(url_for('login'))

    # Get the task details
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()

    if request.method == 'POST':
        # Get the new status from the form
        new_status = request.form['status']
        
        # Update the task status in the database
        cursor.execute("UPDATE tasks SET status = %s WHERE id = %s", (new_status, task_id))
        db.commit()

        # Redirect to the appropriate dashboard
        if 'user' in session:
            return redirect(url_for('user_dashboard'))
        else:
            return redirect(url_for('admin_dashboard'))

    return render_template('edit_status.html', task=task)

@app.route('/manage_tasks/<int:task_id>', methods=['GET', 'POST'])
def manage_tasks(task_id):
    if 'admin' not in session:
        return redirect(url_for('login'))  # Redirect to admin login if not logged in

    if request.method == 'POST':
        # Update the task
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        priority = request.form['priority']
        status = request.form['status']

        cursor.execute("""
            UPDATE tasks SET title = %s, description = %s, due_date = %s, priority = %s, status = %s
            WHERE id = %s
        """, (title, description, due_date, priority, status, task_id))
        db.commit()

        return redirect(url_for('admin_dashboard'))

    # Fetch task details for editing
    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()

    return render_template('manage_tasks.html', task=task)

# Route to display tasks with a priority filter
# Route to display tasks with a priority filter
# Route to display tasks with a priority filter
@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user' not in session:
        return redirect(url_for('user_login'))  # Redirect to login if not logged in

    username = session['user']
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    user_id = cursor.fetchone()[0]

    # Default: Show all tasks
    query = "SELECT * FROM tasks WHERE user_id = %s"
    params = [user_id]

    # Apply priority filter if selected and it's not "All"
    priority = request.args.get('priority')
    if priority and priority != "All":
        query += " AND priority = %s"
        params.append(priority)

    cursor.execute(query, params)
    tasks = cursor.fetchall()

    return render_template('user_dashboard.html', tasks=tasks)


# Admin route to delete a task
@app.route('/delete_task_admin/<int:task_id>')
def delete_task_admin(task_id):
    if 'admin' not in session:
        return redirect(url_for('login'))

    cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    db.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))
# User Login
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if user:
            session['user'] = username
            return redirect(url_for('user_dashboard'))
        else:
            return "Invalid Credentials"
    return render_template('user_login.html')

# User Registration (Optional)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form.get('email')
        confirm_password = request.form['confirm_password']
        
        # Ensure passwords match
        if password != confirm_password:
            return "Passwords do not match"

        # Check if username already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if user:
            return "Username already exists, please choose a different one."

        # Insert new user into the database
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
        db.commit()
        
        return redirect(url_for('user_login'))  # Redirect to login page after successful registration
    
    return render_template('register.html') 
     # Render registration page when GET request is made



# Route to create a new task
@app.route('/create_task', methods=['GET', 'POST'])
def create_task():
    if 'user' not in session:
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        priority = request.form['priority']
        username = session['user']

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO tasks (user_id, title, description, due_date, priority) 
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, title, description, due_date, priority))
        db.commit()

        return redirect(url_for('user_dashboard'))

    return render_template('create_task.html')

# Route to edit a task
@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        due_date = request.form['due_date']
        priority = request.form['priority']

        cursor.execute("""
            UPDATE tasks SET title = %s, description = %s, due_date = %s, priority = %s
            WHERE id = %s
        """, (title, description, due_date, priority, task_id))
        db.commit()

        return redirect(url_for('user_dashboard'))

    cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
    task = cursor.fetchone()
    return render_template('edit_task.html', task=task)

# Route to delete a task
@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user' not in session:
        return redirect(url_for('user_login'))

    cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    db.commit()
    return redirect(url_for('user_dashboard'))



if __name__ == '__main__':
    app.run(debug=True)
