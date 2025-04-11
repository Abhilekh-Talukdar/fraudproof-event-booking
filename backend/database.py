# event-booking-backend/database.py
import sqlite3
import os

DATABASE_NAME = 'events.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # ... (rest of the function preamble remains the same) ...
    if not os.path.exists(DATABASE_NAME):
         print(f"Database '{DATABASE_NAME}' not found. Initializing...")
    else:
         print(f"Database '{DATABASE_NAME}' found. Will ensure tables exist.")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Events Table (if not exists)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT,
            price REAL
        )
    ''')
    print("Ensured 'events' table exists.")

    # Create Bookings Table (if not exists)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            user_dob TEXT NOT NULL,
            booking_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    ''')
    print("Ensured 'bookings' table exists.")


    # --- Updated Seed Data for Events ---
    cursor.execute("SELECT COUNT(*) FROM events")
    count = cursor.fetchone()[0]
    if count == 0:
        print("Seeding initial event data...")
        # --- REPLACE THE OLD LIST WITH THIS NEW ONE ---
        seed_events = [
            ('Tech Innovators Conference', '2025-06-15', 'Bangalore, Karnataka', 'A gathering of tech leaders discussing the future of AI, blockchain, and software development.', 2999.0),
            ('NH7 Weekender Music Festival', '2025-07-20', 'Pune, Maharashtra', 'India’s happiest music festival featuring top indie and international artists.', 2500.0),
            ('Arijit Singh – India Tour 2025', '2025-09-10', 'Mumbai, Maharashtra', 'A soulful evening with Arijit Singh performing his greatest hits.', 3500.0),
            ('Comic Con India', '2025-08-05', 'Delhi', 'A massive pop culture convention featuring comics, movies, video games, and celebrity panels.', 1500.0),
            ('Sunburn Music Festival', '2025-10-12', 'Goa', 'Asia’s biggest electronic music festival with top DJs from around the world.', 4000.0),
            ('India Food & Beverage Festival', '2025-11-03', 'Jaipur, Rajasthan', 'A celebration of India\'s rich culinary heritage with global influences.', 1800.0), # Note escaped apostrophe in India's
            ('Shreya Ghoshal Live', '2025-08-25', 'Hyderabad, Telangana', 'A mesmerizing night with the queen of Indian playback singing.', 2800.0),
            ('Christmas Carnival', '2025-12-25', 'Kolkata, West Bengal', 'A festive celebration with music, food, and holiday cheer at Park Street.', 1000.0)
        ]
        # ---------------------------------------------

        # Ensure the INSERT statement matches the tuple order (name, date, location, description, price)
        cursor.executemany('''
            INSERT INTO events (name, date, location, description, price)
            VALUES (?, ?, ?, ?, ?)
        ''', seed_events)
        print(f"Inserted {len(seed_events)} new seed events.")
    else:
        print("Events table already contains data, skipping seeding.")
    # --- End Seed Data ---


    conn.commit()
    conn.close()
    print("Database initialization check complete.")

if __name__ == '__main__':
    print("Running database initialization directly...")
    init_db()