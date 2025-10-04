db_config.js 
/**
 * PostgreSQL Configuration File for a Backend Service
 *
 * This file is for your backend development environment (e.g., Node.js, Python, Java)
 * to securely connect to the PostgreSQL database set up using the provided SQL script.
 * The client-side HTML/JS code CANNOT use this file directly.
 */

const dbConfig = {
    // --- Connection Credentials ---
    user: 'postgres', // E.g., 'postgres'
    host: 'localhost',          // E.g., 'localhost' or an IP address
    database: 'ExpenseFlow', // Use the name you prefer, e.g., 'expense_db'
    password: 'root',   // Your actual PostgreSQL password
    port: 5432,                       // Default PostgreSQL port
    
    // --- Production/Scaling Settings (optional) ---
    pool: {
        max: 20,
        min: 0,
        idleTimeoutMillis: 30000,
    },
};

// For Flask backend, these settings are configured in app.py
// This file serves as reference for database connection parameters