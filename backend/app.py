# event-booking-backend/app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from database import get_db_connection, init_db
import sys # For printing errors to stderr

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:4200"}})

# Initialize DB on startup
with app.app_context():
     init_db()

# --- Event Routes (keep as they were) ---
@app.route('/api/events', methods=['GET'])
def get_events():
    # ... (implementation from previous step) ...
    print("Backend: /api/events requested (from DB)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY date ASC")
    events_rows = cursor.fetchall()
    conn.close()
    events = [dict(row) for row in events_rows]
    return jsonify(events)


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
     # ... (implementation from previous step) ...
    print(f"Backend: /api/events/{event_id} requested (from DB)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event_row = cursor.fetchone()
    conn.close()
    if event_row:
        return jsonify(dict(event_row))
    else:
        return jsonify({"error": "Event not found"}), 404


# --- Updated Booking Route ---
@app.route('/api/bookings', methods=['POST'])
def create_booking():
    """Handles booking requests for multiple tickets."""
    data = request.json
    event_id = data.get('eventId')
    tickets = data.get('tickets') # Expecting an array of {name, dob}

    print(f"Backend: Received booking request for event ID: {event_id}")
    print(f"Backend: Ticket details received: {len(tickets) if tickets else 0} tickets")

    # --- Input Validation ---
    if not event_id or not isinstance(event_id, int):
        return jsonify({"success": False, "message": "Invalid or missing 'eventId'."}), 400
    if not tickets or not isinstance(tickets, list) or len(tickets) == 0:
        return jsonify({"success": False, "message": "Missing or empty 'tickets' array."}), 400
    if len(tickets) > 4: # Enforce max tickets rule on backend too
         return jsonify({"success": False, "message": "Maximum of 4 tickets allowed per booking."}), 400


    validated_tickets = []
    for i, ticket in enumerate(tickets):
        name = ticket.get('name')
        dob = ticket.get('dob')
        if not name or not isinstance(name, str) or len(name.strip()) == 0:
            return jsonify({"success": False, "message": f"Missing or invalid name for ticket {i+1}."}), 400
        if not dob or not isinstance(dob, str): # Basic check, could add date format validation
            return jsonify({"success": False, "message": f"Missing or invalid Date of Birth for ticket {i+1}."}), 400
        validated_tickets.append({'name': name.strip(), 'dob': dob})

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if event exists
        cursor.execute("SELECT name FROM events WHERE id = ?", (event_id,))
        event_row = cursor.fetchone()
        if not event_row:
            return jsonify({"success": False, "message": f"Event ID {event_id} not found."}), 404
        event_name = event_row['name']

        # --- Insert multiple bookings within a transaction ---
        generated_booking_ids = []
        for ticket in validated_tickets:
            cursor.execute('''
                INSERT INTO bookings (event_id, user_name, user_dob)
                VALUES (?, ?, ?)
            ''', (event_id, ticket['name'], ticket['dob']))
            generated_booking_ids.append(cursor.lastrowid) # Get ID of the inserted row

        conn.commit() # Commit transaction only if all inserts succeed

        print(f"Successfully inserted {len(generated_booking_ids)} bookings for event {event_id}.")
        return jsonify({
            "success": True,
            "message": f"Successfully booked {len(generated_booking_ids)} ticket(s) for '{event_name}'.",
            "bookingIds": generated_booking_ids # Return the list of generated IDs
        }), 201

    except sqlite3.Error as e:
        print(f"Database error during booking: {e}", file=sys.stderr)
        if conn:
            conn.rollback() # Rollback on any error during the transaction
        return jsonify({"success": False, "message": "Database error occurred during booking."}), 500
    except Exception as e:
         print(f"An unexpected error occurred: {e}", file=sys.stderr)
         if conn:
            conn.rollback()
         return jsonify({"success": False, "message": "An unexpected server error occurred."}), 500
    finally:
        if conn:
            conn.close()

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True, port=5001)