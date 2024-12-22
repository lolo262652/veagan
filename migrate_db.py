from app import app, db

with app.app_context():
    # Add active column to client table if it doesn't exist
    with db.engine.connect() as conn:
        conn.execute(db.text("ALTER TABLE client ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.commit()
