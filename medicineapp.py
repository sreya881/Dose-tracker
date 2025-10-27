from flask import Flask, request, jsonify,session,render_template
from flask_cors import CORS
from flask_mail import Mail, Message
import mysql.connector
import schedule
import time
import threading
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash  # for password hashing
from flask import  redirect, url_for,request
app = Flask(__name__)
app.secret_key='your_secret_key_here'
CORS(app)

# Database connection
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'medicine_reminder'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)
  
# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'dosetracker0@gmail.com'
app.config['MAIL_PASSWORD'] = 'dosetracker2025'
mail = Mail(app)

# ------------------- User Registration -------------------
@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    age=request.form.get('age')
    # username=request.form.get('username')
    password=request.form.get('password')
    if not all([name, email, password]):
        return jsonify({'message': 'Missing required registration fields'}), 400
    # Hash the password
    password_hash = generate_password_hash(password)
    try:
     db=get_db_connection()
     cursor = db.cursor()
     cursor.execute(
        'INSERT INTO users (name,age, email, password_hash) VALUES (%s,%s,%s,%s)',
        (name,age,email, password_hash)
    )
     db.commit()
     cursor.close()
     db.close()
     return  redirect(url_for('add_medicine'))
    except mysql.connector.Error as err:
     return jsonify({'message': f'Database Error: {err.msg}'}), 500
    except Exception as e:
     return jsonify({'message': f'an unexpected error occurred: {e}'}), 500

# ------------------- User Login -------------------
@app.route('/login', methods=['POST'])
def login():
    try:
     email = request.form.get('email')
     password = request.form.get('password')
     if  not all([email, password]):
        return jsonify({'message': 'Missing login credentials'}), 400
     user_id=1
     session[user_id]= user['user_id']
     db=get_db_connection()
     cursor = db.cursor(dictionary=True)
     cursor.execute('SELECT user_id,email,password_hash FROM users WHERE email=%s', (email,))
    
     user = cursor.fetchone()
     cursor.close()
     db.close()
     if user and check_password_hash(user['password_hash'], password):
        return redirect(url_for('add_medicine'))
     else:
        return jsonify({'message': 'Invalid email or password'}), 401
    except Exception as e:
     print(f"Error during login: {e}")
     return jsonify({'message': f'an unexpected error occurred: {e}'}), 500
     
# ------------------- new Medicine -------------------
@app.route('/add_medicine', methods=['POST'])
def add_medicine():
    try:
      user_id = session.get('user_id')
      medicine_name = request.form.get('medicine name')
      dosage = request.form.get('dose')
      food_time = request.form.get('food_time')
      morning=True if request.form.get('morning') else False
      night=True if request.form.get('night') else False
      noon=True if request.form.get('noon') else False
      start_date = request.form.get('start_date') or ''
      end_date = request.form.get('end_date') or ''
      if not all([user_id, medicine_name, dosage, start_date, end_date]):
        return jsonify({'message': 'Missing required medicine fields'}), 400
      times_per_day = int(morning) + int(noon) + int(night)
      if times_per_day == 0:
        return jsonify({'message': 'At least one time of day must be selected'}), 400
      db=get_db_connection()
      cursor = db.cursor()
      cursor.execute(
        'INSERT INTO medicines (user_id, medicine_name, dosage, start_date, end_date, times_per_day,schedule_morning,schedule_noon,schedule_night) VALUES (%s, %s, %s, %s, %s, %s,%s,%s,%s)',
        (user_id, medicine_name, dosage, start_date, end_date, times_per_day,morning,noon,night)
     )
      db.commit()
      cursor.close()
      return redirect('medicine.html')
    except mysql.connector.Error as err:
     return jsonify({'message': f'Database Error: {err.msg}'}), 500

# ------------------- Add Medicine via Form -------------------
@app.route('/my_medicines/<int:user_id>', methods=['GET'])
def add_medicine_form():
    try:
       user_id = request.form.get('user_id')
       db=get_db_connection()
       cursor = db.cursor(dictionary=True)
       cursor.execute("""
            SELECT medicine_id, medicine_name, dosage, food_time, 
                   schedule_morning, schedule_noon, schedule_night, start_date, end_date
            FROM medicines
            WHERE user_id = %s """, (user_id,))
       medicines = cursor.fetchall()
       cursor.close()
       db.close()
       return render_template('medicine.html', user_id=user_id,medicines=medicines) 
    except Exception as e:
        print(f"Database error: {e}")
        return jsonify({'message': f'An error occurred: {e}'}), 500

# ------------------- Get Reminders -------------------


# ------------------- Email Reminder -------------------
def send_email_reminder(to_email, subject, message):
    with app.app_context():
      msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[to_email])
    msg.body = message
    try:
      mail.send(msg)
      print(f"remainder sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
# ------------------- Check Reminders -------------------
def check_reminders():
    try:
       db=get_db_connection()
       cursor = db.cursor(dictionary=True)
       cursor.execute(
        "SELECT r.reminder_id, r.reminder_datetime, r.status, u.email, m.medicine_name, m.dosage "
        "FROM reminders r "
        "JOIN medicines m ON r.medicine_id=m.medicine_id "
        "JOIN users u ON m.user_id=u.user_id "
        "WHERE r.status='Pending'"
       )
       reminders = cursor.fetchall()
       now = datetime.now()
       for r in reminders:
        reminder_time = r['reminder_datetime']
        if now >= reminder_time and (now-reminder_time).total_seconds() < 120:
            subject = f"Time for your medicine: {r['medicine_name']}"
            message = f"Please take your medicine {r['medicine_name']} ({r['dosage']}) now."
            send_email_reminder(r['email'], subject, message)
            cursor.execute("UPDATE reminders SET status='Sent' ,sent_at=%s WHERE reminder_id=%s", (r['reminder_id'],))
            db.commit()
        cursor.close()
    except Exception as e:
        print(f"Error checking reminders: {e}")
    finally:
        if db and db.is_connected():
            db.close()

# ------------------- Scheduler Thread -------------------
def run_scheduler():
    schedule.every(1).minutes.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=run_scheduler, daemon=True).start()

# ------------------- Run App -------------------
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0')