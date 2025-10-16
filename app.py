from flask import Flask, render_template, request, redirect, url_for, flash, Response
import mysql.connector
import os
import csv
from io import TextIOWrapper, StringIO

app = Flask(__name__)
app.secret_key = 'secret_key_for_flash_messages'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Madhu@2622",
        database="event_db"
    )

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dashboard')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    title = request.args.get('title', '')
    date = request.args.get('date', '')

    query = """
        SELECT e.id, e.title, e.event_date, e.location, e.capacity,
               COUNT(t.id) AS tickets_sold
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id
    """
    filters, params = [], []
    if title:
        filters.append("e.title LIKE %s")
        params.append(f"%{title}%")
    if date:
        filters.append("e.event_date = %s")
        params.append(date)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " GROUP BY e.id, e.title, e.event_date, e.location, e.capacity ORDER BY e.event_date ASC"
    cursor.execute(query, params)
    events = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', events=events)

@app.route('/import_csv', methods=['GET', 'POST'])
def import_csv_page():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('No file selected!', 'error')
            return redirect(request.url)
        csv_file = TextIOWrapper(file, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        conn = get_db_connection()
        cursor = conn.cursor()
        for row in reader:
            cursor.execute("""
                INSERT INTO events (title, description, event_date, location, capacity)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                row.get('Event Title'),
                row.get('Description'),
                row.get('Date'),
                row.get('Location'),
                int(row.get('Capacity')) if row.get('Capacity') else 0
            ))
        conn.commit()
        cursor.close()
        conn.close()
        flash('CSV imported successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('import_csv.html')

@app.route('/add_event')
def add_event_page():
    return render_template('add_event.html')

@app.route('/add_event', methods=['POST'])
def add_event():
    title = request.form['title']
    description = request.form['description']
    event_date = request.form['event_date']
    location = request.form['location']
    capacity = int(request.form['capacity'])
    ticket_price = request.form['ticket_price']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO events (title, description, event_date, location, capacity, ticket_price) VALUES (%s, %s, %s, %s, %s, %s)",
        (title, description, event_date, location, capacity, ticket_price)
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash('✅ Event added successfully!')
    return redirect(url_for('index'))

@app.route('/register_attendee', methods=['GET', 'POST'])
def register_attendee():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title FROM events ORDER BY event_date ASC")
    events = cursor.fetchall()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        event_id = request.form['event_id']
        cursor.execute("INSERT INTO attendees (name, email, event_id) VALUES (%s, %s, %s)", (name, email, event_id))
        attendee_id = cursor.lastrowid
        cursor.execute("INSERT INTO tickets (event_id, attendee_id, purchase_date) VALUES (%s, %s, NOW())", (event_id, attendee_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"✅ {name} registered successfully!", "success")
        return redirect(url_for('attendees_page'))
    cursor.close()
    conn.close()
    return render_template('register_attendee.html', events=events)

@app.route('/attendees')
def attendees_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.id, a.name, a.email, a.event_id, e.title AS event_title
        FROM attendees a
        LEFT JOIN events e ON a.event_id = e.id
        ORDER BY e.event_date ASC, a.name ASC
    """)
    attendees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('attendees.html', attendees=attendees)

@app.route('/attendees/<int:event_id>')
def view_attendees(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.id, a.name, a.email
        FROM attendees a
        WHERE a.event_id = %s
        ORDER BY a.name ASC
    """, (event_id,))
    attendees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('attendees_for_event.html', attendees=attendees, event_id=event_id)

@app.route('/edit_attendee/<int:attendee_id>', methods=['GET', 'POST'])
def edit_attendee(attendee_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendees WHERE id = %s", (attendee_id,))
    attendee = cursor.fetchone()
    cursor.execute("SELECT * FROM events ORDER BY event_date ASC")
    events = cursor.fetchall()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        new_event_id = request.form['event_id']
        cursor.execute("UPDATE attendees SET name=%s, email=%s, event_id=%s WHERE id=%s", (name, email, new_event_id, attendee_id))
        cursor.execute("UPDATE tickets SET event_id=%s WHERE attendee_id=%s", (new_event_id, attendee_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"✅ Attendee {name} updated successfully!", "success")
        return redirect(url_for('attendees_page'))
    cursor.close()
    conn.close()
    return render_template('edit_attendee.html', attendee=attendee, events=events)

@app.route('/delete_attendee/<int:attendee_id>')
def delete_attendee(attendee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE attendee_id = %s", (attendee_id,))
    cursor.execute("DELETE FROM attendees WHERE id = %s", (attendee_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Attendee deleted successfully!", "success")
    return redirect(url_for('attendees_page'))

@app.route('/edit_event/<int:event_id>')
def edit_event_page(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_event.html', event=event)

@app.route('/edit_event/<int:event_id>', methods=['POST'])
def edit_event(event_id):
    title = request.form['title']
    description = request.form['description']
    event_date = request.form['event_date']
    location = request.form['location']
    capacity = int(request.form['capacity'])
    ticket_price = request.form['ticket_price']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE events
        SET title=%s, description=%s, event_date=%s, location=%s, capacity=%s, ticket_price=%s
        WHERE id=%s
    """, (title, description, event_date, location, capacity, ticket_price, event_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('✏️ Event updated successfully!')
    return redirect(url_for('index'))

@app.route('/delete_event/<int:event_id>')
def delete_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('🗑️ Event deleted successfully!')
    return redirect(url_for('index'))

@app.route('/tickets')
def tickets_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.id, e.title, e.event_date, e.location, e.capacity, e.ticket_price,
               COUNT(t.id) AS tickets_sold
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id
        GROUP BY e.id, e.title, e.event_date, e.location, e.capacity, e.ticket_price
        ORDER BY e.event_date ASC
    """)
    tickets_data = cursor.fetchall()
    for ticket in tickets_data:
        ticket['tickets_sold'] = int(ticket['tickets_sold'])
        ticket['tickets_available'] = ticket['capacity'] - ticket['tickets_sold']
    cursor.close()
    conn.close()
    return render_template('tickets.html', tickets=tickets_data)

@app.route('/buy_ticket/<int:event_id>', methods=['GET', 'POST'])
def buy_ticket(event_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM events WHERE id = %s", (event_id,))
    event = cursor.fetchone()
    if not event:
        cursor.close()
        conn.close()
        flash("Event not found!", "error")
        return redirect(url_for('tickets_page'))
    cursor.execute("SELECT COUNT(*) AS sold FROM tickets WHERE event_id = %s", (event_id,))
    sold = cursor.fetchone()['sold']
    if sold >= event['capacity']:
        cursor.close()
        conn.close()
        flash("Sorry! No tickets available for this event.", "error")
        return redirect(url_for('tickets_page'))
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        cursor.execute("INSERT INTO attendees (name, email, event_id) VALUES (%s, %s, %s)", (name, email, event_id))
        attendee_id = cursor.lastrowid
        cursor.execute("INSERT INTO tickets (event_id, attendee_id, purchase_date) VALUES (%s, %s, NOW())", (event_id, attendee_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f"✅ Ticket booked successfully for {name}!", "success")
        return redirect(url_for('tickets_page'))
    cursor.close()
    conn.close()
    return render_template('buy_ticket.html', event=event)

@app.route('/export_ticket_report')
def export_ticket_report():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.title, e.event_date, e.location, e.capacity, COUNT(t.id) AS tickets_sold,
               (e.capacity - COUNT(t.id)) AS tickets_available,
               COUNT(t.id) * e.ticket_price AS revenue
        FROM events e
        LEFT JOIN tickets t ON e.id = t.event_id
        GROUP BY e.id
        ORDER BY e.event_date ASC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Title','Date','Location','Capacity','Tickets Sold','Tickets Available','Revenue'])
    cw.writerows(rows)
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=ticket_report.csv"}
    )

if __name__ == "__main__":
    app.run(debug=True)
